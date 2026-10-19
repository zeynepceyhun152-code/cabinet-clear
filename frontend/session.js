/* session.js - keeps the sign-in token in memory and sends it with history requests.
 * No other page code needs to change. The token is forgotten when the page is closed, like the sign-in itself. */
(function () {
  'use strict';
  var token = null;
  if (!window.fetch) return;
  var base = window.fetch.bind(window);
  window.fetch = function (input, init) {
    var url = (typeof input === 'string') ? input : (input && input.url) || '';
    var isHistory = url.indexOf('/history/') !== -1;
    var isLogin = url.indexOf('/auth/login') !== -1;
    if (isHistory && token) {
      init = init || {};
      var h = new Headers(init.headers || (input && input.headers) || undefined);
      h.set('Authorization', 'Bearer ' + token);
      init.headers = h;
    }
    var p = base(input, init);
    if (isLogin) {
      p.then(function (res) { return res.clone().json(); })
       .then(function (j) { if (j && j.success && j.token) token = j.token; })
       .catch(function () {});
    }
    if (isHistory) {
      p.then(function (res) { if (res.status === 401) token = null; }).catch(function () {});
    }
    return p;
  };
  window.ccSession = { hasToken: function () { return !!token; }, clear: function () { token = null; } };
})();
