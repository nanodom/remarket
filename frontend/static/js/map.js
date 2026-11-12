import { esc, GEOAPIFY_API_KEY, aviso, COLORES_RUTA } from './config.js';

let map = null;
let camiones = [];
let timerCamion = null;

// Detiene la simulación y quita los camiones. Debe llamarse ANTES de map.remove().
function detenerSimulacion() {
  if (timerCamion) {
    clearTimeout(timerCamion);
    timerCamion = null;
  }
  if (map) camiones.forEach(c => map.removeLayer(c.marker));
  camiones = [];
}

export function initMap(places, plan) {
  detenerSimulacion();
  if (map) {
    map.remove();
    map = null;
  }

  map = L.map("map").setView([-29.93, -71.3], 11);

  const isRetina = L.Browser.retina;
  const baseUrl = `https://maps.geoapify.com/v1/tile/osm-bright/{z}/{x}/{y}.png?apiKey=${GEOAPIFY_API_KEY}`;
  const retinaUrl = `https://maps.geoapify.com/v1/tile/osm-bright/{z}/{x}/{y}@2x.png?apiKey=${GEOAPIFY_API_KEY}`;

  L.tileLayer(isRetina ? retinaUrl : baseUrl, {
    attribution: 'Powered by <a href="https://www.geoapify.com/" target="_blank">Geoapify</a> | © OpenStreetMap contributors',
    maxZoom: 20,
    id: "osm-bright"
  }).addTo(map);

  const COL = { base: "#111", donante: "#17795a", beneficiario: "#2a62c9" };
  const bounds = [];

  places.forEach(p => {
    if (p.lat == null || p.lng == null) return;
    bounds.push([p.lat, p.lng]);
    L.circleMarker([p.lat, p.lng], { radius: 8, color: COL[p.tipo], fillOpacity: .9 })
      .bindPopup(`<b>${esc(p.nombre)}</b><br>${p.tipo}`)
      .addTo(map);
  });

  if (plan && plan.rutas.length) {
    const capas = [];
    plan.rutas.forEach((ru, k) => {
      const color = COLORES_RUTA[k % COLORES_RUTA.length];
      const nombre = ru.vehiculo ? ru.vehiculo.nombre : "Plan anterior";
      if (ru.geometria) {
        capas.push(L.geoJSON(ru.geometria, { style: { color, weight: 5, opacity: .85 } })
          .bindTooltip(esc(nombre), { sticky: true }).addTo(map));
      }
      ru.paradas.forEach((s, i) => {
        if (s.lat == null || s.lng == null) return;   // rutas antiguas del seeder no guardan coordenadas
        L.marker([s.lat, s.lng], {
          icon: L.divIcon({ className: "n", html: `<span style="background:${color}">${i + 1}</span>`, iconSize: [26, 26] })
        }).bindPopup(`${esc(nombre)}<br>${s.tipo}: ${esc(s.nombre)}`).addTo(map);
      });
    });
    if (capas.length) map.fitBounds(L.featureGroup(capas).getBounds().pad(.15));
    else if (bounds.length) map.fitBounds(bounds, { padding: [30, 30] });
  } else if (bounds.length) {
    map.fitBounds(bounds, { padding: [30, 30] });
  }
}

export function simularRecorrido(plan) {
  const rutas = (plan?.rutas || []).filter(r => r.geometria?.coordinates?.length > 1);
  if (!map || !rutas.length) {
    aviso("Primero debes planificar rutas para ver la simulación.", true);
    return;
  }
  detenerSimulacion(); // evita dos animaciones simultáneas

  const TICKS = 300, MS = 100; // ~30 s; todos los camiones terminan a la vez, cada uno a su ritmo
  camiones = rutas.map(r => {
    const coords = r.geometria.coordinates.map(c => [c[1], c[0]]);
    const marker = L.marker(coords[0], {
      icon: L.divIcon({
        className: "camion-animado",
        html: '<div class="camion-emoji" style="font-size:28px">🚚</div>',
        iconSize: [30, 30],
        iconAnchor: [15, 15]
      })
    }).addTo(map);
    return { coords, marker, prev: 0 };
  });

  let t = 0;
  const animar = () => {
    // Si se cambió de pestaña (mapa destruido) o se detuvo, el bucle termina solo.
    if (!map || !camiones.length) return;
    if (t >= TICKS) {
      aviso("¡Simulación de rutas completada!");
      timerCamion = null;
      return;
    }
    t++;
    camiones.forEach(c => {
      const i = Math.round(t / TICKS * (c.coords.length - 1));
      const a = c.coords[c.prev], b = c.coords[i];
      c.marker.setLatLng(b);
      if (a[0] !== b[0] || a[1] !== b[1]) {
        const angulo = Math.atan2(b[1] - a[1], b[0] - a[0]) * 180 / Math.PI;
        const el = c.marker.getElement()?.querySelector(".camion-emoji");
        if (el) el.style.transform = `rotate(${angulo - 90}deg)`;
      }
      c.prev = i;
    });
    timerCamion = setTimeout(animar, MS);
  };

  aviso("Iniciando simulación de la flota...");
  animar();
}

export function destroyMap() {
  detenerSimulacion();
  if (map) {
    map.remove();
    map = null;
  }
}