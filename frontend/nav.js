/* nav.js - pages and a bottom bar for Cabinet Clear.
 *
 * Pages: Home (your existing screen), Sign in, Account, History, Check a medicine.
 * It does NOT rewrite your page. It moves your existing cards (sign-in, history, medicine scanner) between pages,
 * and puts them back when you leave. To undo everything, remove the nav.js and custom.css lines from index.html.
 */
(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var current = 'home';
  var holders = {};            // where each moved card came from, so it can go back
  var letters = null;          // saved letters for the dropdown
  var entry = null;            // how Home looked before the Check page borrowed its cards
  var swapped = false;         // true if a saved letter replaced the letter on Home
  var prevLetter = null;

  function signedIn() { try { return !!currentSessionUser; } catch (e) { return false; } }
  function whoami() { try { return currentSessionUser || ''; } catch (e) { return ''; } }
  function apiBase() { return (typeof API !== 'undefined') ? API : ''; }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; });
  }
  function store(k, v) { try { if (v === undefined) return sessionStorage.getItem(k); sessionStorage.setItem(k, v); } catch (e) { return null; } }

  var S = 'fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"';
  var ICON = {
    user: '<svg viewBox="0 0 24 24" ' + S + '><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4.4 3.6-8 8-8s8 3.6 8 8"/></svg>',
    home: '<svg viewBox="0 0 24 24" ' + S + '><path d="M3 11.5 12 4l9 7.5"/><path d="M5.5 10v10h13V10"/><path d="M10 20v-5h4v5"/></svg>',
    camera: '<svg viewBox="0 0 24 24" ' + S + '><path d="M4 8h3l1.6-2.5h6.8L17 8h3v12H4z"/><circle cx="12" cy="13.5" r="3.6"/></svg>',
    back: '<svg viewBox="0 0 24 24" width="24" height="24" ' + S.replace('currentColor', '#FFFFFF') + '><path d="M15 5l-7 7 7 7"/></svg>'
  };

  // Move a card into a page, remembering where it was.
  function adopt(id, host) {
    var el = $(id);
    if (!el || !host) return;
    if (!holders[id] && el.parentNode) {
      var ph = document.createElement('span');
      ph.setAttribute('data-holder', id); ph.style.display = 'none';
      el.parentNode.insertBefore(ph, el);
      holders[id] = ph;
    }
    if (el.parentNode !== host) host.appendChild(el);
  }
  function giveBack(id) {
    var el = $(id), ph = holders[id];
    if (el && ph && ph.parentNode) ph.parentNode.insertBefore(el, ph);
  }

  function bar(title) {
    return '<div class="view-bar"><button type="button" class="back" data-go="home" aria-label="Back to home">' + ICON.back +
           '</button><span class="view-title">' + title + '</span></div>';
  }

  function build() {
    if ($('bottomNav')) return;

    // pages
    var auth = document.createElement('div'); auth.id = 'viewAuth'; auth.className = 'view';
    auth.innerHTML = bar('Sign in') + '<div class="view-body" id="viewAuthBody"></div>';
    var acct = document.createElement('div'); acct.id = 'viewAccount'; acct.className = 'view';
    acct.innerHTML = bar('Account') + '<div class="view-body" id="viewAccountBody"></div>';
    var hist = document.createElement('div'); hist.id = 'viewHistory'; hist.className = 'view';
    hist.innerHTML = bar('Past cabinet checks') + '<div class="view-body" id="viewHistoryBody"></div>';
    var chk = document.createElement('div'); chk.id = 'viewCheck'; chk.className = 'view';
    chk.innerHTML = bar('Check your medicines') + '<div class="view-body" id="viewCheckBody"></div>';

    // bottom bar: Account, Home (middle), Camera
    var nav = document.createElement('nav'); nav.id = 'bottomNav'; nav.setAttribute('aria-label', 'Main');
    nav.innerHTML =
      '<button type="button" data-go="account">' + ICON.user + '<span>Account</span></button>' +
      '<button type="button" data-go="home">' + ICON.home + '<span>Home</span></button>' +
      '<button type="button" data-go="check">' + ICON.camera + '<span>Check medicine</span></button>';

    var firstScript = document.querySelector('body > script');
    [auth, acct, hist, chk, nav].forEach(function (el) { document.body.insertBefore(el, firstScript); });

    // sign-in card moves into its own page, with a clear way to skip
    adopt('authCard', $('viewAuthBody'));
    var skip = document.createElement('button');
    skip.type = 'button'; skip.className = 'btn btn-ghost'; skip.id = 'authSkip';
    skip.textContent = 'Continue without an account';
    $('viewAuthBody').appendChild(skip);
    skip.addEventListener('click', skipAuth);
    var card = $('authCard');
    if (card && window.MutationObserver) {
      new MutationObserver(function () {
        if (card.classList.contains('hidden') && current === 'auth') { store('cc_skip_auth', '1'); go('home'); }
      }).observe(card, { attributes: true, attributeFilter: ['class'] });
    }

    // history lives under Account, so the old "View My History" button on Home is removed
    var hb = document.querySelector('button[onclick="loadHistory()"]');
    if (hb && hb.parentNode) hb.parentNode.removeChild(hb);

    // the language button goes into the header, so it cannot sit on top of other buttons
    moveLang();

    document.addEventListener('click', function (e) {
      var t = e.target.closest ? e.target.closest('[data-go]') : null;
      if (t) { e.preventDefault(); go(t.getAttribute('data-go')); }
    });

    // first screen: sign in (skippable) unless already signed in or skipped in this visit
    if (!signedIn() && !store('cc_skip_auth')) go('auth'); else go('home');
  }

  function moveLang() {
    var lb = $('ccLangBtn'), inner = document.querySelector('.header-inner');
    if (lb && inner) inner.appendChild(lb); else if (!lb) setTimeout(function () { var b = $('ccLangBtn'); if (b && inner) inner.appendChild(b); }, 400);
  }

  function skipAuth() { store('cc_skip_auth', '1'); go('home'); }

  function go(view) {
    if (view === 'account' && !signedIn()) view = 'auth';
    if (current === 'check' && view !== 'check') leaveCheck();
    current = view;
    document.body.setAttribute('data-view', view);
    if (view === 'auth') { var c = $('authCard'); if (c) c.classList.remove('hidden'); }
    if (view === 'account') renderAccount();
    if (view === 'history') renderHistory();
    if (view === 'check') renderCheck();
    var map = { home: 'home', account: 'account', auth: 'account', history: 'account', check: 'check' };
    var btns = document.querySelectorAll('#bottomNav button');
    for (var i = 0; i < btns.length; i++) {
      var on = btns[i].getAttribute('data-go') === map[view];
      btns[i].classList.toggle('on', on);
      if (on) btns[i].setAttribute('aria-current', 'page'); else btns[i].removeAttribute('aria-current');
    }
    try { window.scrollTo(0, 0); } catch (e) {}
  }

  // ---------------- Account
  function renderAccount() {
    var body = $('viewAccountBody');
    var name = whoami();
    var lang = (window.ccI18n && ccI18n.getLang()) === 'tr' ? 'Türkçe' : 'English';
    body.innerHTML =
      '<div class="acct-head"><div class="acct-avatar">' + esc(name.charAt(0)) + '</div><div><div class="acct-name">' + esc(name) +
      '</div><div class="acct-sub">Signed in</div></div></div>' +
      '<button type="button" class="acct-row" data-go="history"><span>Past cabinet checks</span><span class="val">›</span></button>' +
      '<button type="button" class="acct-row" id="rowLang"><span>Language</span><span class="val" data-no-i18n>' + lang + '</span></button>' +
      (window.ccPrivacy ? '<button type="button" class="acct-row" id="rowPrivacy"><span>Privacy</span><span class="val">›</span></button>' : '') +
      '<button type="button" class="acct-row danger" id="rowLogout"><span>Log out</span></button>' +
      '<div id="acctDelHost"></div>';
    var del = $('acctDel'); if (del) $('acctDelHost').appendChild(del);
    $('rowLang').addEventListener('click', function () {
      if (window.ccI18n) { ccI18n.setLang(ccI18n.getLang() === 'tr' ? 'en' : 'tr'); renderAccount(); }
    });
    var rp = $('rowPrivacy'); if (rp) rp.addEventListener('click', function () { ccPrivacy.open(); });
    $('rowLogout').addEventListener('click', function () {
      if (window.ccSession && ccSession.clear) ccSession.clear();
      store('cc_skip_auth', ''); try { sessionStorage.removeItem('cc_skip_auth'); } catch (e) {}
      window.ccNav.reload();
    });
  }

  // ---------------- History
  function renderHistory() {
    var body = $('viewHistoryBody');
    if (!signedIn()) {
      var hc = $('historyCard'); if (hc) hc.classList.add('hidden');
      body.innerHTML = '<div class="empty-view"><p>Sign in to see your saved checks.</p>' +
        '<button type="button" class="btn btn-primary" data-go="auth">Go to sign in</button></div>';
      return;
    }
    var empty = body.querySelector('.empty-view'); if (empty) empty.parentNode.removeChild(empty);
    adopt('historyCard', body);
    if (typeof loadHistory === 'function') loadHistory();
  }

  // ---------------- Check a medicine (the camera page)
  function leaveCheck() {
    var s2 = $('step2'), rc = $('resultsCard');
    giveBack('step2'); giveBack('resultsCard');
    if (entry) {
      if (s2) s2.classList.toggle('hidden', entry.step2Hidden);
      if (rc) rc.classList.toggle('hidden', entry.resultsHidden);
    }
    if (swapped) { try { dischargeData = prevLetter; } catch (e) {} swapped = false; prevLetter = null; }
    entry = null;
  }

  function renderCheck() {
    var body = $('viewCheckBody');
    if (!entry) {
      var a = $('step2'), b = $('resultsCard');
      entry = { step2Hidden: !a || a.classList.contains('hidden'), resultsHidden: !b || b.classList.contains('hidden') };
    }
    if (!$('qcPanel')) {
      var intro = document.createElement('div');
      intro.className = 'step-intro';
      intro.innerHTML = '<span class="step-intro-icon">📸</span><span>No letter needed. Add each medicine, then check its name and expiry date.</span>';
      body.appendChild(intro);
      var panel = document.createElement('div');
      panel.id = 'qcPanel'; panel.className = 'card qc-panel';
      panel.innerHTML =
        '<button type="button" class="btn btn-primary" id="qcCheck" style="margin-top:0">Check names and dates</button>' +
        '<div class="qc-or">or</div>' +
        '<div id="qcLetterBox"></div>' +
        '<div id="quickResults"></div>';
      body.appendChild(panel);
      $('qcCheck').addEventListener('click', quickCheck);
    }
    adopt('step2', body);
    adopt('resultsCard', body);
    var s2 = $('step2'); if (s2) { s2.classList.remove('hidden'); body.insertBefore(s2, $('qcPanel')); }
    var rc = $('resultsCard'); if (rc) body.appendChild(rc);
    var list = $('medList');
    if (list && !list.children.length && typeof addMedSlot === 'function') addMedSlot();
    renderLetterBox();
  }

  function renderLetterBox() {
    var box = $('qcLetterBox');
    if (!signedIn()) {
      box.innerHTML = '<label>Compare with a saved letter</label>' +
        '<p class="qc-note" style="margin:0 0 10px">Sign in to compare with a letter you saved earlier.</p>' +
        '<button type="button" class="btn btn-ghost" data-go="auth" style="margin-top:0">Go to sign in</button>';
      return;
    }
    box.innerHTML = '<label>Compare with a saved letter</label><select id="qcLetterSel"><option value="">Choose a saved letter…</option></select>' +
      '<button type="button" class="btn btn-ghost" id="qcLetterGo" style="margin-top:10px">Check against this letter</button>';
    $('qcLetterGo').addEventListener('click', checkAgainstLetter);
    fillLetters();
  }

  function fillLetters() {
    var sel = $('qcLetterSel');
    if (!sel) return Promise.resolve();
    return fetch(apiBase() + '/history/get/' + encodeURIComponent(whoami()))
      .then(function (r) { return r.json(); })
      .then(function (j) {
        letters = (j && j.success && j.data) ? j.data : [];
        var sel2 = $('qcLetterSel'); if (!sel2) return;
        if (!letters.length) { sel2.innerHTML = '<option value="">No saved letters yet.</option>'; return; }
        sel2.innerHTML = '<option value="">Choose a saved letter…</option>' + letters.map(function (rec, i) {
          var d = ''; try { d = new Date(rec.timestamp).toLocaleDateString(); } catch (e) {}
          var t = String(rec.diagnosis || 'No diagnosis recorded'); if (t.length > 46) t = t.slice(0, 45) + '…';
          return '<option value="' + i + '">' + esc(d + ' · ' + t) + '</option>';
        }).join('');
      })
      .catch(function () {});
  }

  function medList() { try { return cabinetMeds; } catch (e) { return []; } }

  function checkAgainstLetter() {
    var sel = $('qcLetterSel');
    var rec = (sel && sel.value !== '' && letters) ? letters[+sel.value] : null;
    if (!rec || !rec.letter_data) { alert('Please choose a saved letter first.'); return; }
    if (!medList().length) { alert('Add at least one medicine first.'); return; }
    if (!swapped) { try { prevLetter = dischargeData; } catch (e) {} swapped = true; }
    dischargeData = rec.letter_data;        // the letter the person picked (Home gets its own letter back afterwards)
    var q = $('quickResults'); if (q) q.innerHTML = '';
    runAnalysis();                           // your existing Keep / Dispose / Unclear check
  }

  function quickCheck() {
    var list = medList();
    if (!list.length) { alert('Add at least one medicine first.'); return; }
    var html = '<div class="qc-title">Your medicines</div>';
    list.forEach(function (m) {
      var name = m.drug_name || 'Unknown';
      var st = m.is_expired === true ? ['pill-dispose', '✕ Expired', 'Expired'] :
               m.is_expired === false ? ['pill-keep', '✓ Valid', 'Valid'] : ['pill-unclear', '? Unclear', 'Unclear'];
      var ask = (name === 'Unknown' || m.extraction_confidence === 'low');
      html += '<div class="qc-item"><div><div class="qc-name">' + esc(name + (m.dosage_strength ? ' ' + m.dosage_strength : '')) + '</div>' +
              '<div class="qc-meta">' + st[2] + ' · EXP: ' + esc(m.expiration_date || 'not found') + '</div>' +
              (ask ? '<div class="qc-warn">Ask your pharmacist</div>' : '') +
              (m.confidence_notes ? '<div class="qc-meta">' + esc(m.confidence_notes) + '</div>' : '') +
              '</div><span class="status-pill ' + st[0] + '">' + st[1] + '</span></div>';
    });
    html += '<div class="qc-note">Expiry dates come from the printed label. If you\'re unsure, check the box or ask your pharmacist.</div>';
    $('quickResults').innerHTML = html;
  }

  window.ccNav = { go: go, current: function () { return current; }, reload: function () { window.location.reload(); } };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', build); else build();
})();
