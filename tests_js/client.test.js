const fs = require('fs'); const assert = require('assert');
// ---- minimal browser fakes
const store = {}; global.sessionStorage = { getItem: k => store[k] ?? null, setItem: (k, v) => store[k] = v, removeItem: k => delete store[k] };
global.location = { protocol: 'http:', pathname: '/app/student/find-hub.html', search: '', href: '' };
let fetchImpl; global.fetch = (...a) => fetchImpl(...a);
const load = f => (0, eval)(fs.readFileSync(f, 'utf8').replace(/^const (API|Stream) =/m, 'globalThis.$1 ='));
load('src/shared/api-client.js');
(async () => {
  // 401 clears the session and redirects with ?next=
  API.setSession({ token: 't', role: 'student' });
  fetchImpl = async () => ({ ok: false, status: 401, statusText: 'x', text: async () => '{"detail":"Token expired"}' });
  await API.get('/api/me').catch(e => assert.strictEqual(e.status, 401));
  assert.strictEqual(API.session(), null);
  assert.ok(location.href.startsWith('/app/login.html?next=%2Fapp%2Fstudent%2Ffind-hub.html'), location.href);
  // login endpoints do not redirect on 401
  location.href = ''; fetchImpl = async () => ({ ok: false, status: 401, statusText: 'x', text: async () => '{"detail":"bad"}' });
  await API.login('x@y').catch(() => {}); assert.strictEqual(location.href, '');
  // Bearer header + homeFor
  API.setSession({ token: 'JWT', role: 'operator' }); let seen;
  fetchImpl = async (u, o) => { seen = o.headers.Authorization; return { ok: true, status: 200, text: async () => '{}' }; };
  await API.get('/api/hubs'); assert.strictEqual(seen, 'Bearer JWT');
  assert.strictEqual(API.homeFor({ role: 'student', onboarded: false }), '/app/onboarding.html');
  assert.strictEqual(API.homeFor({ role: 'student', onboarded: true }), '/app/student/find-hub.html');
  assert.strictEqual(API.homeFor({ role: 'operator' }), '/app/operator/dashboard.html');

  // ---- Stream: no EventSource => polling fallback, throttling
  API.setSession({ token: 'JWT', role: 'student' });
  const timers = []; global.setInterval = (fn, ms) => { timers.push([fn, ms]); return timers.length; };
  global.clearInterval = () => {}; global.EventSource = undefined;
  load('src/shared/stream.js');
  Stream.throttleMs = 0; const calls = [];
  Stream.on('hub_updated', d => calls.push(d));
  assert.strictEqual(Stream.status, 'polling'); assert.strictEqual(timers[0][1], 10000);
  timers[0][0](); assert.deepStrictEqual(calls, [{ polled: true }]);
  // with EventSource: wires listeners + token in URL, onopen => live, onerror => polling
  class FakeES { constructor(u) { FakeES.last = this; this.url = u; this.listeners = {}; this.readyState = 1; }
    addEventListener(n, f) { this.listeners[n] = f; } close() { this.readyState = 2; } }
  FakeES.CLOSED = 2; global.EventSource = FakeES; global.setTimeout = (f) => 0;
  load('src/shared/stream.js'); Stream.throttleMs = 0; const got = [];
  Stream.on('alert_created', d => got.push(d));
  assert.ok(FakeES.last.url.startsWith('/api/stream?token=JWT'));
  FakeES.last.onopen(); assert.strictEqual(Stream.status, 'live');
  FakeES.last.listeners.alert_created({ data: '{"message":"Metro full","seq":1}' });
  assert.strictEqual(got[0].message, 'Metro full');
  FakeES.last.onerror(); assert.strictEqual(Stream.status, 'polling');
  console.log('frontend client tests passed');
})().catch(e => { console.error(e); process.exit(1); });
