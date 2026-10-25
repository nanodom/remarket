import { CAT, esc, clp, f1, stc } from './config.js';

export function vLogin() {
  return `<div class="box login-wrapper">
    <h2>Acceso Restringido</h2>
    <p><small>Ingrese sus credenciales de la empresa para acceder a ReMarket 2.0.</small></p>
    <form id="form-login">
      <label>Usuario<input name="username" required autocomplete="username"></label>
      <label>Contraseña<input name="password" type="password" required autocomplete="current-password"></label>
      <button class="b" style="width:100%">Ingresar</button>
    </form>
  </div>`;
}

export function vRegistrar(places) {
  const don = places.filter(p => p.tipo === "donante");
  const ben = places.filter(p => p.tipo === "beneficiario");

  return `<div class="g g2">
    <form class="box" id="form-registrar">
      <h3>Registrar producto disponible</h3>
      <label>Producto<input name="nom" required placeholder="Ej: Leche UHT"></label>
      <label>Categoría<select name="cat">${CAT.map(c => `<option>${c}</option>`).join("")}</select></label>
      <label>Cantidad (kg)<input name="kg" type="number" min="0.5" step="0.5" value="20" required></label>
      <label>Condición<select name="estado"><option>Bueno</option><option>Próximo a vencer</option><option>Regular</option></select></label>
      <label>Fecha de vencimiento (vacío si no vence)<input name="vence" type="date"></label>
      <label>Donante (punto de retiro)<select name="don">${don.map(d => `<option value="${d.id}">${esc(d.nombre)}</option>`).join("")}</select></label>
      <button class="b">Registrar producto</button>
    </form>

    <div class="g">
      <form class="box" id="form-lugar">
        <h3>Agregar donante o beneficiario</h3>
        <label>Tipo
          <select name="tipo" id="tipo-lugar-select">
            <option value="donante">Donante</option>
            <option value="beneficiario">Beneficiario</option>
          </select>
        </label>
        <label>Nombre<input name="nombre" required></label>
        <label>Dirección (se geolocaliza automáticamente)<input name="direccion" required placeholder="Ej: Av. Costanera 123, Coquimbo"></label>
        <div id="bf" style="display:none">
          <label>Personas atendidas<input name="personas" type="number" min="0" value="0"></label>
          <label>Capacidad (kg)<input name="cap" type="number" min="0" value="100"></label>
          <label class="ck"><input type="checkbox" name="frio">Cuenta con cadena de frío</label>
          <label>Necesita</label>${CAT.map(c => `<label class="ck"><input type="checkbox" name="nec" value="${c}">${c}</label>`).join("")}
        </div>
        <button class="b">Buscar y agregar</button>
      </form>
      <div class="box">
        <h3>Actores del modelo</h3>
        <p><b>Donantes:</b> ${don.map(d => esc(d.nombre)).join(", ") || "—"}.</p>
        <p><b>Beneficiarios:</b> ${ben.map(d => esc(d.nombre)).join(", ") || "—"}.</p>
      </div>
    </div>
  </div>`;
}

export function vClasificar(prods) {
  return `<div class="box">
    <h3>Clasificación y prioridad</h3>
    <div class="sc">
      <table>
        <tr><th>Producto</th><th>Categoría</th><th>kg</th><th>Estado</th><th>Vence en</th><th>Puntaje</th><th>Prioridad</th></tr>
        ${prods.map(p => `<tr><td>${esc(p.nombre)}</td><td>${p.categoria}</td><td>${p.kg}</td><td>${p.estado}</td><td>${p.dias >= 999 ? "No vence" : p.dias + " d"}</td><td>${p.puntaje}</td><td><span class="tag ${p.prioridad}">${p.prioridad}</span></td></tr>`).join("")}
      </table>
    </div>
    <p><small>Puntaje = peso de categoría (perecible 30, no perecible o higiene 20, abrigo 10) + urgencia por vencimiento (≤2 días: 15, ≤7 días: 8) + estado (próximo a vencer +10, regular −3). Alta ≥35, Media ≥20.</small></p>
  </div>`;
}

export function vAsignar(places, prods) {
  const dis = prods.filter(p => p.status === "Disponible").length;
  return `<div class="box">
    <h3>Asignación de destinatarios</h3>
    <p>${dis} productos disponibles. Se asigna por prioridad al beneficiario más cercano que necesite la categoría, tenga capacidad y, para perecibles, cadena de frío.</p>
    <button class="b" id="btn-asignar">Asignar automáticamente</button>
  </div>
  <div class="box sc mt">
    <h3>Beneficiarios</h3>
    <table>
      <tr><th>Organización</th><th>Personas</th><th>Necesita</th><th>Frío</th><th>Carga / capacidad</th></tr>
      ${places.filter(p => p.tipo === "beneficiario").map(r => {
        const c = prods.filter(p => p.destino_id === r.id && p.status !== "Entregado").reduce((a, p) => a + p.kg, 0);
        return `<tr><td>${esc(r.nombre)}</td><td>${r.personas}</td><td>${r.necesidades.join(", ")}</td><td>${r.frio ? "Sí" : "No"}</td><td>${c} /${r.capacidad_kg} kg</td></tr>`;
      }).join("")}
    </table>
  </div>`;
}

