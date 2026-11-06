/* Shared page helpers. SHARED FILE.
 * Every page: <head> loads /shared/i18n.js; <body data-role="student|operator|any"> + <nav id="nav"></nav> + <main id="app"></main>
 * then <script src="/shared/api-client.js"> and <script src="/app/assets/js/main.js">.
 * Call  Hub.init()  first; use Hub.render(el, promise, draw) to show loading / 501 TODO / errors uniformly.
 * All user-facing text goes through I18n (data-i18n="key" in HTML, I18n.t('key') in JS) - never hard-code a language.
 * Draw functions are re-run automatically when the language changes, so build your DOM inside draw().
 */
const Hub = (() => {
  const t = (k, v) => I18n.t(k, v);

  const MENU = {
    student: [
      ['find-hub.html', 'menu.findHub'], ['reserve-vehicle.html', 'menu.reserve'],
      ['my-trips.html', 'menu.trips'], ['charging-request.html', 'menu.charging'],
      ['wallet.html', 'menu.wallet'],
    ],
    operator: [
      ['dashboard.html', 'menu.dashboard'], ['incidents.html', 'menu.incidents'],
      ['charging.html', 'menu.stations'], ['what-if.html', 'menu.whatIf'],
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
    const items = s ? (MENU[s.role] || []) : [];
    const base = s ? '/app/' + s.role + '/' : '/app/';
    const here = location.pathname.split('/').pop();
    const dark = I18n.theme === 'dark';
    nav.setAttribute('aria-label', t('common.mainNav'));
    nav.innerHTML =
      `<a class="brand" href="/app/index.html"><span class="logo">${icon('zap')}</span><span>${esc(t('app.name'))}</span></a>` +
      `<div class="links">${items.map(([f, k]) =>
        `<a href="${base}${f}"${f === here ? ' aria-current="page"' : ''}>${esc(t(k))}</a>`).join('')}</div>` +
      `<div class="tools">` +
        `<div class="seg" role="group" aria-label="${esc(t('common.language'))}">` +
          I18n.SUPPORTED.map(l => `<button type="button" data-lang="${l}" aria-pressed="${I18n.lang === l}" lang="${l}">${l.toUpperCase()}</button>`).join('') +
        `</div>` +
        `<button type="button" class="icon-btn" id="theme-toggle" aria-label="${esc(t(dark ? 'common.themeLight' : 'common.themeDark'))}">${icon(dark ? 'sun' : 'moon')}</button>` +
        (s ? `<span class="who"><span class="name"><b>${esc(s.full_name)}</b> · ${esc(t('role.' + s.role))}</span>` +
             `<button type="button" class="icon-btn" id="logout" aria-label="${esc(t('common.logout'))}" title="${esc(t('common.logout'))}">${icon('logout')}</button></span>` : '') +
      `</div>`;
    nav.querySelectorAll('[data-lang]').forEach(b => b.onclick = () => I18n.setLang(b.dataset.lang));
    nav.querySelector('#theme-toggle').onclick = () => I18n.setTheme(I18n.theme === 'dark' ? 'light' : 'dark');
    const lo = nav.querySelector('#logout');
    if (lo) lo.onclick = () => { API.logout(); location.href = '/app/index.html'; };
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
    if (need !== 'any' && (!s || s.role !== need)) { location.href = '/app/index.html'; return null; }
    if (!document.querySelector('.skip-link')) {
      const a = document.createElement('a');
      a.className = 'skip-link'; a.href = '#main'; a.dataset.i18n = 'common.skip';
      document.body.prepend(a);
    }
    const main = document.querySelector('main'); if (main) main.id = 'main';
    drawNav(); I18n.apply();
    return s;
  }

  document.addEventListener('langchange', () => {
    drawNav(); I18n.apply();
    views.forEach((v, el) => { if (el.isConnected) paint(el, v); });
  });
  document.addEventListener('themechange', drawNav);

  return { init, render, esc, icon, t };
})();
