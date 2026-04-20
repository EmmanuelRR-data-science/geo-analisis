/* ===== App State ===== */
const appState = {
  analysisResult: null,
  mapInstance: null,
  markers: [],
  isLoading: false,
  errors: [],
  /* Advanced filters & layers */
  allyFilters: [],
  competitorFilters: [],
  radiusCircle: null,
  agebLayers: {},
  layerControl: null,
  activeLayerKeys: [],
  /* Google category filters */
  googleAllyCategories: [],
  googleCompetitorCategories: [],
};

/* ===== Google Categories (Table A – Google Places types) ===== */
var GOOGLE_CATEGORIES = [
  // Automotriz
  { value: "car_dealer", label: "Agencia de autos", group: "Automotriz" },
  { value: "car_rental", label: "Renta de autos", group: "Automotriz" },
  { value: "car_repair", label: "Taller mecánico", group: "Automotriz" },
  { value: "car_wash", label: "Autolavado", group: "Automotriz" },
  { value: "electric_vehicle_charging_station", label: "Estación de carga eléctrica", group: "Automotriz" },
  { value: "gas_station", label: "Gasolinera", group: "Automotriz" },
  { value: "parking", label: "Estacionamiento", group: "Automotriz" },
  { value: "rest_stop", label: "Parada de descanso", group: "Automotriz" },

  // Negocios
  { value: "corporate_office", label: "Oficina corporativa", group: "Negocios" },
  { value: "farm", label: "Granja", group: "Negocios" },
  { value: "ranch", label: "Rancho", group: "Negocios" },

  // Cultura
  { value: "art_gallery", label: "Galería de arte", group: "Cultura" },
  { value: "art_studio", label: "Estudio de arte", group: "Cultura" },
  { value: "auditorium", label: "Auditorio", group: "Cultura" },
  { value: "cultural_landmark", label: "Sitio cultural", group: "Cultura" },
  { value: "historical_place", label: "Lugar histórico", group: "Cultura" },
  { value: "monument", label: "Monumento", group: "Cultura" },
  { value: "museum", label: "Museo", group: "Cultura" },
  { value: "performing_arts_theater", label: "Teatro", group: "Cultura" },
  { value: "sculpture", label: "Escultura", group: "Cultura" },

  // Educación
  { value: "library", label: "Biblioteca", group: "Educación" },
  { value: "preschool", label: "Preescolar", group: "Educación" },
  { value: "primary_school", label: "Escuela primaria", group: "Educación" },
  { value: "school", label: "Escuela", group: "Educación" },
  { value: "secondary_school", label: "Escuela secundaria", group: "Educación" },
  { value: "university", label: "Universidad", group: "Educación" },

  // Entretenimiento y Recreación
  { value: "amusement_center", label: "Centro de diversiones", group: "Entretenimiento" },
  { value: "amusement_park", label: "Parque de diversiones", group: "Entretenimiento" },
  { value: "aquarium", label: "Acuario", group: "Entretenimiento" },
  { value: "banquet_hall", label: "Salón de banquetes", group: "Entretenimiento" },
  { value: "botanical_garden", label: "Jardín botánico", group: "Entretenimiento" },
  { value: "bowling_alley", label: "Boliche", group: "Entretenimiento" },
  { value: "casino", label: "Casino", group: "Entretenimiento" },
  { value: "community_center", label: "Centro comunitario", group: "Entretenimiento" },
  { value: "concert_hall", label: "Sala de conciertos", group: "Entretenimiento" },
  { value: "convention_center", label: "Centro de convenciones", group: "Entretenimiento" },
  { value: "cultural_center", label: "Centro cultural", group: "Entretenimiento" },
  { value: "event_venue", label: "Lugar de eventos", group: "Entretenimiento" },
  { value: "garden", label: "Jardín", group: "Entretenimiento" },
  { value: "hiking_area", label: "Zona de senderismo", group: "Entretenimiento" },
  { value: "historical_landmark", label: "Sitio histórico", group: "Entretenimiento" },
  { value: "internet_cafe", label: "Café internet", group: "Entretenimiento" },
  { value: "karaoke", label: "Karaoke", group: "Entretenimiento" },
  { value: "marina", label: "Marina", group: "Entretenimiento" },
  { value: "movie_rental", label: "Renta de películas", group: "Entretenimiento" },
  { value: "movie_theater", label: "Cine", group: "Entretenimiento" },
  { value: "national_park", label: "Parque nacional", group: "Entretenimiento" },
  { value: "night_club", label: "Antro/Club nocturno", group: "Entretenimiento" },
  { value: "park", label: "Parque", group: "Entretenimiento" },
  { value: "planetarium", label: "Planetario", group: "Entretenimiento" },
  { value: "plaza", label: "Plaza", group: "Entretenimiento" },
  { value: "tourist_attraction", label: "Atracción turística", group: "Entretenimiento" },
  { value: "visitor_center", label: "Centro de visitantes", group: "Entretenimiento" },
  { value: "water_park", label: "Parque acuático", group: "Entretenimiento" },
  { value: "wedding_venue", label: "Lugar para bodas", group: "Entretenimiento" },
  { value: "zoo", label: "Zoológico", group: "Entretenimiento" },

  // Finanzas
  { value: "accounting", label: "Contabilidad", group: "Finanzas" },
  { value: "atm", label: "Cajero automático", group: "Finanzas" },
  { value: "bank", label: "Banco", group: "Finanzas" },

  // Alimentos y Bebidas
  { value: "bakery", label: "Panadería", group: "Alimentos" },
  { value: "bar", label: "Bar", group: "Alimentos" },
  { value: "bar_and_grill", label: "Bar y parrilla", group: "Alimentos" },
  { value: "barbecue_restaurant", label: "Restaurante de barbacoa", group: "Alimentos" },
  { value: "breakfast_restaurant", label: "Restaurante de desayunos", group: "Alimentos" },
  { value: "brunch_restaurant", label: "Restaurante de brunch", group: "Alimentos" },
  { value: "cafe", label: "Café", group: "Alimentos" },
  { value: "candy_store", label: "Dulcería", group: "Alimentos" },
  { value: "chinese_restaurant", label: "Restaurante chino", group: "Alimentos" },
  { value: "coffee_shop", label: "Cafetería", group: "Alimentos" },
  { value: "deli", label: "Delicatessen", group: "Alimentos" },
  { value: "dessert_restaurant", label: "Restaurante de postres", group: "Alimentos" },
  { value: "dessert_shop", label: "Tienda de postres", group: "Alimentos" },
  { value: "fast_food_restaurant", label: "Comida rápida", group: "Alimentos" },
  { value: "fine_dining_restaurant", label: "Restaurante de alta cocina", group: "Alimentos" },
  { value: "food_court", label: "Área de comida", group: "Alimentos" },
  { value: "french_restaurant", label: "Restaurante francés", group: "Alimentos" },
  { value: "greek_restaurant", label: "Restaurante griego", group: "Alimentos" },
  { value: "hamburger_restaurant", label: "Hamburguesería", group: "Alimentos" },
  { value: "ice_cream_shop", label: "Heladería", group: "Alimentos" },
  { value: "indian_restaurant", label: "Restaurante indio", group: "Alimentos" },
  { value: "indonesian_restaurant", label: "Restaurante indonesio", group: "Alimentos" },
  { value: "italian_restaurant", label: "Restaurante italiano", group: "Alimentos" },
  { value: "japanese_restaurant", label: "Restaurante japonés", group: "Alimentos" },
  { value: "juice_shop", label: "Jugería", group: "Alimentos" },
  { value: "korean_restaurant", label: "Restaurante coreano", group: "Alimentos" },
  { value: "lebanese_restaurant", label: "Restaurante libanés", group: "Alimentos" },
  { value: "meal_delivery", label: "Entrega de comida", group: "Alimentos" },
  { value: "meal_takeaway", label: "Comida para llevar", group: "Alimentos" },
  { value: "mediterranean_restaurant", label: "Restaurante mediterráneo", group: "Alimentos" },
  { value: "mexican_restaurant", label: "Restaurante mexicano", group: "Alimentos" },
  { value: "middle_eastern_restaurant", label: "Restaurante del Medio Oriente", group: "Alimentos" },
  { value: "pizza_restaurant", label: "Pizzería", group: "Alimentos" },
  { value: "pub", label: "Pub", group: "Alimentos" },
  { value: "ramen_restaurant", label: "Restaurante de ramen", group: "Alimentos" },
  { value: "restaurant", label: "Restaurante", group: "Alimentos" },
  { value: "sandwich_shop", label: "Sandwichería", group: "Alimentos" },
  { value: "seafood_restaurant", label: "Marisquería", group: "Alimentos" },
  { value: "spanish_restaurant", label: "Restaurante español", group: "Alimentos" },
  { value: "steak_house", label: "Asador/Steakhouse", group: "Alimentos" },
  { value: "sushi_restaurant", label: "Restaurante de sushi", group: "Alimentos" },
  { value: "tea_house", label: "Casa de té", group: "Alimentos" },
  { value: "thai_restaurant", label: "Restaurante tailandés", group: "Alimentos" },
  { value: "turkish_restaurant", label: "Restaurante turco", group: "Alimentos" },
  { value: "vegan_restaurant", label: "Restaurante vegano", group: "Alimentos" },
  { value: "vegetarian_restaurant", label: "Restaurante vegetariano", group: "Alimentos" },
  { value: "vietnamese_restaurant", label: "Restaurante vietnamita", group: "Alimentos" },
  { value: "wine_bar", label: "Bar de vinos", group: "Alimentos" },

  // Gobierno
  { value: "city_hall", label: "Ayuntamiento", group: "Gobierno" },
  { value: "courthouse", label: "Juzgado", group: "Gobierno" },
  { value: "embassy", label: "Embajada", group: "Gobierno" },
  { value: "fire_station", label: "Estación de bomberos", group: "Gobierno" },
  { value: "government_office", label: "Oficina de gobierno", group: "Gobierno" },
  { value: "local_government_office", label: "Oficina de gobierno local", group: "Gobierno" },
  { value: "police", label: "Policía", group: "Gobierno" },
  { value: "post_office", label: "Oficina de correos", group: "Gobierno" },

  // Salud y Bienestar
  { value: "chiropractor", label: "Quiropráctico", group: "Salud" },
  { value: "dental_clinic", label: "Clínica dental", group: "Salud" },
  { value: "dentist", label: "Dentista", group: "Salud" },
  {
    value: "doctor",
    label: "Consultorio médico",
    group: "Salud",
    aliases: ["medico", "médico", "pediatra", "pediatras", "oculista", "oculistas", "oftalmologo", "oftalmólogo", "especialista", "especialidad"]
  },
  { value: "drugstore", label: "Droguería", group: "Salud" },
  { value: "general_hospital", label: "Hospital general", group: "Salud" },
  { value: "hospital", label: "Hospital", group: "Salud" },
  { value: "massage", label: "Masajes", group: "Salud" },
  { value: "massage_spa", label: "Spa de masajes", group: "Salud" },
  {
    value: "medical_center",
    label: "Centro médico",
    group: "Salud",
    aliases: ["centro de salud"]
  },
  {
    value: "medical_clinic",
    label: "Clínica médica",
    group: "Salud",
    aliases: ["clinica", "clínica", "especialidades medicas", "especialidades médicas"]
  },
  { value: "medical_lab", label: "Laboratorio médico", group: "Salud" },
  { value: "pharmacy", label: "Farmacia", group: "Salud" },
  { value: "physiotherapist", label: "Fisioterapeuta", group: "Salud" },
  { value: "sauna", label: "Sauna", group: "Salud" },
  { value: "skin_care_clinic", label: "Clínica de cuidado de piel", group: "Salud" },
  { value: "spa", label: "Spa", group: "Salud" },
  { value: "tanning_studio", label: "Estudio de bronceado", group: "Salud" },
  { value: "wellness_center", label: "Centro de bienestar", group: "Salud" },
  { value: "yoga_studio", label: "Estudio de yoga", group: "Salud" },

  // Hospedaje
  { value: "bed_and_breakfast", label: "Bed & Breakfast", group: "Hospedaje" },
  { value: "campground", label: "Campamento", group: "Hospedaje" },
  { value: "guest_house", label: "Casa de huéspedes", group: "Hospedaje" },
  { value: "hostel", label: "Hostal", group: "Hospedaje" },
  { value: "hotel", label: "Hotel", group: "Hospedaje" },
  { value: "lodging", label: "Alojamiento", group: "Hospedaje" },
  { value: "motel", label: "Motel", group: "Hospedaje" },
  { value: "resort_hotel", label: "Hotel resort", group: "Hospedaje" },
  { value: "rv_park", label: "Parque de RVs", group: "Hospedaje" },

  // Culto
  { value: "church", label: "Iglesia", group: "Culto" },
  { value: "hindu_temple", label: "Templo hindú", group: "Culto" },
  { value: "mosque", label: "Mezquita", group: "Culto" },
  { value: "synagogue", label: "Sinagoga", group: "Culto" },

  // Servicios
  { value: "barber_shop", label: "Barbería", group: "Servicios" },
  { value: "beauty_salon", label: "Salón de belleza", group: "Servicios" },
  { value: "cemetery", label: "Cementerio", group: "Servicios" },
  { value: "child_care_agency", label: "Guardería", group: "Servicios" },
  { value: "consultant", label: "Consultor", group: "Servicios" },
  { value: "electrician", label: "Electricista", group: "Servicios" },
  { value: "florist", label: "Florería", group: "Servicios" },
  { value: "funeral_home", label: "Funeraria", group: "Servicios" },
  { value: "hair_care", label: "Cuidado del cabello", group: "Servicios" },
  { value: "hair_salon", label: "Salón de cabello", group: "Servicios" },
  { value: "insurance_agency", label: "Agencia de seguros", group: "Servicios" },
  { value: "laundry", label: "Lavandería", group: "Servicios" },
  { value: "lawyer", label: "Abogado", group: "Servicios" },
  { value: "locksmith", label: "Cerrajero", group: "Servicios" },
  { value: "moving_company", label: "Mudanzas", group: "Servicios" },
  { value: "nail_salon", label: "Salón de uñas", group: "Servicios" },
  { value: "painter", label: "Pintor", group: "Servicios" },
  { value: "plumber", label: "Plomero", group: "Servicios" },
  { value: "real_estate_agency", label: "Inmobiliaria", group: "Servicios" },
  { value: "roofing_contractor", label: "Techador", group: "Servicios" },
  { value: "storage", label: "Almacenamiento", group: "Servicios" },
  { value: "tailor", label: "Sastre", group: "Servicios" },
  { value: "travel_agency", label: "Agencia de viajes", group: "Servicios" },
  { value: "veterinary_care", label: "Veterinaria", group: "Servicios" },

  // Compras
  { value: "asian_grocery_store", label: "Tienda asiática", group: "Compras" },
  { value: "auto_parts_store", label: "Refaccionaria", group: "Compras" },
  { value: "bicycle_store", label: "Tienda de bicicletas", group: "Compras" },
  { value: "book_store", label: "Librería", group: "Compras" },
  { value: "butcher_shop", label: "Carnicería", group: "Compras" },
  { value: "cell_phone_store", label: "Tienda de celulares", group: "Compras" },
  { value: "clothing_store", label: "Tienda de ropa", group: "Compras" },
  { value: "convenience_store", label: "Tienda de conveniencia", group: "Compras" },
  { value: "department_store", label: "Tienda departamental", group: "Compras" },
  { value: "discount_store", label: "Tienda de descuento", group: "Compras" },
  { value: "electronics_store", label: "Tienda de electrónica", group: "Compras" },
  { value: "food_store", label: "Tienda de alimentos", group: "Compras" },
  { value: "furniture_store", label: "Mueblería", group: "Compras" },
  { value: "gift_shop", label: "Tienda de regalos", group: "Compras" },
  { value: "grocery_store", label: "Tienda de abarrotes", group: "Compras" },
  { value: "hardware_store", label: "Ferretería", group: "Compras" },
  { value: "home_goods_store", label: "Tienda del hogar", group: "Compras" },
  { value: "home_improvement_store", label: "Tienda de mejoras para el hogar", group: "Compras" },
  { value: "jewelry_store", label: "Joyería", group: "Compras" },
  { value: "liquor_store", label: "Licorería", group: "Compras" },
  { value: "market", label: "Mercado", group: "Compras" },
  { value: "pet_store", label: "Tienda de mascotas", group: "Compras" },
  { value: "shoe_store", label: "Zapatería", group: "Compras" },
  { value: "shopping_mall", label: "Centro comercial", group: "Compras" },
  { value: "sporting_goods_store", label: "Tienda deportiva", group: "Compras" },
  { value: "store", label: "Tienda", group: "Compras" },
  { value: "supermarket", label: "Supermercado", group: "Compras" },
  { value: "wholesaler", label: "Mayorista", group: "Compras" },

  // Deportes
  { value: "athletic_field", label: "Campo deportivo", group: "Deportes" },
  { value: "fitness_center", label: "Centro de fitness", group: "Deportes" },
  { value: "golf_course", label: "Campo de golf", group: "Deportes" },
  { value: "gym", label: "Gimnasio", group: "Deportes" },
  { value: "ice_skating_rink", label: "Pista de hielo", group: "Deportes" },
  { value: "playground", label: "Área de juegos", group: "Deportes" },
  { value: "ski_resort", label: "Centro de esquí", group: "Deportes" },
  { value: "sports_club", label: "Club deportivo", group: "Deportes" },
  { value: "sports_complex", label: "Complejo deportivo", group: "Deportes" },
  { value: "stadium", label: "Estadio", group: "Deportes" },

  // Transporte
  { value: "airport", label: "Aeropuerto", group: "Transporte" },
  { value: "bus_station", label: "Estación de autobuses", group: "Transporte" },
  { value: "bus_stop", label: "Parada de autobús", group: "Transporte" },
  { value: "light_rail_station", label: "Estación de tren ligero", group: "Transporte" },
  { value: "subway_station", label: "Estación de metro", group: "Transporte" },
  { value: "taxi_stand", label: "Sitio de taxis", group: "Transporte" },
  { value: "train_station", label: "Estación de tren", group: "Transporte" },
  { value: "transit_station", label: "Estación de tránsito", group: "Transporte" },
];

