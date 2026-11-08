/* shared/map.js - Leaflet 1.9 wrapper for Smart E-Mobility Hub.   OWNER: Member 1 (TV1)
 * Shared with: Member 3 (Operator Dashboard) and Member 4 (What-if Simulation).
 *
 * Provides:
 *   HubMap.initMap(containerId, options)
 *   HubMap.hubMarker(map, hub, onClick)
 *   HubMap.flyTo(map, lat, lng, zoom)
 *   HubMap.routeTo(map, fromCoord, toCoord, options)
 *   HubMap.userMarker(map, lat, lng)
 *   HubMap.distanceM / walkMinutes / formatDistance / rankHubs   (Haversine distance from any point)
 *   HubMap.hubLayer(map, onSelect)      (create-once hub markers, .update(hubs, distances))
 *   HubMap.originPicker(map, onChange)  (click or drag on the map to set the starting point)
 *   HubMap.locate()                     (GPS -> {lat,lng}; rejects when permission denied)
 */
const HubMap = (() => {
  // Center of VNU-HCM Urban Area (Dormitory Zone A - Metro - University Campus - Central Library)
  const VNU_CENTER = [10.8795, 106.8045];
  const DEFAULT_ZOOM = 15;
  const ROUTER_FOOT = 'https://routing.openstreetmap.de/routed-foot/route/v1/foot';
  // Whole service area: Metro Line 1 (Ben Thanh -> Suoi Tien) + HCMUT campus 1 + Hoa Hao dormitory.
  const WALK_M_PER_MIN = 80;   // ~4.8 km/h
  const DETOUR = 1.3;          // straight line -> street distance

  /* ---------- Geo helpers (same maths as backend modules/reservation/geo.py) ---------- */
  const rad = d => d * Math.PI / 180;
  function distanceM(a, b) {                       // Haversine, metres
    const dLat = rad(b.lat - a.lat), dLng = rad(b.lng - a.lng);
    const x = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
    return 2 * 6371008.8 * Math.asin(Math.min(1, Math.sqrt(x)));
  }
  function walkMinutes(m) { return Math.max(1, Math.round(m * DETOUR / WALK_M_PER_MIN)); }
  function formatDistance(m, lang) {
    if (m == null || isNaN(m)) return '';
    const loc = lang === 'vi' ? 'vi-VN' : 'en-US';
    return m < 1000 ? Math.round(m / 10) * 10 + ' m' : (m / 1000).toLocaleString(loc, { maximumFractionDigits: 1, minimumFractionDigits: 1 }) + ' km';
  }
  /* Hub category from its id: 'metro' | 'dorm' | 'library' | 'campus' */
  function hubKind(h) {
    const id = (h && (h.hub_id || h.id)) || '';
    if (id === 'HUB-METRO' || id.startsWith('HUB-MT-')) return 'metro';
    if (/KTX|HOAHAO/.test(id)) return 'dorm';
    if (id === 'HUB-LIB') return 'library';
    return 'campus';
  }
  const KIND_GLYPH = { metro: '🚇', dorm: '🏠', library: '📚', campus: '🎓' };
  /* Returns [{hub, distance_m, walk_min}] nearest first. */
  function rankHubs(hubs, origin) {
    return hubs.filter(h => h.location).map(h => {
      const d = distanceM(origin, h.location);
      return { hub: h, distance_m: d, walk_min: walkMinutes(d) };
    }).sort((a, b) => a.distance_m - b.distance_m);
  }

  function initMap(container, options = {}) {
    if (typeof L === 'undefined') {
      console.warn('Leaflet (L) is not loaded yet.');
      return null;
    }

    const el = typeof container === 'string' ? document.getElementById(container) : container;
    if (!el) return null;

    const center = options.center || VNU_CENTER;
    const zoom = options.zoom || DEFAULT_ZOOM;

    const map = L.map(el, {
      center: center,
      zoom: zoom,
      zoomControl: true,
      ...options,
    });

    // OpenStreetMap standard tile layer with mandatory attribution
    const tileLayer = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors',
    });

    if (options.onTileError) {
      tileLayer.on('tileerror', options.onTileError);
    }

    tileLayer.addTo(map);
    return map;
  }

  function getStatusColor(hub) {
    if (hub.free_spaces === 0) return '#ef4444'; // Red: 100% full
    if (hub.near_capacity || (hub.vehicles_available !== undefined && hub.vehicles_available === 0)) {
      return '#f59e0b'; // Yellow: limited / near full
    }
    return '#10b981'; // Green: high availability
  }

  function hubMarker(map, hub, onClick) {
    if (!map || typeof L === 'undefined' || !hub.location) return null;

    const lat = hub.location.lat;
    const lng = hub.location.lng;
    const color = getStatusColor(hub);
    const hubName = (typeof I18n !== 'undefined' && I18n.hubName) ? I18n.hubName(hub) : (hub.name || hub.hub_id);
    const vehCount = hub.vehicles_available !== undefined ? hub.vehicles_available : (hub.vehicles_total || 0);
    const spaceCount = hub.free_spaces !== undefined ? hub.free_spaces : 0;

    const html = `
      <div class="hub-leaflet-marker" style="
        width: 38px; height: 38px;
        background: ${color};
        color: white;
        border: 3px solid white;
        border-radius: 50%;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        font-family: system-ui, -apple-system, sans-serif;
        font-weight: 700;
        font-size: 11px;
        line-height: 1;
        cursor: pointer;
        transition: transform 0.2s ease;
      ">
        <span>${vehCount}🚲</span>
      </div>
    `;

    const icon = L.divIcon({
      className: 'custom-hub-icon',
      html: html,
      iconSize: [38, 38],
      iconAnchor: [19, 19],
      popupAnchor: [0, -20],
    });

    const marker = L.marker([lat, lng], { icon: icon }).addTo(map);

    const popupHtml = `
      <div style="font-family:system-ui, sans-serif; padding:4px; min-width:160px;">
        <b style="font-size:14px; color:#111827; display:block; margin-bottom:4px;">${hubName}</b>
        <div style="font-size:12px; color:#4b5563; margin-bottom:6px;">
          <div>🚲 <b>${vehCount}</b> vehicles available</div>
          <div>🅿️ <b>${spaceCount}</b> free return docks</div>
          <div>⚡ <b>${hub.charging_points_free || 0}</b> free chargers</div>
        </div>
      </div>
    `;

    marker.bindPopup(popupHtml);

    marker.on('click', () => {
      if (onClick) onClick(hub);
    });

    return marker;
  }

  function userMarker(map, lat, lng, opts = {}) {
    if (!map || typeof L === 'undefined') return null;

    const html = `
      <div style="
        width: 22px; height: 22px;
        background: #3b82f6;
        border: 3px solid white;
        border-radius: 50%;
        box-shadow: 0 0 0 6px rgba(59, 130, 246, 0.35);
      "></div>
    `;

    const icon = L.divIcon({
      className: 'user-location-pin',
      html: html,
      iconSize: [22, 22],
      iconAnchor: [11, 11],
    });

    return L.marker([lat, lng], { icon: icon, zIndexOffset: 1000, draggable: !!opts.draggable, keyboard: false }).addTo(map);
  }

  function flyTo(map, lat, lng, zoom = 16) {
    if (!map) return;
    map.flyTo([lat, lng], zoom, { duration: 1.0 });
  }

  async function routeTo(map, fromCoord, toCoord, options = {}) {
    if (!map || typeof L === 'undefined') return null;

    const color = options.color || '#3b82f6';
    const weight = options.weight || 5;

    // Remove existing route polyline if present
    if (map._currentRouteLayer) {
      map.removeLayer(map._currentRouteLayer);
      map._currentRouteLayer = null;
    }

    try {
      // The public OSRM demo server ignores the profile (always driving), so ask the
      // FOSSGIS foot instance first, then fall back to a dashed straight line.
      const url = `${ROUTER_FOOT}/${fromCoord.lng},${fromCoord.lat};${toCoord.lng},${toCoord.lat}?overview=full&geometries=geojson`;
      const res = await fetch(url, { signal: AbortSignal.timeout(5000) });
      if (!res.ok) throw new Error('Routing service unavailable');

      const data = await res.json();
      if (!data.routes || !data.routes[0]) throw new Error('No route found');

      const routeGeoJson = data.routes[0].geometry;
      const layer = L.geoJSON(routeGeoJson, {
        style: {
          color: color,
          weight: weight,
          opacity: 0.85,
        },
      }).addTo(map);

      layer.routeInfo = { distance: data.routes[0].distance, duration: data.routes[0].duration, straight: false };
      map._currentRouteLayer = layer;
      return layer;
    } catch (err) {
      console.warn('OSRM walking route failed, drawing fallback line:', err);
      // Fallback straight dashed line (flow ngoại lệ 2)
      const straightLine = L.polyline(
        [[fromCoord.lat, fromCoord.lng], [toCoord.lat, toCoord.lng]],
        {
          color: color,
          weight: weight,
          dashArray: '8, 8',
          opacity: 0.75,
        }
      ).addTo(map);

      const d = distanceM(fromCoord, toCoord);
      straightLine.routeInfo = { distance: d, duration: walkMinutes(d) * 60, straight: true };
      map._currentRouteLayer = straightLine;
      return straightLine;
    }
  }


  /* ---------- Hub marker layer: create once, update in place (no duplicate markers on SSE refresh) ---------- */
  function hubLayer(map, onSelect) {
    const markers = new Map();
    let selectedId = null;
    const esc = x => String(x).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

    function iconFor(hub) {
      const color = getStatusColor(hub);
      const sel = hub.hub_id === selectedId;
      const n = hub.vehicles_available !== undefined ? hub.vehicles_available : 0;
      const size = sel ? 46 : 38;
      return L.divIcon({
        className: 'custom-hub-icon',
        html: `<div style="width:${size}px;height:${size}px;background:${color};color:#fff;border:3px solid ${sel ? '#111827' : '#fff'};border-radius:50%;
          box-shadow:0 4px 12px rgba(0,0,0,.3);display:flex;flex-direction:column;align-items:center;justify-content:center;
          font:700 10px/1.05 system-ui,sans-serif;cursor:pointer"><span style="font-size:${sel ? 15 : 13}px">${KIND_GLYPH[hubKind(hub)]}</span><span>${n}</span></div>`,
        iconSize: [size, size], iconAnchor: [size / 2, size / 2], popupAnchor: [0, -size / 2],
      });
    }
    function popup(hub, info) {
      const name = (typeof I18n !== 'undefined' && I18n.hubName) ? I18n.hubName(hub) : hub.name;
      const lang = (typeof I18n !== 'undefined') ? I18n.lang : 'en';
      const t = (key, values) => typeof I18n !== 'undefined' ? I18n.t(key, values) : key;
      const dist = info ? `<div style="margin-top:4px;font-weight:600;color:var(--brand)">${esc(formatDistance(info.distance_m, lang))} · ${info.walk_min} ${esc(t('student.geo.walkUnit'))}</div>` : '';
      return `<div style="font:13px system-ui,sans-serif;min-width:170px"><b style="font-size:14px">${esc(name)}</b>
        <div class="map-popup-stats"><span>${esc(t('map.vehicles'))}</span><b>${hub.vehicles_available ?? 0}</b>
        <span>${esc(t('map.spaces'))}</span><b>${hub.free_spaces ?? 0}</b>
        <span>${esc(t('map.chargers'))}</span><b>${hub.charging_points_free ?? 0}</b></div>${dist}</div>`;
    }
    function update(hubs, distanceById = {}) {
      const seen = new Set();
      hubs.forEach(hub => {
        if (!hub.location) return;
        seen.add(hub.hub_id);
        let m = markers.get(hub.hub_id);
        if (!m) {
          m = L.marker([hub.location.lat, hub.location.lng], { icon: iconFor(hub), riseOnHover: true }).addTo(map);
          m.on('click', () => onSelect && onSelect(m._hub));
          markers.set(hub.hub_id, m);
        }
        m._hub = hub;
        m.setIcon(iconFor(hub));
        m.bindPopup(popup(hub, distanceById[hub.hub_id]));
      });
      markers.forEach((m, id) => { if (!seen.has(id)) { map.removeLayer(m); markers.delete(id); } });
    }
    function select(id, open) {
      selectedId = id;
      markers.forEach(m => m.setIcon(iconFor(m._hub)));
      const m = markers.get(id);
      if (m && open) m.openPopup();
    }
    function fit(extraLatLngs = []) {
      const pts = [...markers.values()].map(m => m.getLatLng()).concat(extraLatLngs.map(p => L.latLng(p.lat, p.lng)));
      if (pts.length) map.fitBounds(L.latLngBounds(pts), { padding: [28, 28], maxZoom: 16 });
    }
    function visible(ids) {                         // show only markers whose id is in `ids`
      markers.forEach((m, id) => { if (ids.has(id)) { if (!map.hasLayer(m)) m.addTo(map); } else map.removeLayer(m); });
    }
    return { update, select, fit, visible, markers };
  }

  /* ---------- Origin picker: GPS fix OR click / drag on the map ---------- */
  function originPicker(map, onChange) {
    let marker = null;
    function set(lat, lng, source) {
      if (!marker) {
        marker = userMarker(map, lat, lng, { draggable: true });
        marker.on('dragend', () => { const p = marker.getLatLng(); onChange({ lat: p.lat, lng: p.lng }, 'drag'); });
      } else marker.setLatLng([lat, lng]);
      onChange({ lat, lng }, source || 'set');
    }
    map.on('click', e => set(e.latlng.lat, e.latlng.lng, 'map'));
    return { set, get: () => marker && { lat: marker.getLatLng().lat, lng: marker.getLatLng().lng } };
  }

  /* Browser geolocation as a promise; rejects with err.code (1 = permission denied). */
  function locate(timeout = 8000) {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) return reject({ code: 0 });
      navigator.geolocation.getCurrentPosition(
        p => resolve({ lat: p.coords.latitude, lng: p.coords.longitude, accuracy: p.coords.accuracy }),
        e => reject(e), { enableHighAccuracy: true, timeout, maximumAge: 30000 });
    });
  }

  return {
    VNU_CENTER,
    distanceM, walkMinutes, formatDistance, hubKind, rankHubs, hubLayer, originPicker, locate,
    initMap,
    hubMarker,
    userMarker,
    flyTo,
    routeTo,
    getStatusColor,
  };
})();
