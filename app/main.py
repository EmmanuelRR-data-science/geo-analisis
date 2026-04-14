"""FastAPI application — Mapa de Viabilidad de Negocios."""

from __future__ import annotations
import logging
import os
import uuid
import base64
from pathlib import Path
from datetime import datetime, timezone

from fastapi import FastAPI, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app.models.schemas import AnalysisResult, APIError, MultiRadiusResult
from app.services.ageb_reader import AGEBReader
from app.services.data_service import DataService
from app.services.llm_service import LLMService
from app.services.zone_service import ZoneService
from app.services.export_service import ExportService
from app.services.analysis_engine import AnalysisEngine
from app.services.environment_calculator import EnvironmentCalculator
from app.services.target_market_service import TargetMarketService

logger = logging.getLogger(__name__)

# Singletons
zone_service = ZoneService()
ageb_reader = AGEBReader()
llm_service = LLMService()
data_service = DataService(zone_service=zone_service, ageb_reader=ageb_reader)
analysis_engine = AnalysisEngine()
analysis_store = {}

app = FastAPI(title="GeoAnalisis")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Static Files
_STATIC = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")


@app.get("/")
async def root():
    return FileResponse(str(_STATIC / "index.html"))


@app.get("/api/health")
async def health():
    try:
        from sqlalchemy import text
        from app.db import get_engine
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1")).fetchone()
        return {"status": "ok", "database": "connected"}
    except Exception:
        return {"status": "degraded", "database": "disconnected"}


@app.get("/api/zones/search")
async def zones_search(q: str = Query("", description="Texto de búsqueda")):
    zones = zone_service.search_zones(q)
    return {"zones": [{"name": z.name, "agebs": z.ageb_ids} for z in zones]}


@app.get("/api/scian/search")
async def scian_search(q: str = Query("", description="Texto SCIAN")):
    from app.services.scian_catalog import search_scian_catalog
    q = q.strip()
    if len(q) < 3:
        return {"results": []}
    results = search_scian_catalog(q)
    return {"results": [{"code": c, "description": d} for c, d in results[:10]]}