/* ===== DOM refs ===== */
const dom = {
  form: document.getElementById('analysis-form'),
  businessType: document.getElementById('business-type'),
  zoneInput: document.getElementById('zone-input'),
  zoneSuggestions: document.getElementById('zone-suggestions'),
  formErrors: document.getElementById('form-errors'),
  submitBtn: document.getElementById('submit-btn'),
  warningsArea: document.getElementById('warnings-area'),
  summaryPanel: document.getElementById('summary-panel'),
  scoreGauge: document.getElementById('score-gauge'),
  scoreValue: document.getElementById('score-value'),
  scoreCategory: document.getElementById('score-category'),
  metricCompetitors: document.getElementById('metric-competitors'),
  metricComplementary: document.getElementById('metric-complementary'),
  metricPopulation: document.getElementById('metric-population'),
  recommendationSection: document.getElementById('recommendation-section'),
  recommendationText: document.getElementById('recommendation-text'),
  exportButtons: document.getElementById('export-buttons'),
  btnExportPng: document.getElementById('btn-export-png'),
  btnExportPdf: document.getElementById('btn-export-pdf'),
  btnExportHtml: document.getElementById('btn-export-html'),
  btnNewAnalysis: document.getElementById('btn-new-analysis'),
  loadingOverlay: document.getElementById('loading-overlay'),
  /* Radius controls */
  radiusSlider: document.getElementById('radius-slider'),
  radiusValue: document.getElementById('radius-value'),
  /* Filter controls */
  allyInput: document.getElementById('ally-input'),
  allySuggestions: document.getElementById('ally-suggestions'),
  allyTags: document.getElementById('ally-tags'),
  competitorInput: document.getElementById('competitor-input'),
  competitorSuggestions: document.getElementById('competitor-suggestions'),
  competitorTags: document.getElementById('competitor-tags'),
  /* Layer control */
  layerControl: document.getElementById('layer-control'),
  layerToggles: document.getElementById('layer-toggles'),
  /* Color scale legend */
  colorScaleLegend: document.getElementById('color-scale-legend'),
  colorScaleTitle: document.getElementById('color-scale-title'),
  colorScaleMin: document.getElementById('color-scale-min'),
  colorScaleMax: document.getElementById('color-scale-max'),
  /* Google category controls */
  googleAllyTags: document.getElementById('google-ally-tags'),
  googleCompetitorTags: document.getElementById('google-competitor-tags'),
  /* Strategic recommendations */
  strategicRecommendationsSection: document.getElementById('strategic-recommendations-section'),
  strategicRecommendationsList: document.getElementById('strategic-recommendations-list'),
};

