import { esc, GEOAPIFY_API_KEY, aviso } from './config.js';

let map = null;
let markerCamion = null;
let timerCamion = null;

// Detiene el bucle de la simulación y quita el camión. Debe llamarse ANTES de map.remove().
function detenerSimulacion() {
  if (timerCamion) {
    clearTimeout(timerCamion);
    timerCamion = null;
  }
  if (markerCamion && map) map.removeLayer(markerCamion);
  markerCamion = null;
}

export function initMap(places, ruta) {
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

  if (ruta) {
    const geoJsonLayer = L.geoJSON(ruta.geometria, { style: { color: "#2a62c9", weight: 5, opacity: .85 } }).addTo(map);
    ruta.paradas.forEach((s, i) => {
      L.marker([s.lat, s.lng], {
        icon: L.divIcon({ className: "n", html: `<span>${i + 1}</span>`, iconSize: [26, 26] })
      }).bindPopup(`${s.tipo}: ${esc(s.nombre)}`).addTo(map);
    });
    map.fitBounds(geoJsonLayer.getBounds().pad(.15));
  } else if (bounds.length) {
    map.fitBounds(bounds, { padding: [30, 30] });
  }
}

export function simularRecorrido(ruta) {
  if (!map || !ruta?.geometria?.coordinates) {
    aviso("Primero debes planificar una ruta para ver la simulación.", true);
    return;
  }
  detenerSimulacion(); // evita dos animaciones simultáneas

  const todas = ruta.geometria.coordinates.map(c => [c[1], c[0]]);
  if (todas.length < 2) return;

  // La geometría puede tener miles de puntos: se reduce a ~300 pasos para que el movimiento sea fluido.
  const paso = Math.max(1, Math.floor(todas.length / 300));
  const coords = todas.filter((_, i) => i % paso === 0);
  coords.push(todas[todas.length - 1]);
  const intervalo = 30000 / coords.length; // ~30 s en total

  markerCamion = L.marker(coords[0], {
    icon: L.divIcon({
      className: "camion-animado",
      html: '<div id="camion-emoji" style="font-size:28px">🚚</div>',
      iconSize: [30, 30],
      iconAnchor: [15, 15]
    })
  }).addTo(map);

  let i = 0;
  const animar = () => {
    // Si se cambió de pestaña (mapa destruido) o se detuvo, el bucle termina solo.
    if (!map || !markerCamion) return;
    if (i >= coords.length - 1) {
      aviso("¡Simulación de ruta completada!");
      timerCamion = null;
      return;
    }
    const a = coords[i];
    const b = coords[i + 1];
    markerCamion.setLatLng(b);

    const angulo = Math.atan2(b[1] - a[1], b[0] - a[0]) * 180 / Math.PI;
    const emoji = document.getElementById("camion-emoji");
    if (emoji) emoji.style.transform = `rotate(${angulo - 90}deg)`;

    map.panTo(b, { animate: false });
    i++;
    timerCamion = setTimeout(animar, intervalo);
  };

  aviso("Iniciando simulación del recorrido...");
  animar();
}

export function destroyMap() {
  detenerSimulacion();
  if (map) {
    map.remove();
    map = null;
  }
}
