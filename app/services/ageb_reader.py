from __future__ import annotations
import logging
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.models.schemas import AGEBData

logger = logging.getLogger(__name__)

class AGEBReader:
    """Reads demographic data from PostGIS database."""

    def __init__(self) -> None:
        user = os.getenv("POSTGRES_USER", "admin")
        password = os.getenv("POSTGRES_PASSWORD", "admin_password_safe")
        db = os.getenv("POSTGRES_DB", "geoanalisis")
        host = os.getenv("DB_HOST", "geo-db")
        self.engine = create_engine(f"postgresql://{user}:{password}@{host}:5432/{db}")
        self.Session = sessionmaker(bind=self.engine)

    def load(self, filepath: str = "") -> None:
        """Legacy compatibility method."""
        logger.info("Using PostGIS as data source (Excel ignored).")

    def get_zone_data(self, ageb_ids: list[str]) -> AGEBData:
        """Aggregate demographic data from PostGIS for given AGEB IDs."""
        if not ageb_ids:
            return self._empty_data()

        session = self.Session()
        try:
            # Consulta agregada directa en SQL para máxima eficiencia
            query = text("""
                SELECT 
                    SUM(total_population) as total_pop,
                    SUM(economically_active_population) as total_pea,
                    COUNT(*) as ageb_count,
                    AVG((indicators->>'avg_schooling')::float) as avg_schooling,
                    AVG((indicators->>'pct_internet')::float) as pct_internet,
                    AVG((indicators->>'pct_car')::float) as pct_car,
                    AVG((indicators->>'pct_pc')::float) as pct_pc
                FROM ageb_demographics 
                WHERE id IN :ids
            """)
            result = session.execute(query, {"ids": tuple(ageb_ids)}).fetchone()

            if not result or result.total_pop is None:
                return self._empty_data()

            avg_schooling = result.avg_schooling or 0
            nse = "Bajo"
            if avg_schooling >= 14: nse = "Alto"
            elif avg_schooling >= 12: nse = "Medio-Alto"
            elif avg_schooling >= 10: nse = "Medio"
            elif avg_schooling >= 7: nse = "Medio-Bajo"

            return AGEBData(
                total_population=int(result.total_pop),
                population_density=round(result.total_pop / (result.ageb_count * 0.25), 2),
                economically_active_population=int(result.total_pea),
                socioeconomic_level=nse,
                ageb_count=result.ageb_count,
                avg_schooling_years=round(avg_schooling, 1),
                pct_with_internet=round(result.pct_internet or 0, 1),
                pct_with_car=round(result.pct_car or 0, 1),
                pct_with_computer=round(result.pct_pc or 0, 1),
                raw_indicators={}
            )
        except Exception as e:
            logger.error(f"Error querying PostGIS: {e}")
            return self._empty_data()
        finally:
            session.close()

    def _empty_data(self) -> AGEBData:
        return AGEBData(
            total_population=0, population_density=0.0,
            economically_active_population=0, socioeconomic_level="Desconocido",
            ageb_count=0, raw_indicators={}
        )
