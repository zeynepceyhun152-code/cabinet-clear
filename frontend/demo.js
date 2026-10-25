/* demo.js - DEMO MODE ONLY. It does nothing unless the page is opened with ?demo=1
 * (for example https://cabinetclear.vercel.app/?demo=1).
 * In demo mode, the first photo checks answer after a short wait with "unclear" and a pre-computed Grad-CAM image
 * (the real output of my CNN on photos I prepared). Every later photo check goes to the real server as usual.
 */
(function () {
  'use strict';
  var q = new URLSearchParams(location.search);
  if (q.get('demo') !== '1' || !window.fetch) return;

  var SEQUENCE = ['/demo/photo1_gradcam.png', '/demo/photo2_gradcam.png'];   // 1st and 2nd photo check; then the real server
  var DELAY_MS = 1800;                                                       // the short wait before the answer
  var SCAN_DELAY_MS = 1500;                                                  // the short wait before the first scan result
  var SCAN_GROUP_MS = 15000;                                                 // the front and expiry photos of ONE scan count as one
  var FAKE_SCAN = { drug_name: 'unknown', dosage_strength: 'unknown', expiration_date: 'unknown', is_expired: null, extraction_confidence: 'low' };
  var used = 0, scanGroupStart = null, scanDone = false;
  var real = window.fetch.bind(window);

  function toBase64(url) {
    return real(url).then(function (r) { return r.blob(); }).then(function (b) {
      return new Promise(function (resolve, reject) {
        var fr = new FileReader();
        fr.onload = function () { resolve(String(fr.result).split(',')[1]); };
        fr.onerror = reject;
        fr.readAsDataURL(b);
      });
    });
  }

  window.fetch = function (input, init) {
    var url = (typeof input === 'string') ? input : (input && input.url) || '';
    if (url.indexOf('/check-clarity') !== -1 && used < SEQUENCE.length) {
      var image = SEQUENCE[used++];
      return Promise.all([toBase64(image), new Promise(function (r) { setTimeout(r, DELAY_MS); })]).then(function (v) {
        var body = { success: true, data: { is_clear: false, confidence_pct: 99.0, raw_score: 0.01, heatmap_base64: v[0], message: 'Image is unclear' } };
        return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } });
      }).catch(function () { return real(input, init); });          // if the image is missing, just use the real server
    }
    if (url.indexOf('/check-clarity') !== -1) {                      // after the two examples: always green, never a heat map
      var green = function () {
        return new Response(JSON.stringify({ success: true, data: { is_clear: true, confidence_pct: 95.0, raw_score: 0.95, heatmap_base64: '', message: 'Image is clear' } }),
          { status: 200, headers: { 'Content-Type': 'application/json' } });
      };
      return real(input, init).then(function (resp) {
        return resp.clone().json().then(function (j) { return (j && j.success && j.data && j.data.is_clear === false) ? green() : resp; });
      }).catch(green);
    }
    if (url.indexOf('/scan-medicine') !== -1 && !scanDone) {
      var now = Date.now();
      if (scanGroupStart === null) scanGroupStart = now;
      if (now - scanGroupStart <= SCAN_GROUP_MS) {
        return new Promise(function (r) { setTimeout(r, SCAN_DELAY_MS); }).then(function () {
          return new Response(JSON.stringify({ success: true, data: FAKE_SCAN }), { status: 200, headers: { 'Content-Type': 'application/json' } });
        });
      }
      scanDone = true;                                                       // the first scan is over: everything else is real
    }
    return real(input, init);
  };
})();
