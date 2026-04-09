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

/* ===== Google Categories ===== */
var GOOGLE_CATEGORIES = [
  { value: "restaurant", label: "Restaurante" },
  { value: "cafe", label: "Café" },
  { value: "bakery", label: "Panadería" },
  { value: "bar", label: "Bar" },
  { value: "pharmacy", label: "Farmacia" },
  { value: "grocery_store", label: "Tienda de abarrotes" },
  { value: "supermarket", label: "Supermercado" },
  { value: "clothing_store", label: "Tienda de ropa" },
  { value: "shoe_store", label: "Zapatería" },
  { value: "beauty_salon", label: "Salón de belleza" },
  { value: "hair_care", label: "Peluquería" },
  { value: "gym", label: "Gimnasio" },
  { value: "laundry", label: "Lavandería" },
  { value: "hardware_store", label: "Ferretería" },
  { value: "electronics_store", label: "Electrónica" },
  { value: "pet_store", label: "Mascotas" },
  { value: "veterinary_care", label: "Veterinaria" },
  { value: "dentist", label: "Dentista" },
  { value: "doctor", label: "Consultorio médico" },
  { value: "car_repair", label: "Taller mecánico" },
  { value: "gas_station", label: "Gasolinera" },
  { value: "convenience_store", label: "Tienda de conveniencia" },
  { value: "florist", label: "Florería" },
  { value: "book_store", label: "Librería" },
  { value: "bank", label: "Banco" },
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
  googleAllySelect: document.getElementById('google-ally-select'),
  googleAllyTags: document.getElementById('google-ally-tags'),
  googleCompetitorSelect: document.getElementById('google-competitor-select'),
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

/* ===== Google Category Selectors ===== */
function populateGoogleSelect(selectEl, filterType) {
  var otherCategories = filterType === 'googleAlly' ? appState.googleCompetitorCategories : appState.googleAllyCategories;
  var ownCategories = filterType === 'googleAlly' ? appState.googleAllyCategories : appState.googleCompetitorCategories;

  // Clear all options except the placeholder
  selectEl.innerHTML = '<option value="">Seleccionar categoría Google…</option>';

  GOOGLE_CATEGORIES.forEach(function (cat) {
    // Skip if already selected in either list
    if (ownCategories.indexOf(cat.value) !== -1) return;
    if (otherCategories.indexOf(cat.value) !== -1) return;

    var opt = document.createElement('option');
    opt.value = cat.value;
    opt.textContent = cat.label;
    selectEl.appendChild(opt);
  });
}

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
  // Refresh both selects to remove the selected option
  populateGoogleSelect(dom.googleAllySelect, 'googleAlly');
  populateGoogleSelect(dom.googleCompetitorSelect, 'googleCompetitor');
}

function removeGoogleTag(filterType, value) {
  var categories = filterType === 'googleAlly' ? appState.googleAllyCategories : appState.googleCompetitorCategories;
  var idx = categories.indexOf(value);
  if (idx !== -1) {
    categories.splice(idx, 1);
    renderGoogleTags(filterType);
    populateGoogleSelect(dom.googleAllySelect, 'googleAlly');
    populateGoogleSelect(dom.googleCompetitorSelect, 'googleCompetitor');
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

dom.googleAllySelect.addEventListener('change', function () {
  var val = dom.googleAllySelect.value;
  if (val) {
    addGoogleTag('googleAlly', val);
    dom.googleAllySelect.value = '';
  }
});

dom.googleCompetitorSelect.addEventListener('change', function () {
  var val = dom.googleCompetitorSelect.value;
  if (val) {
    addGoogleTag('googleCompetitor', val);
    dom.googleCompetitorSelect.value = '';
  }
});

// Delegate Google tag removal
document.addEventListener('click', function (e) {
  if (e.target.classList.contains('google-tag-remove')) {
    var ft = e.target.getAttribute('data-google-filter-type');
    var value = e.target.getAttribute('data-value');
    removeGoogleTag(ft, value);
  }
});

// Initialize selects on load
populateGoogleSelect(dom.googleAllySelect, 'googleAlly');
populateGoogleSelect(dom.googleCompetitorSelect, 'googleCompetitor');

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
  };

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

/* ===== Render results ===== */
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

  // Export & new analysis buttons
  dom.exportButtons.classList.remove('hidden');
  dom.btnNewAnalysis.classList.remove('hidden');

  // Render map
  renderBusinesses(data.businesses, data.zone);

  // Draw radius circle
  var radiusKm = clampRadius(dom.radiusSlider.value);
  drawRadiusCircle(data.zone, radiusKm);
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

/* ===== Init map on load ===== */
document.addEventListener('DOMContentLoaded', function () {
  appState.mapInstance = initMap();
});
