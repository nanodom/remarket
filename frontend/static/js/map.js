import { esc, GEOAPIFY_API_KEY, aviso } from './config.js';

let map = null;
let markerCamion = null;
let animacionCamion = null;

export function initMap(places, ruta) {
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
  if (!ruta || !ruta.geometria || !ruta.geometria.coordinates) {
    aviso("Primero debes planificar una ruta para ver la simulación.", true);
    return;
  }

  if (animacionCamion) cancelAnimationFrame(animacionCamion);
  if (markerCamion && map) map.removeLayer(markerCamion);

  const coords = ruta.geometria.coordinates.map(c => [c[1], c[0]]);
  if (coords.length < 2) return;

  const iconoCamion = L.divIcon({
    className: 'camion-animado',
    html: '<div id="camion-emoji" style="font-size: 28px; transition: transform 0.1s linear;">🚚</div>',
    iconSize: [30, 30],
    iconAnchor: [15, 15]
  });

  markerCamion = L.marker(coords[0], { icon: iconoCamion }).addTo(map);

  const duracionTotalMs = 30000;
  const tiempoPorPunto = duracionTotalMs / coords.length;
  let index = 0;

  function animar() {
    if (index >= coords.length - 1) {
      aviso("¡Simulación de ruta completada con éxito!");
      markerCamion = null;
      animacionCamion = null;
      return;
    }

    const actual = coords[index];
    const siguiente = coords[index + 1];

    markerCamion.setLatLng(siguiente);

    const angulo = Math.atan2(siguiente[1] - actual[1], siguiente[0] - actual[0]) * 180 / Math.PI;
    const emoji = document.getElementById('camion-emoji');
    if (emoji) emoji.style.transform = `rotate(${angulo - 90}deg)`;

    map.panTo(siguiente, { animate: false });
    index++;

    animacionCamion = requestAnimationFrame(() => {
      setTimeout(animar, tiempoPorPunto);
    });
  }

  aviso("Iniciando simulación de trayecto logístico en tiempo real...");
  animar();
}

export function destroyMap() {
  if (map) {
    map.remove();
    map = null;
  }
}