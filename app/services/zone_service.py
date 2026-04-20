"""Zone validation and catalog service for CDMX colonias."""

from __future__ import annotations

from fuzzywuzzy import fuzz, process

from app.models.schemas import BoundingBox, Zone

_ZONE_CATALOG: list[dict] = [
    {"name": "Del Valle Centro", "ageb_ids": ["0901400010011", "0901400010026", "0901400010030", "0901400010045", "090140001005A", "0901400010064", "0901400010079", "0901400010083", "0901400010098", "0901400010100"], "center_lat": 19.3718, "center_lng": -99.1710, "bbox": {"min_lat": 19.3650, "min_lng": -99.1800, "max_lat": 19.3790, "max_lng": -99.1620}},
    {"name": "Del Valle Norte", "ageb_ids": ["0901400010115", "090140001012A", "0901400010134", "0901400010149", "0901400010153", "0901400010168", "0901400010172"], "center_lat": 19.3780, "center_lng": -99.1700, "bbox": {"min_lat": 19.3740, "min_lng": -99.1770, "max_lat": 19.3820, "max_lng": -99.1630}},
    {"name": "Del Valle Sur", "ageb_ids": ["0901400010187", "0901400010191", "0901400010204", "0901400010219", "0901400010223", "0901400010238"], "center_lat": 19.3650, "center_lng": -99.1720, "bbox": {"min_lat": 19.3600, "min_lng": -99.1790, "max_lat": 19.3700, "max_lng": -99.1650}},
    {"name": "Narvarte Poniente", "ageb_ids": ["0901400010242", "0901400010257", "0901400010261", "0901400010276", "0901400010280", "0901400010295"], "center_lat": 19.3930, "center_lng": -99.1560, "bbox": {"min_lat": 19.3880, "min_lng": -99.1630, "max_lat": 19.3980, "max_lng": -99.1490}},
    {"name": "Narvarte Oriente", "ageb_ids": ["0901400010308", "0901400010312", "0901400010327", "0901400010331", "0901400010346", "0901400010350"], "center_lat": 19.3920, "center_lng": -99.1470, "bbox": {"min_lat": 19.3870, "min_lng": -99.1540, "max_lat": 19.3970, "max_lng": -99.1400}},
    {"name": "Nápoles", "ageb_ids": ["0901400010365", "090140001037A", "0901400010384", "0901400010399", "0901400010401", "0901400010416", "0901400010420"], "center_lat": 19.3880, "center_lng": -99.1780, "bbox": {"min_lat": 19.3830, "min_lng": -99.1850, "max_lat": 19.3930, "max_lng": -99.1710}},
    {"name": "Condesa", "ageb_ids": ["0901500010019", "0901500010023", "0901500010038", "0901500010042", "0901500010057", "0901500010061", "0901500010076", "0901500010080"], "center_lat": 19.4113, "center_lng": -99.1733, "bbox": {"min_lat": 19.4060, "min_lng": -99.1810, "max_lat": 19.4170, "max_lng": -99.1660}},
    {"name": "Roma Norte", "ageb_ids": ["0901500010095", "0901500010108", "0901500010112", "0901500010127", "0901500010131", "0901500010146", "0901500010150", "0901500010165"], "center_lat": 19.4190, "center_lng": -99.1620, "bbox": {"min_lat": 19.4140, "min_lng": -99.1700, "max_lat": 19.4240, "max_lng": -99.1540}},
    {"name": "Roma Sur", "ageb_ids": ["090150001017A", "0901500010184", "0901500010199", "0901500010201", "0901500010216", "0901500010220"], "center_lat": 19.4100, "center_lng": -99.1590, "bbox": {"min_lat": 19.4050, "min_lng": -99.1660, "max_lat": 19.4150, "max_lng": -99.1520}},
    {"name": "Juárez", "ageb_ids": ["0901500010235", "090150001024A", "0901500010254", "0901500010269", "0901500010273", "0901500010288", "0901500010292"], "center_lat": 19.4270, "center_lng": -99.1580, "bbox": {"min_lat": 19.4220, "min_lng": -99.1660, "max_lat": 19.4320, "max_lng": -99.1500}},
    {"name": "Cuauhtémoc", "ageb_ids": ["0901500010305", "090150001031A", "0901500010324", "0901500010339", "0901500010343", "0901500010358", "0901500010362", "0901500010377"], "center_lat": 19.4350, "center_lng": -99.1480, "bbox": {"min_lat": 19.4300, "min_lng": -99.1560, "max_lat": 19.4400, "max_lng": -99.1400}},
    {"name": "Polanco", "ageb_ids": ["0901600010016", "0901600010020", "0901600010035", "090160001004A", "0901600010054", "0901600010069", "0901600010073", "0901600010088", "0901600010092", "0901600010105"], "center_lat": 19.4330, "center_lng": -99.1950, "bbox": {"min_lat": 19.4270, "min_lng": -99.2050, "max_lat": 19.4390, "max_lng": -99.1850}},
    {"name": "Santa Fe", "ageb_ids": ["0901600011090", "0901600011103", "0901600011118", "0901600011122", "0901600011137", "0901600011141", "0901600011156", "0901600011160"], "center_lat": 19.3590, "center_lng": -99.2760, "bbox": {"min_lat": 19.3510, "min_lng": -99.2880, "max_lat": 19.3670, "max_lng": -99.2640}},
    {"name": "Coyoacán Centro", "ageb_ids": ["0900300010018", "0900300010022", "0900300010037", "0900300010041", "0900300010056", "0900300010060", "0900300010075", "090030001008A"], "center_lat": 19.3500, "center_lng": -99.1620, "bbox": {"min_lat": 19.3440, "min_lng": -99.1700, "max_lat": 19.3560, "max_lng": -99.1540}},
    {"name": "San Ángel", "ageb_ids": ["0901000010012", "0901000010027", "0901000010031", "0901000010046", "0901000010050", "0901000010065"], "center_lat": 19.3470, "center_lng": -99.1930, "bbox": {"min_lat": 19.3410, "min_lng": -99.2010, "max_lat": 19.3530, "max_lng": -99.1850}},
    {"name": "Insurgentes Mixcoac", "ageb_ids": ["0901000010084", "0901000010099", "0901000010101", "0901000010116", "0901000010135"], "center_lat": 19.3720, "center_lng": -99.1870, "bbox": {"min_lat": 19.3670, "min_lng": -99.1940, "max_lat": 19.3770, "max_lng": -99.1800}},
    {"name": "Tlalpan Centro", "ageb_ids": ["0901200010017", "0901200010021", "0901200010040", "0901200010074", "0901200010089"], "center_lat": 19.2940, "center_lng": -99.1690, "bbox": {"min_lat": 19.2880, "min_lng": -99.1770, "max_lat": 19.3000, "max_lng": -99.1610}},
    {"name": "Xochimilco Centro", "ageb_ids": ["0901300010014", "0901300010029", "0901300010033", "0901300010052", "0901300010067"], "center_lat": 19.2620, "center_lng": -99.1040, "bbox": {"min_lat": 19.2560, "min_lng": -99.1120, "max_lat": 19.2680, "max_lng": -99.0960}},
]