/* ===== Helpers ===== */
function setLoading(on) {
  appState.isLoading = on;
  dom.loadingOverlay.classList.toggle('hidden', !on);
  dom.submitBtn.disabled = on;
}

function showError(message) {
  dom.formErrors.textContent = message;
  dom.formErrors.classList.remove('hidden');
}

function hideError() {
  dom.formErrors.classList.add('hidden');
  dom.formErrors.textContent = '';
}

function renderWarnings(warnings) {
  if (!warnings || warnings.length === 0) {
    dom.warningsArea.classList.add('hidden');
    return;
  }
  dom.warningsArea.innerHTML = warnings.map(function (w) { return '<p>⚠️ ' + escapeHtml(w) + '</p>'; }).join('');
  dom.warningsArea.classList.remove('hidden');
}

// escapeHtml is defined in map.js (loaded first)

function formatNumber(n) {
  if (n == null) return '—';
  return n.toLocaleString('es-MX');
}

function normalizeText(text) {
  return (text || '')
    .toString()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();
}


/* ===== Zone autocomplete ===== */
var zoneDebounceTimer = null;

dom.zoneInput.addEventListener('input', function () {
  clearTimeout(zoneDebounceTimer);
  var q = dom.zoneInput.value.trim();
  if (q.length < 2) {
    dom.zoneSuggestions.classList.add('hidden');
    return;
  }
  zoneDebounceTimer = setTimeout(function () {
    fetch('/api/zones/search?q=' + encodeURIComponent(q))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var zones = data.zones || [];
        if (zones.length === 0) {
          dom.zoneSuggestions.classList.add('hidden');
          return;
        }
        dom.zoneSuggestions.innerHTML = zones.map(function (z) {
          return '<li data-zone="' + escapeHtml(z.name) + '">' + escapeHtml(z.name) + '</li>';
        }).join('');
        dom.zoneSuggestions.classList.remove('hidden');
      })
      .catch(function () {
        dom.zoneSuggestions.classList.add('hidden');
      });
  }, 300);
});

