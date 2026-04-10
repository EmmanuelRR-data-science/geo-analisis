/* ===== Map module (Leaflet) ===== */

/* Utility: escape HTML to prevent XSS in popups */
function escapeHtml(text) {
  if (text == null) return '';
  var d = document.createElement('div');
  d.textContent = String(text);
  return d.innerHTML;
}

function initMap() {
  var map = L.map('map', { center: [19.4326, -99.1332], zoom: 12, zoomControl: true });
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 19,
  }).addTo(map);
  return map;
}

/* ===== Business markers ===== */

/**
 * Haversine distance in km between two lat/lng points.
 */
function haversineKm(lat1, lng1, lat2, lng2) {
  var R = 6371;
  var dLat = (lat2 - lat1) * Math.PI / 180;
  var dLng = (lng2 - lng1) * Math.PI / 180;
  var a = Math.sin(dLat/2) * Math.sin(dLat/2) +
          Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
          Math.sin(dLng/2) * Math.sin(dLng/2);
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function renderBusinesses(businesses, zone) {
  var map = appState.mapInstance;
  if (!map) { console.error('Map not initialized'); return; }
  map.invalidateSize();

  // Clear previous
  appState.markers.forEach(function (m) { map.removeLayer(m); });
  appState.markers = [];
  if (appState._zoneRect) { map.removeLayer(appState._zoneRect); appState._zoneRect = null; }

  // Determine center for distance calculation
  var cLat = zone && zone.center_lat != null ? zone.center_lat : 0;
  var cLng = zone && zone.center_lng != null ? zone.center_lng : 0;

  businesses.forEach(function (biz) {
    if (biz.classification === 'unclassified') return;
    if (!biz.lat || !biz.lng) return;
    var color = biz.classification === 'complementary' ? '#22c55e' : '#ef4444';
    var marker = L.circleMarker([biz.lat, biz.lng], {
      radius: 10, fillColor: color, color: '#fff', weight: 2, opacity: 1, fillOpacity: 0.85,
    });
    var popupContent = buildPopupHtml(biz);
    marker.bindPopup(popupContent, { maxWidth: 320, closeButton: true });
    // Store distance from center on the marker for ring filtering
    marker._distKm = haversineKm(cLat, cLng, biz.lat, biz.lng);
    marker.addTo(map);
    appState.markers.push(marker);
  });

  // Fit bounds
  if (zone && zone.bbox) {
    var bbox = zone.bbox;
    var bounds = L.latLngBounds([bbox.min_lat, bbox.min_lng], [bbox.max_lat, bbox.max_lng]);
    appState.markers.forEach(function (m) { bounds.extend(m.getLatLng()); });
    map.fitBounds(bounds, { padding: [40, 40] });
  } else if (appState.markers.length > 0) {
    map.fitBounds(L.latLngBounds(appState.markers.map(function (m) { return m.getLatLng(); })), { padding: [40, 40] });
  }
}

/* ===== Popup builder ===== */

function buildPopupHtml(biz) {
  var html = '<div class="business-popup">';
  html += '<h3>' + escapeHtml(biz.name) + '</h3>';
  html += '<p>' + escapeHtml(biz.category) + '</p>';
  var cl = biz.classification === 'complementary' ? 'Complementario' : 'Competidor';
  html += '<span class="popup-badge ' + biz.classification + '">' + cl + '</span> ';
  var rl = biz.relevance === 'high' ? 'Alta' : (biz.relevance === 'medium' ? 'Media' : 'Baja');
  html += '<span class="popup-badge ' + biz.relevance + '">Relevancia: ' + rl + '</span>';

  if (biz.google_rating != null || biz.google_reviews_count != null) {
    html += '<div class="popup-section"><div class="popup-section-title">Datos Google Places</div>';
    if (biz.google_rating != null) html += '<p><span class="popup-stars">' + renderStars(biz.google_rating) + '</span> ' + biz.google_rating.toFixed(1) + '</p>';
    if (biz.google_reviews_count != null) html += '<p>' + biz.google_reviews_count.toLocaleString('es-MX') + ' reseñas</p>';
    if (biz.google_hours && biz.google_hours.length > 0) html += '<p><strong>Horario:</strong><br>' + biz.google_hours.map(escapeHtml).join('<br>') + '</p>';
    if (biz.google_is_open != null) html += '<p class="' + (biz.google_is_open ? 'popup-open' : 'popup-closed') + '">● ' + (biz.google_is_open ? 'Abierto ahora' : 'Cerrado') + '</p>';
    html += '</div>';
  }
  if (biz.denue_scian_code != null) {
    html += '<div class="popup-section"><div class="popup-section-title">Datos DENUE</div>';
    if (biz.denue_employee_stratum) html += '<p><strong>Personal:</strong> ' + escapeHtml(biz.denue_employee_stratum) + '</p>';
    if (biz.denue_registration_date) html += '<p><strong>Fecha de alta:</strong> ' + escapeHtml(biz.denue_registration_date) + '</p>';
    if (biz.denue_scian_code) html += '<p><strong>SCIAN:</strong> ' + escapeHtml(biz.denue_scian_code) + '</p>';
    if (biz.denue_legal_name) html += '<p><strong>Razón social:</strong> ' + escapeHtml(biz.denue_legal_name) + '</p>';
    if (biz.denue_address) html += '<p><strong>Domicilio:</strong> ' + escapeHtml(biz.denue_address) + '</p>';
    html += '</div>';
  }
  return html + '</div>';
}

function renderStars(rating) {
  var full = Math.floor(rating);
  var half = rating - full >= 0.5 ? 1 : 0;
  var empty = 5 - full - half;
  return '★'.repeat(full) + (half ? '½' : '') + '☆'.repeat(empty);
}


/* ===== Radius circles with center marker and inner rings ===== */

/**
 * Compute inner ring distances for a given radius.
 * Returns an array of distances in km (excluding the outer radius itself).
 */
function computeInnerRings(radiusKm) {
  var rings = [];
  if (radiusKm >= 3) rings.push(1);
  if (radiusKm >= 6) rings.push(3);
  if (radiusKm >= 10) rings.push(5);
  if (radiusKm >= 15) rings.push(10);
  // Always add a mid-point ring if none computed
  if (rings.length === 0 && radiusKm > 1) {
    rings.push(Math.round(radiusKm / 2 * 10) / 10);
  }
  return rings.filter(function (r) { return r < radiusKm; });
}

/**
 * Draw center marker, outer radius circle, and inner rings.
 * @param {Object} zone - zone with center_lat, center_lng
 * @param {number} radiusKm - outer radius in km
 */
function drawRadiusCircles(zone, radiusKm) {
  var map = appState.mapInstance;
  if (!map || !zone) return;

  // Clear previous radius elements
  clearRadiusElements();

  var lat = zone.center_lat != null ? zone.center_lat : (zone.bbox ? (zone.bbox.min_lat + zone.bbox.max_lat) / 2 : null);
  var lng = zone.center_lng != null ? zone.center_lng : (zone.bbox ? (zone.bbox.min_lng + zone.bbox.max_lng) / 2 : null);
  if (lat == null || lng == null) return;

  // Center marker
  appState._centerMarker = L.marker([lat, lng], {
    icon: L.divIcon({
      className: 'center-marker-icon',
      html: '<div style="width:14px;height:14px;background:#3b82f6;border:3px solid #fff;border-radius:50%;box-shadow:0 0 6px rgba(0,0,0,0.4);"></div>',
      iconSize: [14, 14],
      iconAnchor: [7, 7],
    }),
    zIndexOffset: 1000,
  }).addTo(map);
  appState._centerMarker.bindTooltip('Centro de búsqueda', { direction: 'top', offset: [0, -10] });

  // Outer radius circle (always visible)
  appState._outerCircle = L.circle([lat, lng], {
    radius: radiusKm * 1000,
    color: '#3b82f6',
    weight: 2,
    fillColor: '#3b82f6',
    fillOpacity: 0.04,
    dashArray: '8 4',
  }).addTo(map);

  // Label for outer circle
  var outerLabel = L.tooltip({ permanent: true, direction: 'right', className: 'ring-label' })
    .setLatLng([lat, lng + (radiusKm * 0.009)]) // approximate offset
    .setContent(radiusKm + ' km');
  outerLabel.addTo(map);
  appState._ringLabels = [outerLabel];

  // Inner rings
  var innerDistances = computeInnerRings(radiusKm);
  appState._innerRings = {};

  innerDistances.forEach(function (dist) {
    var circle = L.circle([lat, lng], {
      radius: dist * 1000,
      color: '#94a3b8',
      weight: 1.5,
      fillColor: 'transparent',
      fillOpacity: 0,
      dashArray: '4 4',
    }).addTo(map);

    var label = L.tooltip({ permanent: true, direction: 'right', className: 'ring-label' })
      .setLatLng([lat, lng + (dist * 0.009)])
      .setContent(dist + ' km');
    label.addTo(map);

    appState._innerRings[dist] = { circle: circle, label: label, visible: true };
    appState._ringLabels.push(label);
  });

  // Build ring filter control
  appState._ringBoundaries = innerDistances.slice().sort(function (a, b) { return a - b; });
  appState._outerRadiusKm = radiusKm;
  buildRingControl(radiusKm, innerDistances);

  // Store center for later use (e.g., centering before export)
  appState._searchCenter = [lat, lng];

  // Center map on search center, fitting the outer circle
  map.fitBounds(appState._outerCircle.getBounds(), { padding: [40, 40] });
}

/**
 * Clear all radius-related elements from the map.
 */
function clearRadiusElements() {
  var map = appState.mapInstance;
  if (!map) return;

  if (appState._centerMarker) { map.removeLayer(appState._centerMarker); appState._centerMarker = null; }
  if (appState._outerCircle) { map.removeLayer(appState._outerCircle); appState._outerCircle = null; }
  if (appState._ringLabels) {
    appState._ringLabels.forEach(function (l) { map.removeLayer(l); });
    appState._ringLabels = [];
  }
  if (appState._innerRings) {
    Object.keys(appState._innerRings).forEach(function (k) {
      var r = appState._innerRings[k];
      if (r.circle) map.removeLayer(r.circle);
      if (r.label) map.removeLayer(r.label);
    });
    appState._innerRings = {};
  }

  // Clear multi-radius circles
  if (appState._multiRadiusCircles) {
    appState._multiRadiusCircles.forEach(function(item) {
      if (item.circle) map.removeLayer(item.circle);
      if (item.label) map.removeLayer(item.label);
    });
    appState._multiRadiusCircles = [];
  }

  // Hide ring control
  var ctrl = document.getElementById('ring-control');
  if (ctrl) ctrl.classList.add('hidden');
}

/**
 * Draw 3 fixed analysis circles at 1km, 3km, 5km with different colors.
 * These are SEPARATE from the user's radius circles.
 */
function drawMultiRadiusCircles(zone) {
  var map = appState.mapInstance;
  if (!map || !zone) return;

  var lat = zone.center_lat;
  var lng = zone.center_lng;
  if (lat == null || lng == null) return;

  // Clear previous multi-radius circles
  if (appState._multiRadiusCircles) {
    appState._multiRadiusCircles.forEach(function(item) {
      if (item.circle) map.removeLayer(item.circle);
      if (item.label) map.removeLayer(item.label);
    });
  }
  appState._multiRadiusCircles = [];

  var radii = [
    { km: 1, color: '#8b5cf6' },  // purple
    { km: 3, color: '#06b6d4' },  // cyan
    { km: 5, color: '#f97316' },  // orange
  ];

  radii.forEach(function(r) {
    var circle = L.circle([lat, lng], {
      radius: r.km * 1000,
      color: r.color,
      weight: 2,
      fillColor: r.color,
      fillOpacity: 0.02,
      dashArray: '6 3',
    }).addTo(map);

    var label = L.tooltip({ permanent: true, direction: 'right', className: 'ring-label multi-radius-label' })
      .setLatLng([lat, lng + (r.km * 0.009)])
      .setContent(r.km + ' km (análisis)');
    label.addTo(map);

    appState._multiRadiusCircles.push({ circle: circle, label: label, km: r.km, visible: true });
  });
}

/**
 * Build the ring filter control panel.
 */
function buildRingControl(outerKm, innerDistances) {
  var ctrl = document.getElementById('ring-control');
  var toggles = document.getElementById('ring-toggles');
  if (!ctrl || !toggles) return;

  toggles.innerHTML = '';

  // Outer ring (always on, disabled checkbox)
  var outerLabel = document.createElement('label');
  outerLabel.className = 'layer-toggle';
  var outerCb = document.createElement('input');
  outerCb.type = 'checkbox';
  outerCb.checked = true;
  outerCb.disabled = true;
  outerLabel.appendChild(outerCb);
  outerLabel.appendChild(document.createTextNode(' ' + outerKm + ' km (radio de búsqueda)'));
  toggles.appendChild(outerLabel);

  // Inner rings
  innerDistances.forEach(function (dist) {
    var label = document.createElement('label');
    label.className = 'layer-toggle';
    var cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.checked = true;
    cb.addEventListener('change', function () {
      toggleInnerRing(dist, cb.checked);
    });
    label.appendChild(cb);
    label.appendChild(document.createTextNode(' ' + dist + ' km'));
    toggles.appendChild(label);
  });

  ctrl.classList.remove('hidden');
}

/**
 * Toggle an inner ring on/off — also shows/hides markers in that distance band.
 * A band for distance D goes from D to the next larger ring (or outer radius).
 */
function toggleInnerRing(dist, visible) {
  var map = appState.mapInstance;
  var ring = appState._innerRings[dist];
  if (!map || !ring) return;

  if (visible) {
    ring.circle.addTo(map);
    ring.label.addTo(map);
  } else {
    map.removeLayer(ring.circle);
    map.removeLayer(ring.label);
  }
  ring.visible = visible;

  // Recompute marker visibility based on all ring states
  updateMarkerVisibility();
}

/**
 * Recompute which markers are visible based on active rings.
 * Each ring at distance D controls markers from D to the next boundary.
 * The innermost band (0 to first ring) is always visible.
 */
function updateMarkerVisibility() {
  var map = appState.mapInstance;
  if (!map || !appState._ringBoundaries) return;

  var boundaries = appState._ringBoundaries; // sorted [1, 3, 5] + outerKm
  var outerKm = appState._outerRadiusKm || 999;

  // Build list of visible bands
  // Band 0: 0 → first boundary (always visible)
  // Band i: boundaries[i-1] → boundaries[i] (visible if ring at boundaries[i-1] is active)
  // Last band: last inner ring → outerKm (visible if last inner ring is active)

  appState.markers.forEach(function (marker) {
    var d = marker._distKm || 0;
    var shouldShow = true;

    // Find which band this marker belongs to
    if (boundaries.length > 0) {
      if (d <= boundaries[0]) {
        // Innermost band — always visible
        shouldShow = true;
      } else {
        // Find the band: between boundaries[i-1] and boundaries[i]
        for (var i = 0; i < boundaries.length; i++) {
          var lower = boundaries[i];
          var upper = (i + 1 < boundaries.length) ? boundaries[i + 1] : outerKm;
          if (d > lower && d <= upper) {
            // This marker is in the band controlled by ring at 'lower'
            var ring = appState._innerRings[lower];
            if (ring && !ring.visible) {
              shouldShow = false;
            }
            break;
          }
        }
        // Beyond outer radius — always show (Google may return slightly outside)
        if (d > outerKm) shouldShow = true;
      }
    }

    if (shouldShow && !map.hasLayer(marker)) {
      marker.addTo(map);
    } else if (!shouldShow && map.hasLayer(marker)) {
      map.removeLayer(marker);
    }
  });
}

/* ===== Legacy stubs for compatibility ===== */
function renderAGEBLayers() {}
function clearAGEBLayers() { clearRadiusElements(); }
function drawRadiusCircle(zone, radiusKm) { drawRadiusCircles(zone, radiusKm); }

/**
 * Center the map on the search center and fit the outer circle.
 * Disables animation so html2canvas captures the final state.
 * Returns a Promise that resolves when the map is ready for capture.
 */
function centerMapForCapture() {
  var map = appState.mapInstance;
  if (!map) return;

  // Disable animation for instant positioning
  if (appState._outerCircle) {
    map.fitBounds(appState._outerCircle.getBounds(), {
      padding: [30, 30],
      animate: false,
      duration: 0,
    });
  } else if (appState._searchCenter) {
    map.setView(appState._searchCenter, 14, { animate: false });
  }

  // Force Leaflet to recalculate layout
  map.invalidateSize({ animate: false });
}
