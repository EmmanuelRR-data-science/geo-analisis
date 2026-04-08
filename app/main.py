"""FastAPI application — Mapa de Viabilidad de Negocios."""

from __future__ import annotations

import logging
import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import base64
import threading
import unicodedata
import re

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app.models.schemas import AnalysisResult, APIError
from app.services.ageb_reader import AGEBReader
from app.services.analysis_engine import AnalysisEngine
from app.services.data_service import DataService
from app.services.llm_service import LLMService
from app.services.zone_service import ZoneService
from app.services.export_service import ExportService
from app.services.scian_catalog import search_scian_catalog
from app.services.ageb_reader import _classify_socioeconomic, _DEFAULT_AGEB_AREA_KM2

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Service singletons (initialised on startup)
# ---------------------------------------------------------------------------

zone_service: ZoneService | None = None
ageb_reader: AGEBReader | None = None
llm_service: LLMService | None = None
data_service: DataService | None = None
analysis_engine: AnalysisEngine | None = None

# In-memory store for analysis results (used later by PDF export)
analysis_store: dict[str, AnalysisResult] = {}

AGEB_FILE_PATH = os.getenv("AGEB_FILE_PATH", "RESAGEBURB_09XLSX20.xlsx")


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global zone_service, ageb_reader, llm_service, data_service, analysis_engine

    zone_service = ZoneService()
    ageb_reader = AGEBReader()

    # Load AGEB data in a background thread so the server starts immediately
    def _load_ageb():
        try:
            ageb_reader.load(AGEB_FILE_PATH)
            logger.info("AGEB data loaded from %s", AGEB_FILE_PATH)
        except (FileNotFoundError, ValueError) as exc:
            logger.warning("Could not load AGEB file: %s", exc)

    ageb_thread = threading.Thread(target=_load_ageb, daemon=True)
    ageb_thread.start()

    llm_service = LLMService()
    data_service = DataService(
        zone_service=zone_service,
        ageb_reader=ageb_reader,
    )
    analysis_engine = AnalysisEngine()

    yield  # app runs here

    # Cleanup (nothing to do for now)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Mapa de Viabilidad de Negocios", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Static files & root
# ---------------------------------------------------------------------------

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if _STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

_INDEX_HTML = Path(__file__).resolve().parent.parent / "templates" / "index.html"


@app.get("/")
async def root():
    """Serve the SPA entry point."""
    if _INDEX_HTML.exists():
        return FileResponse(str(_INDEX_HTML))
    alt = _STATIC_DIR / "index.html"
    if alt.exists():
        return FileResponse(str(alt))
    return JSONResponse({"message": "Frontend not built yet"}, status_code=200)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Zone search
# ---------------------------------------------------------------------------

@app.get("/api/zones/search")
async def zones_search(q: str = Query("", description="Texto de búsqueda de zona")):
    if not zone_service:
        return JSONResponse(
            status_code=503,
            content=APIError(
                error="service_unavailable",
                message="El servicio de zonas no está disponible",
            ).model_dump(),
        )

    zones = zone_service.search_zones(q)
    return {
        "zones": [
            {"name": z.name, "agebs": z.ageb_ids} for z in zones
        ]
    }


# ---------------------------------------------------------------------------
# GET /api/scian/search — SCIAN catalog search for autocomplete
# ---------------------------------------------------------------------------

@app.get("/api/scian/search")
async def scian_search(q: str = Query("", description="Texto de búsqueda SCIAN")):
    """Search the SCIAN catalog for autocomplete suggestions."""
    q = q.strip()
    if len(q) < 3:
        return {"results": []}
    results = search_scian_catalog(q)
    return {"results": [{"code": code, "description": desc} for code, desc in results[:10]]}


# ---------------------------------------------------------------------------
# GET /api/ageb-layers — AGEB indicator layers for choropleth maps
# ---------------------------------------------------------------------------

# NSE label → numeric mapping
_NSE_NUMERIC: dict[str, int] = {
    "Alto": 5,
    "Medio-Alto": 4,
    "Medio": 3,
    "Medio-Bajo": 2,
    "Bajo": 1,
}

# Indicator metadata
_INDICATOR_META: dict[str, dict[str, str]] = {
    "densidad_poblacion": {"label": "Densidad de Población", "unit": "hab/km²"},
    "pea": {"label": "Población Económicamente Activa", "unit": "personas"},
    "escolaridad": {"label": "Escolaridad Promedio", "unit": "años"},
    "nse": {"label": "Nivel Socioeconómico", "unit": "nivel (1-5)"},
    "pct_internet": {"label": "Viviendas con Internet", "unit": "%"},
    "pct_automovil": {"label": "Viviendas con Automóvil", "unit": "%"},
}