_SUGGESTION_THRESHOLD = 60
_SEARCH_THRESHOLD = 50
_MAX_SUGGESTIONS = 5


def _build_zone(entry: dict) -> Zone:
    return Zone(name=entry["name"], ageb_ids=entry["ageb_ids"], center_lat=entry["center_lat"], center_lng=entry["center_lng"], bbox=BoundingBox(**entry["bbox"]))


class ZoneService:
    def __init__(self) -> None:
        self._zones: list[Zone] = [_build_zone(e) for e in _ZONE_CATALOG]
        self._zone_map: dict[str, Zone] = {z.name.lower(): z for z in self._zones}
        self._zone_names: list[str] = [z.name for z in self._zones]

    def validate_zone(self, zone_name: str) -> bool:
        return zone_name.strip().lower() in self._zone_map

    def get_zone(self, zone_name: str) -> Zone | None:
        return self._zone_map.get(zone_name.strip().lower())

    def search_zones(self, query: str) -> list[Zone]:
        query = query.strip()
        if not query:
            return []
        results = process.extract(query, self._zone_names, scorer=fuzz.WRatio, limit=_MAX_SUGGESTIONS)
        return [self.get_zone(name) for name, score, *_ in results if score >= _SEARCH_THRESHOLD]

    def suggest_similar_zones(self, zone_name: str) -> list[str]:
        zone_name = zone_name.strip()
        if not zone_name:
            return []
        results = process.extract(zone_name, self._zone_names, scorer=fuzz.WRatio, limit=_MAX_SUGGESTIONS)
        return [name for name, score, *_ in results if score >= _SUGGESTION_THRESHOLD]

    def validate_input(self, business_type: str, zone: str) -> tuple[bool, list[str]]:
        errors: list[str] = []
        if not business_type or not business_type.strip():
            errors.append("El tipo de negocio es requerido")
        if not zone or not zone.strip():
            errors.append("La zona es requerida")
        elif not self.validate_zone(zone):
            suggestions = self.suggest_similar_zones(zone)
            msg = f"La zona '{zone}' no fue encontrada en CDMX"
            if suggestions:
                msg += f". ¿Quisiste decir: {', '.join(suggestions)}?"
            errors.append(msg)
        return (len(errors) == 0, errors)
