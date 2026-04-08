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

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Service singletons
# ---------------------------------------------------------------------------

zone_service: ZoneService | None = None
ageb_reader: AGEBReader | None = None
llm_service: LLMService | None = None
data_service: DataService | None = None
analysis_engine: AnalysisEngine | None = None

analysis_store: dict[str, AnalysisResult] = {}

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global zone_service, ageb_reader, llm_service, data_service, analysis_engine
    zone_service = ZoneService()
    ageb_reader = AGEBReader()
    llm_service = LLMService()
    data_service = DataService(zone_service=zone_service, ageb_reader=ageb_reader)
    analysis_engine = AnalysisEngine()
    yield

app = FastAPI(title="Mapa de Viabilidad de Negocios", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if _STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

_INDEX_HTML = Path(__file__).resolve().parent.parent / "templates" / "index.html"

@app.get("/")
async def root():
    if _INDEX_HTML.exists():
        return FileResponse(str(_INDEX_HTML))
    alt = _STATIC_DIR / "index.html"
    if alt.exists():
        return FileResponse(str(alt))
    return JSONResponse({"message": "Frontend not ready"}, status_code=200)

@app.get("/api/health")
async def health():
    return {"status": "ok"}

@app.post("/api/analyze")
async def analyze(request: Request):
    warnings: list[str] = []
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid_json"})

    business_type_input = body.get("business_type", "")
    zone_input = body.get("zone", "")
    radius_km = float(body.get("radius_km", 2.0))
    radius_m = int(radius_km * 1000)

    # Dinamización con PostGIS
    zone = zone_service.get_dynamic_zone(zone_input, 19.4326, -99.1332)
    try:
        from app.clients.google_places_client import GooglePlacesClient
        g_client = GooglePlacesClient()
        g_coords = await g_client.get_geocode(zone_input)
        if g_coords:
            lat, lng = g_coords
            zone = zone_service.get_dynamic_zone(zone_input, lat, lng, radius_km=radius_km)
    except Exception as e:
        logger.warning(f"Geocode error: {e}")

    if not zone or not zone.ageb_ids:
        return JSONResponse(status_code=422, content={"error": "zone_not_found", "message": f"No se hallaron AGEBs en {radius_km}km"})

    try:
        # Step 1: LLM Interpret
        business_interpretation = await llm_service.interpret_business_type(business_type_input)
        if business_interpretation.used_fallback:
            warnings.append("Usando fallback de catálogo (Groq no disponible)")

        # Step 2: Businesses
        businesses, biz_warnings = await data_service.get_businesses_in_zone(zone, business_interpretation, radius_m=radius_m)
        warnings.extend(biz_warnings)

        # Step 3: Classify
        classified = await llm_service.classify_businesses(business_interpretation, businesses)

        # Step 4: AGEB Data
        ageb_data = ageb_reader.get_zone_data(zone.ageb_ids)

        # Step 5: Viability
        viability = analysis_engine.calculate_viability(classified, ageb_data)

        # Result construction
        analysis_id = str(uuid.uuid4())
        result = AnalysisResult(
            analysis_id=analysis_id,
            business_type=business_interpretation,
            zone=zone,
            businesses=classified,
            ageb_data=ageb_data,
            viability=viability,
            recommendation_text="",
            warnings=warnings,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        # Step 7: Recommendation
        result.recommendation_text = await llm_service.generate_recommendation(result)
        analysis_store[analysis_id] = result

        return result.model_dump()

    except Exception as exc:
        logger.exception("Analysis failed")
        return JSONResponse(status_code=500, content={"error": "analysis_error", "message": str(exc)})

@app.post("/api/export/pdf")
async def export_pdf(request: Request):
    body = await request.json()
    analysis_id = body.get("analysis_id")
    map_image_base64 = body.get("map_image_base64", "")

    result = analysis_store.get(analysis_id)
    if not result:
        return JSONResponse(status_code=404, content={"error": "not_found"})

    try:
        if "," in map_image_base64:
            map_image_base64 = map_image_base64.split(",", 1)[1]
        map_image_bytes = base64.b64decode(map_image_base64)
        
        pdf_bytes = ExportService.generate_pdf(result, map_image_bytes)
        return Response(
            content=bytes(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="reporte.pdf"'}
        )
    except Exception as e:
        logger.exception("PDF failed")
        return JSONResponse(status_code=500, content={"error": "pdf_error", "message": str(e)})
