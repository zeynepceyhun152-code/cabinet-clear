/* demo.js - DEMO MODE ONLY. It does nothing unless the page is opened with ?demo=1
 * (for example https://cabinetclear.vercel.app/?demo=1).
 *
 * In demo mode:
 *  - The 1st and 2nd photo checks answer after a short wait with "unclear" and a pre-computed Grad-CAM image
 *    (the real output of my CNN on photos I prepared). Every later photo shows the usual green "clear", never a heat map
 *    (the real result is used when it says clear; if the real CNN says unclear, or the server is slow or down, green is shown).
 *  - The first three "Scan this medicine" buttons answer after a few seconds with prepared results:
 *    medicine 1: unknown unknown, medicine 2: ibucold C, medicine 3: D-Colefor. Later scans go to the real server.
 *  - "Please add at least one photo first" does not appear for those three scans (the app throws rejected photos away,
 *    so a stand-in photo is used).
 * Normal links are never touched.
 */
(function () {
  'use strict';
  var q = new URLSearchParams(location.search);
  if (q.get('demo') !== '1' || !window.fetch) return;

  var SEQUENCE = ['/demo/photo1_gradcam.png', '/demo/photo2_gradcam.png'];   // 1st and 2nd photo check
  var DELAY_MS = 1800;                                                       // wait before a photo check answers
  var SCAN_DELAY_MS = 2500;                                                  // wait before a scan answers ("a few seconds")
  var SCAN_RESULTS = [
    { drug_name: 'unknown', dosage_strength: 'unknown', expiration_date: 'unknown', is_expired: null, extraction_confidence: 'low' },               // medicine 1
    { drug_name: 'ibucold C', dosage_strength: '200mg/30mg/300mg', expiration_date: 'S.K.T.: 02/2029', is_expired: false, extraction_confidence: 'high' },  // medicine 2
    { drug_name: 'D-Colefor', dosage_strength: '20,000 I.U.', expiration_date: '03/2029', is_expired: false, extraction_confidence: 'high' }                // medicine 3
  ];
  var used = 0, scanAction = -1, waited = {};
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
  function json(body) { return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } }); }

  var originalScan = window.scanSlot;
  if (typeof originalScan === 'function') {
    window.scanSlot = function (slotId) {
      scanAction++;                                                           // which Scan button press this is (0 = the first)
      try {
        var d = slotData[slotId];
        if (d && !d.front && !d.exp && scanAction < SCAN_RESULTS.length) d.front = new File([new Blob(['demo'])], 'demo.jpg', { type: 'image/jpeg' });
      } catch (e) {}
      return originalScan.apply(this, arguments);
    };
  }

  window.fetch = function (input, init) {
    var url = (typeof input === 'string') ? input : (input && input.url) || '';

    if (url.indexOf('/check-clarity') !== -1 && used < SEQUENCE.length) {
      var image = SEQUENCE[used++];
      return Promise.all([toBase64(image), new Promise(function (r) { setTimeout(r, DELAY_MS); })]).then(function (v) {
        return json({ success: true, data: { is_clear: false, confidence_pct: 99.0, raw_score: 0.01, heatmap_base64: v[0], message: 'Image is unclear' } });
      }).catch(function () { return real(input, init); });          // if the image is missing, just use the real server
    }

    if (url.indexOf('/check-clarity') !== -1) {                      // after the two examples: always green, never a heat map
      var green = function () { return json({ success: true, data: { is_clear: true, confidence_pct: 95.0, raw_score: 0.95, heatmap_base64: '', message: 'Image is clear' } }); };
      return real(input, init).then(function (resp) {
        return resp.clone().json().then(function (j) { return (j && j.success && j.data && j.data.is_clear === false) ? green() : resp; });
      }).catch(green);
    }

    if (url.indexOf('/scan-medicine') !== -1 && scanAction >= 0 && scanAction < SCAN_RESULTS.length) {
      var action = scanAction, wait = waited[action] ? 0 : SCAN_DELAY_MS;   // the front and expiry photos of one scan wait only once
      waited[action] = true;
      return new Promise(function (r) { setTimeout(r, wait); }).then(function () { return json({ success: true, data: SCAN_RESULTS[action] }); });
    }

    return real(input, init);
  };
})();
