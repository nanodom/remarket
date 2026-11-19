import { esc, aviso, COLORES_RUTA } from './config.js';

let map = null;
let camiones = [];
let raf = null;
let pausado = false;
let velocidad = 1;
let ultimo = 0;     // timestamp del último frame
let reloj = 0;      // ms simulados transcurridos (a velocidad 1×)
let ultimoTexto = 0;

const R = 6371000;
const rad = x => x * Math.PI / 180;

// Distancia en metros entre [lat, lng] y [lat, lng]
function metros(a, b) {
  const dl = rad(b[0] - a[0]), dn = rad(b[1] - a[1]);
  const h = Math.sin(dl / 2) ** 2 + Math.cos(rad(a[0])) * Math.cos(rad(b[0])) * Math.sin(dn / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

// Posición a `d` metros del inicio: devuelve el índice del tramo y el punto interpolado
function posicion(c, d) {
  const { acum, coords } = c;
  if (d <= 0) return { i: 0, p: coords[0] };
  if (d >= c.total) return { i: coords.length - 1, p: coords[coords.length - 1] };
  let lo = 0, hi = acum.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (acum[mid] <= d) lo = mid; else hi = mid;
  }
  const f = (d - acum[lo]) / (acum[hi] - acum[lo] || 1);
  const a = coords[lo], b = coords[hi];
  return { i: lo, p: [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f] };
}

// Detiene la animación y quita camiones y rastros. Debe llamarse ANTES de map.remove().
function detenerSimulacion() {
  if (raf) {
    cancelAnimationFrame(raf);
    raf = null;
  }
  if (map) camiones.forEach(c => { map.removeLayer(c.marker); map.removeLayer(c.rastro); });
  camiones = [];
  pausado = false;
  const est = document.getElementById("sim-estado");
  if (est) est.textContent = "";
}

export function initMap(places, plan) {
  detenerSimulacion();
  if (map) {
    map.remove();
    map = null;
  }

  map = L.map("map").setView([-29.93, -71.3], 11);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 19
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
        // Ruta base tenue: el rastro de la simulación se dibuja encima con opacidad completa
        capas.push(L.geoJSON(ru.geometria, { style: { color, weight: 5, opacity: .4 } })
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

function frame(now) {
  raf = requestAnimationFrame(frame);
  if (!map) { detenerSimulacion(); return; }
  // Tope de 100 ms: si la pestaña estuvo en segundo plano no hay saltos bruscos
  const dt = Math.min(now - ultimo, 100);
  ultimo = now;
  if (pausado) return;
  reloj += dt * velocidad;

  let activos = 0;
  camiones.forEach(c => {
    const prog = Math.min(1, reloj / c.durMs);
    const { i, p } = posicion(c, prog * c.total);
    c.marker.setLatLng(p);
    c.rastro.setLatLngs([...c.coords.slice(0, i + 1), p]);

    // Sentido de marcha: el emoji mira a la izquierda; se voltea si va hacia el este
    const sig = c.coords[Math.min(i + 1, c.coords.length - 1)];
    const dx = sig[1] - p[1];
    if (dx !== 0 && (dx > 0) !== c.volteado) {
      c.volteado = dx > 0;
      const el = c.marker.getElement()?.querySelector(".camion-emoji");
      if (el) el.style.transform = c.volteado ? "scaleX(-1)" : "";
    }
    c.pct = Math.round(prog * 100);
    if (prog < 1) activos++;
  });

  if (now - ultimoTexto > 250 || !activos) {
    ultimoTexto = now;
    const est = document.getElementById("sim-estado");
    if (est) est.innerHTML = camiones.map(c =>
      `<small><b style="color:${c.color}">●</b> ${esc(c.nombre)}: ${c.pct}%</small>`).join(" · ");
  }

  if (!activos) {
    cancelAnimationFrame(raf);
    raf = null;
    aviso("¡Simulación de rutas completada!");
  }
}

export function simularRecorrido(plan, vel = 1) {
  const rutas = (plan?.rutas || []).filter(r => r.geometria?.coordinates?.length > 1);
  if (!map || !rutas.length) {
    aviso("Primero debes planificar rutas para ver la simulación.", true);
    return;
  }
  detenerSimulacion(); // evita dos animaciones simultáneas

  // El recorrido más largo dura ~35 s a 1×; los demás, en proporción a sus minutos reales
  const maxMin = Math.max(...rutas.map(r => r.minutos || 1));
  const msPorMin = 35000 / maxMin;

  camiones = rutas.map(r => {
    const k = plan.rutas.indexOf(r);
    const color = COLORES_RUTA[k % COLORES_RUTA.length];
    const nombre = r.vehiculo ? r.vehiculo.nombre : "Vehículo";
    const coords = r.geometria.coordinates.map(c => [c[1], c[0]]);   // GeoJSON [lng,lat] -> Leaflet [lat,lng]
    const acum = [0];
    for (let i = 1; i < coords.length; i++) acum.push(acum[i - 1] + metros(coords[i - 1], coords[i]));

    const marker = L.marker(coords[0], {
      zIndexOffset: 1000,
      icon: L.divIcon({
        className: "camion-animado",
        html: `<div class="camion-wrap"><div class="camion-emoji">🚚</div><span class="camion-tag" style="background:${color}">${esc(nombre)}</span></div>`,
        iconSize: [30, 30],
        iconAnchor: [15, 15]
      })
    }).addTo(map);
    const rastro = L.polyline([], { color, weight: 7, opacity: 1 }).addTo(map);

    return {
      coords, acum, total: acum[acum.length - 1] || 1, marker, rastro, color, nombre,
      durMs: Math.max(3000, (r.minutos || 1) * msPorMin), volteado: false, pct: 0
    };
  });

  reloj = 0;
  pausado = false;
  velocidad = vel;
  ultimo = performance.now();
  aviso(plan.fuente === "osrm"
    ? "Simulando recorrido por calles reales…"
    : "Simulando con ruta ESTIMADA en línea recta: OSRM no respondió, el camión no sigue las calles.", plan.fuente !== "osrm");
  raf = requestAnimationFrame(frame);
}

// Devuelve true si quedó en pausa
export function alternarPausa() {
  if (!raf) return false;   // no hay simulación en curso
  pausado = !pausado;
  return pausado;
}

export function cambiarVelocidad(v) {
  velocidad = v || 1;
}

export function destroyMap() {
  detenerSimulacion();
  if (map) {
    map.remove();
    map = null;
  }
}