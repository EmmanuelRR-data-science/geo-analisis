from __future__ import annotations
from fuzzywuzzy import fuzz, process
from app.models.schemas import BoundingBox, Zone

_ZONE_CATALOG: list[dict] = [
    {
        "name": "Del Valle Centro",
        "ageb_ids": ["0901400010011", "0901400010026", "0901400010030", "0901400010045", "090140001005A"],
        "center_lat": 19.3718, "center_lng": -99.1710,
        "bbox": {"min_lat": 19.3650, "min_lng": -99.1800, "max_lat": 19.3790, "max_lng": -99.1620},
    },
    {
        "name": "Condesa",
        "ageb_ids": ["0901500010019", "0901500010023", "0901500010038", "0901500010042"],
        "center_lat": 19.4113, "center_lng": -99.1733,
        "bbox": {"min_lat": 19.4060, "min_lng": -99.1810, "max_lat": 19.4170, "max_lng": -99.1660},
    },
    {
        "name": "Polanco",
        "ageb_ids": ["0901600010016", "0901600010020", "0901600010035", "090160001004A"],
        "center_lat": 19.4330, "center_lng": -99.1950,
        "bbox": {"min_lat": 19.4270, "min_lng": -99.2050, "max_lat": 19.4390, "max_lng": -99.1850},
    },
    {
        "name": "Roma Norte",
        "ageb_ids": ["0901500010095", "0901500010108", "0901500010112"],
        "center_lat": 19.4190, "center_lng": -99.1620,
        "bbox": {"min_lat": 19.4140, "min_lng": -99.1700, "max_lat": 19.4240, "max_lng": -99.1540},
    }
]

class ZoneService:
    def __init__(self) -> None:
        self._zones = [self._build_zone(e) for e in _ZONE_CATALOG]
        self._names = [z.name for z in self._zones]

    def _build_zone(self, e: dict) -> Zone:
        return Zone(name=e["name"], ageb_ids=e["ageb_ids"], center_lat=e["center_lat"], center_lng=e["center_lng"], bbox=BoundingBox(**e["bbox"]))

    def get_zone(self, name: str) -> Zone | None:
        name = name.lower().strip()
        for z in self._zones:
            if z.name.lower() == name: return z
        return None

    def search_zones(self, query: str) -> list[Zone]:
        results = process.extract(query, self._names, limit=5)
        return [self.get_zone(n) for n, score in results if score > 50]

    def validate_input(self, biz: str, zone: str) -> tuple[bool, list[str]]:
        errors = []
        if not biz: errors.append("Tipo de negocio requerido")
        if not zone: errors.append("Zona requerida")
        return (len(errors) == 0, errors)

    def suggest_similar_zones(self, name: str) -> list[str]:
        results = process.extract(name, self._names, limit=3)
        return [n for n, s in results if s > 40]
