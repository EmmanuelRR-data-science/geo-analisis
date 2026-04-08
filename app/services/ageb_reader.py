from __future__ import annotations
import logging
import pandas as pd
from pathlib import Path
from app.models.schemas import AGEBData

logger = logging.getLogger(__name__)

class AGEBReader:
    """Reads demographic data from INEGI Excel files."""

    def __init__(self) -> None:
        self._df: pd.DataFrame | None = None

    def load(self, filepath: str) -> None:
        """Load the Excel file into memory."""
        logger.info(f"Loading AGEB data from {filepath}")
        if not Path(filepath).exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        
        # Carga optimizada
        self._df = pd.read_excel(filepath)
        # Asegurar tipos de datos para filtros
        self._df['MZA'] = self._df['MZA'].astype(str).str.strip().str.zfill(3)
        self._df['AGEB'] = self._df['AGEB'].astype(str).str.strip().str.zfill(4)
        self._df['ENTIDAD'] = self._df['ENTIDAD'].astype(str).str.strip().str.zfill(2)
        self._df['MUN'] = self._df['MUN'].astype(str).str.strip().str.zfill(3)
        self._df['LOC'] = self._df['LOC'].astype(str).str.strip().str.zfill(4)
        
        # Crear ID único
        self._df['id'] = self._df['ENTIDAD'] + self._df['MUN'] + self._df['LOC'] + self._df['AGEB']

    def get_zone_data(self, ageb_ids: list[str]) -> AGEBData:
        """Aggregate data for a list of AGEB IDs."""
        if self._df is None or not ageb_ids:
            return self._empty_data()

        # Filtrar por IDs y asegurar que sea el total del AGEB (MZA == '000')
        mask = (self._df['id'].isin(ageb_ids)) & (self._df['MZA'] == '000')
        subset = self._df[mask]

        if subset.empty:
            logger.warning(f"No data found for AGEBs: {ageb_ids[:3]}")
            return self._empty_data()

        total_pop = subset['POBTOT'].sum()
        total_pea = subset['PEA'].sum() if 'PEA' in subset else 0
        avg_schooling = subset['GRAPROES'].mean() if 'GRAPROES' in subset else 0

        return AGEBData(
            total_population=int(total_pop),
            population_density=round(total_pop / (len(subset) * 0.25), 2) if len(subset) > 0 else 0,
            economically_active_population=int(total_pea),
            socioeconomic_level=self._classify_nse(avg_schooling),
            ageb_count=len(subset),
            avg_schooling_years=round(avg_schooling, 1),
            raw_indicators={}
        )

    def _classify_nse(self, schooling: float) -> str:
        if schooling >= 14: return "Alto"
        if schooling >= 12: return "Medio-Alto"
        if schooling >= 10: return "Medio"
        return "Bajo"

    def _empty_data(self) -> AGEBData:
        return AGEBData(total_population=0, population_density=0.0, economically_active_population=0, socioeconomic_level="N/D", ageb_count=0, raw_indicators={})