dom.zoneSuggestions.addEventListener('click', function (e) {
  if (e.target.tagName === 'LI') {
    dom.zoneInput.value = e.target.getAttribute('data-zone');
    dom.zoneSuggestions.classList.add('hidden');
  }
});

// Close suggestions on outside click
document.addEventListener('click', function (e) {
  if (!e.target.closest('.zone-group')) {
    dom.zoneSuggestions.classList.add('hidden');
  }
  if (!e.target.closest('#ally-input') && !e.target.closest('#ally-suggestions')) {
    dom.allySuggestions.classList.add('hidden');
  }
  if (!e.target.closest('#competitor-input') && !e.target.closest('#competitor-suggestions')) {
    dom.competitorSuggestions.classList.add('hidden');
  }
});

/* ===== Radius slider + input sync ===== */
function clampRadius(val) {
  var n = parseFloat(val);
  if (isNaN(n)) return 5;
  return Math.min(20, Math.max(0.5, n));
}

dom.radiusSlider.addEventListener('input', function () {
  var v = clampRadius(dom.radiusSlider.value);
  dom.radiusValue.value = v;
});

dom.radiusValue.addEventListener('change', function () {
  var v = clampRadius(dom.radiusValue.value);
  dom.radiusValue.value = v;
  dom.radiusSlider.value = v;
});

/* ===== SCIAN autocomplete ===== */
var scianDebounceTimers = {};

function setupScianAutocomplete(inputEl, suggestionsEl, filterType) {
  inputEl.addEventListener('input', function () {
    clearTimeout(scianDebounceTimers[filterType]);
    var q = inputEl.value.trim();
    if (q.length < 3) {
      suggestionsEl.classList.add('hidden');
      return;
    }
    scianDebounceTimers[filterType] = setTimeout(function () {
      fetch('/api/scian/search?q=' + encodeURIComponent(q))
        .then(function (r) { return r.json(); })
        .then(function (data) {
          var results = data.results || [];
          if (results.length === 0) {
            suggestionsEl.classList.add('hidden');
            return;
          }
          suggestionsEl.innerHTML = results.map(function (item) {
            return '<li data-code="' + escapeHtml(item.code) + '" data-desc="' + escapeHtml(item.description) + '">'
              + '<span class="scian-code">' + escapeHtml(item.code) + '</span>'
              + escapeHtml(item.description)
              + '</li>';
          }).join('');
          suggestionsEl.classList.remove('hidden');
        })
        .catch(function () {
          suggestionsEl.classList.add('hidden');
        });
    }, 300);
  });

  suggestionsEl.addEventListener('click', function (e) {
    var li = e.target.closest('li');
    if (!li) return;
    var code = li.getAttribute('data-code');
    var desc = li.getAttribute('data-desc');
    var label = code + ' - ' + desc;
    addTag(filterType, label);
    inputEl.value = '';
    suggestionsEl.classList.add('hidden');
  });
}

setupScianAutocomplete(dom.allyInput, dom.allySuggestions, 'ally');
setupScianAutocomplete(dom.competitorInput, dom.competitorSuggestions, 'competitor');

/* ===== Tag system ===== */
function addTag(filterType, label) {
  var filters = filterType === 'ally' ? appState.allyFilters : appState.competitorFilters;
  var otherFilters = filterType === 'ally' ? appState.competitorFilters : appState.allyFilters;

  // Prevent duplicates within same list
  if (filters.indexOf(label) !== -1) return;

  // Cross-validation: prevent same category in both
  if (otherFilters.indexOf(label) !== -1) {
    var otherName = filterType === 'ally' ? 'competidores' : 'aliados';
    showError('Esta categoría ya está en ' + otherName + '. No puede estar en ambos.');
    setTimeout(hideError, 3000);
    return;
  }

  filters.push(label);
  renderTags(filterType);
}

function removeTag(filterType, label) {
  var filters = filterType === 'ally' ? appState.allyFilters : appState.competitorFilters;
  var idx = filters.indexOf(label);
  if (idx !== -1) {
    filters.splice(idx, 1);
    renderTags(filterType);
  }
}

function renderTags(filterType) {
  var container = filterType === 'ally' ? dom.allyTags : dom.competitorTags;
  var filters = filterType === 'ally' ? appState.allyFilters : appState.competitorFilters;

  container.innerHTML = filters.map(function (label) {
    return '<span class="tag">'
      + escapeHtml(label)
      + '<button class="tag-remove" data-filter-type="' + filterType + '" data-label="' + escapeHtml(label) + '" type="button" aria-label="Eliminar">&times;</button>'
      + '</span>';
  }).join('');
}

// Delegate tag removal clicks
document.addEventListener('click', function (e) {
  if (e.target.classList.contains('tag-remove')) {
    var ft = e.target.getAttribute('data-filter-type');
    var label = e.target.getAttribute('data-label');
    removeTag(ft, label);
  }
});

/* ===== Google Category Autocomplete ===== */
function addGoogleTag(filterType, value) {
  var categories = filterType === 'googleAlly' ? appState.googleAllyCategories : appState.googleCompetitorCategories;
  var otherCategories = filterType === 'googleAlly' ? appState.googleCompetitorCategories : appState.googleAllyCategories;

  if (categories.indexOf(value) !== -1) return;

  // Cross-validation
  if (otherCategories.indexOf(value) !== -1) {
    var otherName = filterType === 'googleAlly' ? 'competidores Google' : 'aliados Google';
    showError('Esta categoría ya está en ' + otherName + '. No puede estar en ambos.');
    setTimeout(hideError, 3000);
    return;
  }

  categories.push(value);
  renderGoogleTags(filterType);
}

function removeGoogleTag(filterType, value) {
  var categories = filterType === 'googleAlly' ? appState.googleAllyCategories : appState.googleCompetitorCategories;
  var idx = categories.indexOf(value);
  if (idx !== -1) {
    categories.splice(idx, 1);
    renderGoogleTags(filterType);
  }
}

