/* Realtime client (Server-Sent Events). SHARED FILE (owner: TV5).
 *
 *   Stream.on('hub_updated', (d) => reloadHubs());          // d = {hub_id, ts, ...} or {polled:true}
 *   Stream.on('alert_created', (d) => toast(d.message));
 *   Stream.onStatus((st) => badge.textContent = st);        // 'live' | 'polling' | 'idle'
 *
 * Events: hub_updated, vehicle_updated, alert_created, reservation_changed, payment_updated.
 * - Connects to /api/stream?token=<jwt> (EventSource cannot send headers).
 * - Reconnects with back-off. While not connected it falls back to POLLING: every handler is
 *   called with {polled:true} every Stream.pollMs, so a page that simply re-fetches keeps working.
 * - Bursts are coalesced: a handler runs at most once per Stream.throttleMs per event name.
 */
const Stream = (() => {
  const NAMES = ['hub_updated', 'vehicle_updated', 'alert_created', 'reservation_changed', 'payment_updated'];
  const handlers = {}, statusFns = [], lastRun = {}, pending = {};
  let es = null, status = 'idle', retry = 0, pollTimer = null, reconnectTimer = null;
  const api = { pollMs: 10000, throttleMs: 300 };

  function setStatus(s) {
    if (s === status) return;
    status = s; statusFns.forEach(fn => { try { fn(s); } catch (e) {} });
  }
  function run(name, data) {
    (handlers[name] || []).forEach(fn => { try { fn(data); } catch (e) { console.error('stream handler', name, e); } });
  }
  function deliver(name, data) {
    const now = Date.now(), wait = api.throttleMs - (now - (lastRun[name] || 0));
    if (wait <= 0) { lastRun[name] = now; run(name, data); return; }
    clearTimeout(pending[name]);
    pending[name] = setTimeout(() => { lastRun[name] = Date.now(); run(name, data); }, wait);
  }
  function startPolling() {
    if (pollTimer) return;
    setStatus('polling');
    pollTimer = setInterval(() => Object.keys(handlers).forEach(n => deliver(n, { polled: true })), api.pollMs);
  }
  function stopPolling() { clearInterval(pollTimer); pollTimer = null; }

  function connect() {
    const s = API.session();
    if (!s || es || typeof EventSource === 'undefined') { if (!es && !pollTimer) startPolling(); return; }
    es = new EventSource('/api/stream?token=' + encodeURIComponent(s.token));
    NAMES.forEach(n => es.addEventListener(n, e => { try { deliver(n, JSON.parse(e.data)); } catch (err) {} }));
    es.onopen = () => { retry = 0; stopPolling(); setStatus('live'); };
    es.onerror = () => {
      startPolling();                                      // keep the page fresh while we reconnect
      if (es.readyState === EventSource.CLOSED) {          // server refused (401) or went away
        es.close(); es = null;
        API.get('/api/me').catch(() => {});                // a 401 here sends the user to the login page
        clearTimeout(reconnectTimer);
        reconnectTimer = setTimeout(connect, Math.min(30000, 1000 * 2 ** retry++));
      }                                                    // otherwise EventSource retries by itself
    };
  }
  function on(name, fn) {
    (handlers[name] = handlers[name] || []).push(fn);
    connect();
    return () => { handlers[name] = handlers[name].filter(f => f !== fn); };
  }
  function close() { if (es) es.close(); es = null; stopPolling(); clearTimeout(reconnectTimer); setStatus('idle'); }

  Object.assign(api, { on, close, connect, onStatus(fn) { statusFns.push(fn); fn(status); } });
  Object.defineProperty(api, 'status', { get: () => status, enumerable: true });   // live value, not a copy
  return api;
})();
