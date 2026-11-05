/* TV2-only UI helpers. Shared auth/SSE implementation remains owned by TV5. */
const Charging = (() => {
  const t = Hub.t, esc = Hub.esc, $ = id => document.getElementById(id);
  const fmt = value => value ? new Date(value).toLocaleString(I18n.lang) : '—';
  const local = value => {const d=new Date(value);return new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,16);};
  function init() {
    const session=Hub.init(); if(!session)return null;
    const links=[['charging-request.html','charging.request'],['charging-schedule.html','charging.schedulePage'],
      ['charging-status.html','charging.statusPage'],['charging-vehicles.html','charging.vehiclesPage']];
    const nav=$('charging-nav');
    if(nav) nav.innerHTML=links.map(([file,key])=>`<a href="${file}" data-i18n="${key}"${location.pathname.endsWith(file)?' aria-current="page"':''}>${esc(t(key))}</a>`).join('');
    return session;
  }
  function message(text,error=false) {
    const el=$('message');if(!el)return;
    el.textContent=text;el.className=error?'error':'card';el.setAttribute('role',error?'alert':'status');
  }
  async function run(button,fn) {
    if(button)button.disabled=true;
    try {return await fn();} catch(err){message(err.message,true);}
    finally {if(button?.isConnected)button.disabled=false;}
  }
  function field(id,text='') {
    const el=$(id+'-error');if(el)el.textContent=text;
    const input=$(id);if(input)input.setAttribute('aria-invalid',text?'true':'false');
    return !text;
  }
  function stale(items) {
    message(items.map(i=>`${i.id} · ${t('charging.lastUpdate')}: ${fmt(i.last_update)} · ${t('charging.age')}: ${i.age_seconds===null?'—':Math.round(i.age_seconds)} · ${JSON.stringify(i.last_known_values)}`).join('\n'));
    return confirm(t('charging.confirmStale'));
  }
  function cancelButtons(root,refresh) {
    root.querySelectorAll('[data-cancel]').forEach(button=>button.onclick=()=>run(button,async()=>{
      if(!confirm(t('charging.confirmCancel')))return;
      await API.post('/api/charging/reservations/'+encodeURIComponent(button.dataset.cancel)+'/cancel');
      message(t('charging.saved'));await refresh();
    }));
  }
  function live(refresh) {
    let source, debounce, closed=false, reconnectAt=0;
    const indicator=$('live-state');
    function label(live){if(indicator){indicator.dataset.i18n=live?'charging.live':'charging.autoRefresh';indicator.textContent=t(indicator.dataset.i18n);}}
    const update=()=>{clearTimeout(debounce);debounce=setTimeout(()=>{if(!closed&&!document.hidden)Promise.resolve(refresh()).catch(err=>message(err.message,true));},250);};
    const subscriptions=[];
    if(window.Stream?.on) {
      for(const event of ['vehicle_updated','hub_updated','reservation_changed','charging_scheduled','charging_completed']) {
        const unsubscribe=window.Stream.on(event,update);if(typeof unsubscribe==='function')subscriptions.push(unsubscribe);
      }
      label(true);
    }
    function connect() {
      if(closed||window.Stream?.on||source||!window.EventSource||Date.now()<reconnectAt)return;
      source=new EventSource('/api/stream?'+new URLSearchParams({token:API.session()?.token||''}));
      source.onopen=()=>label(true);source.onmessage=update;
      for(const event of ['vehicle_updated','hub_updated','reservation_changed','charging_scheduled','charging_completed']) source.addEventListener(event,update);
      source.onerror=()=>{source?.close();source=null;reconnectAt=Date.now()+60000;label(false);};
    }
    connect();
    const timer=setInterval(()=>{if(!document.hidden){update();connect();}},30000);
    window.addEventListener('pagehide',()=>{closed=true;source?.close();clearInterval(timer);clearTimeout(debounce);subscriptions.forEach(fn=>fn());},{once:true});
  }
  return {init,t,esc,$,fmt,local,message,run,field,stale,cancelButtons,live};
})();