function getGoogleCategoryLabel(value) {
  for (var i = 0; i < GOOGLE_CATEGORIES.length; i++) {
    if (GOOGLE_CATEGORIES[i].value === value) return GOOGLE_CATEGORIES[i].label;
  }
  return value;
}

function renderGoogleTags(filterType) {
  var container = filterType === 'googleAlly' ? dom.googleAllyTags : dom.googleCompetitorTags;
  var categories = filterType === 'googleAlly' ? appState.googleAllyCategories : appState.googleCompetitorCategories;

  container.innerHTML = categories.map(function (value) {
    return '<span class="tag">'
      + escapeHtml(getGoogleCategoryLabel(value))
      + '<button class="tag-remove google-tag-remove" data-google-filter-type="' + filterType + '" data-value="' + escapeHtml(value) + '" type="button" aria-label="Eliminar">&times;</button>'
      + '</span>';
  }).join('');
}

// Delegate Google tag removal
document.addEventListener('click', function (e) {
  if (e.target.classList.contains('google-tag-remove')) {
    var ft = e.target.getAttribute('data-google-filter-type');
    var value = e.target.getAttribute('data-value');
    removeGoogleTag(ft, value);
  }
});

/* ===== Google Category Autocomplete Setup ===== */
function setupGoogleCategoryAutocomplete(inputId, dropdownId, filterType) {
  var input = document.getElementById(inputId);
  var dropdown = document.getElementById(dropdownId);
  if (!input || !dropdown) return;

  input.addEventListener('input', function() {
    var q = normalizeText(input.value.trim());
    if (q.length < 1) { dropdown.classList.add('hidden'); return; }

    var ownCats = filterType === 'googleAlly' ? appState.googleAllyCategories : appState.googleCompetitorCategories;
    var otherCats = filterType === 'googleAlly' ? appState.googleCompetitorCategories : appState.googleAllyCategories;

    var matches = GOOGLE_CATEGORIES.filter(function(cat) {
      if (ownCats.indexOf(cat.value) !== -1 || otherCats.indexOf(cat.value) !== -1) return false;
      var aliases = (cat.aliases || []).map(normalizeText);
      var haystack = [
        normalizeText(cat.label),
        normalizeText(cat.value),
        normalizeText(cat.group)
      ].concat(aliases);
      return haystack.some(function(entry) { return entry.indexOf(q) !== -1; });
    }).slice(0, 15);

    if (matches.length === 0) { dropdown.classList.add('hidden'); return; }

    dropdown.innerHTML = matches.map(function(cat) {
      return '<li data-value="' + cat.value + '"><span class="google-cat-group">' + escapeHtml(cat.group) + '</span> ' + escapeHtml(cat.label) + '</li>';
    }).join('');
    dropdown.classList.remove('hidden');
  });

  dropdown.addEventListener('click', function(e) {
    var li = e.target.closest('li');
    if (!li) return;
    var val = li.getAttribute('data-value');
    addGoogleTag(filterType, val);
    input.value = '';
    dropdown.classList.add('hidden');
  });

  // Close on outside click
  document.addEventListener('click', function(e) {
    if (!e.target.closest('#' + inputId) && !e.target.closest('#' + dropdownId)) {
      dropdown.classList.add('hidden');
    }
  });
}

// Initialize autocomplete for both Google category inputs
setupGoogleCategoryAutocomplete('google-ally-input', 'google-ally-dropdown', 'googleAlly');
setupGoogleCategoryAutocomplete('google-competitor-input', 'google-competitor-dropdown', 'googleCompetitor');

