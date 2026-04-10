"""Módulo puro de cálculo de variables de entorno derivadas.

Calcula Densidad_POI, Índice_Actividad_Comercial y Concentración_Sectorial
a partir de listas de negocios clasificados. Sin I/O.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.schemas import ClassifiedBusiness

# Descripciones de sectores SCIAN por código de 2 dígitos
SCIAN_SECTOR_DESCRIPTIONS: dict[str, str] = {
    "11": "Agricultura, cría y explotación de animales",
    "21": "Minería",
    "22": "Generación y distribución de energía eléctrica",
    "23": "Construcción",
    "31": "Industrias manufactureras",
    "32": "Industrias manufactureras",
    "33": "Industrias manufactureras",
    "43": "Comercio al por mayor",
    "46": "Comercio al por menor",
    "48": "Transportes, correos y almacenamiento",
    "49": "Transportes, correos y almacenamiento",
    "51": "Información en medios masivos",
    "52": "Servicios financieros y de seguros",
    "53": "Servicios inmobiliarios",
    "54": "Servicios profesionales y técnicos",
    "55": "Corporativos",
    "56": "Servicios de apoyo a los negocios",
    "61": "Servicios educativos",
    "62": "Servicios de salud y asistencia social",
    "71": "Servicios de esparcimiento y culturales",
    "72": "Servicios de alojamiento y alimentos",
    "81": "Otros servicios excepto gobierno",
    "93": "Actividades legislativas y gubernamentales",
}


class EnvironmentCalculator:
    """Calcula variables de entorno derivadas de listas de negocios."""

    @staticmethod
    def calculate_poi_density(total_businesses: int, radius_km: float) -> float:
        """Densidad_POI = total_negocios / (π × r²).

        Returns 0.0 if radius_km <= 0 or total_businesses <= 0.
        Result rounded to 2 decimals.
        """
        if radius_km <= 0 or total_businesses <= 0:
            return 0.0
        area = math.pi * radius_km ** 2
        return round(total_businesses / area, 2)

    @staticmethod
    def calculate_commercial_activity_index(businesses: list[ClassifiedBusiness]) -> float:
        """Índice_Actividad_Comercial = (verified_google / total) × 100.

        Returns 0.0 if the list is empty. Result rounded to 1 decimal.
        """
        if not businesses:
            return 0.0
        verified = sum(1 for b in businesses if b.verified_google)
        return round((verified / len(businesses)) * 100, 1)

    @staticmethod
    def calculate_sector_concentration(businesses: list[ClassifiedBusiness]) -> list[dict]:
        """Concentración_Sectorial: agrupa negocios por primeros 2 dígitos SCIAN.

        Returns a list of dicts sorted by count descending:
            {"sector": str, "code_2d": str, "count": int, "percentage": float}

        Skips businesses without denue_scian_code.
        Returns empty list if no businesses have SCIAN codes.
        """
        codes_2d: list[str] = []
        for b in businesses:
            if b.denue_scian_code:
                code = b.denue_scian_code.strip()
                if len(code) >= 2:
                    codes_2d.append(code[:2])

        if not codes_2d:
            return []

        counts = Counter(codes_2d)
        total = sum(counts.values())

        result = []
        for code_2d, count in counts.most_common():
            description = SCIAN_SECTOR_DESCRIPTIONS.get(code_2d, f"Sector {code_2d}")
            result.append({
                "sector": description,
                "code_2d": code_2d,
                "count": count,
                "percentage": round((count / total) * 100, 1),
            })

        return result

    @staticmethod
    def calculate_all(businesses: list[ClassifiedBusiness], radius_km: float) -> dict:
        """Calcula todas las variables derivadas y retorna un diccionario.

        Returns:
            {
                "poi_density": float,
                "commercial_activity_index": float,
                "sector_concentration": list[dict],
            }
        """
        return {
            "poi_density": EnvironmentCalculator.calculate_poi_density(
                len(businesses), radius_km
            ),
            "commercial_activity_index": EnvironmentCalculator.calculate_commercial_activity_index(
                businesses
            ),
            "sector_concentration": EnvironmentCalculator.calculate_sector_concentration(
                businesses
            ),
        }
