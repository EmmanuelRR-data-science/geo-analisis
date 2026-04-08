"""FastAPI application — Mapa de Viabilidad de Negocios."""

from __future__ import annotations
import logging
import os
import uuid
import base64
import threading
from contextlib import asynccontextmanager
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

AGEB_PATH = os.getenv("AGEB_FILE_PATH", "RESAGEBURB_09XLSX20.xlsx")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Carga inicial de datos en segundo plano para no bloquear el inicio
    def load_data():
        try:
            ageb_reader.load(AGEB_PATH)
            logger.info("AGEB Data loaded successfully in background")
        except Exception as e:
            logger.error(f"Failed to load AGEB data: {e}")
    
    thread = threading.Thread(target=load_data, daemon=True)
    thread.start()
    yield

app = FastAPI(title="GeoAnalisis", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Static Files
_STATIC = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")

@app.get("/")
async def root():
    return FileResponse(str(_STATIC / "index.html"))

@app.post("/api/analyze")
async def analyze(request: Request):
    body = await request.json()
    biz_input = body.get("business_type", "")
    zone_name = body.get("zone", "")
    
    zone = zone_service.get_zone(zone_name)
    if not zone:
        return JSONResponse(status_code=404, content={"error": "Zona no encontrada"})

    # Step 1: Interpret
    interpretation = await llm_service.interpret_business_type(biz_input)
    
    # Step 2: Data
    businesses, warnings = await data_service.get_businesses_in_zone(zone, interpretation)
    ageb_data = ageb_reader.get_zone_data(zone.ageb_ids)
    
    # Step 3: Classify
    classified = await llm_service.classify_businesses(interpretation, businesses)
    
    # Step 4: Viability
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
        timestamp=datetime.now(timezone.utc).isoformat()
    )
    
    result.recommendation_text = await llm_service.generate_recommendation(result)
    analysis_store[result.analysis_id] = result
    return result.model_dump()

@app.post("/api/export/pdf")
async def export_pdf(request: Request):
    body = await request.json()
    aid = body.get("analysis_id")
    img = body.get("map_image_base64", "")
    
    res = analysis_store.get(aid)
    if not res: return JSONResponse(status_code=404, content={"error": "Análisis no encontrado"})
    
    try:
        if "," in img: img = img.split(",")[1]
        pdf_bytes = ExportService.generate_pdf(res, base64.b64decode(img))
        return Response(content=bytes(pdf_bytes), media_type="application/pdf")
    except Exception as e:
        logger.exception("PDF Error")
        return JSONResponse(status_code=500, content={"error": str(e)})