@app.post("/api/analyze")
async def analyze(request: Request):
    body = await request.json()
    biz_input = body.get("business_type", "")
    zone_name = body.get("zone", "")
    radius_km = float(body.get("radius_km", 5.0) or 5.0)
    radius_km = max(0.5, min(20.0, radius_km))
    radius_m = int(radius_km * 1000)

    # Custom coordinates (optional)
    custom_lat = body.get("custom_lat")
    custom_lng = body.get("custom_lng")

    # Google categories
    google_ally_categories = body.get("google_ally_categories", []) or []
    google_competitor_categories = body.get("google_competitor_categories", []) or []

    # Target market profile (optional)
    target_profile = body.get("target_profile", "").strip() or None

    # Semantic keywords (free text, comma-separated)
    keyword_ally = body.get("keyword_ally", "") or ""
    keyword_competitor = body.get("keyword_competitor", "") or ""
    keyword_ally_list = [w.strip().lower() for w in keyword_ally.split(",") if w.strip()]
    keyword_competitor_list = [w.strip().lower() for w in keyword_competitor.split(",") if w.strip()]

    ally_filters = body.get("ally_filters", []) or []
    competitor_filters = body.get("competitor_filters", []) or []
    user_filters = None
    if ally_filters or competitor_filters or google_ally_categories or google_competitor_categories or keyword_ally_list or keyword_competitor_list:
        user_filters = {
            "ally_filters": ally_filters,
            "competitor_filters": competitor_filters,
            "google_ally_categories": google_ally_categories,
            "google_competitor_categories": google_competitor_categories,
            "keyword_ally": keyword_ally_list,
            "keyword_competitor": keyword_competitor_list,
        }

    # Validate coordinates if provided
    clat: float | None = None
    clng: float | None = None
    if custom_lat is not None and custom_lat != "" and custom_lng is not None and custom_lng != "":
        try:
            clat = float(custom_lat)
            clng = float(custom_lng)
        except (ValueError, TypeError):
            return JSONResponse(
                status_code=400,
                content={"error": "Las coordenadas deben ser valores numéricos válidos"},
            )

    warnings: list[str] = []

    # Determine zone
    zone = None
    if zone_name:
        zone = zone_service.get_zone(zone_name)
        if not zone:
            return JSONResponse(status_code=404, content={"error": "Zona no encontrada"})

    if zone is None and clat is not None and clng is not None:
        # Create virtual zone from coordinates
        from app.models.schemas import BoundingBox, Zone as ZoneModel
        offset = radius_km * 0.009  # approx degrees per km
        zone = ZoneModel(
            name="Coordenadas personalizadas",
            ageb_ids=[],
            center_lat=clat,
            center_lng=clng,
            bbox=BoundingBox(
                min_lat=clat - offset, min_lng=clng - offset,
                max_lat=clat + offset, max_lng=clng + offset,
            ),
        )
    elif zone is None:
        # No zone and no coordinates
        return JSONResponse(
            status_code=400,
            content={"error": "Se requiere una zona o coordenadas para realizar el análisis"},
        )

    # Override zone center with custom coordinates if zone was selected AND coords provided
    if clat is not None and clng is not None and zone_name:
        from app.models.schemas import BoundingBox
        offset = radius_km * 0.009
        zone = zone.model_copy(update={
            "center_lat": clat,
            "center_lng": clng,
            "bbox": BoundingBox(
                min_lat=clat - offset, min_lng=clng - offset,
                max_lat=clat + offset, max_lng=clng + offset,
            ),
        })

    # CDMX bounds warning
    if clat is not None and clng is not None:
        if not (19.05 <= clat <= 19.60 and -99.40 <= clng <= -98.90):
            warnings.append(
                f"Las coordenadas ({clat}, {clng}) parecen estar fuera de la Ciudad de México. "
                "Los resultados pueden no ser precisos."
            )

    import asyncio

    # Step 1: Run interpretation AND business search in PARALLEL
    interpret_task = asyncio.create_task(llm_service.interpret_business_type(biz_input))
    # For Google search we need a keyword — use the raw input while LLM interprets
    from app.models.schemas import BusinessInterpretation, SCIANCategory
    temp_interp = BusinessInterpretation(
        original_input=biz_input, scian_code="", scian_description=biz_input,
        complementary_categories=[], competitor_categories=[], used_fallback=True
    )
    search_task = asyncio.create_task(data_service.get_businesses_in_zone(zone, temp_interp, radius_m=radius_m))

    # Parse target profile in parallel (if provided)
    profile_task = asyncio.create_task(llm_service.parse_target_profile(target_profile)) if target_profile else None

    # Run Google category searches in parallel with main search
    all_google_categories = list(set(google_ally_categories + google_competitor_categories))
    category_task = asyncio.create_task(
        data_service.search_by_google_categories(zone, all_google_categories, radius_m=radius_m)
    ) if all_google_categories else None

    interpretation, (businesses, biz_warnings) = await asyncio.gather(interpret_task, search_task)
    warnings.extend(biz_warnings)

    # Await target profile parsing result
    target_criteria = None
    if profile_task:
        try:
            target_criteria = await profile_task
        except Exception as e:
            warnings.append(f"Error interpretando perfil objetivo: {e}")
            target_criteria = None

    # Consolidate category search results with main results
    if category_task:
        category_businesses = await category_task
        # Deduplicate by id
        existing_ids = {b.id for b in businesses}
        for cb in category_businesses:
            if cb.id not in existing_ids:
                businesses.append(cb)
                existing_ids.add(cb.id)

    # Step 2: Get AGEB data
    if zone.ageb_ids:
        ageb_data = ageb_reader.get_zone_data(zone.ageb_ids)
    else:
        # Virtual zone — empty AGEB data
        from app.models.schemas import AGEBData
        ageb_data = AGEBData(
            total_population=0,
            population_density=0.0,
            economically_active_population=0,
            socioeconomic_level="Desconocido",
            ageb_count=0,
            raw_indicators={},
        )

    # Step 3: Classify businesses (uses fast model)
    classified = await llm_service.classify_businesses(interpretation, businesses, user_filters=user_filters)
    viability = analysis_engine.calculate_viability(classified, ageb_data)

    # Calculate target market match percentage
    target_match = None
    if target_criteria:
        try:
            target_match = TargetMarketService.calculate_match_percentage(target_criteria, ageb_data)
        except Exception as e:
            warnings.append(f"Error calculando coincidencia de perfil: {e}")

    # Analyze competitor reviews
    review_analysis = None
    competitors_list = [b for b in classified if b.classification == "competitor"]
    if competitors_list:
        try:
            review_analysis = await llm_service.analyze_competitor_reviews(
                competitors_list, target_profile, target_criteria
            )
        except Exception as e:
            warnings.append(f"Error en análisis de reseñas: {e}")

    # Multi-radius analysis (1km, 3km, 5km)
    multi_radii_km = [1, 3, 5]
    multi_radii_m = [1000, 3000, 5000]

    multi_search_tasks = [
        data_service.get_businesses_in_zone(zone, temp_interp, radius_m=r)
        for r in multi_radii_m
    ]
    multi_search_results = await asyncio.gather(*multi_search_tasks, return_exceptions=True)

    multi_radius_results = []
    for r_km, r_result in zip(multi_radii_km, multi_search_results):
        if isinstance(r_result, Exception):
            warnings.append(f"No se pudo completar el análisis a {r_km} km: {r_result}")
            continue
        try:
            mr_businesses, mr_warnings = r_result
            # Classify using fallback only (avoid extra LLM calls for rate limit)
            mr_classified = llm_service._fallback_classify_businesses(interpretation, mr_businesses, user_filters)
            mr_competitors = sum(1 for b in mr_classified if b.classification == "competitor")
            mr_complementary = sum(1 for b in mr_classified if b.classification == "complementary")
            mr_env_vars = EnvironmentCalculator.calculate_all(mr_classified, r_km)
            multi_radius_results.append(MultiRadiusResult(
                radius_km=r_km,
                competitors=mr_competitors,
                complementary=mr_complementary,
                total_population=ageb_data.total_population,
                environment_variables=mr_env_vars,
            ))
        except Exception as e:
            warnings.append(f"Error procesando radio {r_km} km: {e}")

    result = AnalysisResult(
        analysis_id=str(uuid.uuid4()),
        business_type=interpretation,
        zone=zone,
        businesses=classified,
        ageb_data=ageb_data,
        viability=viability,
        recommendation_text="",
        warnings=warnings,
        timestamp=datetime.now(timezone.utc).isoformat(),
        multi_radius_results=multi_radius_results,
        target_profile=target_profile,
        target_criteria=target_criteria.model_dump() if target_criteria else None,
        target_match_percentage=target_match.percentage if target_match else None,
        target_match_population=target_match.estimated_population if target_match else None,
        target_match_breakdown=target_match.breakdown if target_match else None,
        competitor_value_points=[vp.model_dump() for vp in review_analysis.value_points] if review_analysis and not review_analysis.insufficient_data else None,
        competitor_improvement_opportunities=[io.model_dump() for io in review_analysis.improvement_opportunities] if review_analysis and not review_analysis.insufficient_data else None,
        target_customer_insights=[tci.model_dump() for tci in review_analysis.target_customer_insights] if review_analysis and review_analysis.target_customer_insights else None,
    )

    # Step 4: Generate recommendation (uses big model)
    result.recommendation_text = await llm_service.generate_recommendation(result, user_filters=user_filters)

    # Step 5: Generate strategic recommendations
    result.strategic_recommendations = await llm_service.generate_strategic_recommendations(result, user_filters=user_filters)

    analysis_store[result.analysis_id] = result
    return result.model_dump()