def _extract_indicator(indicator_key: str, raw: dict) -> float | None:
    """Extract a single indicator value from an AGEB's raw_indicators dict."""
    if indicator_key == "densidad_poblacion":
        pobtot = raw.get("pobtot")
        if pobtot is not None and pobtot != 0:
            return round(pobtot / _DEFAULT_AGEB_AREA_KM2, 2)
        return None

    if indicator_key == "pea":
        pea = raw.get("pea")
        if pea is not None and pea != 0:
            return float(pea)
        return None

    if indicator_key == "escolaridad":
        graproes = raw.get("graproes")
        if graproes is not None and graproes != 0:
            return float(graproes)
        return None

    if indicator_key == "nse":
        graproes = raw.get("graproes")
        if graproes is not None and graproes != 0:
            nse_label = _classify_socioeconomic(float(graproes))
            return float(_NSE_NUMERIC.get(nse_label, 0))
        return None

    if indicator_key == "pct_internet":
        vph_inter = raw.get("vph_inter")
        vivpar_hab = raw.get("vivpar_hab")
        if vph_inter is not None and vivpar_hab is not None and vivpar_hab != 0:
            return round(vph_inter / vivpar_hab * 100, 1)
        return None

    if indicator_key == "pct_automovil":
        vph_autom = raw.get("vph_autom")
        vivpar_hab = raw.get("vivpar_hab")
        if vph_autom is not None and vivpar_hab is not None and vivpar_hab != 0:
            return round(vph_autom / vivpar_hab * 100, 1)
        return None

    return None


def _estimate_ageb_coordinates(
    ageb_ids: list[str],
    min_lat: float, min_lng: float,
    max_lat: float, max_lng: float,
) -> dict[str, tuple[float, float]]:
    """Distribute AGEBs in a grid within the zone's bounding box.

    Returns a dict mapping ageb_id → (center_lat, center_lng).
    """
    n = len(ageb_ids)
    if n == 0:
        return {}

    import math
    cols = max(1, math.ceil(math.sqrt(n)))
    rows = max(1, math.ceil(n / cols))

    lat_step = (max_lat - min_lat) / rows if rows > 0 else 0
    lng_step = (max_lng - min_lng) / cols if cols > 0 else 0

    coords: dict[str, tuple[float, float]] = {}
    for idx, ageb_id in enumerate(ageb_ids):
        row = idx // cols
        col = idx % cols
        center_lat = round(min_lat + (row + 0.5) * lat_step, 6)
        center_lng = round(min_lng + (col + 0.5) * lng_step, 6)
        coords[ageb_id] = (center_lat, center_lng)

    return coords


@app.get("/api/ageb-layers")
async def ageb_layers(zone: str = Query(..., description="Nombre de la zona")):
    """Return AGEB indicator data for choropleth layers."""
    if not zone_service:
        return JSONResponse(
            status_code=503,
            content=APIError(
                error="service_unavailable",
                message="El servicio de zonas no está disponible",
            ).model_dump(),
        )

    zone_obj = zone_service.get_zone(zone)
    if zone_obj is None:
        suggestions = zone_service.suggest_similar_zones(zone)
        msg = f"La zona '{zone}' no fue encontrada"
        if suggestions:
            msg += f". ¿Quisiste decir: {', '.join(suggestions)}?"
        return JSONResponse(
            status_code=422,
            content=APIError(
                error="zone_not_found",
                message=msg,
            ).model_dump(),
        )

    if not ageb_reader or ageb_reader._df is None:
        return JSONResponse(
            status_code=503,
            content=APIError(
                error="data_not_loaded",
                message="Los datos AGEB aún se están cargando. Intente de nuevo en unos segundos.",
            ).model_dump(),
        )

    # Get AGEB data with raw_indicators
    ageb_data = ageb_reader.get_zone_data(zone_obj.ageb_ids)
    raw_indicators = ageb_data.raw_indicators  # {ageb_id: {field: value, ...}}

    # Estimate coordinates for each AGEB within the zone bbox
    coords = _estimate_ageb_coordinates(
        zone_obj.ageb_ids,
        zone_obj.bbox.min_lat, zone_obj.bbox.min_lng,
        zone_obj.bbox.max_lat, zone_obj.bbox.max_lng,
    )

    # Build layers response
    layers: dict = {}
    for indicator_key, meta in _INDICATOR_META.items():
        agebs_list = []
        for ageb_id in zone_obj.ageb_ids:
            raw = raw_indicators.get(ageb_id, {})
            value = _extract_indicator(indicator_key, raw)
            lat, lng = coords.get(ageb_id, (zone_obj.center_lat, zone_obj.center_lng))
            agebs_list.append({
                "ageb_id": ageb_id,
                "value": value,
                "center_lat": lat,
                "center_lng": lng,
            })
        layers[indicator_key] = {
            "label": meta["label"],
            "unit": meta["unit"],
            "agebs": agebs_list,
        }

    return {"layers": layers}


