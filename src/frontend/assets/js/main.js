/* Shared page helpers. SHARED FILE.
 * Every page: <head> loads /shared/i18n.js; <body data-role="student|operator|any"> + <nav id="nav"></nav> + <main id="app"></main>
 * then <script src="/shared/api-client.js"> and <script src="/app/assets/js/main.js">.
 * Call  Hub.init()  first; use Hub.render(el, promise, draw) to show loading / 501 TODO / errors uniformly.
 * All user-facing text goes through I18n (data-i18n="key" in HTML, I18n.t('key') in JS) - never hard-code a language.
 * Draw functions are re-run automatically when the language changes, so build your DOM inside draw().
 */
if (!document.querySelector('link[rel~="icon"]')) {
  const favicon = document.createElement('link');
  favicon.rel = 'icon';
  favicon.type = 'image/png';
  favicon.href = '/app/assets/img/brand-mark.png';
  document.head.appendChild(favicon);
}

const Hub = (() => {
  const t = (k, v) => I18n.t(k, v);

  /* [file, i18n key, icon, short tab label key] */
  const MENU = {
    student: [
      ['find-hub.html', 'menu.findHub', 'map', 'tab.discover'],
      ['my-trips.html', 'menu.trips', 'bike', 'tab.trips'],
      ['charging-request.html', 'menu.charging', 'zap', 'tab.charge'],
      ['personal.html', 'menu.personal', 'user', 'tab.personal'],
    ],
    operator: [
      ['dashboard.html', 'menu.dashboard', 'grid'], ['alerts.html', 'menu.alerts', 'alert'],
      ['redistribution.html', 'menu.redistribution', 'bike'], ['incidents.html', 'menu.incidents', 'bell'],
      ['charging.html', 'menu.stations', 'plug'], ['what-if.html', 'menu.whatIf', 'sliders'],
    ],
  };

  /* Inline SVG icons (Lucide-style, stroke = currentColor). Decorative by default -> aria-hidden. */
  const ICONS = {
    zap: '<path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    bike: '<circle cx="5.5" cy="17.5" r="3.5"/><circle cx="18.5" cy="17.5" r="3.5"/><path d="M15 6h-3l-3 6 3 5.5M12 12h6.5l-3.5-6"/>',
    shield: '<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6l-8-3z"/><path d="m9 12 2 2 4-4"/>',
    parking: '<rect x="3" y="3" width="18" height="18" rx="4"/><path d="M9 17V7h4a3 3 0 0 1 0 6H9"/>',
    plug: '<path d="M9 2v6M15 2v6M6 8h12v4a6 6 0 0 1-12 0V8zM12 18v4"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    moon: '<path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z"/>',
    construction: '<path d="M12 3 2 21h20L12 3z"/><path d="M12 10v5M12 18h.01"/>',
    alert: '<circle cx="12" cy="12" r="10"/><path d="M12 8v5M12 16h.01"/>',
    map: '<path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2zM9 4v14M15 6v14"/>',
    pin: '<path d="M12 21s7-6.2 7-11.5a7 7 0 0 0-14 0C5 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    chevron: '<path d="m9 6 6 6-6 6"/>',
    locate: '<circle cx="12" cy="12" r="3"/><circle cx="12" cy="12" r="8"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/>',
    grid: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    bell: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 8 3 8H3s3-1 3-8M10 20a2 2 0 0 0 4 0"/>',
    chart: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    sliders: '<path d="M4 6h10M18 6h2M4 12h2M10 12h10M4 18h12"/><circle cx="16" cy="6" r="2"/><circle cx="8" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>',
    refresh: '<path d="M21 12a9 9 0 0 1-15.5 6.2M3 12A9 9 0 0 1 18.5 5.8M18 2v4h-4M6 22v-4h4"/>',
    logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>',
  };
  function icon(name, cls) {
    return `<svg class="icon ${cls || ''}" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${ICONS[name] || ''}</svg>`;
  }

  function esc(s) { return String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }

  /* ---------- Navigation ---------- */
  function drawNav() {
    const nav = document.getElementById('nav');
    if (!nav) return;
    const s = API.session();
    const role = s ? s.role : null;
    document.body.classList.toggle('shell-student', role === 'student');
    document.body.classList.toggle('shell-operator', role === 'operator');
    const items = s ? (MENU[s.role] || []) : [];
    const base = s ? '/app/' + s.role + '/' : '/app/';
    const here = location.pathname.split('/').pop();
    // Reservation pages are entered from Discover (with a selected hub) or Trips (viewing a pass).
    const activeFile = here === 'reserve-vehicle.html'
      ? (new URLSearchParams(location.search).has('hub_id') ? 'find-hub.html' : 'my-trips.html')
      : here;
    const dark = I18n.theme === 'dark';
    const sub = role ? `<small>${esc(t('role.' + role))}</small>` : '';
    nav.setAttribute('aria-label', t('common.mainNav'));
    nav.innerHTML =
      `<a class="brand" href="/app/index.html"><span class="logo"><img src="/app/assets/img/brand-mark.png" alt=""></span><span class="t"><span>${esc(t('app.name'))}</span>${sub}</span></a>` +
      `<div class="links">${items.map(([f, k, ic]) =>
        `<a href="${base}${f}"${f === activeFile ? ' aria-current="page"' : ''}>${role === 'operator' ? icon(ic) : ''}${esc(t(k))}</a>`).join('')}</div>` +
      `<div class="tools">` +
        `<div class="seg language-switch" role="group" aria-label="${esc(t('common.language'))}">` +
          I18n.SUPPORTED.map(l => `<button type="button" data-lang="${l}" aria-pressed="${I18n.lang === l}" lang="${l}">${l.toUpperCase()}</button>`).join('') +
        `</div>` +
        `<button type="button" class="icon-btn" id="theme-toggle" aria-label="${esc(t(dark ? 'common.themeLight' : 'common.themeDark'))}">${icon(dark ? 'sun' : 'moon')}</button>` +
        (s ? `<span class="who"><span class="name"><b>${esc(s.full_name)}</b><br>${esc(t('role.' + s.role))}</span>` +
             `<button type="button" class="icon-btn" id="logout" aria-label="${esc(t('common.logout'))}" title="${esc(t('common.logout'))}">${icon('logout')}</button></span>` : '') +
      `</div>`;
    nav.querySelector('#theme-toggle').onclick = () => I18n.setTheme(I18n.theme === 'dark' ? 'light' : 'dark');
    nav.querySelectorAll('[data-lang]').forEach(b => b.onclick = () => I18n.setLang(b.dataset.lang));
    const lo = nav.querySelector('#logout');
    if (lo) lo.onclick = () => { API.logout(); location.href = '/app/index.html'; };

    /* Student: bottom tab bar (thumb reach), separate landmark from the top bar. */
    let tb = document.getElementById('tabbar');
    if (role === 'student') {
      if (!tb) { tb = document.createElement('nav'); tb.id = 'tabbar'; tb.className = 'tabbar'; document.body.appendChild(tb); }
      tb.setAttribute('aria-label', t('common.mainNav'));
      tb.innerHTML = items.map(([f, k, ic, sk]) =>
        `<a href="${base}${f}"${f === activeFile ? ' aria-current="page"' : ''}>${icon(ic)}<span>${esc(t(sk))}</span></a>`).join('');
    } else if (tb) tb.remove();
  }

  /* ---------- Render API results (loading / data / 501 / error), re-drawn on language change ---------- */
  const views = new Map();   // el -> { state, data, err, draw }

  function paint(el, v) {
    if (v.state === 'loading') {
      el.setAttribute('aria-busy', 'true');
      el.innerHTML = `<div class="skeleton" role="status" aria-label="${esc(t('common.loading'))}"><i></i><i></i><i></i></div>`;
      return;
    }
    el.removeAttribute('aria-busy');
    if (v.state === 'data') { el.innerHTML = ''; v.draw(v.data); return; }
    if (v.state === 'todo') {
      const td = v.err.todo;
      el.innerHTML = `<div class="todo" role="status">${icon('construction')}<div><b>${esc(t('common.notImplemented'))}</b> — ${esc(td.use_case)}` +
        ` · ${esc(t('common.owner'))}: <b>${esc(td.owner)}</b>` +
        (td.hint ? `<br><small class="muted">${esc(td.hint)}</small>` : '') + `</div></div>`;
      return;
    }
    el.innerHTML = `<div class="error" role="alert">${icon('alert')}<div><b>${esc(t('common.error'))}:</b> ${esc(v.err.message)}</div></div>`;
  }

  async function render(el, promise, draw) {
    const v = { state: 'loading', draw };
    views.set(el, v); paint(el, v);
    try { v.data = await promise; v.state = 'data'; }
    catch (err) { v.err = err; v.state = err.todo ? 'todo' : 'error'; }
    paint(el, v);
  }

  function init() {
    const s = API.session();
    const need = document.body.dataset.role || 'any';
    if (need !== 'any' && !s) { API.toLogin(); return null; }
    if (need !== 'any' && s.role !== need) { location.href = API.homeFor(s); return null; }
    if (need === 'student' && s.onboarded === false && !location.pathname.endsWith('/onboarding.html')) {
      location.href = '/app/onboarding.html'; return null;
    }
    if (!document.querySelector('.skip-link')) {
      const a = document.createElement('a');
      a.className = 'skip-link'; a.href = '#main'; a.dataset.i18n = 'common.skip';
      document.body.prepend(a);
    }
    const main = document.querySelector('main'); if (main) main.id = 'main';
    drawNav(); I18n.apply();
    /* Keep demo resets data-only. Reloading the document here discarded unfinished form
       input (for example, a name being entered during onboarding). */
    const startResetListener = () => {
      if (typeof Stream !== 'undefined' && !window.__hubResetListener) {
        window.__hubResetListener = true;
        Stream.on('system_reset', () => {
          window.dispatchEvent(new CustomEvent('hub:data-reset'));
        });
      }
    };
    if (typeof Stream !== 'undefined') startResetListener();
    else {
      const streamScript = document.createElement('script');
      streamScript.src = '/shared/stream.js';
      streamScript.onload = startResetListener;
      document.head.appendChild(streamScript);
    }
    return s;
  }

  document.addEventListener('langchange', () => {
    drawNav(); I18n.apply();
    views.forEach((v, el) => { if (el.isConnected) paint(el, v); });
  });
  document.addEventListener('themechange', drawNav);

  /* Count-up for KPI numbers (one orchestrated moment on load; skipped for reduced motion). */
  function countUp(el, to) {
    if (matchMedia('(prefers-reduced-motion: reduce)').matches || !isFinite(to)) { el.textContent = to; return; }
    const t0 = performance.now(), dur = 700;
    const step = now => { const p = Math.min(1, (now - t0) / dur); el.textContent = Math.round(to * (1 - Math.pow(1 - p, 3))); if (p < 1) requestAnimationFrame(step); };
    requestAnimationFrame(step);
  }
  /* Stock tone shared by student map/list and operator console: '' | 'warn' | 'bad'. */
  function tone(h) { return h.free_spaces === 0 ? 'bad' : (h.vehicles_available <= 2 ? 'warn' : ''); }
  const SLOTS = [[27, 29], [73, 36], [52, 60], [27, 80], [76, 86], [52, 24]];   // schematic pin positions (% of map)
  function mapHtml(hubs, labelFn, selected) {
    return '<div class="cmap" role="group" aria-label="' + esc(t('page.findHub.mapNote')) + '">' +
      '<i class="block" style="left:8%;top:54%;width:26%;height:16%"></i><i class="block" style="left:56%;top:8%;width:20%;height:24%"></i><i class="block" style="left:62%;top:66%;width:28%;height:14%"></i>' +
      '<i class="route" style="left:27%;top:29%;width:21%;height:51%"></i>' +
      hubs.map((h, i) => { const [x, y] = SLOTS[i % SLOTS.length]; const tn = tone(h);
        return `<button type="button" class="pin ${tn}" data-hub="${esc(h.hub_id)}" aria-pressed="${selected === h.hub_id}" style="left:${x}%;top:${y}%"><span class="tag"><b>${esc(I18n.hubName(h))}</b><span>${labelFn(h)}</span></span><span class="dot"></span></button>`; }).join('') +
      '<span class="note">' + esc(t('page.findHub.mapNote')) + '</span></div>';
  }
  /* ---------- Toast + confirm modal (shared components, TV5) ---------- */
  function toast(message, kind) {
    let box = document.getElementById('toasts');
    if (!box) { box = document.createElement('div'); box.id = 'toasts'; box.className = 'toasts'; box.setAttribute('role', 'status'); box.setAttribute('aria-live', 'polite'); document.body.appendChild(box); }
    const el = document.createElement('div');
    el.className = 'toast ' + (kind || 'info');
    el.textContent = message;
    box.appendChild(el);
    setTimeout(() => { el.classList.add('out'); setTimeout(() => el.remove(), 250); }, 4500);
    while (box.children.length > 4) box.firstChild.remove();
  }
  function confirmDialog(title, body, okLabel) {
    return new Promise(resolve => {
      const back = document.createElement('div');
      back.className = 'modal-backdrop';
      back.innerHTML = `<div class="modal" role="dialog" aria-modal="true" aria-labelledby="mdl-t"><h2 id="mdl-t">${esc(title)}</h2><p>${esc(body || '')}</p>` +
        `<div class="actions"><button type="button" class="secondary" data-x="0">${esc(t('common.cancel'))}</button><button type="button" data-x="1">${esc(okLabel || t('common.confirm'))}</button></div></div>`;
      const done = v => { back.remove(); document.removeEventListener('keydown', onKey); resolve(v); };
      const onKey = e => { if (e.key === 'Escape') done(false); };
      back.addEventListener('click', e => { if (e.target === back) done(false); const b = e.target.closest('[data-x]'); if (b) done(b.dataset.x === '1'); });
      document.addEventListener('keydown', onKey);
      document.body.appendChild(back);
      back.querySelector('[data-x="1"]').focus();
    });
  }
  /* Small live/polling indicator for the top bar; call once on pages that use Stream. */
  function liveBadge() {
    if (typeof Stream === 'undefined') return;
    let b = document.getElementById('live-badge');
    if (!b) { b = document.createElement('span'); b.id = 'live-badge'; b.className = 'live-badge'; (document.getElementById('nav') || document.body).appendChild(b); }
    Stream.onStatus(st => { b.dataset.state = st; b.textContent = t('live.' + st); });
    document.addEventListener('langchange', () => { b.textContent = t('live.' + (Stream.status || 'idle')); });
  }
  return { init, render, esc, icon, t, countUp, tone, mapHtml, toast, confirmDialog, liveBadge };
})();
