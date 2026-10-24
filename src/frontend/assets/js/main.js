/* Shared page helpers. SHARED FILE.
 * Every page: <body data-role="student|operator|any"> + <nav id="nav"></nav> + <main id="app"></main>
 * then <script src="/shared/api-client.js"> and <script src="/app/assets/js/main.js">.
 * Call  Hub.init()  first; use Hub.render(el, promise) to show loading / 501 TODO / errors uniformly.
 */
const Hub = (() => {
  const MENU = {
    student: [
      ['find-hub.html', 'Tìm Hub & xe'], ['reserve-vehicle.html', 'Đặt xe / chỗ đỗ'],
      ['my-trips.html', 'Chuyến của tôi'], ['charging-request.html', 'Sạc xe'],
    ],
    operator: [
      ['dashboard.html', 'Dashboard'], ['incidents.html', 'Sự cố'],
      ['charging.html', 'Trạm sạc'], ['what-if.html', 'What-if'],
    ],
  };

  function esc(s) { return String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }

  function init() {
    const s = API.session();
    const need = document.body.dataset.role || 'any';
    if (need !== 'any' && (!s || s.role !== need)) { location.href = '/app/index.html'; return null; }
    const nav = document.getElementById('nav');
    if (nav) {
      const items = s ? (MENU[s.role] || []) : [];
      const base = s ? '/app/' + s.role + '/' : '/app/';
      nav.innerHTML = '<a class="brand" href="/app/index.html">⚡ Smart E-Mobility Hub</a>' +
        items.map(([f, t]) => `<a href="${base}${f}">${t}</a>`).join('') +
        (s ? `<span class="who">${esc(s.full_name)} (${s.role}) <a href="#" id="logout">Đăng xuất</a></span>` : '');
      const lo = document.getElementById('logout');
      if (lo) lo.onclick = (e) => { e.preventDefault(); API.logout(); location.href = '/app/index.html'; };
    }
    return s;
  }

  /* Show result of an API promise inside el. Unfinished backend -> yellow TODO box with the owner. */
  async function render(el, promise, draw) {
    el.innerHTML = '<p class="muted">Đang tải…</p>';
    try { const data = await promise; el.innerHTML = ''; draw(data); }
    catch (err) {
      if (err.todo) el.innerHTML = `<div class="todo">⏳ Chưa làm: <b>${esc(err.todo.use_case)}</b> — người phụ trách: <b>${esc(err.todo.owner)}</b><br><small>${esc(err.todo.hint || '')}</small></div>`;
      else el.innerHTML = `<div class="error">Lỗi: ${esc(err.message)}</div>`;
    }
  }

  return { init, render, esc };
})();
