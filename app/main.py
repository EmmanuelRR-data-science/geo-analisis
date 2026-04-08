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

from app.models.schemas import AnalysisResult, APIError
from app.services.ageb_reader import AGEBReader
from app.services.data_service import DataService
from app.services.llm_service import LLMService
from app.services.zone_service import ZoneService
from app.services.export_service import ExportService
from app.services.analysis_engine import AnalysisEngine

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

    ally_filters = body.get("ally_filters", []) or []
    competitor_filters = body.get("competitor_filters", []) or []
    user_filters = None
    if ally_filters or competitor_filters:
        user_filters = {"ally_filters": ally_filters, "competitor_filters": competitor_filters}

    zone = zone_service.get_zone(zone_name)
    if not zone:
        return JSONResponse(status_code=404, content={"error": "Zona no encontrada"})

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

    interpretation, (businesses, warnings) = await asyncio.gather(interpret_task, search_task)

    # Step 2: Get AGEB data (fast, from DB)
    ageb_data = ageb_reader.get_zone_data(zone.ageb_ids)

    # Step 3: Classify businesses (uses fast model)
    classified = await llm_service.classify_businesses(interpretation, businesses, user_filters=user_filters)
    viability = analysis_engine.calculate_viability(classified, ageb_data)

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
    )

    # Step 4: Generate recommendation (uses big model)
    result.recommendation_text = await llm_service.generate_recommendation(result, user_filters=user_filters)
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
