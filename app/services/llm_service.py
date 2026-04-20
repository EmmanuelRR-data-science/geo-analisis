"""Servicio LLM para comunicación con Groq API.

Encapsula la interpretación de tipo de negocio, clasificación de negocios
y generación de recomendaciones. Incluye fallbacks locales cuando la API
no está disponible.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

import httpx
from dotenv import load_dotenv

from app.models.schemas import (
    AnalysisResult,
    Business,
    BusinessInterpretation,
    ClassifiedBusiness,
    CompetitorReviewAnalysis,
    ImprovementOpportunity,
    SCIANCategory,
    TargetCriteria,
    TargetCustomerInsight,
    ValuePoint,
)
from app.services.scian_catalog import (
    AFFINITY_RULES,
    SCIAN_CATALOG,
    get_affinity,
    search_scian_catalog,
)

load_dotenv()

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_MODEL_FAST = "llama-3.1-8b-instant"  # Faster model with higher rate limits for classification
GROQ_TIMEOUT = 30.0
GROQ_MAX_RETRIES = 4

class LLMService:
    """Servicio de comunicación con Groq API para análisis de negocios."""

    def __init__(self) -> None:
        self.api_key = os.getenv("GROQ_API_KEY", "")
        if self.api_key:
            logger.info(f"GROQ_API_KEY detectada (longitud: {len(self.api_key)})")
        else:
            logger.error("GROQ_API_KEY NO DETECTADA en el entorno")

    async def _call_groq(self, messages: list[dict[str, str]], temperature: float = 0.3, model: str | None = None) -> str | None:
        """Realiza una llamada a la API de Groq con reintentos y manejo de 429."""
        if not self.api_key:
            logger.warning("GROQ_API_KEY no configurada")
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model or GROQ_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 4096,
        }

        for attempt in range(GROQ_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=GROQ_TIMEOUT) as client:
                    response = await client.post(
                        GROQ_API_URL,
                        headers=headers,
                        json=payload,
                    )
                    
                    if response.status_code == 429:
                        wait_time = (attempt + 1) * 2 + 1
                        logger.warning("Groq Rate Limit (429). Esperando %d segundos...", wait_time)
                        await asyncio.sleep(wait_time)
                        continue
                        
                    response.raise_for_status()
                    data = response.json()
                    return data["choices"][0]["message"]["content"]
            except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError, KeyError, IndexError) as e:
                logger.warning("Groq API intento %d falló: %s", attempt + 1, e)
                if attempt >= GROQ_MAX_RETRIES:
                    return None
                await asyncio.sleep(1)
        return None

    def _parse_json_response(self, text: str) -> dict[str, Any] | None:
        """Intenta extraer JSON de la respuesta del LLM.

        Maneja casos donde el LLM envuelve el JSON en bloques de código.
        """
        if not text:
            return None
        # Strip markdown code blocks if present
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first and last lines (``` markers)
            lines = [line for line in lines if not line.strip().startswith("```")]
            cleaned = "\n".join(lines)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to find JSON object in the text
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(cleaned[start : end + 1])
                except json.JSONDecodeError:
                    pass
            logger.warning("No se pudo parsear JSON de la respuesta LLM")
            return None

    # ----------------------------------------------------------------
    # interpret_business_type
    # ----------------------------------------------------------------

    async def interpret_business_type(self, user_input: str) -> BusinessInterpretation:
        """Interpreta el tipo de negocio del usuario usando LLM o fallback.

        Args:
            user_input: Descripción libre del tipo de negocio.

        Returns:
            BusinessInterpretation con código SCIAN y categorías relacionadas.
        """
        prompt = (
            "Eres un experto en clasificación económica mexicana (SCIAN). "
            "El usuario quiere abrir un negocio y lo describe así: "
            f'"{user_input}"\n\n'
            "Identifica:\n"
            "1. El código SCIAN de 6 dígitos más apropiado\n"
            "2. La descripción oficial de esa categoría SCIAN\n"
            "3. Al menos 2 categorías de negocios complementarios (que generan sinergia)\n"
            "4. Al menos 2 categorías de negocios competidores (misma actividad o similar)\n\n"
            "Responde ÚNICAMENTE con un JSON válido con esta estructura exacta:\n"
            "{\n"
            '  "scian_code": "código de 6 dígitos",\n'
            '  "scian_description": "descripción oficial",\n'
            '  "complementary": [{"code": "código", "description": "descripción"}, ...],\n'
            '  "competitor": [{"code": "código", "description": "descripción"}, ...]\n'
            "}\n"
            "No incluyas texto adicional fuera del JSON."
        )

        messages = [
            {"role": "system", "content": "Eres un asistente experto en clasificación económica SCIAN de México. Responde siempre en español y en formato JSON."},
            {"role": "user", "content": prompt},
        ]

        response_text = await self._call_groq(messages, temperature=0, model=GROQ_MODEL_FAST)
        if response_text:
            parsed = self._parse_json_response(response_text)
            if parsed:
                try:
                    complementary = [
                        SCIANCategory(code=c["code"], description=c["description"])
                        for c in parsed.get("complementary", [])
                    ]
                    competitor = [
                        SCIANCategory(code=c["code"], description=c["description"])
                        for c in parsed.get("competitor", [])
                    ]
                    return BusinessInterpretation(
                        original_input=user_input,
                        scian_code=str(parsed.get("scian_code", "")),
                        scian_description=str(parsed.get("scian_description", "")),
                        complementary_categories=complementary,
                        competitor_categories=competitor,
                        used_fallback=False,
                    )
                except (KeyError, TypeError, ValueError) as e:
                    logger.warning("Error parseando respuesta LLM para interpret: %s", e)

        # Fallback: búsqueda textual contra catálogo SCIAN local
        return self._fallback_interpret_business_type(user_input)

    def _fallback_interpret_business_type(self, user_input: str) -> BusinessInterpretation:
        """Fallback: búsqueda textual contra catálogo SCIAN local.

        Args:
            user_input: Descripción libre del tipo de negocio.

        Returns:
            BusinessInterpretation usando catálogo local.
        """
        results = search_scian_catalog(user_input)

        if results:
            best_code, best_desc = results[0]
        else:
            # Default genérico si no hay coincidencia
            best_code = "461110"
            best_desc = SCIAN_CATALOG.get(best_code, "Comercio al por menor")

        affinity = get_affinity(best_code)

        return BusinessInterpretation(
            original_input=user_input,
            scian_code=best_code,
            scian_description=best_desc,
            complementary_categories=affinity["complementary"],
            competitor_categories=affinity["competitor"],
            used_fallback=True,
        )

    # ----------------------------------------------------------------
    # classify_businesses
    # ----------------------------------------------------------------

    async def classify_businesses(
        self,
        user_business: BusinessInterpretation,
        businesses: list[Business],
        user_filters: dict | None = None,
    ) -> list[ClassifiedBusiness]:
        if not businesses:
            return []

        # Build compact business list
        biz_lines = []
        for b in businesses:
            biz_lines.append(f"{b.id}|{b.name}|{b.category}")
        biz_text = "\n".join(biz_lines)

        prompt = (
            f"El usuario quiere abrir: {user_business.scian_description}\n\n"
        )

        # User filters are CRITICAL — put them prominently BEFORE the classification instructions
        if user_filters:
            ally = user_filters.get("ally_filters", [])
            comp = user_filters.get("competitor_filters", [])
            google_ally = user_filters.get("google_ally_categories", [])
            google_comp = user_filters.get("google_competitor_categories", [])
            kw_ally = user_filters.get("keyword_ally", [])
            kw_comp = user_filters.get("keyword_competitor", [])
            if ally or comp or google_ally or google_comp or kw_ally or kw_comp:
                prompt += "⚠️ REGLAS OBLIGATORIAS DEL USUARIO:\n"
                if comp:
                    prompt += f"- Negocios tipo [{', '.join(comp)}] son SIEMPRE competidores (X)\n"
                if ally:
                    prompt += f"- Negocios tipo [{', '.join(ally)}] son SIEMPRE complementarios (C)\n"
                if google_comp:
                    prompt += f"- Negocios con categoría Google [{', '.join(google_comp)}] son SIEMPRE competidores (X)\n"
                if google_ally:
                    prompt += f"- Negocios con categoría Google [{', '.join(google_ally)}] son SIEMPRE complementarios (C)\n"
                if kw_comp:
                    prompt += f"- Si el nombre, categoría o reseñas del negocio contienen las palabras [{', '.join(kw_comp)}], clasifícalo como competidor (X)\n"
                if kw_ally:
                    prompt += f"- Si el nombre, categoría o reseñas del negocio contienen las palabras [{', '.join(kw_ally)}], clasifícalo como complementario (C)\n"
                prompt += "Estas reglas tienen PRIORIDAD ABSOLUTA sobre tu criterio.\n\n"

        prompt += (
            "Clasifica cada negocio:\n"
            "C = complementario (genera sinergia)\n"
            "X = competidor (mismo tipo de negocio o similar)\n"
            "U = sin relación (SOLO si no hay ninguna conexión)\n"
            "Relevancia: H=alta, M=media, L=baja\n\n"
            f"Negocios (id|nombre|categoría):\n{biz_text}\n\n"
            f'Responde SOLO JSON: {{"r":[{{"i":"id","c":"C|X|U","r":"H|M|L"}},...]}}'
        )

        messages = [
            {"role": "system", "content": "Clasifica negocios comerciales. RESPETA las reglas del usuario. Responde SOLO JSON."},
            {"role": "user", "content": prompt},
        ]

        response_text = await self._call_groq(messages, temperature=0, model=GROQ_MODEL_FAST)
        if response_text:
            parsed = self._parse_json_response(response_text)
            if parsed and "r" in parsed:
                try:
                    cls_map = {"C": "complementary", "X": "competitor", "U": "unclassified",
                               "complementary": "complementary", "competitor": "competitor", "unclassified": "unclassified"}
                    rel_map = {"H": "high", "M": "medium", "L": "low",
                               "high": "high", "medium": "medium", "low": "low"}

                    classification_map = {}
                    for item in parsed["r"]:
                        cid = item.get("i", "")
                        classification_map[cid] = {
                            "classification": cls_map.get(item.get("c", "U"), "unclassified"),
                            "relevance": rel_map.get(item.get("r", "L"), "low"),
                        }

                    result = []
                    for b in businesses:
                        info = classification_map.get(b.id, {})
                        cls = info.get("classification", "unclassified")
                        rel = info.get("relevance", "low")
                        result.append(ClassifiedBusiness(**b.model_dump(), classification=cls, relevance=rel))
                    return result
                except (KeyError, TypeError, ValueError) as e:
                    logger.warning("Error parseando clasificación LLM: %s", e)

        return self._fallback_classify_businesses(user_business, businesses, user_filters)

    def _fallback_classify_businesses(
        self,
        user_business: BusinessInterpretation,
        businesses: list[Business],
        user_filters: dict | None = None,
    ) -> list[ClassifiedBusiness]:
        """Fallback: clasificación por reglas de texto y SCIAN."""
        user_code = user_business.scian_code
        user_desc = user_business.scian_description.lower()
        user_input = user_business.original_input.lower()

        complementary_codes = {c.code for c in user_business.complementary_categories}
        competitor_codes = {c.code for c in user_business.competitor_categories}
        complementary_descs = {c.description.lower() for c in user_business.complementary_categories}
        competitor_descs = {c.description.lower() for c in user_business.competitor_categories}

        rules = AFFINITY_RULES.get(user_code, {})
        complementary_codes.update(rules.get("complementary", []))
        competitor_codes.update(rules.get("competitor", []))

        # User filter sets
        uf_comp_words: set[str] = set()
        uf_ally_words: set[str] = set()
        if user_filters:
            for f in user_filters.get("competitor_filters", []):
                for w in str(f).lower().split():
                    if len(w) > 2:
                        uf_comp_words.add(w)
            for f in user_filters.get("ally_filters", []):
                for w in str(f).lower().split():
                    if len(w) > 2:
                        uf_ally_words.add(w)

        # Google category sets (highest priority)
        google_comp_cats: set[str] = set()
        google_ally_cats: set[str] = set()
        if user_filters:
            for cat in user_filters.get("google_competitor_categories", []):
                google_comp_cats.add(str(cat).lower())
            for cat in user_filters.get("google_ally_categories", []):
                google_ally_cats.add(str(cat).lower())

        # Semantic keyword sets (search in name + category + reviews + editorial)
        kw_comp_list: list[str] = []
        kw_ally_list: list[str] = []
        if user_filters:
            kw_comp_list = [str(k).lower() for k in user_filters.get("keyword_competitor", []) if k]
            kw_ally_list = [str(k).lower() for k in user_filters.get("keyword_ally", []) if k]

        # Keywords from user's business for competitor detection
        user_keywords = set()
        for w in (user_desc + " " + user_input).split():
            if len(w) > 3:
                user_keywords.add(w)

        result = []
        for b in businesses:
            biz_code = b.denue_scian_code or ""
            biz_text = (b.name + " " + b.category).lower()
            # Build extended text including reviews and editorial for keyword search
            biz_extended = biz_text
            if b.google_reviews:
                biz_extended += " " + " ".join(r.text.lower() for r in b.google_reviews)
            if b.google_editorial_summary:
                biz_extended += " " + b.google_editorial_summary.lower()
            biz_words = {w for w in biz_text.split() if len(w) > 2}
            classification = "complementary"
            relevance = "low"

            # Collect business google_types as lowercase set
            biz_google_types: set[str] = set()
            if b.google_types:
                biz_google_types = {t.lower() for t in b.google_types}

            # 0. Google categories (HIGHEST priority)
            if google_comp_cats and (google_comp_cats & biz_google_types):
                classification = "competitor"
                relevance = "high"
            elif google_ally_cats and (google_ally_cats & biz_google_types):
                classification = "complementary"
                relevance = "high"
            # 0.5. Semantic keywords (search in extended text: name + category + reviews + editorial)
            elif kw_comp_list and any(kw in biz_extended for kw in kw_comp_list):
                classification = "competitor"
                relevance = "high"
            elif kw_ally_list and any(kw in biz_extended for kw in kw_ally_list):
                classification = "complementary"
                relevance = "high"
            # 1. User text filters (high priority)
            elif uf_comp_words and (uf_comp_words & biz_words):
                classification = "competitor"
                relevance = "high"
            elif uf_ally_words and (uf_ally_words & biz_words):
                classification = "complementary"
                relevance = "high"
            # 2. SCIAN code matching
            elif biz_code and biz_code in competitor_codes:
                classification = "competitor"
                relevance = "high" if biz_code == user_code else "medium"
            elif biz_code and biz_code in complementary_codes:
                classification = "complementary"
                relevance = "medium"
            elif biz_code and user_code and biz_code[:4] == user_code[:4]:
                classification = "competitor"
                relevance = "low"
            # 3. Text matching against competitor/complementary descriptions
            elif any(d in biz_text for d in competitor_descs if len(d) > 3):
                classification = "competitor"
                relevance = "medium"
            elif any(d in biz_text for d in complementary_descs if len(d) > 3):
                classification = "complementary"
                relevance = "medium"
            # 4. Keyword overlap with user's business = likely competitor
            elif user_keywords & biz_words:
                classification = "competitor"
                relevance = "medium" if len(user_keywords & biz_words) > 1 else "low"
            # 5. Default: complementary with low relevance (better than unclassified)
            else:
                classification = "complementary"
                relevance = "low"

            result.append(ClassifiedBusiness(**b.model_dump(), classification=classification, relevance=relevance))
        return result

    # ----------------------------------------------------------------
    # generate_recommendation
    # ----------------------------------------------------------------

    async def generate_recommendation(
        self,
        analysis_data: AnalysisResult,
        user_filters: dict | None = None,
    ) -> str:
        """Genera una recomendación en lenguaje natural usando LLM o fallback.

        Args:
            analysis_data: Resultado completo del análisis.
            user_filters: Filtros opcionales del usuario con claves
                ``ally_filters`` y ``competitor_filters``.

        Returns:
            Texto de recomendación en español (100-300 palabras).
        """
        viability = analysis_data.viability
        num_competitors = sum(
            1 for b in analysis_data.businesses if b.classification == "competitor"
        )
        num_complementary = sum(
            1 for b in analysis_data.businesses if b.classification == "complementary"
        )

        category_instructions = ""
        if viability.category == "Recomendable":
            category_instructions = (
                "La categoría es 'Recomendable'. Enfatiza los principales factores positivos "
                "de la zona que favorecen la apertura del negocio. Sé optimista pero realista."
            )
        elif viability.category == "No recomendable":
            category_instructions = (
                "La categoría es 'No recomendable'. Explica los principales factores de riesgo "
                "identificados y sugiere al emprendedor considerar zonas alternativas. "
                "Sé honesto pero empático."
            )
        else:  # Viable con enfoque estratégico
            category_instructions = (
                "La categoría es 'Viable con enfoque estratégico'. Presenta tanto los factores positivos "
                "como los riesgos identificados. Sugiere precauciones que el emprendedor "
                "debería tomar antes de decidir."
            )

        ageb = analysis_data.ageb_data
        prompt = (
            f"Genera una recomendación en español para un emprendedor que quiere abrir "
            f"un negocio de tipo '{analysis_data.business_type.scian_description}' "
            f"en la zona '{analysis_data.zone.name}' de la Ciudad de México.\n\n"
            f"Datos del análisis:\n"
            f"- Puntaje de viabilidad: {viability.score:.1f}/100\n"
            f"- Categoría: {viability.category}\n"
            f"- Negocios competidores encontrados: {num_competitors}\n"
            f"- Negocios complementarios encontrados: {num_complementary}\n\n"
            f"Datos demográficos de la zona (INEGI AGEB):\n"
            f"- Población total: {ageb.total_population:,}\n"
            f"- Densidad de población: {ageb.population_density:.1f} hab/km²\n"
            f"- PEA: {ageb.economically_active_population:,}\n"
            f"- Nivel socioeconómico: {ageb.socioeconomic_level}\n"
            f"- Escolaridad promedio: {ageb.avg_schooling_years:.1f} años\n"
        )
        if ageb.pct_with_internet:
            prompt += f"- Viviendas con internet: {ageb.pct_with_internet:.1f}%\n"
        if ageb.pct_with_car:
            prompt += f"- Viviendas con automóvil: {ageb.pct_with_car:.1f}%\n"
        prompt += f"\n{category_instructions}\n\n"

        # Inject user filter context when filters are provided
        if user_filters:
            ally = user_filters.get("ally_filters", [])
            comp = user_filters.get("competitor_filters", [])
            if ally or comp:
                prompt += "El usuario ha indicado las siguientes preferencias:\n"
                if ally:
                    prompt += f"- Considera como aliados: {', '.join(ally)}\n"
                if comp:
                    prompt += f"- Considera como competidores: {', '.join(comp)}\n"
                prompt += "Incluye esta información en tu análisis.\n\n"

        if analysis_data.multi_radius_results:
            prompt += "\nAnálisis multi-radio:\n"
            for mr in analysis_data.multi_radius_results:
                env = mr.environment_variables
                prompt += (
                    f"- A {mr.radius_km:.0f} km: {mr.competitors} competidores, "
                    f"{mr.complementary} complementarios, "
                    f"densidad POI: {env.get('poi_density', 0):.2f} negocios/km², "
                    f"actividad comercial: {env.get('commercial_activity_index', 0):.1f}%\n"
                )
            prompt += "Menciona cómo varían las condiciones a diferentes distancias si hay diferencias significativas.\n"

        # Foot traffic data
        if analysis_data.zone_traffic_profile:
            ztp = analysis_data.zone_traffic_profile
            if isinstance(ztp, dict):
                prompt += "\nDATOS DE TRÁFICO PEATONAL DE LA ZONA:\n"
                prompt += f"- Día más concurrido: {ztp.get('busiest_day', 'N/D')}\n"
                prompt += f"- Día más tranquilo: {ztp.get('quietest_day', 'N/D')}\n"
                prompt += f"- Tiempo promedio de permanencia: {ztp.get('avg_dwell_time_minutes', 0):.0f} minutos\n"
                prompt += f"- Datos basados en {ztp.get('venues_with_data', 0)} de {ztp.get('venues_total', 0)} competidores\n"
                # Peak hours summary
                peak_by_day = ztp.get('peak_hours_by_day', {})
                if peak_by_day:
                    prompt += "- Horas pico por día: "
                    parts = []
                    for day, hours in peak_by_day.items():
                        if hours:
                            parts.append(f"{day}: {', '.join(str(h) + ':00' for h in hours[:2])}")
                    prompt += "; ".join(parts[:3]) + "\n"
                prompt += "Incluye recomendaciones sobre horarios óptimos de apertura, cierre y turnos de mayor personal basándote en estos datos de afluencia.\n"

        prompt += (
            "El texto debe:\n"
            "- Estar en español\n"
            "- Tener entre 150 y 400 palabras\n"
            "- Incluir un resumen de la zona analizada con datos demográficos clave\n"
            "- Mencionar la cantidad de competidores y complementarios\n"
            "- Incluir factores demográficos relevantes como escolaridad, PEA, acceso a internet\n"
            "- Terminar con una conclusión clara sobre la viabilidad\n"
            "- Usar un tono accesible, sin jerga técnica\n"
            "- No usar formato markdown ni viñetas, solo texto corrido en párrafos\n"
        )

        messages = [
            {"role": "system", "content": "Eres un consultor de negocios experto en el mercado mexicano. Generas recomendaciones claras y útiles para emprendedores. Siempre respondes en español."},
            {"role": "user", "content": prompt},
        ]

        response_text = await self._call_groq(messages, temperature=0.5)
        if response_text and len(response_text.split()) >= 50:
            return response_text.strip()

        # Fallback: plantilla predefinida con datos interpolados
        return self._fallback_generate_recommendation(analysis_data)

    def _fallback_generate_recommendation(self, analysis_data: AnalysisResult) -> str:
        """Fallback: genera recomendación con plantillas predefinidas.

        Produce texto en español de al menos 100 palabras con datos interpolados.

        Args:
            analysis_data: Resultado completo del análisis.

        Returns:
            Texto de recomendación basado en plantilla.
        """
        viability = analysis_data.viability
        zone_name = analysis_data.zone.name
        business_desc = analysis_data.business_type.scian_description
        num_competitors = sum(
            1 for b in analysis_data.businesses if b.classification == "competitor"
        )
        num_complementary = sum(
            1 for b in analysis_data.businesses if b.classification == "complementary"
        )
        population = analysis_data.ageb_data.total_population
        pea = analysis_data.ageb_data.economically_active_population
        density = analysis_data.ageb_data.population_density
        socioeconomic = analysis_data.ageb_data.socioeconomic_level
        score = viability.score

        # Sección de resumen de zona (común a todas las categorías)
        zone_summary = (
            f"Tras analizar la zona de {zone_name} en la Ciudad de México para la apertura "
            f"de un negocio de {business_desc}, se obtuvieron los siguientes resultados. "
            f"La zona cuenta con una población total de {population:,} habitantes, "
            f"una densidad de población de {density:.1f} habitantes por hectárea "
            f"y una población económicamente activa de {pea:,} personas. "
            f"El nivel socioeconómico predominante en la zona es {socioeconomic}."
        )

        # Sección de ecosistema comercial
        ecosystem = (
            f"En cuanto al ecosistema comercial, se identificaron {num_competitors} "
            f"negocios competidores directos y {num_complementary} negocios complementarios "
            f"que podrían generar sinergia con su emprendimiento."
        )

        # Sección específica por categoría
        if viability.category == "Recomendable":
            category_text = (
                f"Con un puntaje de viabilidad de {score:.1f} sobre 100, la zona se clasifica "
                f"como Recomendable para abrir su negocio. Los factores positivos incluyen "
                f"una buena proporción de negocios complementarios que pueden atraer clientes "
                f"a la zona, así como indicadores demográficos favorables. La presencia de "
                f"población económicamente activa sugiere un mercado con capacidad de consumo "
                f"adecuada para este tipo de negocio. Se recomienda proceder con la planificación "
                f"de apertura, considerando las condiciones favorables identificadas en el análisis."
            )
        elif viability.category == "No recomendable":
            category_text = (
                f"Con un puntaje de viabilidad de {score:.1f} sobre 100, la zona se clasifica "
                f"como No recomendable para abrir su negocio en este momento. Los principales "
                f"factores de riesgo incluyen una alta concentración de competidores directos "
                f"que podrían dificultar la captación de clientes, así como condiciones "
                f"demográficas que no favorecen completamente este tipo de actividad comercial. "
                f"Se sugiere considerar zonas alternativas donde la competencia sea menor "
                f"y las condiciones demográficas sean más favorables para su emprendimiento. "
                f"Evaluar otras ubicaciones podría mejorar significativamente sus posibilidades de éxito."
            )
        else:  # Viable con enfoque estratégico
            category_text = (
                f"Con un puntaje de viabilidad de {score:.1f} sobre 100, la zona se clasifica "
                f"como Viable con enfoque estratégico. Existen factores positivos como la presencia de "
                f"negocios complementarios y ciertos indicadores demográficos favorables. "
                f"Sin embargo, también se identificaron riesgos que deben considerarse, "
                f"como la cantidad de competidores en la zona y algunas limitaciones en "
                f"los indicadores socioeconómicos. Se recomienda realizar un análisis más "
                f"detallado antes de tomar una decisión final, prestando especial atención "
                f"a la diferenciación de su oferta comercial frente a los competidores existentes."
            )

        return f"{zone_summary} {ecosystem} {category_text}"

    # ----------------------------------------------------------------
    # generate_strategic_recommendations
    # ----------------------------------------------------------------

    async def generate_strategic_recommendations(
        self,
        analysis_data: AnalysisResult,
        user_filters: dict | None = None,
    ) -> list[str]:
        """Generate 3-7 actionable strategic recommendations based on competitor data.

        Uses the big Groq model for quality. Falls back to rule-based generation
        if the LLM is unavailable.

        Args:
            analysis_data: Complete analysis result with classified businesses.
            user_filters: Optional user filters with google categories.

        Returns:
            List of 3-7 recommendation strings.
        """
        competitors = [b for b in analysis_data.businesses if b.classification == "competitor"]
        complementary = [b for b in analysis_data.businesses if b.classification == "complementary"]
        ageb = analysis_data.ageb_data

        # Build competitor data summary
        comp_summary_parts = []
        for c in competitors[:15]:
            parts = [f"- {c.name} ({c.category})"]
            if c.google_rating is not None:
                parts.append(f"rating={c.google_rating}")
            if c.google_reviews_count is not None:
                parts.append(f"reseñas={c.google_reviews_count}")
            if c.google_price_level is not None:
                parts.append(f"precio={c.google_price_level}")
            if c.google_hours:
                parts.append(f"horario={'; '.join(c.google_hours[:3])}")
            if c.google_reviews:
                snippets = [f'"{r.text[:80]}" ({r.rating}★)' for r in c.google_reviews[:2]]
                parts.append(f"reseñas_texto=[{', '.join(snippets)}]")
            comp_summary_parts.append(", ".join(parts))

        comp_text = "\n".join(comp_summary_parts) if comp_summary_parts else "No se encontraron competidores directos."

        prompt = (
            f"Eres un consultor de negocios experto. Analiza los siguientes datos de competidores "
            f"para un emprendedor que quiere abrir un negocio de '{analysis_data.business_type.scian_description}' "
            f"en la zona '{analysis_data.zone.name}'.\n\n"
            f"COMPETIDORES ({len(competitors)}):\n{comp_text}\n\n"
            f"COMPLEMENTARIOS: {len(complementary)} negocios\n\n"
            f"DATOS DEMOGRÁFICOS:\n"
            f"- Población: {ageb.total_population:,}\n"
            f"- PEA: {ageb.economically_active_population:,}\n"
            f"- Nivel socioeconómico: {ageb.socioeconomic_level}\n"
            f"- Escolaridad promedio: {ageb.avg_schooling_years:.1f} años\n\n"
        )

        if user_filters:
            google_comp = user_filters.get("google_competitor_categories", [])
            google_ally = user_filters.get("google_ally_categories", [])
            if google_comp:
                prompt += f"Categorías Google competidoras: {', '.join(google_comp)}\n"
            if google_ally:
                prompt += f"Categorías Google aliadas: {', '.join(google_ally)}\n"

        ext = analysis_data.ageb_data.extended_indicators
        if ext:
            prompt += "\nINDICADORES SOCIOECONÓMICOS ADICIONALES:\n"
            if ext.get("unemployment_rate"):
                prompt += f"- Tasa de desempleo: {ext['unemployment_rate']:.1f}%\n"
            if ext.get("economic_participation_rate"):
                prompt += f"- Tasa de participación económica: {ext['economic_participation_rate']:.1f}%\n"
            if ext.get("dependency_index"):
                prompt += f"- Índice de dependencia: {ext['dependency_index']:.1f}%\n"
            if ext.get("pct_with_refrigerator"):
                prompt += f"- Viviendas con refrigerador: {ext['pct_with_refrigerator']:.1f}%\n"
            if ext.get("pct_with_washing_machine"):
                prompt += f"- Viviendas con lavadora: {ext['pct_with_washing_machine']:.1f}%\n"

        if analysis_data.multi_radius_results:
            prompt += "\nANÁLISIS MULTI-RADIO:\n"
            for mr in analysis_data.multi_radius_results:
                prompt += f"- A {mr.radius_km:.0f} km: {mr.competitors} competidores, {mr.complementary} complementarios\n"

        # Foot traffic data
        if analysis_data.zone_traffic_profile:
            ztp = analysis_data.zone_traffic_profile
            if isinstance(ztp, dict):
                prompt += "\nDATOS DE TRÁFICO PEATONAL DE LA ZONA:\n"
                prompt += f"- Día más concurrido: {ztp.get('busiest_day', 'N/D')}\n"
                prompt += f"- Día más tranquilo: {ztp.get('quietest_day', 'N/D')}\n"
                prompt += f"- Tiempo promedio de permanencia: {ztp.get('avg_dwell_time_minutes', 0):.0f} minutos\n"
                prompt += f"- Datos basados en {ztp.get('venues_with_data', 0)} de {ztp.get('venues_total', 0)} competidores\n"
                # Peak hours summary
                peak_by_day = ztp.get('peak_hours_by_day', {})
                if peak_by_day:
                    prompt += "- Horas pico por día: "
                    parts = []
                    for day, hours in peak_by_day.items():
                        if hours:
                            parts.append(f"{day}: {', '.join(str(h) + ':00' for h in hours[:2])}")
                    prompt += "; ".join(parts[:3]) + "\n"
                prompt += "Incluye recomendaciones sobre horarios óptimos de apertura, cierre y turnos de mayor personal basándote en estos datos de afluencia.\n"

        prompt += (
            "\nGenera entre 3 y 7 recomendaciones estratégicas ACCIONABLES. Cada recomendación debe:\n"
            "- Ser concreta y accionable (no genérica)\n"
            "- Incluir datos cuantitativos de respaldo cuando sea posible\n"
            "- Cubrir aspectos como: horarios diferenciados, posicionamiento de precio, "
            "diferenciación de servicio, brechas de mercado\n\n"
            'Responde ÚNICAMENTE con un JSON array de strings: ["recomendación 1", "recomendación 2", ...]\n'
            "No incluyas texto adicional fuera del JSON."
        )

        messages = [
            {"role": "system", "content": "Eres un consultor de negocios experto en el mercado mexicano. Generas recomendaciones estratégicas accionables. Responde siempre en español y en formato JSON."},
            {"role": "user", "content": prompt},
        ]

        response_text = await self._call_groq(messages, temperature=0.4, model=GROQ_MODEL)
        if response_text:
            try:
                cleaned = response_text.strip()
                if cleaned.startswith("```"):
                    lines = cleaned.split("\n")
                    lines = [line for line in lines if not line.strip().startswith("```")]
                    cleaned = "\n".join(lines)
                parsed = json.loads(cleaned)
                if isinstance(parsed, list):
                    recs = [str(r).strip() for r in parsed if str(r).strip()]
                    if 3 <= len(recs) <= 7:
                        return recs
                    # If outside range, trim or pad
                    if len(recs) > 7:
                        return recs[:7]
                    # If less than 3, fall through to fallback
            except (json.JSONDecodeError, TypeError, ValueError):
                logger.warning("Could not parse strategic recommendations from LLM")

        return self._fallback_strategic_recommendations(analysis_data)

    def _fallback_strategic_recommendations(
        self,
        analysis_data: AnalysisResult,
    ) -> list[str]:
        """Fallback: generate strategic recommendations using predefined rules.

        Analyzes competitor hours, ratings, price levels, and demographics
        to produce 3-7 non-empty recommendation strings.

        Args:
            analysis_data: Complete analysis result.

        Returns:
            List of 3-7 recommendation strings.
        """
        competitors = [b for b in analysis_data.businesses if b.classification == "competitor"]
        ageb = analysis_data.ageb_data
        recs: list[str] = []

        if not competitors:
            # Pioneer opportunity recommendations
            recs.append(
                "Oportunidad de mercado pionero: no se identificaron competidores directos en la zona. "
                "Esto representa una ventaja de primer movimiento para captar la demanda existente."
            )
            if ageb.total_population > 0:
                recs.append(
                    f"La zona cuenta con {ageb.total_population:,} habitantes y "
                    f"{ageb.economically_active_population:,} personas económicamente activas. "
                    f"Considere estrategias de marketing local para captar este mercado sin competencia directa."
                )
            recs.append(
                "Al ser pionero, establezca precios competitivos iniciales para generar lealtad "
                "de clientes antes de que lleguen competidores a la zona."
            )
            recs.append(
                "Invierta en visibilidad local (señalización, redes sociales geolocalizadas) "
                "para posicionarse como la referencia del sector en la zona."
            )
            return recs[:7]

        # 1. Analyze hours gaps
        days_coverage: dict[str, int] = {}
        for c in competitors:
            if c.google_hours:
                for h in c.google_hours:
                    day = h.split(":")[0].strip().lower() if ":" in h else h.strip().lower()
                    days_coverage[day] = days_coverage.get(day, 0) + 1

        if days_coverage:
            min_day = min(days_coverage, key=days_coverage.get)  # type: ignore[arg-type]
            min_count = days_coverage[min_day]
            total = len(competitors)
            recs.append(
                f"Horario diferenciado: solo {min_count} de {total} competidores operan los {min_day}. "
                f"Considere abrir en ese horario para captar demanda desatendida."
            )

        # 2. Analyze ratings
        ratings = [c.google_rating for c in competitors if c.google_rating is not None]
        if ratings:
            avg_rating = sum(ratings) / len(ratings)
            if avg_rating < 3.5:
                recs.append(
                    f"Diferenciación por calidad: el rating promedio de competidores es {avg_rating:.1f}/5. "
                    f"Enfóquese en calidad de servicio para superar esta media y atraer clientes insatisfechos."
                )
            elif avg_rating >= 4.0:
                recs.append(
                    f"Mercado exigente: el rating promedio de competidores es {avg_rating:.1f}/5. "
                    f"Asegure estándares de calidad altos desde el inicio para competir efectivamente."
                )
            else:
                recs.append(
                    f"El rating promedio de competidores es {avg_rating:.1f}/5. "
                    f"Apunte a superar esta media con un servicio diferenciado para destacar en la zona."
                )

        # 3. Analyze price levels
        price_levels = [c.google_price_level for c in competitors if c.google_price_level is not None]
        if price_levels:
            avg_price = sum(price_levels) / len(price_levels)
            price_labels = {0: "Gratis", 1: "Económico", 2: "Moderado", 3: "Caro", 4: "Muy caro"}
            # Find underserved price range
            price_counts = {i: 0 for i in range(5)}
            for p in price_levels:
                price_counts[p] = price_counts.get(p, 0) + 1
            min_price = min(price_counts, key=price_counts.get)  # type: ignore[arg-type]
            recs.append(
                f"Posicionamiento de precio: la mayoría de competidores tiene nivel de precio promedio "
                f"{avg_price:.1f} ({price_labels.get(round(avg_price), 'Moderado')}). "
                f"El rango '{price_labels.get(min_price, 'Moderado')}' está menos cubierto — considere posicionarse ahí."
            )

        # 4. Volume-based recommendation
        if len(competitors) <= 3:
            recs.append(
                f"Baja competencia: solo {len(competitors)} competidores directos en la zona. "
                f"Esto indica una oportunidad de mercado con demanda potencialmente insatisfecha."
            )
        elif len(competitors) >= 10:
            recs.append(
                f"Alta competencia: {len(competitors)} competidores directos en la zona. "
                f"Es fundamental diferenciarse claramente en servicio, precio o especialización."
            )

        # 5. Reviews-based recommendation
        review_ratings = []
        for c in competitors:
            if c.google_reviews:
                for r in c.google_reviews:
                    review_ratings.append(r.rating)
        if review_ratings:
            low_reviews = sum(1 for r in review_ratings if r <= 2)
            if low_reviews > 0:
                recs.append(
                    f"Se encontraron {low_reviews} reseñas negativas (≤2 estrellas) entre competidores. "
                    f"Identifique las quejas comunes y asegúrese de no repetir esos errores."
                )

        # 6. Demographic recommendation
        if ageb.total_population > 0:
            if ageb.avg_schooling_years >= 12:
                recs.append(
                    f"La escolaridad promedio de la zona es {ageb.avg_schooling_years:.1f} años (nivel medio-superior). "
                    f"Considere una oferta que apele a un público con mayor nivel educativo."
                )
            elif ageb.avg_schooling_years > 0:
                recs.append(
                    f"La escolaridad promedio de la zona es {ageb.avg_schooling_years:.1f} años. "
                    f"Adapte su comunicación y oferta al perfil educativo de la población local."
                )

        # 7. Generic differentiation (always include if needed)
        if len(recs) < 3:
            recs.append(
                "Desarrolle una propuesta de valor única que lo diferencie claramente de los competidores "
                "existentes. Considere especialización, horarios extendidos o servicios adicionales."
            )

        # Ensure 3-7 range
        if len(recs) < 3:
            recs.append(
                "Establezca presencia digital (Google Maps, redes sociales) desde antes de la apertura "
                "para generar expectativa y captar clientes potenciales."
            )
        if len(recs) < 3:
            recs.append(
                "Considere alianzas con negocios complementarios de la zona para generar tráfico cruzado "
                "y fortalecer su posición en el mercado local."
            )

        return recs[:7]

    def build_recommendation_prompt(
        self,
        analysis_data: AnalysisResult,
        user_filters: dict | None = None,
    ) -> str:
        """Construye el prompt de recomendación para testing.

        Expone la lógica de construcción del prompt para validación
        en tests de propiedades.

        Args:
            analysis_data: Resultado completo del análisis.
            user_filters: Filtros opcionales del usuario.

        Returns:
            Texto del prompt construido.
        """
        viability = analysis_data.viability
        num_competitors = sum(
            1 for b in analysis_data.businesses if b.classification == "competitor"
        )
        num_complementary = sum(
            1 for b in analysis_data.businesses if b.classification == "complementary"
        )

        category_instructions = ""
        if viability.category == "Recomendable":
            category_instructions = (
                "La categoría es 'Recomendable'. Enfatiza los principales factores positivos "
                "de la zona que favorecen la apertura del negocio."
            )
        elif viability.category == "No recomendable":
            category_instructions = (
                "La categoría es 'No recomendable'. Explica los principales factores de riesgo "
                "identificados y sugiere al emprendedor considerar zonas alternativas."
            )
        else:
            category_instructions = (
                "La categoría es 'Viable con enfoque estratégico'. Presenta tanto los factores positivos "
                "como los riesgos identificados."
            )

        prompt = (
            f"Genera una recomendación en español para un emprendedor que quiere abrir "
            f"un negocio de tipo '{analysis_data.business_type.scian_description}' "
            f"en la zona '{analysis_data.zone.name}' de la Ciudad de México.\n\n"
            f"Datos del análisis:\n"
            f"- Puntaje de viabilidad: {viability.score:.1f}/100\n"
            f"- Categoría: {viability.category}\n"
            f"- Negocios competidores encontrados: {num_competitors}\n"
            f"- Negocios complementarios encontrados: {num_complementary}\n"
            f"- Población de la zona: {analysis_data.ageb_data.total_population:,}\n"
            f"- Densidad de población: {analysis_data.ageb_data.population_density:.1f}\n"
            f"- Población económicamente activa: {analysis_data.ageb_data.economically_active_population:,}\n"
            f"- Nivel socioeconómico: {analysis_data.ageb_data.socioeconomic_level}\n\n"
            f"{category_instructions}\n\n"
        )

        # Inject user filter context when filters are provided
        if user_filters:
            ally = user_filters.get("ally_filters", [])
            comp = user_filters.get("competitor_filters", [])
            if ally or comp:
                prompt += "El usuario ha indicado las siguientes preferencias:\n"
                if ally:
                    prompt += f"- Considera como aliados: {', '.join(ally)}\n"
                if comp:
                    prompt += f"- Considera como competidores: {', '.join(comp)}\n"
                prompt += "Incluye esta información en tu análisis.\n\n"

        prompt += (
            "El texto debe:\n"
            "- Estar en español\n"
            "- Tener entre 100 y 300 palabras\n"
            "- Incluir un resumen de la zona analizada\n"
            "- Mencionar la cantidad de competidores y complementarios\n"
            "- Incluir factores demográficos relevantes\n"
            "- Terminar con una conclusión clara sobre la viabilidad\n"
        )
        return prompt

    # ----------------------------------------------------------------
    # parse_target_profile
    # ----------------------------------------------------------------

    async def parse_target_profile(self, profile_text: str) -> TargetCriteria:
        """Parse free-text target profile into demographic criteria using fast model (8b)."""
        prompt = (
            "Eres un experto en demografía mexicana. El usuario describe su cliente ideal así:\n"
            f'"{profile_text}"\n\n'
            "Extrae los criterios demográficos y responde ÚNICAMENTE con JSON:\n"
            '{"gender": "male|female|all", "age_min": int, "age_max": int, '
            '"socioeconomic_level": "Alto|Medio-Alto|Medio|Bajo|all", '
            '"min_schooling_years": float_or_null}\n'
            "Reglas:\n"
            "- gender: male si menciona hombres, female si mujeres, all si no especifica\n"
            "- age_min/age_max: rango de edad mencionado (0-99)\n"
            "- socioeconomic_level: Alto (ejecutivos, alto poder adquisitivo), Medio-Alto (profesionistas), Medio (clase media), Bajo (popular), all si no especifica\n"
            "- min_schooling_years: años de escolaridad mínima si se menciona, null si no\n"
        )
        messages = [
            {"role": "system", "content": "Extrae criterios demográficos de texto libre. Responde SOLO JSON."},
            {"role": "user", "content": prompt},
        ]
        response = await self._call_groq(messages, temperature=0, model=GROQ_MODEL_FAST)
        if response:
            parsed = self._parse_json_response(response)
            if parsed:
                try:
                    return TargetCriteria(
                        gender=parsed.get("gender", "all"),
                        age_min=int(parsed.get("age_min", 0)),
                        age_max=int(parsed.get("age_max", 99)),
                        socioeconomic_level=parsed.get("socioeconomic_level", "all"),
                        min_schooling_years=parsed.get("min_schooling_years"),
                    )
                except (ValueError, TypeError):
                    pass
        # Fallback
        return TargetCriteria()

    # ----------------------------------------------------------------
    # format_target_profile
    # ----------------------------------------------------------------

    @staticmethod
    def format_target_profile(criteria: TargetCriteria) -> str:
        """Convert TargetCriteria to human-readable Spanish text. Pure function."""
        parts = []
        if criteria.gender == "female":
            parts.append("Mujeres")
        elif criteria.gender == "male":
            parts.append("Hombres")
        else:
            parts.append("Población general")

        if not (criteria.age_min == 0 and criteria.age_max == 99):
            parts.append(f"de {criteria.age_min} a {criteria.age_max} años")

        if criteria.socioeconomic_level != "all":
            parts.append(f"nivel socioeconómico {criteria.socioeconomic_level}")

        if criteria.min_schooling_years is not None:
            parts.append(f"con al menos {criteria.min_schooling_years:.0f} años de escolaridad")

        return ", ".join(parts)

    # ----------------------------------------------------------------
    # analyze_competitor_reviews
    # ----------------------------------------------------------------

    async def analyze_competitor_reviews(
        self,
        competitors: list[ClassifiedBusiness],
        target_profile: str | None = None,
        target_criteria: TargetCriteria | None = None,
    ) -> CompetitorReviewAnalysis:
        """Analyze competitor reviews for value points and opportunities. Uses big model (70b)."""
        # Collect all reviews
        positive_reviews = []
        negative_reviews = []
        for c in competitors:
            if not c.google_reviews:
                continue
            for rev in c.google_reviews:
                if rev.rating >= 4:
                    positive_reviews.append(f"{c.name}: \"{rev.text[:100]}\" ({rev.rating}★)")
                elif rev.rating <= 2:
                    negative_reviews.append(f"{c.name}: \"{rev.text[:100]}\" ({rev.rating}★)")

        total_reviews = len(positive_reviews) + len(negative_reviews)
        if total_reviews < 3:
            return CompetitorReviewAnalysis(insufficient_data=True)

        prompt = (
            "Analiza las reseñas de competidores para un negocio de tipo similar.\n\n"
            "RESEÑAS POSITIVAS (4-5★):\n" + "\n".join(positive_reviews[:15]) + "\n\n"
            "RESEÑAS NEGATIVAS (1-2★):\n" + "\n".join(negative_reviews[:10]) + "\n\n"
        )

        if target_profile and target_criteria:
            profile_desc = LLMService.format_target_profile(target_criteria)
            prompt += f"PERFIL DEL CLIENTE OBJETIVO: {target_profile} ({profile_desc})\n\n"

        prompt += (
            'Responde ÚNICAMENTE con JSON:\n'
            '{\n'
            '  "value_points": [{"title": "...", "description": "...", "source_type": "positive|negative"}],\n'
            '  "improvement_opportunities": [{"issue": "...", "recommendation": "..."}],\n'
            '  "target_customer_insights": [{"title": "...", "explanation": "..."}]\n'
            '}\n'
            "Reglas:\n"
            "- value_points: 3-5 puntos de valor que los clientes valoran (de reseñas positivas)\n"
            "- improvement_opportunities: 3-5 oportunidades de mejora con recomendación accionable (de reseñas negativas)\n"
        )
        if target_profile:
            prompt += "- target_customer_insights: 3-5 insights de lo que el cliente objetivo valora, cruzando reseñas con el perfil\n"
        else:
            prompt += "- target_customer_insights: dejar como lista vacía []\n"

        messages = [
            {"role": "system", "content": "Eres un consultor de negocios experto. Analiza reseñas de competidores. Responde SOLO JSON en español."},
            {"role": "user", "content": prompt},
        ]

        response = await self._call_groq(messages, temperature=0.3, model=GROQ_MODEL)
        if response:
            parsed = self._parse_json_response(response)
            if parsed:
                try:
                    vps = [ValuePoint(**vp) for vp in parsed.get("value_points", [])]
                    ios = [ImprovementOpportunity(**io) for io in parsed.get("improvement_opportunities", [])]
                    tcis = [TargetCustomerInsight(**tci) for tci in parsed.get("target_customer_insights", [])]
                    return CompetitorReviewAnalysis(
                        value_points=vps[:5],
                        improvement_opportunities=ios[:5],
                        target_customer_insights=tcis[:5],
                    )
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning("Error parsing competitor review analysis: %s", e)

        return CompetitorReviewAnalysis(insufficient_data=True)
