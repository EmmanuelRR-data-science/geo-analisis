from __future__ import annotations

from sqlalchemy import Column, Float, Integer, String, JSON
from sqlalchemy.orm import DeclarativeBase
from geoalchemy2 import Geometry

class Base(DeclarativeBase):
    pass

class AGEBDemographics(Base):
    __tablename__ = "ageb_demographics"

    id = Column(String(20), primary_key=True)  # Clave compuesta Entidad+Municipio+Loc+AGEB
    entidad = Column(String(2))
    municipio = Column(String(3))
    localidad = Column(String(4))
    ageb_id = Column(String(4))
    
    # Demográficos principales
    total_population = Column(Integer)
    population_density = Column(Float)
    economically_active_population = Column(Integer)
    socioeconomic_level = Column(String(20))
    
    # Indicadores extendidos (JSON para flexibilidad de ciencia de datos)
    indicators = Column(JSON)
    
    # Campo Geoespacial (PostGIS)
    # Usamos Punto para el centroide en este MVP, escalable a Multipolígono
    location = Column(Geometry(geometry_type='POINT', srid=4326))

    def __repr__(self) -> str:
        return f"<AGEBDemographics(id='{self.id}', population={self.total_population})>"
