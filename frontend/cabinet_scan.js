/* cabinet_scan.js - "Scan a whole shelf at once".
 * Adds a box to the cabinet step: take one photo, see numbered outlines over it, tick the medicines you want,
 * and add them to the same list "Check my cabinet" already uses. Nothing else on the page changes. */
(function () {
  'use strict';

  var CSS = '' +
    '.shelf-card{border:1.5px dashed var(--border,#CBD5E1);border-radius:12px;padding:16px;margin-bottom:16px;background:var(--accent-light,#EFF6FF)}' +
    '.shelf-head{display:flex;align-items:center;gap:8px;font-weight:700;color:var(--navy,#1E3A5F);margin-bottom:4px}' +
    '.shelf-sub{font-size:.85rem;color:var(--muted,#64748B);margin-bottom:12px}' +
    '.shelf-img-wrap{position:relative;display:block;margin:12px 0;border-radius:10px;overflow:hidden;line-height:0}' +
    '.shelf-img-wrap img{width:100%;height:auto;display:block}' +
    '.shelf-ov{position:absolute;box-sizing:border-box;border:3px solid;border-radius:4px;cursor:pointer}' +
    '.shelf-ov.ov-high{border-color:#22C55E}.shelf-ov.ov-med{border-color:#F59E0B}.shelf-ov.ov-low{border-color:#EF4444}' +
    '.shelf-ov.on{box-shadow:0 0 0 3px rgba(30,58,95,.55);background:rgba(255,255,255,.18)}' +
    '.shelf-n{display:inline-flex;align-items:center;justify-content:center;min-width:22px;height:22px;border-radius:11px;' +
    'background:var(--navy,#1E3A5F);color:#fff;font-size:.72rem;font-weight:700;line-height:22px;padding:0 5px}' +
    '.shelf-ov .shelf-n{position:absolute;top:-1px;left:-1px;border-radius:4px 0 6px 0}' +
    '.shelf-item{display:flex;align-items:flex-start;gap:10px;padding:10px;margin-bottom:8px;border:1.5px solid var(--border,#E2E8F0);' +
    'border-radius:10px;background:#fff;cursor:pointer}.shelf-item.on{border-color:var(--navy,#1E3A5F)}' +
    '.shelf-item input{margin-top:4px;width:18px;height:18px}.shelf-item .body{flex:1;min-width:0}' +
    '.shelf-name{font-weight:600;font-size:.92rem;word-break:break-word}' +
    '.shelf-meta{font-size:.78rem;color:var(--muted,#64748B);margin-top:2px}.shelf-warn{font-size:.78rem;color:#B45309;margin-top:3px}' +
    '.shelf-found{font-weight:600;margin:6px 0 10px}';

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function pct(v) { return Math.round(v * 10000) / 100; }   // 0.3 -> 30, with no long decimals
  function apiBase() { return (typeof API !== 'undefined') ? API : ''; }

  var state = { items: [], added: {}, url: null };

  function build() {
    var step2 = document.getElementById('step2');
    if (!step2 || document.getElementById('shelfCard')) return;
    var st = document.createElement('style'); st.id = 'shelfStyle'; st.textContent = CSS; document.head.appendChild(st);
    var card = document.createElement('div');
    card.id = 'shelfCard'; card.className = 'shelf-card';
    card.innerHTML =
      '<div class="shelf-head"><span>📷</span><span>Scan a whole shelf at once</span></div>' +
      '<div class="shelf-sub">Take one photo of your shelf or cabinet. We\'ll outline each package and read what we can.</div>' +
      '<input type="file" accept="image/*" id="shelfFile" style="display:none">' +
      '<button class="btn btn-ghost" id="shelfBtn" type="button">Take or choose a photo</button>' +
      '<div id="shelfOut" class="hidden"></div>';
    var anchor = step2.querySelector('.step-intro');
    if (anchor && anchor.nextSibling) step2.insertBefore(card, anchor.nextSibling); else step2.appendChild(card);
    var input = document.getElementById('shelfFile');
    document.getElementById('shelfBtn').addEventListener('click', function () { input.click(); });
    input.addEventListener('change', function () { if (input.files && input.files[0]) scan(input.files[0]); });
  }

  function scan(file) {
    var btn = document.getElementById('shelfBtn'), out = document.getElementById('shelfOut');
    btn.disabled = true; btn.textContent = 'Looking at your shelf…';
    if (state.url && window.URL && URL.revokeObjectURL) URL.revokeObjectURL(state.url);
    state.url = (window.URL && URL.createObjectURL) ? URL.createObjectURL(file) : '';
    var fd = new FormData(); fd.append('file', file);
    return fetch(apiBase() + '/scan-cabinet', { method: 'POST', body: fd })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        if (!j.success) throw new Error(j.error || 'Scan failed');
        render(j.data, state.url);
      })
      .catch(function (e) { alert('Scan failed: ' + e.message); })
      .then(function () { btn.disabled = false; btn.textContent = 'Take or choose a photo'; });
  }

  function label(it) {
    return it.name ? esc(it.name + (it.strength ? ' ' + it.strength : '')) : null;
  }

  function render(data, url) {
    var out = document.getElementById('shelfOut');
    state.items = data.items || []; state.added = {};
    var html = '';
    if (!state.items.length) {
      out.innerHTML = '<div class="result-meta" style="margin-top:12px">No packages found. Try a closer, brighter photo.</div>';
      out.classList.remove('hidden'); return;
    }
    html += '<div class="shelf-img-wrap" id="shelfWrap"><img id="shelfImg" alt="" src="' + esc(url) + '">';
    state.items.forEach(function (it) {
      var b = it.box, cls = it.needs_closeup ? 'ov-low' : (it.confidence === 'high' ? 'ov-high' : 'ov-med');
      html += '<div class="shelf-ov ' + cls + '" data-id="' + it.id + '" style="left:' + pct(b[0]) + '%;top:' + pct(b[1]) +
              '%;width:' + pct(b[2] - b[0]) + '%;height:' + pct(b[3] - b[1]) + '%"><span class="shelf-n">' + it.id + '</span></div>';
    });
    html += '</div>';
    html += '<div class="shelf-found">We found ' + state.items.length + ' package' + (state.items.length === 1 ? '' : 's') + '.</div>';
    if (data.notes) html += '<div class="result-meta" style="margin-bottom:8px">' + esc(data.notes) + '</div>';
    state.items.forEach(function (it) {
      var name = label(it), pill = it.needs_closeup ? ['pill-unclear', '⚠ Close-up needed'] : (it.confidence === 'high' ? ['pill-keep', '✓ Read'] : ['pill-unclear', '? Check']);
      html += '<label class="shelf-item" data-id="' + it.id + '"><input type="checkbox" data-id="' + it.id + '"' + (it.needs_closeup ? '' : ' checked') + '>' +
        '<span class="shelf-n">' + it.id + '</span><div class="body">' +
        '<div class="shelf-name">' + (name || ('Package ' + it.id)) + '</div>' +
        '<div class="shelf-meta">' + (it.expiry ? '<span>EXP: ' + esc(it.expiry) + '</span>' : '<span>expiry not visible</span>') + '</div>' +
        (name ? '' : '<div class="shelf-warn">Couldn\'t read the name</div>') +
        (it.needs_closeup ? '<div class="shelf-warn">Take a close-up of this one with "Add a medicine" below.</div>' : '') +
        (it.notes ? '<div class="shelf-meta">' + esc(it.notes) + '</div>' : '') +
        '</div><span class="status-pill ' + pill[0] + '">' + pill[1] + '</span></label>';
    });
    html += '<div class="result-meta" style="margin:10px 0">The outlines are estimates and names are only what could be read. Always check each one against the real box.</div>' +
            '<button class="btn btn-primary" id="shelfAdd" type="button">Add checked medicines to my cabinet check</button>' +
            '<div class="next-hint hidden" id="shelfDone">✓ Added to your cabinet check</div>';
    out.innerHTML = html; out.classList.remove('hidden');
    document.getElementById('shelfAdd').addEventListener('click', addChecked);
    out.querySelectorAll('.shelf-ov').forEach(function (el) { el.addEventListener('click', function () { highlight(el.getAttribute('data-id')); }); });
    out.querySelectorAll('.shelf-item').forEach(function (el) { el.addEventListener('click', function (ev) { if (ev.target.tagName !== 'INPUT') highlight(el.getAttribute('data-id')); }); });
  }

  function highlight(id) {
    document.querySelectorAll('#shelfOut .shelf-ov, #shelfOut .shelf-item').forEach(function (el) {
      el.classList.toggle('on', el.getAttribute('data-id') === String(id) && !el.classList.contains('on'));
    });
  }

  function addChecked() {
    var list = (typeof cabinetMeds !== 'undefined') ? cabinetMeds : null;
    if (!list) return;
    var added = 0;
    document.querySelectorAll('#shelfOut input[type=checkbox]:checked').forEach(function (cb) {
      var it = state.items.filter(function (x) { return String(x.id) === cb.getAttribute('data-id'); })[0];
      if (!it || state.added[it.id]) return;
      var e = it.entry;
      var dup = e.drug_name !== 'Unknown' && list.some(function (m) { return m.drug_name === e.drug_name && (m.dosage_strength || '') === (e.dosage_strength || ''); });
      state.added[it.id] = true;
      cb.disabled = true;
      if (dup) return;
      list.push(e); added++;
    });
    if (added) {
      try { scannedCount += added; } catch (err) {}
      if (typeof updateMedCount === 'function') updateMedCount();
      var hint = document.getElementById('hint2'); if (hint) hint.classList.remove('hidden');
    }
    var done = document.getElementById('shelfDone');
    done.textContent = added ? '✓ Added to your cabinet check' : 'Nothing new to add.';
    done.classList.remove('hidden');
  }

  window.ccShelf = { render: render, scan: scan, state: state };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', build); else build();
})();
