/* demo.js - DEMO MODE ONLY. It does nothing unless the page is opened with ?demo=1
 * (for example https://cabinetclear.vercel.app/?demo=1).
 * In demo mode, the first photo checks answer after a short wait with "unclear" and a pre-computed Grad-CAM image
 * (the real output of my CNN on photos I prepared). Every later photo check goes to the real server as usual.
 * Add &badge=0 to hide the small "Demo mode" label.
 */
(function () {
  'use strict';
  var q = new URLSearchParams(location.search);
  if (q.get('demo') !== '1' || !window.fetch) return;

  var SEQUENCE = ['/demo/photo1_gradcam.png', '/demo/photo2_gradcam.png'];   // 1st and 2nd photo check; then the real server
  var DELAY_MS = 1800;                                                       // the short wait before the answer
  var used = 0;
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
    return real(input, init);
  };

  if (q.get('badge') !== '0') {
    var b = document.createElement('div');
    b.textContent = 'Demo mode';
    b.style.cssText = 'position:fixed;left:10px;bottom:84px;z-index:99999;background:rgba(11,36,71,.85);color:#fff;font:600 12px system-ui,sans-serif;padding:4px 10px;border-radius:999px;pointer-events:none';
    document.body.appendChild(b);
  }
})();
