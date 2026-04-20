"""Catálogo SCIAN local con reglas de afinidad comercial.

Contiene categorías comunes de negocios con sus códigos SCIAN,
descripciones y relaciones de complementariedad/competencia.
"""

from __future__ import annotations

from app.models.schemas import SCIANCategory

# Catálogo SCIAN: código -> descripción
SCIAN_CATALOG: dict[str, str] = {
    "461110": "Comercio al por menor de abarrotes y alimentos",
    "461121": "Comercio al por menor de carnes rojas",
    "461122": "Comercio al por menor de carne de aves",
    "461123": "Comercio al por menor de pescados y mariscos",
    "461130": "Comercio al por menor de frutas y verduras frescas",
    "461140": "Comercio al por menor de semillas y granos alimenticios",
    "461150": "Comercio al por menor de leche y otros productos lácteos",
    "461160": "Comercio al por menor de dulces y materias primas para repostería",
    "461170": "Comercio al por menor de paletas de hielo y helados",
    "461190": "Comercio al por menor de otros alimentos",
    "461211": "Comercio al por menor de bebidas no alcohólicas y hielo",
    "461212": "Comercio al por menor de bebidas alcohólicas",
    "461213": "Comercio al por menor de cigarros y tabaco",
    "462111": "Comercio al por menor en tiendas de autoservicio",
    "462112": "Comercio al por menor en tiendas departamentales",
    "463211": "Comercio al por menor de ropa de bebé",
    "463212": "Comercio al por menor de ropa para niños y niñas",
    "463213": "Comercio al por menor de ropa para damas",
    "463214": "Comercio al por menor de ropa para caballeros",
    "463215": "Comercio al por menor de ropa de cuero y piel",
    "463310": "Comercio al por menor de calzado",
    "464111": "Farmacias sin minisuper",
    "464112": "Farmacias con minisuper",
    "464211": "Comercio al por menor de lentes",
    "465111": "Comercio al por menor de computadoras y accesorios",
    "465112": "Comercio al por menor de teléfonos y accesorios",
    "465211": "Comercio al por menor de muebles para el hogar",
    "465212": "Comercio al por menor de electrodomésticos menores",
    "465311": "Comercio al por menor de artículos de papelería",
    "465312": "Comercio al por menor de libros",
    "465911": "Comercio al por menor de mascotas y accesorios",
    "466111": "Comercio al por menor de muebles para baño",
    "466112": "Comercio al por menor de pintura",
    "466113": "Comercio al por menor de vidrios y espejos",
    "466114": "Comercio al por menor de pisos y recubrimientos cerámicos",
    "467111": "Comercio al por menor de artículos de perfumería y cosméticos",
    "467115": "Comercio al por menor de artículos de joyería y relojes",
    "468211": "Comercio al por menor de partes y refacciones automotrices",
    "468213": "Comercio al por menor de llantas y cámaras",
    "468411": "Gasolineras",
    "468412": "Comercio al por menor de gas LP",
    "722511": "Restaurantes con servicio de preparación de alimentos a la carta",
    "722512": "Restaurantes con servicio de preparación de comida rápida",
    "722513": "Restaurantes con servicio de preparación de tacos y tortas",
    "722514": "Restaurantes con servicio de preparación de pizzas",
    "722515": "Cafeterías, fuentes de sodas, neverías y similares",
    "722516": "Restaurantes con servicio de preparación de antojitos",
    "722517": "Restaurantes con servicio de preparación de pescados y mariscos",
    "722518": "Restaurantes con servicio de comedor",
    "722519": "Otros restaurantes con servicio de preparación de alimentos",
    "713111": "Gimnasios y centros de acondicionamiento físico",
    "713112": "Clubes deportivos",
    "713120": "Centros de entretenimiento y diversión",
    "611111": "Escuelas de educación preescolar del sector privado",
    "611121": "Escuelas de educación primaria del sector privado",
    "611131": "Escuelas de educación secundaria del sector privado",
    "611171": "Escuelas de educación media superior del sector privado",
    "611211": "Escuelas de educación superior del sector privado",
    "611311": "Escuelas de computación del sector privado",
    "611312": "Escuelas de idiomas del sector privado",
    "621111": "Consultorios de medicina general del sector privado",
    "621112": "Consultorios de medicina especializada del sector privado",
    "621211": "Consultorios dentales del sector privado",
    "621311": "Consultorios de quiropráctica del sector privado",
    "621312": "Consultorios de optometría",
    "621320": "Consultorios de psicología del sector privado",
    "624111": "Guarderías del sector privado",
    "811111": "Reparación mecánica en general de automóviles y camiones",
    "811112": "Reparación del sistema eléctrico de automóviles y camiones",
    "811121": "Hojalatería y pintura de automóviles y camiones",
    "811192": "Lavado y lubricado de automóviles y camiones",
    "811211": "Reparación de aparatos electrónicos",
    "811219": "Reparación de otros aparatos eléctricos",
    "811410": "Reparación de tapicería de muebles",
    "812110": "Salones y clínicas de belleza y peluquerías",
    "812210": "Lavanderías y tintorerías",
    "812310": "Servicios funerarios",
    "541110": "Bufetes jurídicos",
    "541211": "Servicios de contabilidad y auditoría",
    "541310": "Servicios de arquitectura",
    "541410": "Servicios de diseño industrial",
    "541511": "Servicios de diseño de sistemas de cómputo",
    "541610": "Servicios de consultoría en administración",
    "541810": "Agencias de publicidad",
    "541921": "Servicios de fotografía",
    "561431": "Fotocopiado, fax y afines",
    "561432": "Servicios de acceso a computadoras",
    "711111": "Compañías de teatro",
    "711121": "Compañías de danza",
    "711312": "Promotores de espectáculos artísticos",
    "721111": "Hoteles con otros servicios integrados",
    "721112": "Hoteles sin otros servicios integrados",
    "721210": "Campamentos y albergues recreativos",
}


