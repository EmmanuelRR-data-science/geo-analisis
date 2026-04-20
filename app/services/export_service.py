"""Export service — PDF and standalone HTML generation."""

from __future__ import annotations

import html as html_mod
import json
import logging
import tempfile
from datetime import datetime, timezone

from app.models.schemas import AnalysisResult

logger = logging.getLogger(__name__)

# Font family — will be set to "Uni" (Arial Unicode) or "Helvetica" (fallback)
_F = "Helvetica"
_DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_DAY_NAMES_ES = {
    "Monday": "Lunes",
    "Tuesday": "Martes",
    "Wednesday": "Miércoles",
    "Thursday": "Jueves",
    "Friday": "Viernes",
    "Saturday": "Sábado",
    "Sunday": "Domingo",
}
_DAY_SHORT_ES = {
    "Monday": "Lun",
    "Tuesday": "Mar",
    "Wednesday": "Mié",
    "Thursday": "Jue",
    "Friday": "Vie",
    "Saturday": "Sáb",
    "Sunday": "Dom",
}


def _setup_pdf_font(pdf) -> str:
    """Register a Unicode TTF font if available, return font family name."""
    global _F
    import os as _os

    # Try common font paths (Windows, Linux/Docker)
    font_candidates = [
        # Windows
        (_os.path.join(_os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "arial.ttf"),
         _os.path.join(_os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "arialbd.ttf"),
         _os.path.join(_os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "ariali.ttf"),
         _os.path.join(_os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "arialbi.ttf")),
        # Linux (DejaVu from fonts-dejavu-core package)
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf"),
        # Liberation Sans (from fonts-liberation package)
        ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-BoldItalic.ttf"),
        # Liberation Sans (some distros)
        ("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
         "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
         "/usr/share/fonts/truetype/liberation2/LiberationSans-Italic.ttf",
         "/usr/share/fonts/truetype/liberation2/LiberationSans-BoldItalic.ttf"),
    ]

    for regular, bold, italic, bold_italic in font_candidates:
        if not all(_os.path.exists(p) for p in (regular, bold, italic, bold_italic)):
            continue
        try:
            pdf.add_font("Uni", "", fname=regular)
            pdf.add_font("Uni", "B", fname=bold)
            pdf.add_font("Uni", "I", fname=italic)
            pdf.add_font("Uni", "BI", fname=bold_italic)
            _F = "Uni"
            return _F
        except Exception:
            continue

    _F = "Helvetica"
    return _F


def _clean_text(text: str) -> str:
    """Clean text for FPDF. When using Unicode font, keep accents. When using Helvetica, strip them."""
    if not text:
        return ""
    # Map smart quotes and special chars
    mapping = {
        "\u201c": '"', "\u201d": '"',
        "\u2018": "'", "\u2019": "'",
        "\u2013": "-", "\u2014": "-",
        "\u2026": "...",
    }
    for k, v in mapping.items():
        text = text.replace(k, v)
    # If using Unicode font, keep accents
    if _F == "Uni":
        return text
    # Fallback: strip to latin-1
    return text.encode("latin-1", "replace").decode("latin-1")


def _format_opening_hours_summary(opening_hours_by_day: dict[str, str]) -> str:
    """Format opening ranges by day into a compact human-readable summary."""
    if not opening_hours_by_day:
        return "Horario no disponible"
    parts = []
    for day in _DAY_ORDER:
        day_range = opening_hours_by_day.get(day)
        if day_range:
            parts.append(f"{_DAY_SHORT_ES.get(day, day)}: {day_range}")
    if not parts:
        return "Horario no disponible"
    return " | ".join(parts)