# ---------------------------------------------------------------------------
# POST /api/analyze — main analysis endpoint
# ---------------------------------------------------------------------------

def _clamp_radius_km(value: float) -> tuple[float, bool]:
    """Clamp radius_km to [0.5, 20.0]. Returns (clamped_value, was_adjusted)."""
    clamped = max(0.5, min(20.0, value))
    return clamped, clamped != value


def _validate_filters(
    ally_filters: list[str], competitor_filters: list[str]
) -> tuple[bool, str]:
    """Validate that no categories are duplicated between allies and competitors.

    Returns:
        (is_valid, error_message). error_message is empty when valid.
    """
    ally_set = set(ally_filters)
    competitor_set = set(competitor_filters)
    overlap = ally_set & competitor_set
    if overlap:
        duplicates = ", ".join(sorted(overlap))
        return False, f"Las siguientes categorías están duplicadas entre aliados y competidores: {duplicates}"
    return True, ""


@app.post("/api/analyze")
async def analyze(request: Request):
    """Orchestrate the full viability analysis flow."""
    warnings: list[str] = []

    # --- Parse body ---
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content=APIError(
                error="invalid_json",
                message="El cuerpo de la solicitud no es JSON válido",
            ).model_dump(),
        )

    business_type_input: str = body.get("business_type", "")
    zone_input: str = body.get("zone", "")

    # --- Parse new optional fields ---
    raw_radius_km = body.get("radius_km", 5.0)
    try:
        radius_km_float = float(raw_radius_km)
    except (TypeError, ValueError):
        radius_km_float = 5.0

    radius_km, was_adjusted = _clamp_radius_km(radius_km_float)
    if was_adjusted:
        warnings.append(
            f"El radio de búsqueda fue ajustado a {radius_km} km (rango permitido: 0.5-20 km)"
        )
    radius_m = int(radius_km * 1000)

    ally_filters: list[str] = body.get("ally_filters", []) or []
    competitor_filters: list[str] = body.get("competitor_filters", []) or []

    # Ensure they are lists of strings
    if not isinstance(ally_filters, list):
        ally_filters = []
    if not isinstance(competitor_filters, list):
        competitor_filters = []
    ally_filters = [str(f) for f in ally_filters if f]
    competitor_filters = [str(f) for f in competitor_filters if f]

    # Validate no duplicates between allies and competitors
    filters_valid, filters_error = _validate_filters(ally_filters, competitor_filters)
    if not filters_valid:
        return JSONResponse(
            status_code=422,
            content=APIError(
                error="duplicate_filter",
                message=filters_error,
            ).model_dump(),
        )

    # --- Validate input ---
    if not zone_service:
        return JSONResponse(
            status_code=503,
            content=APIError(
                error="service_unavailable",
                message="Los servicios no están disponibles",
            ).model_dump(),
        )

    is_valid, errors = zone_service.validate_input(business_type_input, zone_input)
    if not is_valid:
        return JSONResponse(
            status_code=422,
            content=APIError(
                error="validation_error",
                message="Error de validación",
                details="; ".join(errors),
            ).model_dump(),
        )

    # --- Get zone ---
    zone = zone_service.get_zone(zone_input)
    if zone is None:
        suggestions = zone_service.suggest_similar_zones(zone_input)
        msg = f"La zona '{zone_input}' no fue encontrada"
        if suggestions:
            msg += f". ¿Quisiste decir: {', '.join(suggestions)}?"
        return JSONResponse(
            status_code=422,
            content=APIError(
                error="zone_not_found",
                message=msg,
            ).model_dump(),
        )

    if not llm_service or not data_service or not analysis_engine:
        return JSONResponse(
            status_code=503,
            content=APIError(
                error="service_unavailable",
                message="Los servicios de análisis no están disponibles",
            ).model_dump(),
        )

    try:
        # --- Step 1: Interpret business type via LLM ---
        logger.info("Step 1: Interpreting business type: %s", business_type_input)
        business_interpretation = await llm_service.interpret_business_type(
            business_type_input
        )
        logger.info("  → SCIAN: %s (%s), fallback=%s", business_interpretation.scian_code, business_interpretation.scian_description, business_interpretation.used_fallback)
        if business_interpretation.used_fallback:
            warnings.append(
                "La interpretación inteligente no está disponible temporalmente; "
                "se usó búsqueda textual contra catálogo SCIAN"
            )

        # --- Step 2: Get businesses in zone ---
        logger.info("Step 2: Getting businesses in zone %s (center: %s, %s, radius_m=%d)", zone.name, zone.center_lat, zone.center_lng, radius_m)
        businesses, biz_warnings = await data_service.get_businesses_in_zone(
            zone, business_interpretation, radius_m=radius_m
        )
        logger.info("  → Found %d businesses, %d warnings", len(businesses), len(biz_warnings))
        warnings.extend(biz_warnings)

        # --- Step 3: Classify businesses ---
        logger.info("Step 3: Classifying %d businesses", len(businesses))
        # Prepare user_filters for LLM (LLMService will accept these in Task 2)
        user_filters: dict | None = None
        if ally_filters or competitor_filters:
            user_filters = {
                "ally_filters": ally_filters,
                "competitor_filters": competitor_filters,
            }
        classified = await llm_service.classify_businesses(
            business_interpretation, businesses, user_filters=user_filters
        )
        n_comp = sum(1 for b in classified if b.classification == "competitor")
        n_compl = sum(1 for b in classified if b.classification == "complementary")
        logger.info("  → %d competitors, %d complementary", n_comp, n_compl)

        # --- Step 4: Get AGEB data ---
        logger.info("Step 4: Getting AGEB data for %d AGEBs: %s", len(zone.ageb_ids), zone.ageb_ids[:3])
        ageb_data = await data_service.get_ageb_data(zone.ageb_ids)
        logger.info("  → Population: %d, PEA: %d, NSE: %s", ageb_data.total_population, ageb_data.economically_active_population, ageb_data.socioeconomic_level)

        # --- Step 5: Calculate viability ---
        viability = analysis_engine.calculate_viability(classified, ageb_data)

        if viability.data_completeness < 0.5:
            warnings.append(
                "Análisis parcial: los datos disponibles son insuficientes "
                "para un cálculo completamente confiable"
            )

        # --- Step 6: Build preliminary result for recommendation ---
        analysis_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        preliminary_result = AnalysisResult(
            analysis_id=analysis_id,
            business_type=business_interpretation,
            zone=zone,
            businesses=classified,
            ageb_data=ageb_data,
            viability=viability,
            recommendation_text="",
            warnings=warnings,
            timestamp=timestamp,
        )

        # --- Step 7: Generate recommendation ---
        recommendation = await llm_service.generate_recommendation(
            preliminary_result, user_filters=user_filters
        )

        # --- Build final result ---
        result = preliminary_result.model_copy(
            update={"recommendation_text": recommendation}
        )

        # Store for later PDF export
        analysis_store[analysis_id] = result

        return result.model_dump()

    except Exception as exc:
        logger.exception("Error during analysis")
        return JSONResponse(
            status_code=500,
            content=APIError(
                error="analysis_error",
                message="Ocurrió un error durante el análisis",
                details=str(exc),
                warnings=warnings,
            ).model_dump(),
        )


