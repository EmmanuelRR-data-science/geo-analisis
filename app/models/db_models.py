"""SQLAlchemy models for AGEB demographic data."""

from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, Index, Integer, JSON, String
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func
from geoalchemy2 import Geometry


class Base(DeclarativeBase):
    pass


class AGEBDemographics(Base):
    __tablename__ = "ageb_demographics"

    id = Column(String(20), primary_key=True)
    entidad = Column(String(2), nullable=False)
    municipio = Column(String(3), nullable=False)
    localidad = Column(String(4), nullable=False)
    ageb_id = Column(String(4), nullable=False)
    mza = Column(String(3))

    # Demographic columns
    pobtot = Column(Integer)
    pobfem = Column(Integer)
    pobmas = Column(Integer)
    p_12ymas = Column(Integer)
    p_15ymas = Column(Integer)
    p_18ymas = Column(Integer)
    p_60ymas = Column(Integer)
    pob0_14 = Column(Integer)
    pob15_64 = Column(Integer)
    pob65_mas = Column(Integer)
    graproes = Column(Float)
    pea = Column(Integer)
    pe_inac = Column(Integer)
    pocupada = Column(Integer)
    pdesocup = Column(Integer)
    psinder = Column(Integer)
    pder_ss = Column(Integer)
    tothog = Column(Integer)
    pobhog = Column(Integer)
    vivtot = Column(Integer)
    vivpar_hab = Column(Integer)
    ocupvivpar = Column(Integer)
    prom_ocup = Column(Float)
    vph_c_elec = Column(Integer)
    vph_aguadv = Column(Integer)
    vph_drenaj = Column(Integer)
    vph_refri = Column(Integer)
    vph_lavad = Column(Integer)
    vph_autom = Column(Integer)
    vph_pc = Column(Integer)
    vph_cel = Column(Integer)
    vph_inter = Column(Integer)

    location = Column(Geometry("POINT", srid=4326))

    def __repr__(self) -> str:
        return f"<AGEBDemographics(id='{self.id}', pobtot={self.pobtot})>"


class BestTimeCache(Base):
    __tablename__ = "besttime_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    venue_id = Column(String(100), index=True)
    venue_name = Column(String(500), nullable=False)
    venue_address = Column(String(500), nullable=False)
    forecast_data = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_besttime_cache_name_address", "venue_name", "venue_address"),
    )
