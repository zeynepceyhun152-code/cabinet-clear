/* session.js - keeps you signed in, sends your sign-in token with history requests, and saves to history as you go.
 *  - The token is kept on the phone, so a page reload (iPhone does this when you use the camera) does not sign you out.
 *    It is forgotten when you log out, delete your account, or it expires (7 days).
 *  - When you are signed in, your letter is saved to history as soon as it is read, and the changes you compare are
 *    added to the same entry (the server merges saves of the same letter into one entry).
 */
(function () {
  'use strict';
  var KEY_T = 'cc_token', KEY_U = 'cc_user';
  var token = null;
  if (!window.fetch) return;

  function remember(t, u) { try { localStorage.setItem(KEY_T, t); localStorage.setItem(KEY_U, u || ''); } catch (e) {} }
  function forget() { try { localStorage.removeItem(KEY_T); localStorage.removeItem(KEY_U); } catch (e) {} }
  function setUser(u) { try { currentSessionUser = u; } catch (e) {} }
  function apiBase() { return (typeof API !== 'undefined') ? API : ''; }

  try {
    var st = localStorage.getItem(KEY_T), su = localStorage.getItem(KEY_U);
    if (st && su) { token = st; setUser(su); }
  } catch (e) {}

  var base = window.fetch.bind(window);

  function post(diagnosis, letter, cabinet) {
    if (!token || !letter) return;
    window.fetch(apiBase() + '/history/save', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ diagnosis: diagnosis || 'Unspecified Medical Evaluation', letter_data: letter, cabinet_data: cabinet || {} })
    }).catch(function () {});
  }

  window.fetch = function (input, init) {
    var url = (typeof input === 'string') ? input : (input && input.url) || '';
    var needsAuth = url.indexOf('/history/') !== -1 || url.indexOf('/account') !== -1;
    var isLogin = url.indexOf('/auth/login') !== -1;
    var isLetter = url.indexOf('/extract-letter') !== -1;
    var isCompare = url.indexOf('/reconcile') !== -1;
    if (needsAuth && token) {
      init = init || {};
      var h = new Headers(init.headers || (input && input.headers) || undefined);
      h.set('Authorization', 'Bearer ' + token);
      init.headers = h;
    }
    var p = base(input, init);
    if (isLogin) {
      p.then(function (res) { return res.clone().json(); })
       .then(function (j) { if (j && j.success && j.token) { token = j.token; remember(j.token, j.username); } })
       .catch(function () {});
    }
    if (needsAuth) {
      p.then(function (res) { if (res.status === 401) { token = null; forget(); setUser(null); } }).catch(function () {});
    }
    if (isLetter && token) {                       // the letter was read: save it now
      p.then(function (res) { return res.clone().json(); })
       .then(function (j) { if (j && j.success && j.data) post(j.data.diagnosis_summary, j.data, {}); })
       .catch(function () {});
    }
    if (isCompare && token) {                      // "What changed?" was worked out: add it to the same entry
      p.then(function (res) { return res.clone().json(); })
       .then(function (j) {
         var letter = null; try { letter = dischargeData; } catch (e) {}
         if (j && j.success && j.data && letter) post(letter.diagnosis_summary, letter, { changes: j.data });
       }).catch(function () {});
    }
    return p;
  };

  // If a token was kept, check it quietly (this also wakes the free server early). An old token clears itself.
  function check() {
    var u = ''; try { u = currentSessionUser; } catch (e) {}
    if (token && u) {
      window.fetch(apiBase() + '/history/get/' + encodeURIComponent(u)).catch(function () {});
      if (typeof loadSavedHistory === 'function') { try { loadSavedHistory(); } catch (e) {} }
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', check); else setTimeout(check, 0);

  window.ccSession = {
    hasToken: function () { return !!token; },
    clear: function () { token = null; forget(); setUser(null); }
  };
})();