/* ===== Form submission ===== */
dom.form.addEventListener('submit', function (e) {
  e.preventDefault();
  hideError();

  var businessType = dom.businessType.value.trim();
  var zone = dom.zoneInput.value.trim();

  var customLat = document.getElementById('custom-lat').value.trim();
  var customLng = document.getElementById('custom-lng').value.trim();
  var hasCoords = customLat !== '' && customLng !== '';

  // Local validation
  if (!businessType) {
    showError('Por favor ingresa el tipo de negocio.');
    return;
  }

  if (!zone && !hasCoords) {
    showError('Se requiere una zona o coordenadas. Proporciona al menos uno de los dos.');
    return;
  }

  if (hasCoords && (isNaN(parseFloat(customLat)) || isNaN(parseFloat(customLng)))) {
    showError('Las coordenadas deben ser valores numéricos válidos.');
    return;
  }

  var radiusKm = clampRadius(dom.radiusSlider.value);

  setLoading(true);

  var payload = {
    business_type: businessType,
    zone: zone,
    radius_km: radiusKm,
    ally_filters: appState.allyFilters,
    competitor_filters: appState.competitorFilters,
    google_ally_categories: appState.googleAllyCategories,
    google_competitor_categories: appState.googleCompetitorCategories,
    keyword_ally: document.getElementById('keyword-ally').value.trim(),
    keyword_competitor: document.getElementById('keyword-competitor').value.trim(),
  };

  payload.target_profile = document.getElementById('target-profile').value.trim();

  if (hasCoords) {
    payload.custom_lat = parseFloat(customLat);
    payload.custom_lng = parseFloat(customLng);
  }

  fetch('/api/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
    .then(function (response) {
      return response.json().then(function (data) {
        return { ok: response.ok, status: response.status, data: data };
      });
    })
    .then(function (result) {
      setLoading(false);

      if (!result.ok) {
        var msg = result.data.message || 'Error desconocido';
        if (result.data.details) msg += ': ' + result.data.details;
        showError(msg);
        renderWarnings(result.data.warnings || []);
        return;
      }

      appState.analysisResult = result.data;
      renderResults(result.data);
    })
    .catch(function (err) {
      setLoading(false);
      showError('No se pudo conectar con el servidor. Intenta de nuevo.');
      console.error(err);
    });
});

/* ===== Multi-radius panel ===== */
function renderMultiRadiusPanel(multiRadiusResults) {
  var panel = document.getElementById('multi-radius-panel');
  var table = document.getElementById('multi-radius-table');
  if (!panel || !table || !multiRadiusResults || multiRadiusResults.length === 0) {
    if (panel) panel.classList.add('hidden');
    return;
  }

  // Find best radius (lowest competitor ratio)
  var bestIdx = -1;
  var bestRatio = Infinity;
  multiRadiusResults.forEach(function(mr, idx) {
    var total = mr.competitors + mr.complementary;
    var ratio = total > 0 ? mr.competitors / total : 0;
    if (ratio < bestRatio || (ratio === bestRatio && mr.complementary > (multiRadiusResults[bestIdx] || {}).complementary)) {
      bestRatio = ratio;
      bestIdx = idx;
    }
  });

  var html = '<table class="comparison-table"><thead><tr><th>Indicador</th>';
  multiRadiusResults.forEach(function(mr) {
    html += '<th>' + mr.radius_km + ' km</th>';
  });
  html += '</tr></thead><tbody>';

  // Rows
  var rows = [
    { label: 'Competidores', key: 'competitors' },
    { label: 'Complementarios', key: 'complementary' },
    { label: 'Población', key: 'total_population' },
    { label: 'Densidad POI', key: 'poi_density', fromEnv: true, format: 'density' },
    { label: 'Actividad comercial', key: 'commercial_activity_index', fromEnv: true, format: 'pct' },
  ];

  rows.forEach(function(row) {
    html += '<tr><td>' + row.label + '</td>';
    multiRadiusResults.forEach(function(mr, idx) {
      var val;
      if (row.fromEnv) {
        val = mr.environment_variables ? mr.environment_variables[row.key] : null;
      } else {
        val = mr[row.key];
      }
      var cls = idx === bestIdx ? ' class="best-radius"' : '';
      if (val == null) {
        html += '<td' + cls + '>Sin datos</td>';
      } else if (row.format === 'density') {
        html += '<td' + cls + '>' + val.toFixed(2) + ' /km²</td>';
      } else if (row.format === 'pct') {
        html += '<td' + cls + '>' + val.toFixed(1) + '%</td>';
      } else {
        html += '<td' + cls + '>' + formatNumber(val) + '</td>';
      }
    });
    html += '</tr>';
  });

  html += '</tbody></table>';
  table.innerHTML = html;
  panel.classList.remove('hidden');
}

/* ===== Environment variables section ===== */
function renderEnvironmentVars(multiRadiusResults, extendedIndicators) {
  var section = document.getElementById('environment-vars-section');
  var content = document.getElementById('environment-vars-content');
  if (!section || !content) return;

  var html = '';

  // Commercial activity subsection (from multi-radius, use the largest radius available)
  var mainMr = null;
  if (multiRadiusResults && multiRadiusResults.length > 0) {
    mainMr = multiRadiusResults[multiRadiusResults.length - 1]; // largest radius
  }
  if (mainMr && mainMr.environment_variables) {
    var env = mainMr.environment_variables;
    html += '<h3>Actividad Comercial</h3><div class="env-vars-grid">';
    html += '<div class="env-var"><span class="env-label">Densidad POI</span><span class="env-value">' + (env.poi_density || 0).toFixed(2) + ' /km²</span></div>';
    html += '<div class="env-var"><span class="env-label">Índice de actividad comercial</span><span class="env-value">' + (env.commercial_activity_index || 0).toFixed(1) + '%</span></div>';
    // Top sectors
    if (env.sector_concentration && env.sector_concentration.length > 0) {
      html += '<div class="env-var full-width"><span class="env-label">Concentración sectorial (top 5)</span><ul class="sector-list">';
      env.sector_concentration.slice(0, 5).forEach(function(s) {
        html += '<li>' + escapeHtml(s.sector) + ' (' + s.code_2d + '): ' + s.count + ' negocios (' + s.percentage.toFixed(1) + '%)</li>';
      });
      html += '</ul></div>';
    }
    html += '</div>';
  }

  // Extended demographic indicators
  if (extendedIndicators && Object.keys(extendedIndicators).length > 0) {
    var ei = extendedIndicators;
    html += '<h3>Perfil Demográfico Ampliado</h3><div class="env-vars-grid">';
    if (ei.unemployment_rate != null) html += '<div class="env-var"><span class="env-label">Tasa de desempleo</span><span class="env-value">' + ei.unemployment_rate.toFixed(1) + '%</span></div>';
    if (ei.economic_participation_rate != null) html += '<div class="env-var"><span class="env-label">Participación económica</span><span class="env-value">' + ei.economic_participation_rate.toFixed(1) + '%</span></div>';
    if (ei.dependency_index != null) html += '<div class="env-var"><span class="env-label">Índice de dependencia</span><span class="env-value">' + ei.dependency_index.toFixed(1) + '%</span></div>';
    if (ei.pct_with_refrigerator != null) html += '<div class="env-var"><span class="env-label">Viviendas con refrigerador</span><span class="env-value">' + ei.pct_with_refrigerator.toFixed(1) + '%</span></div>';
    if (ei.pct_with_washing_machine != null) html += '<div class="env-var"><span class="env-label">Viviendas con lavadora</span><span class="env-value">' + ei.pct_with_washing_machine.toFixed(1) + '%</span></div>';
    html += '</div>';
  }

  if (html) {
    content.innerHTML = html;
    section.classList.remove('hidden');
  } else {
    section.classList.add('hidden');
  }
}

/* ===== Render results ===== */
var DAY_NAMES_ES = {Monday:'Lun',Tuesday:'Mar',Wednesday:'Mié',Thursday:'Jue',Friday:'Vie',Saturday:'Sáb',Sunday:'Dom'};
var DAY_ORDER = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];

function renderFootTrafficHeatmap(ztp) {
  var section = document.getElementById('foot-traffic-section');
  var heatmapDiv = document.getElementById('foot-traffic-heatmap');
  var summaryDiv = document.getElementById('foot-traffic-summary');
  if (!section || !heatmapDiv || !ztp || !ztp.hourly_matrix) {
    if (section) section.classList.add('hidden');
    return;
  }

  // Build heatmap table
  var html = '<table class="heatmap-table"><thead><tr><th></th>';
  // Hours: 6AM to 5AM (indices 0-23 map to hours 6,7,...,23,0,1,2,3,4,5)
  for (var i = 0; i < 24; i++) {
    var h = (i + 6) % 24;
    html += '<th>' + h + '</th>';
  }
  html += '</tr></thead><tbody>';

  DAY_ORDER.forEach(function(day) {
    var hours = ztp.hourly_matrix[day] || [];
    html += '<tr><td class="day-label">' + (DAY_NAMES_ES[day] || day) + '</td>';
    for (var i = 0; i < 24; i++) {
      var val = hours[i] || 0;
      var color = getHeatColor(val);
      var hour = (i + 6) % 24;
      html += '<td class="heatmap-cell" style="background:' + color + '" title="' + (DAY_NAMES_ES[day]||day) + ' ' + hour + ':00 — ' + Math.round(val) + '%"></td>';
    }
    html += '</tr>';
  });
  html += '</tbody></table>';
  heatmapDiv.innerHTML = html;

  // Summary
  var busyEs = DAY_NAMES_ES[ztp.busiest_day] || ztp.busiest_day;
  var quietEs = DAY_NAMES_ES[ztp.quietest_day] || ztp.quietest_day;
  summaryDiv.innerHTML = '<p class="foot-traffic-summary">'
    + '<strong>Día más concurrido:</strong> ' + busyEs
    + ' · <strong>Día más tranquilo:</strong> ' + quietEs
    + ' · <strong>Permanencia promedio:</strong> ' + (ztp.avg_dwell_time_minutes || 0).toFixed(0) + ' min'
    + ' · <strong>Datos de:</strong> ' + (ztp.venues_with_data || 0) + '/' + (ztp.venues_total || 0) + ' competidores'
    + '</p>';

  section.classList.remove('hidden');
}

function getHeatColor(val) {
  // 0=green, 50=yellow, 100=red
  val = Math.max(0, Math.min(100, val));
  if (val <= 50) {
    var r = Math.round(34 + (245 - 34) * (val / 50));
    var g = Math.round(197 + (158 - 197) * (val / 50));
    var b = Math.round(94 + (11 - 94) * (val / 50));
  } else {
    var r = Math.round(245 + (239 - 245) * ((val - 50) / 50));
    var g = Math.round(158 + (68 - 158) * ((val - 50) / 50));
    var b = Math.round(11 + (68 - 11) * ((val - 50) / 50));
  }
  return 'rgb(' + r + ',' + g + ',' + b + ')';
}