export function vRutas(ruta) {
  const r = ruta;
  return `<div class="box">
    <h3>Planificación de ruta</h3>
    <p>Los tiempos y distancias salen de la red vial real (OSRM). Se ordenan primero los retiros y luego las entregas, volviendo al centro de acopio.</p>
    <div class="fx">
      <button class="b" id="btn-planificar">Planificar ruta con productos asignados</button>
      ${r ? `<button class="b s" id="btn-simular">Simular recorrido del camión</button>` : ""}
    </div>
  </div>
  ${r ? `<div class="g g5 mt">${[["Distancia", f1(r.km) + " km"], ["Tiempo estimado", Math.round(r.minutos) + " min"], ["Costo total", clp(r.costo)], ["Costo por retiro", clp(r.costo_por_retiro)], ["Ahorro vs. orden simple", f1(r.ahorro_km) + " km"]].map(a => `<div class="box kpi"><b>${a[1]}</b><span>${a[0]}</span></div>`).join("")}</div>` : ""}
  <div class="box mt">
    <div id="map" role="img" aria-label="Mapa con puntos de retiro, entrega y ruta"></div>
    <p><small>Verde: donantes · azul: beneficiarios · negro: centro de acopio. ${r ? (r.fuente === "osrm" ? "Ruta calculada por calle con OSRM." : "OSRM no está disponible: se muestran distancias estimadas en línea recta.") : "Planifica una ruta para verla en el mapa."}</small></p>
    ${r ? `<div class="sc"><table><tr><th>Parada</th><th>Tipo</th><th>Lugar</th></tr>${r.paradas.map((p, i) => `<tr><td>${i + 1}</td><td>${p.tipo}</td><td>${esc(p.nombre)}</td></tr>`).join("")}</table></div>` : ""}
  </div>`;
}

export function vSeg(prods, places) {
  const P = id => places.find(p => p.id === id) || { nombre: "—", personas: 0 };
  return `<div class="box sc">
    <h3>Seguimiento de retiros y entregas</h3>
    <table>
      <tr><th>Producto</th><th>kg</th><th>Origen</th><th>Destino</th><th>Estado</th><th></th></tr>
      ${prods.map(p => `<tr>
        <td>${esc(p.nombre)}</td>
        <td>${p.kg}</td>
        <td>${esc(P(p.donante_id).nombre)}</td>
        <td>${p.destino_id ? esc(P(p.destino_id).nombre) : "—"}</td>
        <td><span class="tag ${stc(p.status)}">${p.status}</span></td>
        <td>${p.status === "En ruta" ? `<button class="b s btn-entregar" data-id="${p.id}">Marcar entregado</button>` : ""}</td>
      </tr>`).join("")}
    </table>
  </div>`;
}

export function vInd(ind, prods) {
  const k = ind;
  const kc = CAT.map(c => [c, prods.filter(p => p.status === "Entregado" && p.categoria === c).reduce((a, p) => a + p.kg, 0)]);
  const mx = Math.max(1, ...kc.map(a => a[1]));

  return `<div class="g g5">${[["Kilómetros recorridos", f1(k.km_recorridos) + " km"], ["Costo por retiro", clp(k.costo_por_retiro)], ["Tiempo de entrega", f1(k.tiempo_entrega_horas) + " h"], ["Kilogramos recuperados", f1(k.kg_recuperados) + " kg"], ["Beneficiarios", k.beneficiarios_org + " org. · " + k.beneficiarios_personas + " personas"]].map(a => `<div class="box kpi"><b style="font-size:22px">${a[1]}</b><span>${a[0]}</span></div>`).join("")}</div>
  <div class="g g2 mt">
    <div class="box">
      <h3>Kilogramos entregados por categoría</h3>
      ${kc.map(a => `<div class="bar"><em>${a[0]}</em><i style="width:${a[1] / mx * 50}%"></i>${a[1]} kg</div>`).join("")}
    </div>
    <div class="box sc">
      <h3>Definición de indicadores</h3>
      <table>
        <tr><th>Indicador</th><th>Fórmula</th></tr>
        <tr><td>Km recorridos</td><td>Σ distancia real por calle de las rutas, km</td></tr>
        <tr><td>Costo por retiro</td><td>(km × ${clp(k.costo_km)} + retiros × ${clp(k.fijo_retiro)}) ÷ retiros, CLP</td></tr>
        <tr><td>Tiempo de entrega</td><td>promedio (entrega − solicitud), horas</td></tr>
        <tr><td>Kg recuperados</td><td>Σ kg de productos entregados</td></tr>
        <tr><td>Beneficiarios</td><td>organizaciones distintas con entrega y suma de sus personas</td></tr>
      </table>
    </div>
  </div>`;
}