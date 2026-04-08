"""Export service — PDF and standalone HTML generation."""

from __future__ import annotations

import html as html_mod
import json
import logging
import tempfile
import base64
from datetime import datetime, timezone

from app.models.schemas import AnalysisResult

logger = logging.getLogger(__name__)

# Font family — will be set to "Uni" (Arial Unicode) or "Helvetica" (fallback)
_F = "Helvetica"


def _setup_pdf_font(pdf) -> str:
    """Register Arial Unicode font if available, return font family name."""
    global _F
    import os as _os
    _winfonts = _os.path.join(_os.environ.get("WINDIR", "C:\\Windows"), "Fonts")
    _arial = _os.path.join(_winfonts, "arial.ttf")
    if _os.path.exists(_arial):
        pdf.add_font("Uni", "", fname=_arial)
        pdf.add_font("Uni", "B", fname=_os.path.join(_winfonts, "arialbd.ttf"))
        pdf.add_font("Uni", "I", fname=_os.path.join(_winfonts, "ariali.ttf"))
        pdf.add_font("Uni", "BI", fname=_os.path.join(_winfonts, "arialbi.ttf"))
        _F = "Uni"
    else:
        _F = "Helvetica"
    return _F


class ExportService:
    """Generates PDF and HTML reports from analysis results."""

    @staticmethod
    def generate_pdf(analysis_result: AnalysisResult, map_image_bytes: bytes) -> bytes:
        from fpdf import FPDF

        result = analysis_result
        ageb = result.ageb_data
        now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
        score = round(result.viability.score)
        category = result.viability.category
        zone_name = result.zone.name
        business_type = result.business_type.original_input
        recommendation = result.recommendation_text or "Sin recomendación disponible."

        competitors = sum(1 for b in result.businesses if b.classification == "competitor")
        complementary = sum(1 for b in result.businesses if b.classification == "complementary")

        if category == "Recomendable":
            cr, cg, cb = 39, 174, 96
        elif category == "Viable con reservas":
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

        # --- Ecosistema comercial ---
        unclassified = len(result.businesses) - competitors - complementary
        _section(pdf, "Ecosistema Comercial")
        _row(pdf, "Competidores directos", str(competitors))
        _row(pdf, "Negocios complementarios", str(complementary))
        if unclassified > 0:
            _row(pdf, "Sin clasificar", str(unclassified))
        _row(pdf, "Total de negocios analizados", str(len(result.businesses)))
        pdf.ln(4)

        # --- Detalle de negocios ---
        if result.businesses:
            _section(pdf, "Detalle de Negocios Encontrados")
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

        # --- Datos demográficos AGEB ---
        _section(pdf, "Datos Demográficos (INEGI — AGEB)")
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

        # --- Factores de viabilidad ---
        _section(pdf, "Desglose de Factores de Viabilidad")
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

        # --- Recomendación ---
        _section(pdf, "Recomendación")
        pdf.set_font(_F, "", 10)
        pdf.set_text_color(60, 60, 60)
        pdf.multi_cell(0, 5.5, recommendation)
        pdf.ln(4)

        # --- Mapa ---
        if map_image_bytes:
            if pdf.get_y() > 160:
                pdf.add_page()
            _section(pdf, "Mapa de la Zona")
            try:
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp.write(map_image_bytes)
                    tmp_path = tmp.name
                pdf.image(tmp_path, x=10, w=190)
                import os
                os.unlink(tmp_path)
            except Exception as e:
                logger.warning("Could not embed map image: %s", e)

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

        cat_color = "#27ae60" if category == "Recomendable" else ("#f39c12" if category == "Viable con reservas" else "#e74c3c")
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
<div class="legend"><div class="item"><div class="dot" style="background:#22c55e"></div> Complementario</div><div class="item"><div class="dot" style="background:#ef4444"></div> Competidor</div></div>
<div class="map-wrapper"><div id="map"></div>{layer_html}</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
var B={businesses_json},Z={zone_json},S={summary_json},AL={ageb_layers_json};
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