function renderResults(data) {
  // Hide form, show results
  dom.form.classList.add('hidden');

  // Warnings
  renderWarnings(data.warnings);

  // Score
  var score = Math.round(data.viability.score);
  var category = data.viability.category;
  var colorClass = getColorClass(category);

  dom.scoreGauge.className = 'score-gauge ' + colorClass;
  dom.scoreValue.textContent = score;
  dom.scoreCategory.textContent = category;
  dom.scoreCategory.className = 'score-category badge ' + colorClass;

  // Metrics
  var competitors = data.businesses.filter(function (b) { return b.classification === 'competitor'; }).length;
  var complementary = data.businesses.filter(function (b) { return b.classification === 'complementary'; }).length;
  var population = data.ageb_data.total_population;

  dom.metricCompetitors.textContent = formatNumber(competitors);
  dom.metricComplementary.textContent = formatNumber(complementary);
  dom.metricPopulation.textContent = formatNumber(population);

  dom.summaryPanel.classList.remove('hidden');

  // Recommendation
  dom.recommendationText.textContent = data.recommendation_text;
  dom.recommendationSection.classList.remove('hidden');

  // Strategic recommendations
  if (data.strategic_recommendations && data.strategic_recommendations.length > 0) {
    dom.strategicRecommendationsList.innerHTML = data.strategic_recommendations.map(function (rec, i) {
      return '<li>' + escapeHtml(rec) + '</li>';
    }).join('');
    dom.strategicRecommendationsSection.classList.remove('hidden');
  } else {
    dom.strategicRecommendationsSection.classList.add('hidden');
  }

  // Multi-radius panel
  renderMultiRadiusPanel(data.multi_radius_results);

  // Environment variables
  renderEnvironmentVars(data.multi_radius_results, data.ageb_data.extended_indicators);

  // Foot traffic heatmap
  renderFootTrafficHeatmap(data.zone_traffic_profile);

  // Export & new analysis buttons
  dom.exportButtons.classList.remove('hidden');
  dom.btnNewAnalysis.classList.remove('hidden');

  // Target market sections
  renderTargetMarket(data);
  renderCompetitorValue(data);
  renderTargetInsights(data);

  // Comparison buttons
  document.getElementById('comparison-buttons').classList.remove('hidden');
  updateSavedBadge();

  // Render map
  renderBusinesses(data.businesses, data.zone);

  // Draw radius circle
  var radiusKm = clampRadius(dom.radiusSlider.value);
  drawRadiusCircle(data.zone, radiusKm);

  // Draw multi-radius circles (1, 3, 5 km)
  drawMultiRadiusCircles(data.zone);
}

function getColorClass(category) {
  if (category === 'Recomendable') return 'green';
  if (category === 'Viable con enfoque estratégico') return 'amber';
  return 'red';
}

/* ===== New analysis ===== */
dom.btnNewAnalysis.addEventListener('click', function () {
  // Show form again, preserve values
  dom.form.classList.remove('hidden');
  dom.summaryPanel.classList.add('hidden');
  dom.recommendationSection.classList.add('hidden');
  dom.strategicRecommendationsSection.classList.add('hidden');
  dom.exportButtons.classList.add('hidden');
  dom.btnNewAnalysis.classList.add('hidden');
  dom.warningsArea.classList.add('hidden');
  document.getElementById('multi-radius-panel').classList.add('hidden');
  document.getElementById('environment-vars-section').classList.add('hidden');
  document.getElementById('foot-traffic-section').classList.add('hidden');
  document.getElementById('target-market-section').classList.add('hidden');
  document.getElementById('competitor-value-section').classList.add('hidden');
  document.getElementById('target-insights-section').classList.add('hidden');
  document.getElementById('comparison-buttons').classList.add('hidden');
  document.getElementById('comparison-view').classList.add('hidden');
  hideError();

  // Clear radius elements
  clearRadiusElements();
});

/* ===== Export PNG ===== */
dom.btnExportPng.addEventListener('click', function () {
  exportMapAsPng();
});

/* ===== Export PDF ===== */
dom.btnExportPdf.addEventListener('click', function () {
  if (!appState.analysisResult) return;
  exportAnalysisAsPdf(appState.analysisResult.analysis_id, dom.btnExportPdf);
});

/* ===== Export HTML ===== */
dom.btnExportHtml.addEventListener('click', function () {
  if (!appState.analysisResult) return;

  var btn = dom.btnExportHtml;
  btn.disabled = true;
  btn.textContent = 'Generando…';

  fetch('/api/export/html', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      analysis_id: appState.analysisResult.analysis_id,
      active_layers: appState.activeLayerKeys,
      radius_km: clampRadius(dom.radiusSlider.value),
    }),
  })
    .then(function (resp) {
      if (!resp.ok) throw new Error('HTML export failed');
      return resp.blob();
    })
    .then(function (blob) {
      var link = document.createElement('a');
      var zoneName = appState.analysisResult.zone
        ? appState.analysisResult.zone.name.toLowerCase().replace(/\s+/g, '-')
        : 'zona';
      link.download = 'mapa-viabilidad-' + zoneName + '.html';
      link.href = URL.createObjectURL(blob);
      link.click();
    })
    .catch(function () {
      alert('No se pudo generar el mapa HTML. Intenta de nuevo.');
    })
    .finally(function () {
      btn.disabled = false;
      btn.textContent = 'Descargar Mapa (HTML)';
    });
});

/* ===== Target market rendering ===== */
function renderTargetMarket(data) {
  var section = document.getElementById('target-market-section');
  var content = document.getElementById('target-market-content');
  if (!section || !content || data.target_match_percentage == null) {
    if (section) section.classList.add('hidden');
    return;
  }
  var pct = data.target_match_percentage;
  var pop = data.target_match_population || 0;
  var colorClass = pct >= 30 ? 'green' : (pct >= 15 ? 'amber' : 'red');
  var html = '<div class="target-profile-desc">' + escapeHtml(data.target_profile || '') + '</div>';
  html += '<div class="match-bar-container"><div class="match-bar ' + colorClass + '" style="width:' + Math.min(pct, 100) + '%"></div><span class="match-pct">' + pct.toFixed(1) + '%</span></div>';
  html += '<p class="match-pop">Población estimada: <strong>' + formatNumber(pop) + '</strong> personas</p>';
  if (data.target_match_breakdown) {
    var bd = data.target_match_breakdown;
    html += '<div class="match-breakdown"><span>Género: ' + (bd.gender_factor * 100).toFixed(0) + '%</span><span>Edad: ' + (bd.age_factor * 100).toFixed(0) + '%</span><span>NSE: ' + (bd.socioeconomic_factor * 100).toFixed(0) + '%</span></div>';
  }
  content.innerHTML = html;
  section.classList.remove('hidden');
}