class ExportService:
    """Generates PDF and HTML reports from analysis results."""

    @staticmethod
    def generate_pdf(analysis_result: AnalysisResult, map_image_bytes: bytes) -> bytes:
        from fpdf import FPDF

        result = analysis_result
        ageb = result.ageb_data
        now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
        score = round(result.viability.score)
        category = _clean_text(result.viability.category)
        zone_name = _clean_text(result.zone.name)
        business_type = _clean_text(result.business_type.original_input)
        recommendation = _clean_text(result.recommendation_text or "Sin recomendacion disponible.")

        competitors = sum(1 for b in result.businesses if b.classification == "competitor")
        complementary = sum(1 for b in result.businesses if b.classification == "complementary")

        if category == "Recomendable":
            cr, cg, cb = 39, 174, 96
        elif category == "Viable con enfoque estratégico":
            cr, cg, cb = 243, 156, 18
        else:
            cr, cg, cb = 231, 76, 60

        pdf = FPDF()
        _setup_pdf_font(pdf)
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=20)

        # --- Encabezado ---
        pdf.set_font(_F, "B", 20)
        pdf.cell(0, 12, "Informe de Viabilidad de Negocios", new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(44, 62, 80)
        pdf.set_line_width(0.8)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(4)
        pdf.set_font(_F, "", 10)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 6, f"Fecha: {now}   |   Zona: {zone_name}   |   Negocio: {business_type}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(6)

        # --- Puntaje ---
        pdf.set_text_color(cr, cg, cb)
        pdf.set_font(_F, "B", 48)
        pdf.cell(40, 25, str(score), align="C")
        pdf.set_font(_F, "B", 16)
        pdf.cell(0, 25, f"  {category}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)
        # --- 1) Decisión y acciones prioritarias ---
        _section(pdf, "1) Decisión Ejecutiva")
        pdf.set_font(_F, "", 10)
        pdf.set_text_color(60, 60, 60)
        pdf.multi_cell(0, 5.5, recommendation)
        pdf.ln(2)

        if result.strategic_recommendations:
            _sub(pdf, "Acciones Prioritarias")
            for idx, rec in enumerate(result.strategic_recommendations, 1):
                if pdf.get_y() > 260:
                    pdf.add_page()
                pdf.set_font(_F, "B", 10)
                pdf.set_text_color(44, 62, 80)
                pdf.cell(8, 6, f"{idx}.")
                pdf.set_font(_F, "", 10)
                pdf.set_text_color(60, 60, 60)
                pdf.multi_cell(0, 5.5, _clean_text(rec))
                pdf.ln(1)
        pdf.ln(2)

        # --- 2) Evidencia de viabilidad ---
        _section(pdf, "2) Evidencia de Viabilidad")
        _sub(pdf, "Desglose de Factores")
        _factor_labels = {
            "competencia": "Competencia",
            "complementarios": "Complementarios",
            "demografico": "Demográfico",
            "socioeconomico": "Socioeconómico",
        }
        for factor, val in result.viability.factor_scores.items():
            label = _factor_labels.get(factor, factor.replace("_", " ").capitalize())
            _row(pdf, label, f"{val:.1f} / 100")
        _row(pdf, "Completitud de datos", f"{result.viability.data_completeness * 100:.0f}%")
        pdf.ln(4)

        # --- Ecosistema comercial ---
        unclassified = len(result.businesses) - competitors - complementary
        _section(pdf, "2.1) Ecosistema Comercial")
        _row(pdf, "Competidores directos", str(competitors))
        _row(pdf, "Negocios complementarios", str(complementary))
        if unclassified > 0:
            _row(pdf, "Sin clasificar", str(unclassified))
        _row(pdf, "Total de negocios analizados", str(len(result.businesses)))
        pdf.ln(4)

        # --- Análisis Multi-Radio ---
        if result.multi_radius_results:
            _section(pdf, "2.2) Análisis Multi-Radio")
            # Table header
            pdf.set_font(_F, "B", 9)
            pdf.set_text_color(44, 62, 80)
            col_w = [25, 30, 35, 30, 35, 35]  # Radio, Comp, Compl, Pobl, Densidad, Actividad
            headers = ["Radio", "Competidores", "Complementarios", "Población", "Densidad POI", "Actividad (%)"]
            for i, h in enumerate(headers):
                pdf.cell(col_w[i], 7, h, border=1, align="C")
            pdf.ln()
            # Table rows
            pdf.set_font(_F, "", 9)
            pdf.set_text_color(60, 60, 60)
            for mr in result.multi_radius_results:
                env = mr.environment_variables or {}
                pdf.cell(col_w[0], 6, f"{mr.radius_km:.0f} km", border=1, align="C")
                pdf.cell(col_w[1], 6, str(mr.competitors), border=1, align="C")
                pdf.cell(col_w[2], 6, str(mr.complementary), border=1, align="C")
                pdf.cell(col_w[3], 6, f"{mr.total_population:,}", border=1, align="C")
                pdf.cell(col_w[4], 6, f"{env.get('poi_density', 0):.2f} /km²", border=1, align="C")
                pdf.cell(col_w[5], 6, f"{env.get('commercial_activity_index', 0):.1f}%", border=1, align="C")
                pdf.ln()
            pdf.ln(4)


        # --- Datos demográficos AGEB ---
        _section(pdf, "3) Contexto Demográfico y de Mercado (INEGI — AGEB)")
        _row(pdf, "AGEBs analizadas", str(ageb.ageb_count))
        _row(pdf, "Población total", f"{ageb.total_population:,}")
        if ageb.female_population:
            _row(pdf, "Población femenina", f"{ageb.female_population:,}")
        if ageb.male_population:
            _row(pdf, "Población masculina", f"{ageb.male_population:,}")
        _row(pdf, "Densidad de población", f"{ageb.population_density:,.1f} hab/km²")
        pdf.ln(2)

        if ageb.population_0_14 or ageb.population_15_64 or ageb.population_65_plus:
            _sub(pdf, "Estructura Etaria")
            _row(pdf, "Población 0–14 años", f"{ageb.population_0_14:,}")
            _row(pdf, "Población 15–64 años", f"{ageb.population_15_64:,}")
            _row(pdf, "Población 65+ años", f"{ageb.population_65_plus:,}")
            pdf.ln(2)

        _sub(pdf, "Indicadores Económicos")
        _row(pdf, "Población Económicamente Activa (PEA)", f"{ageb.economically_active_population:,}")
        if ageb.occupied_population:
            _row(pdf, "Población ocupada", f"{ageb.occupied_population:,}")
        if ageb.unemployed_population:
            _row(pdf, "Población desocupada", f"{ageb.unemployed_population:,}")
        if ageb.inactive_population:
            _row(pdf, "Población inactiva", f"{ageb.inactive_population:,}")
        _row(pdf, "Nivel socioeconómico", ageb.socioeconomic_level)
        _row(pdf, "Escolaridad promedio", f"{ageb.avg_schooling_years:.1f} años")
        pdf.ln(2)

        _sub(pdf, "Vivienda y Hogares")
        if ageb.total_households:
            _row(pdf, "Total de hogares", f"{ageb.total_households:,}")
        if ageb.total_dwellings:
            _row(pdf, "Total de viviendas", f"{ageb.total_dwellings:,}")
        if ageb.avg_occupants_per_dwelling:
            _row(pdf, "Ocupantes promedio por vivienda", f"{ageb.avg_occupants_per_dwelling:.1f}")
        pdf.ln(2)

        if ageb.population_with_health_services or ageb.population_without_health_services:
            _sub(pdf, "Servicios de Salud")
            _row(pdf, "Con servicios de salud", f"{ageb.population_with_health_services:,}")
            _row(pdf, "Sin servicios de salud", f"{ageb.population_without_health_services:,}")
            pdf.ln(2)

        if ageb.pct_with_electricity or ageb.pct_with_internet:
            _sub(pdf, "Infraestructura de Viviendas (%)")
            if ageb.pct_with_electricity:
                _row(pdf, "Con electricidad", f"{ageb.pct_with_electricity:.1f}%")
            if ageb.pct_with_water:
                _row(pdf, "Con agua entubada", f"{ageb.pct_with_water:.1f}%")
            if ageb.pct_with_drainage:
                _row(pdf, "Con drenaje", f"{ageb.pct_with_drainage:.1f}%")
            if ageb.pct_with_internet:
                _row(pdf, "Con internet", f"{ageb.pct_with_internet:.1f}%")
            if ageb.pct_with_cellphone:
                _row(pdf, "Con celular", f"{ageb.pct_with_cellphone:.1f}%")
            if ageb.pct_with_computer:
                _row(pdf, "Con computadora", f"{ageb.pct_with_computer:.1f}%")
            if ageb.pct_with_car:
                _row(pdf, "Con automóvil", f"{ageb.pct_with_car:.1f}%")
            pdf.ln(2)

        # --- Variables de Entorno Ampliadas ---
        ext = ageb.extended_indicators
        if ext:
            _section(pdf, "3.1) Variables de Entorno Ampliadas")
            _sub(pdf, "Indicadores Socioeconómicos")
            if ext.get("unemployment_rate") is not None:
                _row(pdf, "Tasa de desempleo", f"{ext['unemployment_rate']:.1f}%")
            if ext.get("economic_participation_rate") is not None:
                _row(pdf, "Tasa de participación económica", f"{ext['economic_participation_rate']:.1f}%")
            if ext.get("dependency_index") is not None:
                _row(pdf, "Índice de dependencia", f"{ext['dependency_index']:.1f}%")
            pdf.ln(2)
            _sub(pdf, "Equipamiento de Vivienda")
            if ext.get("pct_with_refrigerator") is not None:
                _row(pdf, "Con refrigerador", f"{ext['pct_with_refrigerator']:.1f}%")
            if ext.get("pct_with_washing_machine") is not None:
                _row(pdf, "Con lavadora", f"{ext['pct_with_washing_machine']:.1f}%")
            pdf.ln(2)
            _sub(pdf, "Población por Rango de Edad")
            if ext.get("population_12_plus"):
                _row(pdf, "Población de 12 años y más", f"{ext['population_12_plus']:,}")
            if ext.get("population_15_plus"):
                _row(pdf, "Población de 15 años y más", f"{ext['population_15_plus']:,}")
            if ext.get("population_18_plus"):
                _row(pdf, "Población de 18 años y más", f"{ext['population_18_plus']:,}")
            if ext.get("population_60_plus"):
                _row(pdf, "Población de 60 años y más", f"{ext['population_60_plus']:,}")
            if ext.get("household_population"):
                _row(pdf, "Población en hogares", f"{ext['household_population']:,}")
            pdf.ln(2)

        # --- Actividad Comercial (from multi-radius) ---
        if result.multi_radius_results:
            main_mr = result.multi_radius_results[-1]  # largest radius
            env = main_mr.environment_variables or {}
            _sub(pdf, "Actividad Comercial")
            _row(pdf, "Densidad POI", f"{env.get('poi_density', 0):.2f} negocios/km²")
            _row(pdf, "Índice de actividad comercial", f"{env.get('commercial_activity_index', 0):.1f}%")
            sectors = env.get("sector_concentration", [])
            if sectors:
                _sub(pdf, "Concentración Sectorial (Top 5)")
                for s in sectors[:5]:
                    _row(pdf, f"{s.get('sector', '')} ({s.get('code_2d', '')})", f"{s.get('count', 0)} negocios ({s.get('percentage', 0):.1f}%)")
            pdf.ln(4)

        # --- Perfil de Mercado Objetivo ---
        if result.target_profile:
            _section(pdf, "4) Perfil de Mercado Objetivo")
            pdf.set_font(_F, "I", 10)
            pdf.set_text_color(100, 100, 100)
            pdf.multi_cell(0, 5, _clean_text(result.target_profile))
            pdf.ln(2)
            if result.target_match_percentage is not None:
                _row(pdf, "Coincidencia demográfica", f"{result.target_match_percentage:.1f}%")
            if result.target_match_population is not None:
                _row(pdf, "Población estimada objetivo", f"{result.target_match_population:,}")
            if result.target_match_breakdown:
                bd = result.target_match_breakdown
                _sub(pdf, "Desglose de Factores")
                if "gender_factor" in bd:
                    _row(pdf, "Factor de género", f"{bd['gender_factor'] * 100:.0f}%")
                if "age_factor" in bd:
                    _row(pdf, "Factor de edad", f"{bd['age_factor'] * 100:.0f}%")
                if "socioeconomic_factor" in bd:
                    _row(pdf, "Factor socioeconómico", f"{bd['socioeconomic_factor'] * 100:.0f}%")
            pdf.ln(4)

        # --- Análisis de Competidores — Puntos de Valor ---
        if result.competitor_value_points:
            _section(pdf, "5) Inteligencia Competitiva — Puntos de Valor")
            _sub(pdf, "Lo que valoran los clientes")
            for vp in result.competitor_value_points:
                if pdf.get_y() > 260:
                    pdf.add_page()
                pdf.set_font(_F, "B", 9)
                pdf.set_text_color(39, 174, 96)
                pdf.cell(6, 5, "✓")
                pdf.set_text_color(44, 62, 80)
                pdf.cell(0, 5, _clean_text(vp.get("title", "")), new_x="LMARGIN", new_y="NEXT")
                pdf.set_font(_F, "", 8)
                pdf.set_text_color(100, 100, 100)
                pdf.multi_cell(0, 4, _clean_text(vp.get("description", "")))
                pdf.ln(2)
            pdf.ln(2)

        if result.competitor_improvement_opportunities:
            _sub(pdf, "Oportunidades de Mejora")
            for io in result.competitor_improvement_opportunities:
                if pdf.get_y() > 260:
                    pdf.add_page()
                pdf.set_font(_F, "B", 9)
                pdf.set_text_color(243, 156, 18)
                pdf.cell(6, 5, "⚡")
                pdf.set_text_color(44, 62, 80)
                pdf.cell(0, 5, _clean_text(io.get("issue", "")), new_x="LMARGIN", new_y="NEXT")
                pdf.set_font(_F, "I", 8)
                pdf.set_text_color(146, 64, 14)
                pdf.multi_cell(0, 4, "Recomendación: " + _clean_text(io.get("recommendation", "")))
                pdf.ln(2)
            pdf.ln(2)

        # --- Lo que tu cliente objetivo valora ---
        if result.target_customer_insights:
            _section(pdf, "Lo que tu Cliente Objetivo Valora")
            for insight in result.target_customer_insights:
                if pdf.get_y() > 260:
                    pdf.add_page()
                pdf.set_font(_F, "B", 9)
                pdf.set_text_color(30, 64, 175)
                pdf.cell(6, 5, "★")
                pdf.set_text_color(44, 62, 80)
                pdf.cell(0, 5, _clean_text(insight.get("title", "")), new_x="LMARGIN", new_y="NEXT")
                pdf.set_font(_F, "", 8)
                pdf.set_text_color(100, 100, 100)
                pdf.multi_cell(0, 4, _clean_text(insight.get("explanation", "")))
                pdf.ln(2)
            pdf.ln(4)


        # --- Gráficas de análisis de competidores ---
        competitors = [b for b in result.businesses if b.classification == "competitor"]
        if competitors:
            from app.services.chart_generator import (
                extract_schedule_data,
                extract_top_complaints,
                generate_price_chart,
                generate_ratings_chart,
                generate_schedule_opportunity_chart,
            )

            # Schedule opportunity chart
            schedule_png = generate_schedule_opportunity_chart(competitors)
            if schedule_png:
                if pdf.get_y() > 140:
                    pdf.add_page()
                _section(pdf, "5.1) Análisis de Horarios de Competidores")
                try:
                    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                        tmp.write(schedule_png)
                        tmp_path = tmp.name
                    pdf.image(tmp_path, x=15, w=170)
                    import os
                    os.unlink(tmp_path)
                except Exception as e:
                    logger.warning("Could not embed schedule chart: %s", e)
                pdf.ln(4)

            # Schedule data table
            schedule_data = extract_schedule_data(competitors)
            if schedule_data:
                pdf.ln(2)
                # Table header
                pdf.set_font(_F, "B", 8)
                pdf.set_text_color(44, 62, 80)
                col_w = [28, 24, 24, 24, 28, 62]
                headers = ["Día", "Abiertos", "Cerrados", "Total", "% Abiertos", "Interpretación"]
                for i, h in enumerate(headers):
                    pdf.cell(col_w[i], 6, h, border=1, align="C")
                pdf.ln()
                # Table rows
                pdf.set_font(_F, "", 8)
                pdf.set_text_color(60, 60, 60)
                for row in schedule_data:
                    # Interpretation based on open percentage
                    if row["open_pct"] >= 80:
                        interp = "Alta competencia"
                    elif row["open_pct"] >= 50:
                        interp = "Competencia moderada"
                    else:
                        interp = "Baja competencia (oportunidad)"
                    pdf.cell(col_w[0], 5, row["day"], border=1, align="C")
                    pdf.cell(col_w[1], 5, str(row["open"]), border=1, align="C")
                    pdf.cell(col_w[2], 5, str(row["closed"]), border=1, align="C")
                    pdf.cell(col_w[3], 5, str(row["total"]), border=1, align="C")
                    pdf.cell(col_w[4], 5, f"{row['open_pct']:.0f}%", border=1, align="C")
                    pdf.cell(col_w[5], 5, interp, border=1, align="C")
                    pdf.ln()
                pdf.ln(3)

                # AI explanation text
                # Find the day with least competition and most competition
                min_day = min(schedule_data, key=lambda x: x["open_pct"])
                max_day = max(schedule_data, key=lambda x: x["open_pct"])

                explanation = (
                    f"Esta tabla muestra cuántos de los {schedule_data[0]['total']} competidores identificados "
                    f"operan cada día de la semana. "
                    f"El día con menor competencia es {min_day['day']} ({min_day['open']} de {min_day['total']} abiertos, "
                    f"{min_day['open_pct']:.0f}%), lo que representa una oportunidad para captar clientes desatendidos. "
                    f"El día con mayor competencia es {max_day['day']} ({max_day['open']} de {max_day['total']} abiertos, "
                    f"{max_day['open_pct']:.0f}%), donde será necesario diferenciarse más para competir. "
                    f"Considere ajustar sus horarios de operación para aprovechar los días con menor presencia de competidores."
                )

                pdf.set_font(_F, "I", 9)
                pdf.set_text_color(80, 80, 80)
                pdf.multi_cell(0, 4.5, _clean_text(explanation))
                pdf.ln(4)

            # Ratings chart
            ratings_png = generate_ratings_chart(competitors)
            if ratings_png:
                if pdf.get_y() > 140:
                    pdf.add_page()
                _section(pdf, "5.2) Análisis de Ratings de Competidores")
                try:
                    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                        tmp.write(ratings_png)
                        tmp_path = tmp.name
                    pdf.image(tmp_path, x=15, w=170)
                    import os
                    os.unlink(tmp_path)
                except Exception as e:
                    logger.warning("Could not embed ratings chart: %s", e)
                pdf.ln(4)

            # Price distribution chart
            price_png = generate_price_chart(competitors)
            if price_png:
                if pdf.get_y() > 160:
                    pdf.add_page()
                _section(pdf, "5.3) Distribución de Precios de Competidores")
                try:
                    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                        tmp.write(price_png)
                        tmp_path = tmp.name
                    pdf.image(tmp_path, x=30, w=140)
                    import os
                    os.unlink(tmp_path)
                except Exception as e:
                    logger.warning("Could not embed price chart: %s", e)
                pdf.ln(4)

            # Top 5 complaints
            complaints = extract_top_complaints(competitors, n=5)
            if complaints:
                if pdf.get_y() > 200:
                    pdf.add_page()
                _section(pdf, "5.4) Top 5 Quejas Más Comunes de Competidores")
                for idx, complaint in enumerate(complaints, 1):
                    if pdf.get_y() > 260:
                        pdf.add_page()
                    stars = "★" * complaint["rating"] + "☆" * (5 - complaint["rating"])
                    pdf.set_font(_F, "B", 9)
                    pdf.set_text_color(44, 62, 80)
                    pdf.cell(0, 5, f"{idx}. {_clean_text(complaint['business_name'])} — {stars}", new_x="LMARGIN", new_y="NEXT")
                    pdf.set_font(_F, "I", 8)
                    pdf.set_text_color(100, 100, 100)
                    pdf.multi_cell(0, 4.5, f'"{_clean_text(complaint["text"])}"')
                    pdf.ln(2)
                pdf.ln(4)

        # --- Tráfico Peatonal ---
        if result.zone_traffic_profile:
            ztp = result.zone_traffic_profile
            if isinstance(ztp, dict) and ztp.get('hourly_matrix'):
                from app.services.chart_generator import generate_foot_traffic_chart

                if pdf.get_y() > 140:
                    pdf.add_page()
                _section(pdf, "6) Tráfico Peatonal de Competidores (BestTime)")

                # Chart
                traffic_png = generate_foot_traffic_chart(ztp)
                if traffic_png:
                    try:
                        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                            tmp.write(traffic_png)
                            tmp_path = tmp.name
                        pdf.image(tmp_path, x=15, w=170)
                        import os
                        os.unlink(tmp_path)
                    except Exception as e:
                        logger.warning("Could not embed foot traffic chart: %s", e)
                    pdf.ln(4)

                # Summary
                busiest = _DAY_NAMES_ES.get(ztp.get('busiest_day', ''), ztp.get('busiest_day', ''))
                quietest = _DAY_NAMES_ES.get(ztp.get('quietest_day', ''), ztp.get('quietest_day', ''))
                _row(pdf, "Día más concurrido", busiest)
                _row(pdf, "Día más tranquilo", quietest)
                _row(pdf, "Permanencia promedio", f"{ztp.get('avg_dwell_time_minutes', 0):.0f} minutos")
                _row(pdf, "Competidores con datos", f"{ztp.get('venues_with_data', 0)} de {ztp.get('venues_total', 0)}")
                pdf.ln(2)

                source_venues = ztp.get("source_venues", [])
                if source_venues:
                    _sub(pdf, "Comercios incluidos en BestTime")
                    for idx, venue in enumerate(source_venues, 1):
                        if pdf.get_y() > 260:
                            pdf.add_page()
                        venue_name = _clean_text(venue.get("venue_name", "") or "Comercio sin nombre")
                        venue_category = _clean_text(venue.get("venue_category", "") or "Categoría no disponible")
                        opening_hours = venue.get("opening_hours_by_day", {}) or {}
                        opening_summary = _clean_text(_format_opening_hours_summary(opening_hours))

                        pdf.set_font(_F, "B", 9)
                        pdf.set_text_color(44, 62, 80)
                        pdf.cell(0, 5, f"{idx}. {venue_name}", new_x="LMARGIN", new_y="NEXT")
                        pdf.set_font(_F, "", 8)
                        pdf.set_text_color(100, 100, 100)
                        pdf.multi_cell(0, 4, f"Categoría: {venue_category}")
                        pdf.multi_cell(0, 4, f"Horario reportado: {opening_summary}")
                        pdf.ln(1)
                    pdf.ln(2)

                # Peak/quiet hours table
                peak_by_day = ztp.get('peak_hours_by_day', {})
                quiet_by_day = ztp.get('quiet_hours_by_day', {})
                if peak_by_day:
                    _sub(pdf, "Horas Pico y Tranquilas por Día")
                    pdf.set_font(_F, "B", 8)
                    pdf.set_text_color(44, 62, 80)
                    col_w = [30, 50, 50, 60]
                    for i, h in enumerate(["Día", "Horas pico", "Horas tranquilas", "Interpretación"]):
                        pdf.cell(col_w[i], 6, h, border=1, align="C")
                    pdf.ln()
                    pdf.set_font(_F, "", 8)
                    pdf.set_text_color(60, 60, 60)
                    for day_en in _DAY_ORDER:
                        day_es = _DAY_NAMES_ES.get(day_en, day_en)
                        peaks = peak_by_day.get(day_en, [])
                        quiets = quiet_by_day.get(day_en, [])
                        peak_str = ", ".join(f"{h}:00" for h in peaks[:3]) if peaks else "—"
                        quiet_str = ", ".join(f"{h}:00" for h in quiets[:3]) if quiets else "—"
                        # Interpretation
                        matrix = ztp.get('hourly_matrix', {})
                        day_hours = matrix.get(day_en, [])
                        day_avg = sum(day_hours) / len(day_hours) if day_hours else 0
                        if day_avg >= 50:
                            interp = "Alta afluencia"
                        elif day_avg >= 25:
                            interp = "Afluencia moderada"
                        else:
                            interp = "Baja afluencia"
                        pdf.cell(col_w[0], 5, day_es, border=1, align="C")
                        pdf.cell(col_w[1], 5, peak_str, border=1, align="C")
                        pdf.cell(col_w[2], 5, quiet_str, border=1, align="C")
                        pdf.cell(col_w[3], 5, interp, border=1, align="C")
                        pdf.ln()
                    pdf.ln(4)

        # --- Mapa ---
        if map_image_bytes:
            if pdf.get_y() > 160:
                pdf.add_page()
            _section(pdf, "7) Evidencia Geográfica — Mapa de la Zona")
            try:
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp.write(map_image_bytes)
                    tmp_path = tmp.name
                pdf.image(tmp_path, x=10, w=190)
                import os
                os.unlink(tmp_path)
            except Exception as e:
                logger.warning("Could not embed map image: %s", e)

        # --- Anexo: detalle de negocios ---
        if result.businesses:
            if pdf.get_y() > 220:
                pdf.add_page()
            _section(pdf, "Anexo — Detalle de Negocios Encontrados")
            groups = [
                ("Competidores", [b for b in result.businesses if b.classification == "competitor"]),
                ("Complementarios", [b for b in result.businesses if b.classification == "complementary"]),
                ("Sin clasificar", [b for b in result.businesses if b.classification == "unclassified"]),
            ]
            for group_label, biz_list in groups:
                if not biz_list:
                    continue
                _sub(pdf, f"{group_label} ({len(biz_list)})")
                for b in biz_list:
                    if pdf.get_y() > 260:
                        pdf.add_page()
                    pdf.set_font(_F, "B", 9)
                    pdf.set_text_color(44, 62, 80)
                    pdf.cell(0, 5, b.name, new_x="LMARGIN", new_y="NEXT")
                    pdf.set_font(_F, "", 8)
                    pdf.set_text_color(100, 100, 100)
                    details = b.category
                    if b.google_rating is not None:
                        details += f"  |  Rating: {b.google_rating:.1f}"
                    if b.google_reviews_count is not None:
                        details += f"  |  {b.google_reviews_count} reseñas"
                    if b.denue_employee_stratum:
                        details += f"  |  Personal: {b.denue_employee_stratum}"
                    pdf.cell(0, 4, details, new_x="LMARGIN", new_y="NEXT")
                    pdf.ln(2)
            pdf.ln(2)

        # --- Pie de página ---
        pdf.ln(8)
        pdf.set_font(_F, "I", 8)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(0, 5, "Generado por Mapa de Viabilidad de Negocios — CDMX | Datos: INEGI, Google Places", align="C")

        return pdf.output()

    @staticmethod
    def generate_standalone_html(
        analysis_result: AnalysisResult,
        ageb_layers_data: dict | None = None,
        radius_km: float = 5.0,
    ) -> str:
        """Generate a standalone HTML file with an interactive Leaflet map."""
        result = analysis_result
        zone = result.zone
        bbox = zone.bbox
        score = round(result.viability.score)
        category = result.viability.category
        competitors = sum(1 for b in result.businesses if b.classification == "competitor")
        complementary = sum(1 for b in result.businesses if b.classification == "complementary")
        population = result.ageb_data.total_population

        businesses_json = json.dumps([
            {k: getattr(b, k) for k in (
                "id","name","lat","lng","category","classification","relevance","source",
                "google_rating","google_reviews_count","google_hours","google_is_open",
                "denue_scian_code","denue_employee_stratum","denue_registration_date",
                "denue_legal_name","denue_address",
            )}
            for b in result.businesses if b.classification != "unclassified"
        ], ensure_ascii=False)

        zone_json = json.dumps({"name": zone.name, "center_lat": zone.center_lat, "center_lng": zone.center_lng,
            "bbox": {"min_lat": bbox.min_lat, "min_lng": bbox.min_lng, "max_lat": bbox.max_lat, "max_lng": bbox.max_lng}}, ensure_ascii=False)
        summary_json = json.dumps({"score": score, "category": category, "competitors": competitors, "complementary": complementary, "population": population}, ensure_ascii=False)
        ageb_layers_json = json.dumps(ageb_layers_data if ageb_layers_data else {}, ensure_ascii=False)

        multi_radius_json = json.dumps([
            {"radius_km": mr.radius_km, "competitors": mr.competitors, "complementary": mr.complementary,
             "total_population": mr.total_population, "environment_variables": mr.environment_variables}
            for mr in result.multi_radius_results
        ], ensure_ascii=False) if result.multi_radius_results else "[]"

        cat_color = "#27ae60" if category == "Recomendable" else ("#f39c12" if category == "Viable con enfoque estratégico" else "#e74c3c")
        esc = html_mod.escape
        layer_html = ('<div id="ring-control" class="hidden" style="position:absolute;top:10px;right:10px;z-index:1000;'
                      'background:#fff;padding:12px;border-radius:6px;box-shadow:0 2px 8px rgba(0,0,0,.2);max-width:260px;font-size:13px">'
                      '<h3 style="margin-bottom:8px;font-size:14px;color:#2c3e50">Anillos de distancia</h3>'
                      '<div id="ring-toggles"></div></div>')

        return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Mapa de Viabilidad - {esc(zone.name)}</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f5f5f5}}
