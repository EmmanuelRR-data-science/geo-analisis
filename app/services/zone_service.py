from __future__ import annotations
import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fuzzywuzzy import fuzz, process
from app.models.schemas import BoundingBox, Zone

logger = logging.getLogger(__name__)

class ZoneService:
    """Service for zone validation and dynamic AGEB lookup via PostGIS."""

    def __init__(self) -> None:
        user = os.getenv("POSTGRES_USER", "admin")
        password = os.getenv("POSTGRES_PASSWORD", "admin_password_safe")
        db = os.getenv("POSTGRES_DB", "geoanalisis")
        host = os.getenv("DB_HOST", "geo-db")
        self.engine = create_engine(f"postgresql://{user}:{password}@{host}:5432/{db}")
        self.Session = sessionmaker(bind=self.engine)

    def get_dynamic_zone(self, name: str, lat: float, lng: float, radius_km: float = 2.0) -> Zone:
        """Find AGEBs dynamically around a point using PostGIS."""
        session = self.Session()
        try:
            # Consulta espacial: busca AGEBs en un radio ST_DWithin (metros)
            query = text("""
                SELECT id 
                FROM ageb_demographics 
                WHERE ST_DWithin(location, ST_SetSRID(ST_Point(:lng, :lat), 4326), :radius)
            """)
            result = session.execute(query, {"lng": lng, "lat": lat, "radius": radius_km * 1000})
            ageb_ids = [row.id for row in result]
            
            logger.info(f"Dynamic zone lookup: Found {len(ageb_ids)} AGEBs for {name} in {radius_km}km")

            return Zone(
                name=name,
                ageb_ids=ageb_ids,
                center_lat=lat,
                center_lng=lng,
                bbox=BoundingBox(
                    min_lat=lat - 0.02, min_lng=lng - 0.02,
                    max_lat=lat + 0.02, max_lng=lng + 0.02
                )
            )
        except Exception as e:
            logger.error(f"Error in dynamic zone lookup: {e}")
            return Zone(
                name=name, ageb_ids=[], center_lat=lat, center_lng=lng,
                bbox=BoundingBox(min_lat=lat, min_lng=lng, max_lat=lat, max_lng=lng)
            )
        finally:
            session.close()

    def validate_input(self, business_type: str, zone: str) -> tuple[bool, list[str]]:
        errors = []
        if not business_type or not business_type.strip(): errors.append("Tipo de negocio requerido")
        if not zone or not zone.strip(): errors.append("Zona requerida")
        return (len(errors) == 0, errors)
