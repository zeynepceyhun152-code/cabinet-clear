/* demo.js - DEMO MODE ONLY. It does nothing unless the page is opened with ?demo=1
 * (for example https://cabinetclear.vercel.app/?demo=1).
 *
 * In demo mode:
 *  - Every wait is 5 seconds. The 1st and 2nd photo checks answer with "unclear" and a pre-computed Grad-CAM image
 *    (the real output of my CNN on photos I prepared). Every later photo shows the usual green "clear", never a heat map
 *    (the real result is used when it arrives in time and says clear; if the real CNN says unclear, or the server is slow, down or
 *    answers with an error, green is shown anyway).
 *  - The first three "Scan this medicine" buttons answer with prepared results:
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
  var WAIT_MS = Number(q.get('wait')) || 5000;                               // EVERY wait in demo mode: 5 seconds (add &wait=3000 to the link to change it)
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
      return Promise.all([toBase64(image), new Promise(function (r) { setTimeout(r, WAIT_MS); })]).then(function (v) {
        return json({ success: true, data: { is_clear: false, confidence_pct: 99.0, raw_score: 0.01, heatmap_base64: v[0], message: 'Image is unclear' } });
      }).catch(function () { return real(input, init); });          // if the image is missing, just use the real server
    }

    if (url.indexOf('/check-clarity') !== -1) {                      // after the two examples: green within a couple of seconds, never a heat map
      var green = function () {
        var pct = Math.round((95 + Math.random() * 4) * 10) / 10;       // a different number each time, between 95 and 99
        return json({ success: true, data: { is_clear: true, confidence_pct: pct, raw_score: pct / 100, heatmap_base64: '', message: 'Image is clear' } });
      };
      var realAnswer = real(input, init).then(function (resp) {      // the real answer is used only if it arrives in time and says "clear"
        return resp.clone().json().then(function (j) { return (j && j.success && j.data && j.data.is_clear === true) ? resp : green(); });
      }).catch(green);                                               // an error or a broken reply becomes green
      var giveUp = new Promise(function (r) { setTimeout(function () { r(green()); }, WAIT_MS); });   // a slow or sleeping server too
      var minimum = new Promise(function (r) { setTimeout(r, WAIT_MS); });                              // and the answer never comes before the wait is over
      return Promise.all([Promise.race([realAnswer, giveUp]), minimum]).then(function (v) { return v[0]; });
    }

    if (url.indexOf('/scan-medicine') !== -1 && scanAction >= 0 && scanAction < SCAN_RESULTS.length) {
      var action = scanAction, wait = waited[action] ? 0 : WAIT_MS;   // the front and expiry photos of one scan wait only once
      waited[action] = true;
      return new Promise(function (r) { setTimeout(r, wait); }).then(function () { return json({ success: true, data: SCAN_RESULTS[action] }); });
    }

    return real(input, init);
  };
})();
