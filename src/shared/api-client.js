/* Shared frontend <-> backend client. SHARED FILE (owner: TV5) - do not edit without telling the team.
 *
 *   const hubs = await API.get('/api/hubs');
 *   await API.post('/api/reservation/vehicles/reserve', { hub_id: 'HUB-METRO' });
 *
 * - Same origin as the backend (pages are served at /app/), so BASE is ''.
 * - The login session ({token: <JWT>, role, full_name, ...}) lives in sessionStorage; the JWT is
 *   sent as `Authorization: Bearer <jwt>`.
 * - HTTP 401 (missing / expired / forged token) clears the session and redirects to /app/login.html.
 * - Unfinished backend endpoints return 501 {owner, use_case}; the client surfaces it as err.todo.
 *
 * Login helpers:  API.loginGoogle(credential) | API.login(email)  (demo accounts, DEMO_MODE only)
 *                 API.config() -> {google_client_id, demo_mode, demo_accounts}
 *                 API.homeFor(session) -> first page for that role (onboarding for new students)
 */
const API = (() => {
  const BASE = location.protocol === 'file:' ? 'http://localhost:8000' : '';
  const KEY = 'hub_session';

  function session() {
    try { return JSON.parse(sessionStorage.getItem(KEY)) || null; } catch (e) { return null; }
  }
  function setSession(s) {
    try { s ? sessionStorage.setItem(KEY, JSON.stringify(s)) : sessionStorage.removeItem(KEY); } catch (e) {}
  }
  function toLogin() {
    setSession(null);
    const next = encodeURIComponent(location.pathname + location.search);
    if (!location.pathname.endsWith('/login.html')) location.href = '/app/login.html?next=' + next;
  }

  async function request(method, path, body) {
    const headers = { 'Content-Type': 'application/json' };
    const s = session();
    if (s) headers.Authorization = 'Bearer ' + s.token;
    const res = await fetch(BASE + path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
    const text = await res.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch (e) { data = text; }
    if (!res.ok) {
      const detail = data && data.detail;
      const err = new Error(typeof detail === 'string' ? detail : (detail && detail.message) || res.statusText);
      err.detail = detail;   // Structured business errors (e.g. confirm outdated data).
      err.status = res.status;
      err.todo = res.status === 501 ? data : null;   // {owner, use_case, hint}
      if (res.status === 401 && s && !path.startsWith('/api/auth/')) toLogin();
      throw err;
    }
    return data;
  }

  function homeFor(s) {
    if (!s) return '/app/login.html';
    if (s.role === 'operator') return '/app/operator/dashboard.html';
    return s.onboarded === false ? '/app/onboarding.html' : '/app/student/find-hub.html';
  }

  return {
    session, setSession, homeFor, toLogin,
    get: (p) => request('GET', p),
    post: (p, b) => request('POST', p, b === undefined ? {} : b),
    patch: (p, b) => request('PATCH', p, b),
    config: () => request('GET', '/api/auth/config'),
    async login(email) { const s = await request('POST', '/api/auth/demo-login', { email }); setSession(s); return s; },
    async loginGoogle(credential) { const s = await request('POST', '/api/auth/google', { credential }); setSession(s); return s; },
    async refreshProfile() {
      const me = await request('GET', '/api/me');
      const s = session(); if (s) setSession({ ...s, full_name: me.full_name, student_code: me.student_code, onboarded: me.onboarded });
      return me;
    },
    logout() { setSession(null); },
  };
})();
