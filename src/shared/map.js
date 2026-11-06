/* shared/map.js - Leaflet 1.9 wrapper for Smart E-Mobility Hub.   OWNER: Member 1 (TV1)
 * Shared with: Member 3 (Operator Dashboard) and Member 4 (What-if Simulation).
 *
 * Provides:
 *   HubMap.initMap(containerId, options)
 *   HubMap.hubMarker(map, hub, onClick)
 *   HubMap.flyTo(map, lat, lng, zoom)
 *   HubMap.routeTo(map, fromCoord, toCoord, options)
 *   HubMap.userMarker(map, lat, lng)
 */
const HubMap = (() => {
  // Center of VNU-HCM Urban Area (Dormitory Zone A - Metro - University Campus - Central Library)
  const VNU_CENTER = [10.8795, 106.8045];
  const DEFAULT_ZOOM = 15;

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

  function userMarker(map, lat, lng) {
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

    return L.marker([lat, lng], { icon: icon, zIndexOffset: 1000 }).addTo(map);
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
      // OSRM walking route demo endpoint
      const url = `https://router.project-osrm.org/route/v1/walking/${fromCoord.lng},${fromCoord.lat};${toCoord.lng},${toCoord.lat}?overview=full&geometries=geojson`;
      const res = await fetch(url, { signal: AbortSignal.timeout(4000) });
      if (!res.ok) throw new Error('OSRM service unavailable');

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

      map._currentRouteLayer = straightLine;
      return straightLine;
    }
  }

  return {
    VNU_CENTER,
    initMap,
    hubMarker,
    userMarker,
    flyTo,
    routeTo,
    getStatusColor,
  };
})();