# ---------------------------------------------------------------------------
# POST /api/export/pdf — PDF report generation
# ---------------------------------------------------------------------------

@app.post("/api/export/pdf")
async def export_pdf(request: Request):
    """Generate a PDF report for a completed analysis."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content=APIError(
                error="invalid_json",
                message="El cuerpo de la solicitud no es JSON válido",
            ).model_dump(),
        )

    analysis_id: str = body.get("analysis_id", "")
    map_image_base64: str = body.get("map_image_base64", "")

    if not analysis_id:
        return JSONResponse(
            status_code=400,
            content=APIError(
                error="missing_field",
                message="El campo 'analysis_id' es requerido",
            ).model_dump(),
        )

    # Look up stored analysis result
    analysis_result = analysis_store.get(analysis_id)
    if analysis_result is None:
        return JSONResponse(
            status_code=404,
            content=APIError(
                error="not_found",
                message="No se encontró el análisis solicitado. Realiza un nuevo análisis.",
            ).model_dump(),
        )

    # Decode map image from base64
    try:
        # Strip data-URL prefix if present (e.g. "data:image/png;base64,...")
        if "," in map_image_base64:
            map_image_base64 = map_image_base64.split(",", 1)[1]
        map_image_bytes = base64.b64decode(map_image_base64)
    except Exception:
        return JSONResponse(
            status_code=400,
            content=APIError(
                error="invalid_image",
                message="La imagen del mapa no es válida",
            ).model_dump(),
        )

    # Generate PDF
    try:
        pdf_bytes = ExportService.generate_pdf(analysis_result, map_image_bytes)
    except Exception as exc:
        logger.exception("PDF generation failed")
        return JSONResponse(
            status_code=500,
            content=APIError(
                error="pdf_generation_error",
                message=f"Error generando PDF: {exc}",
            ).model_dump(),
        )

    return Response(
        content=bytes(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="informe-viabilidad.pdf"',
        },
    )


# ---------------------------------------------------------------------------
# POST /api/export/html — Standalone HTML map export
# ---------------------------------------------------------------------------

def _make_zone_slug(zone_name: str) -> str:
    """Convert a zone name to a URL-safe slug (lowercase, no accents, hyphens)."""
    # Normalize unicode to decomposed form, strip combining marks (accents)
    nfkd = unicodedata.normalize("NFKD", zone_name)
    ascii_text = "".join(c for c in nfkd if not unicodedata.combining(c))
    slug = ascii_text.lower().strip()
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"[^a-z0-9\-]", "", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


@app.post("/api/export/html")
async def export_html(request: Request):
    """Generate a standalone HTML map for a completed analysis."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content=APIError(
                error="invalid_json",
                message="El cuerpo de la solicitud no es JSON válido",
            ).model_dump(),
        )

    analysis_id: str = body.get("analysis_id", "")
    active_layers: list[str] = body.get("active_layers", []) or []
    radius_km: float = float(body.get("radius_km", 5.0) or 5.0)

    if not analysis_id:
        return JSONResponse(
            status_code=400,
            content=APIError(
                error="missing_field",
                message="El campo 'analysis_id' es requerido",
            ).model_dump(),
        )

    # Look up stored analysis result
    analysis_result = analysis_store.get(analysis_id)
    if analysis_result is None:
        return JSONResponse(
            status_code=404,
            content=APIError(
                error="not_found",
                message="No se encontró el análisis solicitado. Realiza un nuevo análisis.",
            ).model_dump(),
        )

    # Fetch AGEB layer data if active_layers requested
    ageb_layers_data: dict | None = None
    if active_layers and ageb_reader and ageb_reader._df is not None and zone_service:
        try:
            zone_obj = zone_service.get_zone(analysis_result.zone.name)
            if zone_obj:
                ageb_data = ageb_reader.get_zone_data(zone_obj.ageb_ids)
                raw_indicators = ageb_data.raw_indicators
                coords = _estimate_ageb_coordinates(
                    zone_obj.ageb_ids,
                    zone_obj.bbox.min_lat, zone_obj.bbox.min_lng,
                    zone_obj.bbox.max_lat, zone_obj.bbox.max_lng,
                )
                layers: dict = {}
                for indicator_key in active_layers:
                    meta = _INDICATOR_META.get(indicator_key)
                    if not meta:
                        continue
                    agebs_list = []
                    for ageb_id in zone_obj.ageb_ids:
                        raw = raw_indicators.get(ageb_id, {})
                        value = _extract_indicator(indicator_key, raw)
                        lat, lng = coords.get(ageb_id, (zone_obj.center_lat, zone_obj.center_lng))
                        agebs_list.append({
                            "ageb_id": ageb_id,
                            "value": value,
                            "center_lat": lat,
                            "center_lng": lng,
                        })
                    layers[indicator_key] = {
                        "label": meta["label"],
                        "unit": meta["unit"],
                        "agebs": agebs_list,
                    }
                if layers:
                    ageb_layers_data = layers
        except Exception as exc:
            logger.warning("Could not fetch AGEB layers for HTML export: %s", exc)

    # Generate HTML
    try:
        html_content = ExportService.generate_standalone_html(
            analysis_result, ageb_layers_data=ageb_layers_data, radius_km=radius_km
        )
    except Exception as exc:
        logger.exception("HTML export generation failed")
        return JSONResponse(
            status_code=500,
            content=APIError(
                error="html_generation_error",
                message="Error generando el mapa HTML interactivo. Intente nuevamente.",
                details=str(exc),
            ).model_dump(),
        )

    zone_slug = _make_zone_slug(analysis_result.zone.name)
    filename = f"mapa-viabilidad-{zone_slug}.html"

    return Response(
        content=html_content,
        media_type="text/html",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