#map{{width:100%;height:70vh;min-height:400px}}.summary-panel{{background:#fff;padding:16px 20px;display:flex;align-items:center;gap:24px;flex-wrap:wrap;box-shadow:0 2px 8px rgba(0,0,0,.1);z-index:500}}
.summary-panel .score{{font-size:48px;font-weight:bold;color:{cat_color}}}.summary-panel .category{{font-size:18px;font-weight:600;color:{cat_color}}}
.summary-panel .metric{{text-align:center}}.summary-panel .metric .value{{font-size:22px;font-weight:bold;color:#2c3e50}}.summary-panel .metric .label{{font-size:12px;color:#888}}
.legend{{background:#fff;padding:10px 14px;border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,.15);display:flex;gap:16px;align-items:center;margin:8px 20px;font-size:13px}}
.legend .item{{display:flex;align-items:center;gap:6px}}.legend .dot{{width:14px;height:14px;border-radius:50%;border:2px solid #fff;box-shadow:0 0 2px rgba(0,0,0,.3)}}
#layer-control{{position:absolute;top:10px;right:10px;z-index:1000;background:#fff;padding:12px;border-radius:6px;box-shadow:0 2px 8px rgba(0,0,0,.2);max-width:260px;font-size:13px}}
#layer-control h3{{margin-bottom:8px;font-size:14px;color:#2c3e50}}.layer-toggle{{display:block;margin-bottom:4px;cursor:pointer}}.layer-toggle input{{margin-right:6px}}
#color-scale-legend{{position:absolute;bottom:30px;right:10px;z-index:1000;background:#fff;padding:10px 14px;border-radius:6px;box-shadow:0 2px 8px rgba(0,0,0,.2);font-size:12px;min-width:180px}}
#color-scale-legend.hidden{{display:none}}.color-bar{{height:12px;border-radius:3px;margin:6px 0;background:linear-gradient(to right,#ffffcc,#fed976,#fd8d3c,#e31a1c,#800026)}}
.color-labels{{display:flex;justify-content:space-between;font-size:11px;color:#666}}
.popup-badge{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;margin-right:4px}}
.popup-badge.complementary{{background:#dcfce7;color:#166534}}.popup-badge.competitor{{background:#fee2e2;color:#991b1b}}
.popup-badge.high{{background:#dbeafe;color:#1e40af}}.popup-badge.medium{{background:#fef9c3;color:#854d0e}}.popup-badge.low{{background:#f3f4f6;color:#374151}}
.popup-section{{margin-top:8px;padding-top:6px;border-top:1px solid #eee}}.popup-section-title{{font-weight:600;font-size:12px;color:#555;margin-bottom:4px}}.map-wrapper{{position:relative}}</style>
</head><body>
<div class="summary-panel"><div class="score">{score}</div><div><div class="category">{esc(category)}</div><div style="font-size:13px;color:#888">{esc(zone.name)}</div></div>
<div class="metric"><div class="value">{competitors}</div><div class="label">Competidores</div></div>
<div class="metric"><div class="value">{complementary}</div><div class="label">Complementarios</div></div>
<div class="metric"><div class="value">{population:,}</div><div class="label">Población</div></div></div>
<div style="width:100%;margin-top:12px" id="mr-panel"></div>
<div class="legend"><div class="item"><div class="dot" style="background:#22c55e"></div> Complementario</div><div class="item"><div class="dot" style="background:#ef4444"></div> Competidor</div></div>
<div class="map-wrapper"><div id="map"></div>{layer_html}</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
var B={businesses_json},Z={zone_json},S={summary_json},AL={ageb_layers_json},MR={multi_radius_json};
function esc(t){{var d=document.createElement('div');d.textContent=t;return d.innerHTML}}
function popup(b){{var h='<div style="max-width:300px;font-size:13px"><h3 style="margin:0 0 4px">'+esc(b.name)+'</h3><p style="margin:0 0 6px;color:#666">'+esc(b.category)+'</p>';
var cl=b.classification==='complementary'?'Complementario':'Competidor';h+='<span class="popup-badge '+b.classification+'">'+cl+'</span> ';
var rl=b.relevance==='high'?'Alta':(b.relevance==='medium'?'Media':'Baja');h+='<span class="popup-badge '+b.relevance+'">Relevancia: '+rl+'</span>';
if(b.google_rating!=null||b.google_reviews_count!=null){{h+='<div class="popup-section"><div class="popup-section-title">Datos Google Places</div>';
if(b.google_rating!=null)h+='<p>Rating: '+b.google_rating.toFixed(1)+'</p>';if(b.google_reviews_count!=null)h+='<p>'+b.google_reviews_count+' reseñas</p>';
if(b.google_hours&&b.google_hours.length)h+='<p><strong>Horario:</strong><br>'+b.google_hours.map(esc).join('<br>')+'</p>';
if(b.google_is_open!=null)h+='<p>'+(b.google_is_open?'● Abierto':'● Cerrado')+'</p>';h+='</div>'}}
if(b.denue_scian_code!=null){{h+='<div class="popup-section"><div class="popup-section-title">Datos DENUE</div>';
if(b.denue_employee_stratum)h+='<p><strong>Personal:</strong> '+esc(b.denue_employee_stratum)+'</p>';
if(b.denue_scian_code)h+='<p><strong>SCIAN:</strong> '+esc(b.denue_scian_code)+'</p>';h+='</div>'}}return h+'</div>'}}
var map=L.map('map',{{center:[Z.center_lat,Z.center_lng],zoom:14}});
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',{{attribution:'© OpenStreetMap',maxZoom:19}}).addTo(map);

// Haversine distance in km
function hav(la1,lo1,la2,lo2){{var R=6371,dL=(la2-la1)*Math.PI/180,dG=(lo2-lo1)*Math.PI/180;var a=Math.sin(dL/2)*Math.sin(dL/2)+Math.cos(la1*Math.PI/180)*Math.cos(la2*Math.PI/180)*Math.sin(dG/2)*Math.sin(dG/2);return R*2*Math.atan2(Math.sqrt(a),Math.sqrt(1-a))}}

// Center marker
L.marker([Z.center_lat,Z.center_lng],{{icon:L.divIcon({{className:'',html:'<div style=\"width:14px;height:14px;background:#3b82f6;border:3px solid #fff;border-radius:50%;box-shadow:0 0 6px rgba(0,0,0,.4)\"></div>',iconSize:[14,14],iconAnchor:[7,7]}}),zIndexOffset:1000}}).addTo(map).bindTooltip('Centro de búsqueda',{{direction:'top',offset:[0,-10]}});

// Radius and inner rings
var RAD={radius_km};
var innerDists=[];
if(RAD>=3)innerDists.push(1);if(RAD>=6)innerDists.push(3);if(RAD>=10)innerDists.push(5);if(RAD>=15)innerDists.push(10);
if(!innerDists.length&&RAD>1)innerDists.push(Math.round(RAD/2*10)/10);
innerDists=innerDists.filter(function(r){{return r<RAD}});

// Outer circle
L.circle([Z.center_lat,Z.center_lng],{{radius:RAD*1000,color:'#3b82f6',weight:2,fillColor:'#3b82f6',fillOpacity:.04,dashArray:'8 4'}}).addTo(map);

// Inner ring circles and state
var rings={{}};
innerDists.forEach(function(d){{
  var c=L.circle([Z.center_lat,Z.center_lng],{{radius:d*1000,color:'#94a3b8',weight:1.5,fillColor:'transparent',fillOpacity:0,dashArray:'4 4'}}).addTo(map);
  rings[d]={{circle:c,visible:true}};
}});

// Markers with distance
var markers=[];
var bounds=L.latLngBounds([[Z.bbox.min_lat,Z.bbox.min_lng],[Z.bbox.max_lat,Z.bbox.max_lng]]);
B.forEach(function(b){{if(!b.lat||!b.lng)return;var c=b.classification==='complementary'?'#22c55e':'#ef4444';
var m=L.circleMarker([b.lat,b.lng],{{radius:8,fillColor:c,color:'#fff',weight:2,opacity:1,fillOpacity:.85}});
m.bindPopup(popup(b),{{maxWidth:320}});m._dk=hav(Z.center_lat,Z.center_lng,b.lat,b.lng);m.addTo(map);markers.push(m);bounds.extend(m.getLatLng())}});
map.fitBounds(bounds,{{padding:[40,40]}});

// Ring control
var rc=document.getElementById('ring-control'),rt=document.getElementById('ring-toggles');
if(rc&&rt){{
  // Outer (always on)
  var ol=document.createElement('label');ol.className='layer-toggle';var oc=document.createElement('input');oc.type='checkbox';oc.checked=true;oc.disabled=true;
  ol.appendChild(oc);ol.appendChild(document.createTextNode(' '+RAD+' km (radio)'));rt.appendChild(ol);
  // Inner rings
  innerDists.forEach(function(d){{
    var lb=document.createElement('label');lb.className='layer-toggle';var cb=document.createElement('input');cb.type='checkbox';cb.checked=true;
    cb.addEventListener('change',function(){{
      var r=rings[d];if(!r)return;
      if(cb.checked){{r.circle.addTo(map);r.visible=true}}else{{map.removeLayer(r.circle);r.visible=false}}
      // Update marker visibility
      var bds=innerDists.slice().sort(function(a,b){{return a-b}});
      markers.forEach(function(m){{
        var dk=m._dk||0,show=true;
        if(bds.length&&dk>bds[0]){{
          for(var i=0;i<bds.length;i++){{
            var lo=bds[i],up=(i+1<bds.length)?bds[i+1]:RAD;
            if(dk>lo&&dk<=up){{var ri=rings[lo];if(ri&&!ri.visible)show=false;break}}
          }}
        }}
        if(show&&!map.hasLayer(m))m.addTo(map);
        else if(!show&&map.hasLayer(m))map.removeLayer(m);
      }});
    }});
    lb.appendChild(cb);lb.appendChild(document.createTextNode(' '+d+' km'));rt.appendChild(lb);
  }});
  rc.classList.remove('hidden');
}}

// --- Multi-radius circles and panel ---
var mrColors={{1:'#e74c3c',3:'#f39c12',5:'#8e44ad'}};
var mrCircles={{}};
if(MR&&MR.length){{
  MR.forEach(function(mr){{
    var col=mrColors[mr.radius_km]||'#3498db';
    var c=L.circle([Z.center_lat,Z.center_lng],{{radius:mr.radius_km*1000,color:col,weight:2,fillColor:col,fillOpacity:.03,dashArray:'6 4'}}).addTo(map);
    c.bindTooltip(mr.radius_km+' km',{{permanent:true,direction:'top',className:''}});
    mrCircles[mr.radius_km]={{circle:c,visible:true}};
  }});
  // Add multi-radius toggles to ring control
  if(rt){{
    var sep=document.createElement('div');sep.style.cssText='margin:6px 0;border-top:1px solid #eee;padding-top:4px;font-size:11px;color:#888';sep.textContent='Anillos multi-radio';rt.appendChild(sep);
    MR.forEach(function(mr){{
      var col=mrColors[mr.radius_km]||'#3498db';
      var lb=document.createElement('label');lb.className='layer-toggle';var cb=document.createElement('input');cb.type='checkbox';cb.checked=true;
      cb.addEventListener('change',(function(rk){{return function(){{
        var mc=mrCircles[rk];if(!mc)return;
        if(this.checked){{mc.circle.addTo(map);mc.visible=true}}else{{map.removeLayer(mc.circle);mc.visible=false}}
      }}}})(mr.radius_km));
      lb.appendChild(cb);
      var sp=document.createElement('span');sp.style.cssText='display:inline-block;width:10px;height:10px;border-radius:50%;background:'+col+';margin:0 4px';
      lb.appendChild(sp);lb.appendChild(document.createTextNode(mr.radius_km+' km'));rt.appendChild(lb);
    }});
  }}
  // Render comparison panel
  var mp=document.getElementById('mr-panel');
  if(mp){{
    var t='<table style="width:100%;border-collapse:collapse;font-size:13px;margin-top:8px"><tr style="background:#f8f9fa">';
    t+='<th style="padding:6px 8px;text-align:left;border:1px solid #dee2e6">Radio</th>';
    t+='<th style="padding:6px 8px;text-align:center;border:1px solid #dee2e6">Comp.</th>';
    t+='<th style="padding:6px 8px;text-align:center;border:1px solid #dee2e6">Compl.</th>';
    t+='<th style="padding:6px 8px;text-align:center;border:1px solid #dee2e6">Población</th>';
    t+='<th style="padding:6px 8px;text-align:center;border:1px solid #dee2e6">Densidad POI</th>';
    t+='<th style="padding:6px 8px;text-align:center;border:1px solid #dee2e6">Actividad (%)</th></tr>';
    // Find best radius (lowest competitor ratio)
    var bestIdx=-1,bestRatio=Infinity;
    MR.forEach(function(mr,i){{var total=mr.competitors+mr.complementary;if(total>0){{var ratio=mr.competitors/total;if(ratio<bestRatio||(ratio===bestRatio&&mr.complementary>(MR[bestIdx]||{{}}).complementary)){{bestRatio=ratio;bestIdx=i}}}}}});
    MR.forEach(function(mr,i){{
      var env=mr.environment_variables||{{}};
      var bg=i===bestIdx?'background:#eafaf1;':'';
      var col=mrColors[mr.radius_km]||'#3498db';
      t+='<tr style="'+bg+'">';
      t+='<td style="padding:4px 8px;border:1px solid #dee2e6;font-weight:600"><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:'+col+';margin-right:4px"></span>'+mr.radius_km+' km</td>';
      t+='<td style="padding:4px 8px;text-align:center;border:1px solid #dee2e6">'+mr.competitors+'</td>';
      t+='<td style="padding:4px 8px;text-align:center;border:1px solid #dee2e6">'+mr.complementary+'</td>';
      t+='<td style="padding:4px 8px;text-align:center;border:1px solid #dee2e6">'+(mr.total_population||0).toLocaleString()+'</td>';
      t+='<td style="padding:4px 8px;text-align:center;border:1px solid #dee2e6">'+(env.poi_density||0).toFixed(2)+' /km²</td>';
      t+='<td style="padding:4px 8px;text-align:center;border:1px solid #dee2e6">'+(env.commercial_activity_index||0).toFixed(1)+'%</td>';
      t+='</tr>';
    }});
    t+='</table>';
    if(bestIdx>=0)t+='<div style="font-size:11px;color:#27ae60;margin-top:4px">★ Mejor radio: '+MR[bestIdx].radius_km+' km (menor competencia relativa)</div>';
    mp.innerHTML='<div style="margin-top:8px"><strong style="font-size:14px;color:#2c3e50">Análisis Multi-Radio</strong>'+t+'</div>';
  }}
}}
</script></body></html>"""


# ---------------------------------------------------------------------------
# PDF helper functions
# ---------------------------------------------------------------------------

def _section(pdf, title: str):
    pdf.set_text_color(44, 62, 80)
    pdf.set_font(_F, "B", 12)
    pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(200, 200, 200)
    pdf.set_line_width(0.3)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(3)


def _sub(pdf, title: str):
    pdf.set_text_color(80, 80, 80)
    pdf.set_font(_F, "BI", 10)
    pdf.cell(0, 6, title, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)


def _row(pdf, label: str, value: str):
    pdf.set_font(_F, "", 10)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(85, 6, label + ":")
    pdf.set_font(_F, "B", 10)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(0, 6, value, new_x="LMARGIN", new_y="NEXT")
