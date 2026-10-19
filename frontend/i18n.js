/* i18n.js - English / Turkish switch for Cabinet Clear.
 *
 * How it works:
 *  - tr.json holds exact English -> Turkish strings plus patterns for text that contains names or numbers.
 *  - This script translates the text already on the page, and anything the app adds later.
 *  - Text the AI writes is NOT translated here: the server is told the language (X-Lang header)
 *    and writes it in Turkish itself.
 *  - Medicine names, doses and numbers are never touched.
 */
(function () {
  'use strict';
  var KEY = 'cc_lang';
  var data = { strings: {}, patterns: [], freq: [] };
  var rx = [];
  var lang = 'en';
  var originals = new WeakMap();   // text node -> English text
  var written = new WeakMap();     // text node -> Turkish text we wrote
  var attrOrig = new WeakMap();    // element -> { attr: English }
  var ATTRS = ['placeholder', 'title', 'aria-label', 'alt'];
  var SKIP = { SCRIPT: 1, STYLE: 1, TEXTAREA: 1, CODE: 1 };
  var origFetch = window.fetch ? window.fetch.bind(window) : null;
  var origAlert = window.alert ? window.alert.bind(window) : null;
  var observer = null;

  function pickLang() {
    try { var s = localStorage.getItem(KEY); if (s === 'tr' || s === 'en') return s; } catch (e) {}
    return ((navigator.language || 'en').toLowerCase().indexOf('tr') === 0) ? 'tr' : 'en';
  }
  function norm(s) { return String(s).replace(/\s+/g, ' ').trim(); }

  function freq(s) {
    for (var i = 0; i < data.freq.length; i++) { s = s.split(data.freq[i][0]).join(data.freq[i][1]); }
    return s;
  }

  // Returns the Turkish text, or null if there is nothing to translate.
  function translate(text, depth) {
    depth = depth || 0;
    if (depth > 3) return null;
    var key = norm(text);
    if (!key) return null;
    if (Object.prototype.hasOwnProperty.call(data.strings, key)) return data.strings[key];
    for (var i = 0; i < rx.length; i++) {
      var m = rx[i].re.exec(key);
      if (!m) continue;
      return rx[i].tr.replace(/\{(t|f|ts)?(\d)\}/g, function (_, kind, n) {
        var g = m[+n] || '';
        if (kind === 't') { var t = translate(g, depth + 1); return t === null ? g : t; }
        if (kind === 'f') { var f = translate(g, depth + 1); return f === null ? freq(g) : f; }
        if (kind === 'ts') {
          return g.split('; ').map(function (part) { var t = translate(part, depth + 1); return t === null ? part : t; }).join('; ');
        }
        return g;
      });
    }
    return null;
  }

  function keepSpaces(original, translated) {
    var lead = (original.match(/^\s*/) || [''])[0];
    var trail = (original.match(/\s*$/) || [''])[0];
    return lead + translated + trail;
  }

  function doText(node) {
    var p = node.parentNode;
    if (!p || SKIP[p.nodeName] || (p.closest && p.closest('[data-no-i18n]'))) return;
    var cur = node.nodeValue;
    if (lang === 'tr') {
      if (written.get(node) === cur) return;               // already ours
      var t = translate(cur);
      if (t !== null && norm(t) !== norm(cur)) {
        originals.set(node, cur);
        var out = keepSpaces(cur, t);
        written.set(node, out);
        node.nodeValue = out;
      }
    } else if (originals.has(node) && written.get(node) === cur) {
      node.nodeValue = originals.get(node);
      originals.delete(node); written.delete(node);
    }
  }

  function doAttrs(el) {
    if (!el.getAttribute || (el.closest && el.closest('[data-no-i18n]'))) return;
    var saved = attrOrig.get(el) || {};
    ATTRS.forEach(function (a) {
      var v = el.getAttribute(a);
      if (v === null) return;
      if (lang === 'tr') {
        if (saved[a] && saved[a].tr === v) return;
        var t = translate(v);
        if (t !== null) { saved[a] = { en: v, tr: t }; el.setAttribute(a, t); }
      } else if (saved[a] && saved[a].tr === v) {
        el.setAttribute(a, saved[a].en); delete saved[a];
      }
    });
    attrOrig.set(el, saved);
  }

  function walk(root) {
    if (!root) return;
    if (root.nodeType === 3) { doText(root); return; }
    if (root.nodeType !== 1 && root.nodeType !== 9) return;
    if (root.nodeType === 1) doAttrs(root);
    var w = document.createTreeWalker(root, 4 | 1, null);   // text + elements
    var n = w.nextNode();
    while (n) { if (n.nodeType === 3) doText(n); else doAttrs(n); n = w.nextNode(); }
  }

  function applyAll() {
    walk(document.body);
    var tt = document.querySelector('title');
    if (tt) walk(tt);
    document.documentElement.setAttribute('lang', lang);
    var b = document.getElementById('ccLangBtn');
    if (b) { b.textContent = lang === 'tr' ? 'English' : 'Türkçe'; b.setAttribute('aria-label', lang === 'tr' ? 'Switch to English' : 'Türkçeye geç'); }
  }

  function setLang(l) {
    lang = (l === 'tr') ? 'tr' : 'en';
    try { localStorage.setItem(KEY, lang); } catch (e) {}
    applyAll();
  }

  function startObserver() {
    if (!window.MutationObserver) return;
    observer = new MutationObserver(function (muts) {
      muts.forEach(function (m) {
        if (m.type === 'childList') { m.addedNodes.forEach(function (n) { walk(n); }); }
        else if (m.type === 'characterData') { doText(m.target); }
        else if (m.type === 'attributes') { doAttrs(m.target); }
      });
    });
    observer.observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRS });
  }

  function addButton() {
    if (document.getElementById('ccLangBtn')) return;
    var b = document.createElement('button');
    b.id = 'ccLangBtn';
    b.type = 'button';
    b.setAttribute('data-no-i18n', '');
    b.style.cssText = 'position:fixed;top:10px;right:10px;z-index:9999;padding:7px 14px;border-radius:20px;' +
      'border:1.5px solid var(--accent,#3B82F6);background:#fff;color:var(--accent,#3B82F6);font-weight:600;' +
      'font-size:0.8rem;font-family:inherit;cursor:pointer;box-shadow:0 1px 4px rgba(0,0,0,0.12)';
    b.addEventListener('click', function () { setLang(lang === 'tr' ? 'en' : 'tr'); });
    document.body.appendChild(b);
  }

  // Tell the server which language to write in.
  if (origFetch) {
    window.fetch = function (input, init) {
      try {
        var url = (typeof input === 'string') ? input : (input && input.url) || '';
        if (url.indexOf('tr.json') === -1) {
          init = init || {};
          var h = new Headers(init.headers || (input && input.headers) || undefined);
          h.set('X-Lang', lang);
          init.headers = h;
        }
      } catch (e) {}
      return origFetch(input, init);
    };
  }
  // Pop-up messages
  if (origAlert) {
    window.alert = function (msg) {
      var t = (lang === 'tr') ? translate(String(msg)) : null;
      return origAlert(t === null ? msg : t);
    };
  }

  function load() {
    lang = pickLang();
    addButton();
    startObserver();
    if (!origFetch) return;
    origFetch('/tr.json', { cache: 'no-cache' })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        data = d;
        rx = (d.patterns || []).map(function (p) { return { re: new RegExp(p.re), tr: p.tr }; });
        applyAll();
      })
      .catch(function () { applyAll(); });
  }

  window.ccI18n = { setLang: setLang, getLang: function () { return lang; }, translate: translate };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', load); else load();
})();