function renderCompetitorValue(data) {
  var section = document.getElementById('competitor-value-section');
  var content = document.getElementById('competitor-value-content');
  if (!section || !content) return;
  var vps = data.competitor_value_points;
  var ios = data.competitor_improvement_opportunities;
  if ((!vps || !vps.length) && (!ios || !ios.length)) { section.classList.add('hidden'); return; }
  var html = '';
  if (vps && vps.length) {
    html += '<h3>✅ Lo que valoran los clientes</h3><ul class="value-list">';
    vps.forEach(function(vp) { html += '<li class="value-item positive"><strong>' + escapeHtml(vp.title) + '</strong><p>' + escapeHtml(vp.description) + '</p></li>'; });
    html += '</ul>';
  }
  if (ios && ios.length) {
    html += '<h3>⚡ Oportunidades de mejora</h3><ul class="value-list">';
    ios.forEach(function(io) { html += '<li class="value-item opportunity"><strong>' + escapeHtml(io.issue) + '</strong><p class="recommendation">💡 ' + escapeHtml(io.recommendation) + '</p></li>'; });
    html += '</ul>';
  }
  content.innerHTML = html;
  section.classList.remove('hidden');
}

function renderTargetInsights(data) {
  var section = document.getElementById('target-insights-section');
  var content = document.getElementById('target-insights-content');
  if (!section || !content || !data.target_customer_insights || !data.target_customer_insights.length) {
    if (section) section.classList.add('hidden');
    return;
  }
  var html = '<ul class="insights-list">';
  data.target_customer_insights.forEach(function(insight) {
    html += '<li class="insight-item"><strong>' + escapeHtml(insight.title) + '</strong><p>' + escapeHtml(insight.explanation) + '</p></li>';
  });
  html += '</ul>';
  content.innerHTML = html;
  section.classList.remove('hidden');
}

/* ===== Comparison: localStorage save/manage ===== */
var STORAGE_KEY = 'geoanalisis_saved';
var MAX_SAVED = 10;

function getSavedAnalyses() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]'); }
  catch(e) { localStorage.setItem(STORAGE_KEY, '[]'); return []; }
}

function saveAnalysis() {
  var data = appState.analysisResult;
  if (!data) return;
  var saved = getSavedAnalyses();
  if (saved.length >= MAX_SAVED) { alert('Has alcanzado el límite de 10 análisis guardados. Elimina uno existente.'); return; }
  saved.push({
    id: data.analysis_id,
    savedAt: new Date().toISOString(),
    zoneName: data.zone.name,
    businessType: data.business_type.original_input,
    score: Math.round(data.viability.score),
    category: data.viability.category,
    competitors: data.businesses.filter(function(b){return b.classification==='competitor'}).length,
    complementary: data.businesses.filter(function(b){return b.classification==='complementary'}).length,
    population: data.ageb_data.total_population,
    socioeconomicLevel: data.ageb_data.socioeconomic_level,
    matchPercentage: data.target_match_percentage || null,
  });
  localStorage.setItem(STORAGE_KEY, JSON.stringify(saved));
  updateSavedBadge();
  alert('Análisis guardado para comparación.');
}

function deleteSavedAnalysis(id) {
  var saved = getSavedAnalyses().filter(function(s){return s.id !== id});
  localStorage.setItem(STORAGE_KEY, JSON.stringify(saved));
  updateSavedBadge();
  renderComparisonView();
}

function updateSavedBadge() {
  var saved = getSavedAnalyses();
  var badge = document.getElementById('saved-count-badge');
  var btnCompare = document.getElementById('btn-compare');
  if (badge) { badge.textContent = saved.length; badge.classList.toggle('hidden', saved.length === 0); }
  if (btnCompare) btnCompare.disabled = saved.length < 2;
}

/* ===== Comparison view ===== */
function showComparisonView() {
  document.getElementById('summary-panel').classList.add('hidden');
  document.getElementById('recommendation-section').classList.add('hidden');
  document.getElementById('strategic-recommendations-section').classList.add('hidden');
  document.getElementById('target-market-section').classList.add('hidden');
  document.getElementById('competitor-value-section').classList.add('hidden');
  document.getElementById('target-insights-section').classList.add('hidden');
  document.getElementById('multi-radius-panel').classList.add('hidden');
  document.getElementById('environment-vars-section').classList.add('hidden');
  document.getElementById('foot-traffic-section').classList.add('hidden');
  document.getElementById('export-buttons').classList.add('hidden');
  document.getElementById('comparison-buttons').classList.add('hidden');
  document.getElementById('btn-new-analysis').classList.add('hidden');
  document.getElementById('comparison-view').classList.remove('hidden');
  renderComparisonView();
}

function hideComparisonView() {
  document.getElementById('comparison-view').classList.add('hidden');
  document.getElementById('summary-panel').classList.remove('hidden');
  document.getElementById('recommendation-section').classList.remove('hidden');
  document.getElementById('export-buttons').classList.remove('hidden');
  document.getElementById('comparison-buttons').classList.remove('hidden');
  document.getElementById('btn-new-analysis').classList.remove('hidden');
  if (appState.analysisResult) renderResults(appState.analysisResult);
}

function renderComparisonView() {
  var container = document.getElementById('comparison-table-container');
  var saved = getSavedAnalyses();
  if (!container || saved.length < 2) { container.innerHTML = '<p>Se necesitan al menos 2 análisis guardados.</p>'; return; }

  var bestIdx = 0;
  saved.forEach(function(s, i) { if (s.score > saved[bestIdx].score) bestIdx = i; });

  var html = '<table class="comparison-table"><thead><tr><th>Métrica</th>';
  saved.forEach(function(s) { html += '<th>' + escapeHtml(s.zoneName) + '</th>'; });
  html += '</tr></thead><tbody>';

  var rows = [
    {label:'Negocio', key:'businessType'},
    {label:'Puntaje', key:'score', highlight:true},
    {label:'Categoría', key:'category'},
    {label:'Competidores', key:'competitors'},
    {label:'Complementarios', key:'complementary'},
    {label:'Población', key:'population', fmt:'number'},
    {label:'Nivel socioeconómico', key:'socioeconomicLevel'},
    {label:'% Perfil objetivo', key:'matchPercentage', fmt:'pct'},
    {label:'Fecha', key:'savedAt', fmt:'date'},
  ];

  rows.forEach(function(row) {
    html += '<tr><td><strong>' + row.label + '</strong></td>';
    saved.forEach(function(s, i) {
      var val = s[row.key];
      var cls = (row.highlight && i === bestIdx) ? ' class="best-score"' : '';
      if (val == null) html += '<td' + cls + '>—</td>';
      else if (row.fmt === 'number') html += '<td' + cls + '>' + formatNumber(val) + '</td>';
      else if (row.fmt === 'pct') html += '<td' + cls + '>' + val.toFixed(1) + '%</td>';
      else if (row.fmt === 'date') html += '<td' + cls + '>' + new Date(val).toLocaleDateString('es-MX') + '</td>';
      else html += '<td' + cls + '>' + escapeHtml(String(val)) + '</td>';
    });
    html += '</tr>';
  });

  // Delete row
  html += '<tr><td></td>';
  saved.forEach(function(s) { html += '<td><button class="delete-btn" onclick="deleteSavedAnalysis(\'' + s.id + '\')">🗑️ Eliminar</button></td>'; });
  html += '</tr></tbody></table>';

  container.innerHTML = html;
}

/* ===== Comparison button wiring ===== */
document.getElementById('btn-save-compare').addEventListener('click', saveAnalysis);
document.getElementById('btn-compare').addEventListener('click', function() { showComparisonView(); });
document.getElementById('btn-back-from-compare').addEventListener('click', function() { hideComparisonView(); });

/* ===== Init map on load ===== */
document.addEventListener('DOMContentLoaded', function () {
  appState.mapInstance = initMap();
});