# Reglas de afinidad: código SCIAN -> (complementarios, competidores)
# Cada entrada mapea un código a listas de códigos relacionados
AFFINITY_RULES: dict[str, dict[str, list[str]]] = {
    # Abarrotes
    "461110": {
        "complementary": ["461121", "461130", "461150", "461160", "461211", "464112"],
        "competitor": ["462111", "462112"],
    },
    # Carnes rojas
    "461121": {
        "complementary": ["461110", "461130", "461150", "722511"],
        "competitor": ["461122", "461123", "462111"],
    },
    # Carne de aves
    "461122": {
        "complementary": ["461110", "461130", "461150", "722511"],
        "competitor": ["461121", "461123", "462111"],
    },
    # Pescados y mariscos
    "461123": {
        "complementary": ["461110", "461130", "722517"],
        "competitor": ["461121", "461122", "462111"],
    },
    # Frutas y verduras
    "461130": {
        "complementary": ["461110", "461121", "461150", "722511"],
        "competitor": ["462111", "462112"],
    },
    # Lácteos
    "461150": {
        "complementary": ["461110", "461130", "461160", "722515"],
        "competitor": ["462111", "462112"],
    },
    # Dulces y repostería
    "461160": {
        "complementary": ["461150", "461170", "722515", "465311"],
        "competitor": ["462111"],
    },
    # Helados
    "461170": {
        "complementary": ["461160", "722515", "713120"],
        "competitor": ["722515"],
    },
    # Bebidas no alcohólicas
    "461211": {
        "complementary": ["461110", "722512", "722513"],
        "competitor": ["462111"],
    },
    # Bebidas alcohólicas
    "461212": {
        "complementary": ["722511", "722519", "461110"],
        "competitor": ["462111", "462112"],
    },
    # Autoservicio
    "462111": {
        "complementary": ["468411", "464112", "812110"],
        "competitor": ["462112", "461110"],
    },
    # Tiendas departamentales
    "462112": {
        "complementary": ["722511", "812110", "713120"],
        "competitor": ["462111", "463213", "463214"],
    },
    # Ropa de bebé
    "463211": {
        "complementary": ["463212", "624111", "464112", "465911"],
        "competitor": ["462112", "463213"],
    },
    # Ropa para niños
    "463212": {
        "complementary": ["463211", "463310", "611111", "611121"],
        "competitor": ["462112"],
    },
    # Ropa para damas
    "463213": {
        "complementary": ["463310", "467111", "467115", "812110"],
        "competitor": ["462112", "463214"],
    },
    # Ropa para caballeros
    "463214": {
        "complementary": ["463310", "467115", "812110"],
        "competitor": ["462112", "463213"],
    },
    # Calzado
    "463310": {
        "complementary": ["463213", "463214", "467111", "467115"],
        "competitor": ["462112"],
    },
    # Farmacias sin minisuper
    "464111": {
        "complementary": ["621111", "621112", "621211", "464211"],
        "competitor": ["464112", "462111"],
    },
    # Farmacias con minisuper
    "464112": {
        "complementary": ["621111", "621112", "621211", "464211"],
        "competitor": ["464111", "462111"],
    },
    # Lentes / ópticas
    "464211": {
        "complementary": ["621312", "621112", "464111"],
        "competitor": ["462112"],
    },
    # Computadoras
    "465111": {
        "complementary": ["465112", "541511", "611311", "561432"],
        "competitor": ["462112"],
    },
    # Teléfonos
    "465112": {
        "complementary": ["465111", "811211", "561432"],
        "competitor": ["462112"],
    },
    # Muebles para el hogar
    "465211": {
        "complementary": ["465212", "466111", "466114", "811410"],
        "competitor": ["462112"],
    },
    # Electrodomésticos
    "465212": {
        "complementary": ["465211", "811211", "811219"],
        "competitor": ["462112"],
    },
    # Papelería
    "465311": {
        "complementary": ["465312", "561431", "611121", "611131"],
        "competitor": ["462112"],
    },
    # Libros
    "465312": {
        "complementary": ["465311", "722515", "611211"],
        "competitor": ["462112"],
    },
    # Mascotas
    "465911": {
        "complementary": ["621111", "812110", "461110"],
        "competitor": ["462112"],
    },
    # Perfumería y cosméticos
    "467111": {
        "complementary": ["812110", "463213", "463310", "467115"],
        "competitor": ["462112"],
    },
    # Joyería y relojes
    "467115": {
        "complementary": ["463213", "463214", "467111", "812110"],
        "competitor": ["462112"],
    },
    # Refacciones automotrices
    "468211": {
        "complementary": ["468213", "811111", "811112", "811121", "811192"],
        "competitor": ["462112"],
    },
    # Llantas
    "468213": {
        "complementary": ["468211", "811111", "811192"],
        "competitor": ["462112"],
    },
    # Gasolineras
    "468411": {
        "complementary": ["811111", "811192", "468211", "462111"],
        "competitor": ["468412"],
    },
    # Restaurantes a la carta
    "722511": {
        "complementary": ["461212", "722515", "812110", "713120"],
        "competitor": ["722512", "722513", "722514", "722516", "722517", "722518", "722519"],
    },
    # Comida rápida
    "722512": {
        "complementary": ["461211", "713120", "465112"],
        "competitor": ["722511", "722513", "722514", "722516"],
    },
    # Tacos y tortas
    "722513": {
        "complementary": ["461211", "461212"],
        "competitor": ["722511", "722512", "722514", "722516"],
    },
    # Pizzas
    "722514": {
        "complementary": ["461211", "461212", "713120"],
        "competitor": ["722511", "722512", "722513"],
    },
    # Cafeterías y neverías
    "722515": {
        "complementary": ["465312", "461160", "461170", "713120"],
        "competitor": ["722511", "722512"],
    },
    # Antojitos
    "722516": {
        "complementary": ["461211", "461212"],
        "competitor": ["722511", "722512", "722513"],
    },
    # Pescados y mariscos (restaurante)
    "722517": {
        "complementary": ["461123", "461212"],
        "competitor": ["722511", "722513", "722516"],
    },
    # Gimnasios
    "713111": {
        "complementary": ["812110", "467111", "464111", "621111"],
        "competitor": ["713112"],
    },
    # Clubes deportivos
    "713112": {
        "complementary": ["812110", "467111", "464111"],
        "competitor": ["713111"],
    },
    # Entretenimiento
    "713120": {
        "complementary": ["722511", "722512", "722515", "461170"],
        "competitor": ["711312"],
    },
    # Escuelas preescolar
    "611111": {
        "complementary": ["624111", "463211", "465311", "464111"],
        "competitor": ["611121"],
    },
    # Escuelas primaria
    "611121": {
        "complementary": ["465311", "463212", "464111", "722512"],
        "competitor": ["611111", "611131"],
    },
    # Escuelas secundaria
    "611131": {
        "complementary": ["465311", "465312", "722512", "561431"],
        "competitor": ["611121", "611171"],
    },
    # Escuelas idiomas
    "611312": {
        "complementary": ["611311", "465312", "722515"],
        "competitor": ["611211"],
    },
    # Consultorios medicina general
    "621111": {
        "complementary": ["464111", "464112", "621211", "621312", "621320"],
        "competitor": ["621112"],
    },
    # Consultorios medicina especializada
    "621112": {
        "complementary": ["464111", "464112", "621211", "621312"],
        "competitor": ["621111"],
    },
    # Consultorios dentales
    "621211": {
        "complementary": ["621111", "464111", "621312"],
        "competitor": ["621112"],
    },
    # Optometría
    "621312": {
        "complementary": ["464211", "621111", "621112"],
        "competitor": ["621211"],
    },
    # Psicología
    "621320": {
        "complementary": ["621111", "621112", "464111"],
        "competitor": ["621312"],
    },
    # Guarderías
    "624111": {
        "complementary": ["611111", "463211", "464111", "465911"],
        "competitor": ["611121"],
    },
    # Reparación mecánica
    "811111": {
        "complementary": ["468211", "468213", "811112", "811121", "811192"],
        "competitor": ["811112"],
    },
    # Reparación eléctrica automotriz
    "811112": {
        "complementary": ["468211", "811111", "811121", "811192"],
        "competitor": ["811111"],
    },
    # Hojalatería y pintura
    "811121": {
        "complementary": ["811111", "811112", "468211"],
        "competitor": ["811192"],
    },
    # Lavado de autos
    "811192": {
        "complementary": ["468411", "811111", "468211"],
        "competitor": ["811121"],
    },
    # Reparación electrónicos
    "811211": {
        "complementary": ["465111", "465112", "465212"],
        "competitor": ["811219"],
    },
    # Salones de belleza
    "812110": {
        "complementary": ["467111", "463213", "467115", "713111"],
        "competitor": ["462112"],
    },
    # Lavanderías
    "812210": {
        "complementary": ["463213", "463214", "812110"],
        "competitor": ["462112"],
    },
    # Bufetes jurídicos
    "541110": {
        "complementary": ["541211", "561431", "541610"],
        "competitor": ["541211"],
    },
    # Contabilidad
    "541211": {
        "complementary": ["541110", "541610", "561431"],
        "competitor": ["541110"],
    },
    # Diseño de sistemas
    "541511": {
        "complementary": ["465111", "611311", "541810"],
        "competitor": ["541410"],
    },
    # Publicidad
    "541810": {
        "complementary": ["541511", "541921", "561431"],
        "competitor": ["541410"],
    },
    # Fotografía
    "541921": {
        "complementary": ["541810", "711312", "812110"],
        "competitor": ["561431"],
    },
    # Fotocopiado
    "561431": {
        "complementary": ["465311", "561432", "611121", "611131"],
        "competitor": ["541921"],
    },
    # Acceso a computadoras (ciber)
    "561432": {
        "complementary": ["465111", "465112", "561431", "611311"],
        "competitor": ["465111"],
    },
    # Hoteles con servicios
    "721111": {
        "complementary": ["722511", "713120", "812110", "468411"],
        "competitor": ["721112", "721210"],
    },
    # Hoteles sin servicios
    "721112": {
        "complementary": ["722511", "722512", "468411"],
        "competitor": ["721111", "721210"],
    },
}


