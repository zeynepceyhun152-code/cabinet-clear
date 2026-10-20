/* privacy.js - a plain-language Privacy note, and "Delete my account and history".
 * Adds a small "Privacy" link at the bottom of the page and a delete control inside the history card.
 * The note asks the server whether saved history is encrypted, so it never claims more than is true. */
(function () {
  'use strict';

  var CSS = '' +
    '.priv-foot{text-align:center;margin:18px 0 8px;font-size:.8rem}.priv-foot a{color:var(--muted,#64748B);text-decoration:none;font-weight:600;cursor:pointer}' +
    '.priv-foot a:hover{text-decoration:underline}' +
    '#privModal{position:fixed;inset:0;z-index:10000;background:rgba(15,23,42,.55);display:flex;align-items:center;justify-content:center;padding:16px}' +
    '#privModal.hidden{display:none}' +
    '.priv-card{background:#fff;border-radius:14px;max-width:560px;width:100%;max-height:85vh;overflow:auto;padding:22px 22px 18px;box-shadow:0 10px 40px rgba(0,0,0,.3)}' +
    '.priv-card h3{font-size:1.15rem;color:var(--navy,#1E3A5F);margin-bottom:10px}' +
    '.priv-card h4{font-size:.78rem;letter-spacing:.06em;text-transform:uppercase;color:var(--accent,#3B82F6);margin:14px 0 4px}' +
    '.priv-card p{font-size:.9rem;line-height:1.55;color:var(--text,#0F172A)}.priv-card a{color:var(--accent,#3B82F6);font-weight:600}' +
    '.acct-del{margin-top:22px;padding-top:14px;border-top:1px dashed var(--border,#CBD5E1)}' +
    '.acct-del input{width:100%;padding:10px 12px;border:1.5px solid var(--border,#CBD5E1);border-radius:8px;font-size:1rem;margin:6px 0 10px;box-sizing:border-box;font-family:inherit}' +
    '.acct-del .danger{background:#DC2626;border-color:#DC2626;color:#fff}';

  function apiBase() { return (typeof API !== 'undefined') ? API : ''; }

  var NOTE = '' +
    '<h3>Your privacy</h3>' +
    '<h4>What we keep</h4>' +
    '<p>If you use the app without signing in, nothing about you is saved. If you sign in and run a check, we save your letter summary, your medicine list and your cabinet results so you can see them later. We also keep your username and a scrambled version of your password, never the password itself.</p>' +
    '<p>Your letters and photos are not stored by us. They are deleted from our server as soon as they have been read.</p>' +
    '<h4>How it is protected</h4>' +
    '<p id="privProtect"></p>' +
    '<h4>What goes to the AI</h4>' +
    '<p>To read your letter and photos, the app sends them to Anthropic\'s AI service. Anthropic says it does not train its models on content sent this way by default, and keeps it only for a limited time under its own policy.</p>' +
    '<p><a href="https://www.anthropic.com/legal/privacy" target="_blank" rel="noopener noreferrer">Read Anthropic\'s privacy policy</a></p>' +
    '<h4>Your choices</h4>' +
    '<p>You can delete your account and every saved check at any time from the Past Cabinet Checks card.</p>' +
    '<p>This app gives general information. It is not medical advice. Always confirm with your doctor or pharmacist.</p>' +
    '<button class="btn btn-primary" id="privClose" type="button" style="margin-top:14px">Close</button>';

  function build() {
    if (document.getElementById('privModal')) return;
    var st = document.createElement('style'); st.id = 'privStyle'; st.textContent = CSS; document.head.appendChild(st);

    var foot = document.createElement('div');
    foot.className = 'priv-foot';
    foot.innerHTML = '<a id="privLink" role="button">Privacy</a>';
    (document.querySelector('.container') || document.body).appendChild(foot);

    var modal = document.createElement('div');
    modal.id = 'privModal'; modal.className = 'hidden';
    modal.innerHTML = '<div class="priv-card" role="dialog" aria-modal="true">' + NOTE + '</div>';
    document.body.appendChild(modal);

    document.getElementById('privLink').addEventListener('click', openNote);
    document.getElementById('privClose').addEventListener('click', closeNote);
    modal.addEventListener('click', function (e) { if (e.target === modal) closeNote(); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeNote(); });

    var hist = document.getElementById('historyCard');
    if (hist) {
      var box = document.createElement('div');
      box.className = 'acct-del'; box.id = 'acctDel';
      box.innerHTML =
        '<button class="btn btn-ghost" id="acctDelBtn" type="button">Delete my account and history</button>' +
        '<div id="acctDelForm" class="hidden">' +
        '<div class="result-meta">This permanently deletes your account and every saved check. It cannot be undone.</div>' +
        '<label>Password</label><input type="password" id="acctDelPw" autocomplete="current-password">' +
        '<button class="btn danger" id="acctDelGo" type="button">Yes, delete everything</button>' +
        '<button class="btn btn-ghost" id="acctDelCancel" type="button">Cancel</button></div>';
      hist.appendChild(box);
      document.getElementById('acctDelBtn').addEventListener('click', function () {
        document.getElementById('acctDelBtn').classList.add('hidden');
        document.getElementById('acctDelForm').classList.remove('hidden');
        document.getElementById('acctDelPw').focus();
      });
      document.getElementById('acctDelCancel').addEventListener('click', resetDelete);
      document.getElementById('acctDelGo').addEventListener('click', doDelete);
    }
  }

  function resetDelete() {
    document.getElementById('acctDelForm').classList.add('hidden');
    document.getElementById('acctDelBtn').classList.remove('hidden');
    document.getElementById('acctDelPw').value = '';
  }

  function setProtect(encrypted) {
    document.getElementById('privProtect').textContent = encrypted
      ? 'Saved history is encrypted in our database, and only you can open it after signing in.'
      : 'Saved history is protected by your sign-in: only you can open it after signing in.';
  }

  function openNote() {
    setProtect(false);                                  // never claim encryption until the server confirms it
    document.getElementById('privModal').classList.remove('hidden');
    try {
      fetch(apiBase() + '/health').then(function (r) { return r.json(); })
        .then(function (j) { if (j && j.encrypted === true) setProtect(true); }).catch(function () {});
    } catch (e) {}
  }
  function closeNote() { document.getElementById('privModal').classList.add('hidden'); }

  function doDelete() {
    var pw = document.getElementById('acctDelPw').value;
    if (!pw) { alert('Please enter your password.'); return Promise.resolve(); }
    var btn = document.getElementById('acctDelGo');
    btn.disabled = true; btn.textContent = 'Deleting…';
    return fetch(apiBase() + '/account', { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password: pw }) })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        if (!j.success) throw new Error(j.error || 'Delete failed');
        if (window.ccSession && window.ccSession.clear) window.ccSession.clear();
        alert('Your account and history were deleted.');
        window.ccPrivacy.reload();
      })
      .catch(function (e) { alert('Delete failed: ' + e.message); })
      .then(function () { btn.disabled = false; btn.textContent = 'Yes, delete everything'; });
  }

  window.ccPrivacy = { open: openNote, close: closeNote, del: doDelete, reload: function () { window.location.reload(); } };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', build); else build();
})();
