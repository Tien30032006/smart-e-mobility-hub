/* Shared frontend <-> backend client. SHARED FILE - do not edit without telling the team.
 *
 *   const hubs = await API.get('/api/hubs');
 *   await API.post('/api/reservation/vehicles/reserve', { hub_id: 'HUB-METRO' });
 *
 * - Same origin as the backend (pages are served at /app/), so BASE is ''.
 * - The login token (= user_id) is kept in sessionStorage and sent as a Bearer header.
 * - Unfinished backend endpoints return 501 {owner, use_case}; the client surfaces it as err.todo.
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

  async function request(method, path, body) {
    const headers = { 'Content-Type': 'application/json' };
    const s = session();
    if (s) headers.Authorization = 'Bearer ' + s.token;
    const res = await fetch(BASE + path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
    const text = await res.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch (e) { data = text; }
    if (!res.ok) {
      const err = new Error((data && data.detail) || res.statusText);
      err.status = res.status;
      err.todo = res.status === 501 ? data : null;   // {owner, use_case, hint}
      throw err;
    }
    return data;
  }

  return {
    session, setSession,
    get: (p) => request('GET', p),
    post: (p, b) => request('POST', p, b === undefined ? {} : b),
    patch: (p, b) => request('PATCH', p, b),
    async login(email) { const s = await request('POST', '/api/auth/login', { email }); setSession(s); return s; },
    logout() { setSession(null); },
  };
})();