@app.post("/api/export/pdf")
async def export_pdf(request: Request):
    body = await request.json()
    aid = body.get("analysis_id")
    img = body.get("map_image_base64", "")

    res = analysis_store.get(aid)
    if not res:
        return JSONResponse(status_code=404, content={"error": "Análisis no encontrado"})

    try:
        if "," in img:
            img = img.split(",")[1]
        img_bytes = base64.b64decode(img)
        pdf_bytes = ExportService.generate_pdf(res, img_bytes)
        return Response(
            content=bytes(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="informe-viabilidad.pdf"'},
        )
    except Exception as e:
        logger.exception("PDF generation error")
        return JSONResponse(status_code=500, content={"error": f"Error generando PDF: {e}"})


@app.post("/api/export/html")
async def export_html(request: Request):
    body = await request.json()
    aid = body.get("analysis_id")
    radius_km = float(body.get("radius_km", 5.0) or 5.0)

    res = analysis_store.get(aid)
    if not res:
        return JSONResponse(status_code=404, content={"error": "Análisis no encontrado"})

    try:
        html = ExportService.generate_standalone_html(res, radius_km=radius_km)
        import unicodedata, re
        nfkd = unicodedata.normalize("NFKD", res.zone.name)
        slug = "".join(c for c in nfkd if not unicodedata.combining(c)).lower()
        slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
        return Response(
            content=html,
            media_type="text/html",
            headers={"Content-Disposition": f'attachment; filename="mapa-viabilidad-{slug}.html"'},
        )
    except Exception as e:
        logger.exception("HTML export error")
        return JSONResponse(status_code=500, content={"error": str(e)})
