"""Servicio LLM para comunicación con Groq API.

Encapsula la interpretación de tipo de negocio, clasificación de negocios
y generación de recomendaciones. Incluye fallbacks locales cuando la API
no está disponible.
"""

from __future__ import annotations

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
    SCIANCategory,
    ViabilityResult,
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
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_TIMEOUT = 10.0
GROQ_MAX_RETRIES = 1


class LLMService:
    """Servicio de comunicación con Groq API para análisis de negocios."""

    def __init__(self) -> None:
        self.api_key = os.getenv("GROQ_API_KEY", "")

    async def _call_groq(self, messages: list[dict[str, str]], temperature: float = 0.3) -> str | None:
        """Realiza una llamada a la API de Groq con reintentos.

        Args:
            messages: Lista de mensajes para el chat completion.
            temperature: Temperatura de generación.

        Returns:
            Texto de respuesta o None si falla.
        """
        if not self.api_key:
            logger.warning("GROQ_API_KEY no configurada")
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": GROQ_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 2048,
        }

        for attempt in range(GROQ_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=GROQ_TIMEOUT) as client:
                    response = await client.post(
                        GROQ_API_URL,
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    data = response.json()
                    return data["choices"][0]["message"]["content"]
            except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError, KeyError, IndexError) as e:
                logger.warning("Groq API intento %d falló: %s", attempt + 1, e)
                if attempt >= GROQ_MAX_RETRIES:
                    return None
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
            lines = [l for l in lines if not l.strip().startswith("```")]
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

        response_text = await self._call_groq(messages)
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
        """Clasifica negocios como complementarios o competidores usando LLM o fallback.

        Args:
            user_business: Interpretación del negocio del usuario.
            businesses: Lista de negocios a clasificar.
            user_filters: Filtros opcionales del usuario con claves
                ``ally_filters`` y ``competitor_filters``.

        Returns:
            Lista de ClassifiedBusiness con clasificación y relevancia.
        """
        if not businesses:
            return []

        # Build business list for prompt (limit to avoid token overflow)
        biz_list = []
        for b in businesses:
            biz_list.append({
                "id": b.id,
                "name": b.name,
                "category": b.category,
                "scian_code": b.denue_scian_code or "",
            })

        prompt = (
            f"El usuario quiere abrir un negocio de tipo: {user_business.scian_description} "
            f"(código SCIAN: {user_business.scian_code}).\n\n"
            "A continuación hay una lista de negocios existentes en la zona. "
            "Para cada uno, clasifícalo como:\n"
            '- "complementary": genera sinergia con el negocio del usuario\n'
            '- "competitor": compite directamente con el negocio del usuario\n'
            '- "unclassified": no se puede determinar la relación\n\n'
            "Y asigna un nivel de relevancia:\n"
            '- "high": relación muy directa\n'
            '- "medium": relación moderada\n'
            '- "low": relación indirecta\n\n'
            f"Negocios a clasificar:\n{json.dumps(biz_list, ensure_ascii=False)}\n\n"
        )

        # Inject user filter context when filters are provided
        if user_filters:
            ally = user_filters.get("ally_filters", [])
            comp = user_filters.get("competitor_filters", [])
            if ally or comp:
                prompt += "Además, el usuario ha indicado las siguientes preferencias:\n"
                if ally:
                    prompt += f"- Considera como ALIADOS (complementarios): {', '.join(ally)}\n"
                if comp:
                    prompt += f"- Considera como COMPETIDORES: {', '.join(comp)}\n"
                prompt += "Prioriza estas preferencias del usuario en tu clasificación.\n\n"

        prompt += (
            "Responde ÚNICAMENTE con un JSON válido con esta estructura:\n"
            "{\n"
            '  "classifications": [\n'
            '    {"id": "id_negocio", "classification": "complementary|competitor|unclassified", "relevance": "high|medium|low"},\n'
            "    ...\n"
            "  ]\n"
            "}\n"
            "No incluyas texto adicional fuera del JSON."
        )

        messages = [
            {"role": "system", "content": "Eres un experto en análisis de ecosistemas comerciales en México. Clasifica negocios según su relación con el negocio del usuario. Responde en JSON."},
            {"role": "user", "content": prompt},
        ]

        response_text = await self._call_groq(messages)
        if response_text:
            parsed = self._parse_json_response(response_text)
            if parsed and "classifications" in parsed:
                try:
                    classification_map: dict[str, dict[str, str]] = {}
                    for c in parsed["classifications"]:
                        classification_map[c["id"]] = {
                            "classification": c.get("classification", "unclassified"),
                            "relevance": c.get("relevance", "low"),
                        }

                    result = []
                    for b in businesses:
                        info = classification_map.get(b.id, {})
                        classification = info.get("classification", "unclassified")
                        relevance = info.get("relevance", "low")
                        # Validate values
                        if classification not in ("complementary", "competitor", "unclassified"):
                            classification = "unclassified"
                        if relevance not in ("high", "medium", "low"):
                            relevance = "low"
                        result.append(
                            ClassifiedBusiness(
                                **b.model_dump(),
                                classification=classification,
                                relevance=relevance,
                            )
                        )
                    return result
                except (KeyError, TypeError, ValueError) as e:
                    logger.warning("Error parseando clasificación LLM: %s", e)

        # Fallback: reglas estáticas basadas en códigos SCIAN
        return self._fallback_classify_businesses(user_business, businesses, user_filters)

    def _fallback_classify_businesses(
        self,
        user_business: BusinessInterpretation,
        businesses: list[Business],
        user_filters: dict | None = None,
    ) -> list[ClassifiedBusiness]:
        """Fallback: clasificación por reglas estáticas SCIAN.

        When *user_filters* are provided they take priority over the static
        ``AFFINITY_RULES``.  A business whose SCIAN code or category matches
        an ``ally_filters`` entry is classified as ``"complementary"``; one
        matching a ``competitor_filters`` entry is classified as
        ``"competitor"``.

        Args:
            user_business: Interpretación del negocio del usuario.
            businesses: Lista de negocios a clasificar.
            user_filters: Filtros opcionales del usuario.

        Returns:
            Lista de ClassifiedBusiness usando reglas estáticas.
        """
        user_code = user_business.scian_code
        complementary_codes = {c.code for c in user_business.complementary_categories}
        competitor_codes = {c.code for c in user_business.competitor_categories}

        # Also get from affinity rules
        rules = AFFINITY_RULES.get(user_code, {})
        complementary_codes.update(rules.get("complementary", []))
        competitor_codes.update(rules.get("competitor", []))

        # Build user-filter lookup sets (codes and lowered descriptions)
        uf_ally_codes: set[str] = set()
        uf_ally_descs: set[str] = set()
        uf_comp_codes: set[str] = set()
        uf_comp_descs: set[str] = set()
        if user_filters:
            for f in user_filters.get("ally_filters", []):
                f_str = str(f).strip()
                if f_str:
                    uf_ally_codes.add(f_str)
                    uf_ally_descs.add(f_str.lower())
            for f in user_filters.get("competitor_filters", []):
                f_str = str(f).strip()
                if f_str:
                    uf_comp_codes.add(f_str)
                    uf_comp_descs.add(f_str.lower())

        result = []
        for b in businesses:
            biz_code = b.denue_scian_code or ""
            biz_category_lower = b.category.lower()
            classification = "unclassified"
            relevance = "low"

            # --- User filters take priority ---
            matched_by_user_filter = False
            if uf_ally_codes or uf_comp_codes:
                # Check competitor filters first (user explicitly said competitor)
                if biz_code and biz_code in uf_comp_codes:
                    classification = "competitor"
                    relevance = "high"
                    matched_by_user_filter = True
                elif any(d in biz_category_lower for d in uf_comp_descs):
                    classification = "competitor"
                    relevance = "high"
                    matched_by_user_filter = True
                # Then ally filters
                elif biz_code and biz_code in uf_ally_codes:
                    classification = "complementary"
                    relevance = "high"
                    matched_by_user_filter = True
                elif any(d in biz_category_lower for d in uf_ally_descs):
                    classification = "complementary"
                    relevance = "high"
                    matched_by_user_filter = True

            # --- Standard AFFINITY_RULES logic (only if not matched by user filter) ---
            if not matched_by_user_filter:
                if biz_code:
                    if biz_code in competitor_codes:
                        classification = "competitor"
                        relevance = "high" if biz_code == user_code else "medium"
                    elif biz_code in complementary_codes:
                        classification = "complementary"
                        relevance = "medium"
                    elif biz_code[:4] == user_code[:4]:
                        # Same 4-digit group = likely competitor
                        classification = "competitor"
                        relevance = "low"
                    elif biz_code[:2] == user_code[:2]:
                        # Same 2-digit sector = possibly complementary
                        classification = "complementary"
                        relevance = "low"

                # Text-based fallback if no SCIAN code
                if classification == "unclassified" and not biz_code:
                    category_lower = b.category.lower()
                    user_desc_lower = user_business.scian_description.lower()
                    # Simple keyword overlap check
                    user_words = {w for w in user_desc_lower.split() if len(w) > 3}
                    cat_words = {w for w in category_lower.split() if len(w) > 3}
                    overlap = user_words & cat_words
                    if overlap:
                        classification = "competitor"
                        relevance = "medium" if len(overlap) > 1 else "low"

            result.append(
                ClassifiedBusiness(
                    **b.model_dump(),
                    classification=classification,
                    relevance=relevance,
                )
            )
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
        else:  # Viable con reservas
            category_instructions = (
                "La categoría es 'Viable con reservas'. Presenta tanto los factores positivos "
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
        else:  # Viable con reservas
            category_text = (
                f"Con un puntaje de viabilidad de {score:.1f} sobre 100, la zona se clasifica "
                f"como Viable con reservas. Existen factores positivos como la presencia de "
                f"negocios complementarios y ciertos indicadores demográficos favorables. "
                f"Sin embargo, también se identificaron riesgos que deben considerarse, "
                f"como la cantidad de competidores en la zona y algunas limitaciones en "
                f"los indicadores socioeconómicos. Se recomienda realizar un análisis más "
                f"detallado antes de tomar una decisión final, prestando especial atención "
                f"a la diferenciación de su oferta comercial frente a los competidores existentes."
            )

        return f"{zone_summary} {ecosystem} {category_text}"

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
                "La categoría es 'Viable con reservas'. Presenta tanto los factores positivos "
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
