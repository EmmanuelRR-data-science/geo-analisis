"""AGEBReader — queries demographic data from PostgreSQL."""

from __future__ import annotations
import logging
from sqlalchemy import text
from app.models.schemas import AGEBData

logger = logging.getLogger(__name__)


class AGEBReader:
    """Reads demographic data from PostgreSQL."""

    def __init__(self) -> None:
        self._engine = None
        try:
            from app.db import get_engine
            self._engine = get_engine()
        except Exception as e:
            logger.warning(f"Database not available: {e}")

    def get_zone_data(self, ageb_ids: list[str]) -> AGEBData:
        """Aggregate demographic data for a list of AGEB IDs."""
        if not self._engine or not ageb_ids:
            return self._empty_data()

        try:
            with self._engine.connect() as conn:
                query = text(
                    "SELECT "
                    "  COUNT(*) AS cnt, "
                    "  COALESCE(SUM(pobtot), 0) AS sum_pobtot, "
                    "  COALESCE(SUM(pobfem), 0) AS sum_pobfem, "
                    "  COALESCE(SUM(pobmas), 0) AS sum_pobmas, "
                    "  COALESCE(SUM(pob0_14), 0) AS sum_pob0_14, "
                    "  COALESCE(SUM(pob15_64), 0) AS sum_pob15_64, "
                    "  COALESCE(SUM(pob65_mas), 0) AS sum_pob65_mas, "
                    "  COALESCE(SUM(pea), 0) AS sum_pea, "
                    "  COALESCE(SUM(pe_inac), 0) AS sum_pe_inac, "
                    "  COALESCE(SUM(pocupada), 0) AS sum_pocupada, "
                    "  COALESCE(SUM(pdesocup), 0) AS sum_pdesocup, "
                    "  COALESCE(SUM(psinder), 0) AS sum_psinder, "
                    "  COALESCE(SUM(pder_ss), 0) AS sum_pder_ss, "
                    "  COALESCE(SUM(tothog), 0) AS sum_tothog, "
                    "  COALESCE(SUM(vivtot), 0) AS sum_vivtot, "
                    "  COALESCE(SUM(vivpar_hab), 0) AS sum_vivpar_hab, "
                    "  COALESCE(SUM(ocupvivpar), 0) AS sum_ocupvivpar, "
                    "  COALESCE(AVG(graproes), 0) AS avg_graproes, "
                    "  COALESCE(AVG(prom_ocup), 0) AS avg_prom_ocup, "
                    "  COALESCE(SUM(vph_c_elec), 0) AS sum_vph_c_elec, "
                    "  COALESCE(SUM(vph_aguadv), 0) AS sum_vph_aguadv, "
                    "  COALESCE(SUM(vph_drenaj), 0) AS sum_vph_drenaj, "
                    "  COALESCE(SUM(vph_inter), 0) AS sum_vph_inter, "
                    "  COALESCE(SUM(vph_autom), 0) AS sum_vph_autom, "
                    "  COALESCE(SUM(vph_cel), 0) AS sum_vph_cel, "
                    "  COALESCE(SUM(vph_pc), 0) AS sum_vph_pc, "
                    "  COALESCE(SUM(p_12ymas), 0) AS sum_p_12ymas, "
                    "  COALESCE(SUM(p_15ymas), 0) AS sum_p_15ymas, "
                    "  COALESCE(SUM(p_18ymas), 0) AS sum_p_18ymas, "
                    "  COALESCE(SUM(p_60ymas), 0) AS sum_p_60ymas, "
                    "  COALESCE(SUM(pobhog), 0) AS sum_pobhog, "
                    "  COALESCE(SUM(vph_refri), 0) AS sum_vph_refri, "
                    "  COALESCE(SUM(vph_lavad), 0) AS sum_vph_lavad "
                    "FROM ageb_demographics "
                    "WHERE id = ANY(:ids) AND (mza = '000' OR mza IS NULL)"
                )
                row = conn.execute(query, {"ids": ageb_ids}).fetchone()

            if not row or row.cnt == 0:
                return self._empty_data()

            total_pop = int(row.sum_pobtot)
            cnt = int(row.cnt)
            vivpar_hab = int(row.sum_vivpar_hab)

            def pct(numerator: int) -> float:
                if vivpar_hab <= 0:
                    return 0.0
                return min(100.0, round(numerator / vivpar_hab * 100, 1))

            # Extract new AGEB variables
            pea = int(row.sum_pea)
            pdesocup = int(row.sum_pdesocup)
            pob0_14 = int(row.sum_pob0_14)
            pob15_64 = int(row.sum_pob15_64)
            pob65_mas = int(row.sum_pob65_mas)
            p_15ymas = int(row.sum_p_15ymas)
            vph_refri = int(row.sum_vph_refri)
            vph_lavad = int(row.sum_vph_lavad)

            # Calculate derived indicators with division-by-zero protection
            unemployment_rate = round(pdesocup / pea * 100, 1) if pea > 0 else 0.0
            economic_participation_rate = round(pea / p_15ymas * 100, 1) if p_15ymas > 0 else 0.0
            dependency_index = round((pob0_14 + pob65_mas) / pob15_64 * 100, 1) if pob15_64 > 0 else 0.0
            pct_with_refrigerator = min(100.0, round(vph_refri / vivpar_hab * 100, 1)) if vivpar_hab > 0 else 0.0
            pct_with_washing_machine = min(100.0, round(vph_lavad / vivpar_hab * 100, 1)) if vivpar_hab > 0 else 0.0

            extended_indicators = {
                "unemployment_rate": unemployment_rate,
                "economic_participation_rate": economic_participation_rate,
                "dependency_index": dependency_index,
                "pct_with_refrigerator": pct_with_refrigerator,
                "pct_with_washing_machine": pct_with_washing_machine,
                "population_12_plus": int(row.sum_p_12ymas),
                "population_15_plus": p_15ymas,
                "population_18_plus": int(row.sum_p_18ymas),
                "population_60_plus": int(row.sum_p_60ymas),
                "household_population": int(row.sum_pobhog),
            }

            return AGEBData(
                total_population=total_pop,
                population_density=round(total_pop / (cnt * 0.25), 2) if cnt > 0 else 0,
                economically_active_population=pea,
                socioeconomic_level=self._classify_nse(float(row.avg_graproes)),
                ageb_count=cnt,
                female_population=int(row.sum_pobfem),
                male_population=int(row.sum_pobmas),
                population_0_14=pob0_14,
                population_15_64=pob15_64,
                population_65_plus=pob65_mas,
                occupied_population=int(row.sum_pocupada),
                unemployed_population=pdesocup,
                inactive_population=int(row.sum_pe_inac),
                avg_schooling_years=round(float(row.avg_graproes), 1),
                total_households=int(row.sum_tothog),
                total_dwellings=int(row.sum_vivtot),
                avg_occupants_per_dwelling=round(float(row.avg_prom_ocup), 1),
                population_with_health_services=int(row.sum_pder_ss),
                population_without_health_services=int(row.sum_psinder),
                pct_with_electricity=pct(int(row.sum_vph_c_elec)),
                pct_with_water=pct(int(row.sum_vph_aguadv)),
                pct_with_drainage=pct(int(row.sum_vph_drenaj)),
                pct_with_internet=pct(int(row.sum_vph_inter)),
                pct_with_car=pct(int(row.sum_vph_autom)),
                pct_with_cellphone=pct(int(row.sum_vph_cel)),
                pct_with_computer=pct(int(row.sum_vph_pc)),
                raw_indicators={},
                extended_indicators=extended_indicators,
            )
        except Exception as e:
            logger.error(f"Database query failed: {e}")
            return self._empty_data()

    def _classify_nse(self, schooling: float) -> str:
        if schooling >= 14:
            return "Alto"
        if schooling >= 12:
            return "Medio-Alto"
        if schooling >= 10:
            return "Medio"
        return "Bajo"

    def _empty_data(self) -> AGEBData:
        return AGEBData(
            total_population=0,
            population_density=0.0,
            economically_active_population=0,
            socioeconomic_level="N/D",
            ageb_count=0,
            raw_indicators={},
        )