def search_scian_catalog(query: str) -> list[tuple[str, str]]:
    """Busca en el catálogo SCIAN por coincidencia textual.

    Args:
        query: Texto de búsqueda del usuario.

    Returns:
        Lista de tuplas (código, descripción) que coinciden.
    """
    query_lower = query.lower().strip()
    if not query_lower:
        return []

    results: list[tuple[str, str]] = []
    query_words = query_lower.split()

    for code, description in SCIAN_CATALOG.items():
        desc_lower = description.lower()
        # Match if any significant word from query appears in description
        if any(word in desc_lower for word in query_words if len(word) > 2):
            results.append((code, description))

    return results


def get_affinity(scian_code: str) -> dict[str, list[SCIANCategory]]:
    """Obtiene categorías complementarias y competidoras para un código SCIAN.

    Args:
        scian_code: Código SCIAN a consultar.

    Returns:
        Dict con claves 'complementary' y 'competitor', cada una con lista de SCIANCategory.
    """
    rules = AFFINITY_RULES.get(scian_code, {})

    complementary = []
    for code in rules.get("complementary", []):
        desc = SCIAN_CATALOG.get(code, "Categoría desconocida")
        complementary.append(SCIANCategory(code=code, description=desc))

    competitor = []
    for code in rules.get("competitor", []):
        desc = SCIAN_CATALOG.get(code, "Categoría desconocida")
        competitor.append(SCIANCategory(code=code, description=desc))

    # If no rules found, provide generic defaults based on catalog proximity
    if not complementary and not competitor:
        # Find codes in same 4-digit group as complementary, same 6-digit as competitor
        prefix_4 = scian_code[:4] if len(scian_code) >= 4 else scian_code
        prefix_6 = scian_code[:6] if len(scian_code) >= 6 else scian_code
        for code, desc in SCIAN_CATALOG.items():
            if code == scian_code:
                continue
            if code.startswith(prefix_6) and code != scian_code:
                competitor.append(SCIANCategory(code=code, description=desc))
            elif code.startswith(prefix_4) and code != scian_code:
                complementary.append(SCIANCategory(code=code, description=desc))

        # Ensure at least one of each
        if not complementary:
            for code, desc in SCIAN_CATALOG.items():
                if code != scian_code and code[:3] == scian_code[:3]:
                    complementary.append(SCIANCategory(code=code, description=desc))
                    if len(complementary) >= 2:
                        break
        if not competitor:
            for code, desc in SCIAN_CATALOG.items():
                if code != scian_code and code[:4] == scian_code[:4]:
                    competitor.append(SCIANCategory(code=code, description=desc))
                    if len(competitor) >= 2:
                        break

    return {"complementary": complementary, "competitor": competitor}
