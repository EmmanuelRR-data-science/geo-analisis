/* ===== Export Module ===== */

/**
 * Capture the map container as a PNG and trigger download.
 * Includes markers, zone boundary, and legend.
 */
function exportMapAsPng() {
  var mapEl = document.getElementById('map');
  if (typeof html2canvas === 'undefined') {
    alert('La librería de captura no está disponible.');
    return;
  }
  html2canvas(mapEl, { useCORS: true, allowTaint: true })
    .then(function (canvas) {
      var link = document.createElement('a');
      link.download = 'mapa-viabilidad.png';
      link.href = canvas.toDataURL('image/png');
      link.click();
    })
    .catch(function () {
      alert('No se pudo capturar el mapa. Intenta de nuevo.');
    });
}

/**
 * Capture the map, send it to the backend PDF endpoint, and trigger download.
 * @param {string} analysisId - The analysis_id from the current analysis result.
 * @param {HTMLElement} btnEl - The PDF button element (for disabling during generation).
 */
function exportAnalysisAsPdf(analysisId, btnEl) {
  if (!analysisId) return;

  var mapEl = document.getElementById('map');
  if (typeof html2canvas === 'undefined') {
    alert('La librería de captura no está disponible.');
    return;
  }

  if (btnEl) {
    btnEl.disabled = true;
    btnEl.textContent = 'Generando…';
  }

  html2canvas(mapEl, { useCORS: true, allowTaint: true })
    .then(function (canvas) {
      var base64 = canvas.toDataURL('image/png');
      return fetch('/api/export/pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          analysis_id: analysisId,
          map_image_base64: base64,
        }),
      });
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
}
