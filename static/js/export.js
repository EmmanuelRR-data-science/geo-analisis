/* ===== Export Module ===== */

/**
 * Center map on search area, wait for tiles to load, then capture.
 */
function _captureMap(callback) {
  var mapEl = document.getElementById('map');
  if (typeof html2canvas === 'undefined') {
    alert('La librería de captura no está disponible.');
    return;
  }

  // Center map on the search area before capturing
  if (typeof centerMapForCapture === 'function') {
    centerMapForCapture();
  }

  // Wait for tiles to fully render after centering (no animation)
  setTimeout(function () {
    // Force one more layout recalculation
    if (appState.mapInstance) {
      appState.mapInstance.invalidateSize({ animate: false });
    }
    // Wait again for tiles to load
    setTimeout(function () {
      html2canvas(mapEl, { useCORS: true, allowTaint: true, scale: 2 })
        .then(callback)
        .catch(function () {
          alert('No se pudo capturar el mapa. Intenta de nuevo.');
        });
    }, 800);
  }, 300);
}

/**
 * Capture the map as PNG and trigger download.
 */
function exportMapAsPng() {
  _captureMap(function (canvas) {
    var link = document.createElement('a');
    link.download = 'mapa-viabilidad.png';
    link.href = canvas.toDataURL('image/png');
    link.click();
  });
}

/**
 * Capture the map, send to backend for PDF, and trigger download.
 */
function exportAnalysisAsPdf(analysisId, btnEl) {
  if (!analysisId) return;

  if (btnEl) {
    btnEl.disabled = true;
    btnEl.textContent = 'Generando…';
  }

  _captureMap(function (canvas) {
    var base64 = canvas.toDataURL('image/png');
    fetch('/api/export/pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        analysis_id: analysisId,
        map_image_base64: base64,
      }),
    })
      .then(function (resp) {
        if (!resp.ok) throw new Error('PDF generation failed');
        return resp.blob();
      })
      .then(function (blob) {
        var link = document.createElement('a');
        link.download = 'informe-viabilidad.pdf';
        link.href = URL.createObjectURL(blob);
        link.click();
      })
      .catch(function () {
        alert('No se pudo generar el informe PDF. Intenta de nuevo.');
      })
      .finally(function () {
        if (btnEl) {
          btnEl.disabled = false;
          btnEl.textContent = 'Descargar Informe (PDF)';
        }
      });
  });
}
