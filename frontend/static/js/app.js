import { TABS, $, aviso, f1 } from './config.js';
import { api, cargarDatosAPI } from './api.js';
import { initMap, simularRecorrido, destroyMap } from './map.js';
import { vLogin, vRegistrar, vClasificar, vAsignar, vFlota, vRutas, vSeg, vInd } from './views.js';

const estadoInicial = () => ({
  tab: 0, places: [], prods: [], ind: {}, ruta: null, vehiculos: [], editVeh: null
});
let state = estadoInicial();

// Carga inicial y actualización de estado
async function actualizarEstado() {
  const datos = await cargarDatosAPI();
  state = { ...state, ...datos };
}

async function runAccion(fn) {
  try {
    const mensaje = await fn();
    await actualizarEstado();
    render();
    aviso(mensaje);
  } catch (e) {
    aviso(e.message, true);
  }
}

// Handlers de acciones
async function handleLogin(e) {
  e.preventDefault();
  const f = e.target;
  try {
    aviso("");
    const r = await api("/login", {
      method: "POST",
      body: JSON.stringify({ username: f.username.value, password: f.password.value })
    });
    localStorage.setItem("token", r.token);
    initApp();
  } catch (err) {
    aviso(err.message, true);
  }
}

function handleLogout() {
  localStorage.removeItem("token");
  destroyMap();
  state = estadoInicial();
  $("#app-header").style.display = "none";
  $("#nav").innerHTML = "";
  $("#v").innerHTML = vLogin();
  bindEvents();
  aviso("");
}

// Renderizado principal
function renderNav() {
  $("#nav").innerHTML = TABS.map((t, i) =>
    `<button class="${i === state.tab ? "on" : ""}" data-tab="${i}">${t}</button>`
  ).join("");
}

function render() {
  renderNav();
  window.remarketTab = TABS[state.tab]; // lo lee chatbot.js para dar contexto
  // El orden debe coincidir con TABS en config.js
  const vistas = [
    () => vRegistrar(state.places),
    () => vClasificar(state.prods),
    () => vAsignar(state.places, state.prods),
    () => vFlota(state.vehiculos, state.editVeh),
    () => vRutas(state.ruta),
    () => vSeg(state.prods, state.places),
    () => vInd(state.ind, state.prods)
  ];

  $("#v").innerHTML = vistas[state.tab]();

  if (TABS[state.tab] === "Rutas") {
    initMap(state.places, state.ruta);
  } else {
    destroyMap();
  }

  bindEvents();
}

// Delegación y vinculación de eventos
function bindEvents() {
  // Navegación
  $("#nav").onclick = (e) => {
    if (e.target.tagName === 'BUTTON') {
      state.tab = +e.target.dataset.tab;
      aviso('');
      render();
    }
  };

  // Login
  const formLogin = $("#form-login");
  if (formLogin) formLogin.onsubmit = handleLogin;

  // Registrar producto
  const formReg = $("#form-registrar");
  if (formReg) {
    formReg.onsubmit = e => {
      e.preventDefault();
      const f = e.target;
      runAccion(async () => {
        await api("/productos", {
          method: "POST",
          body: JSON.stringify({
            nombre: f.nom.value,
            categoria: f.cat.value,
            kg: +f.kg.value,
            estado: f.estado.value,
            vence: f.vence.value || null,
            donante_id: f.don.value // UUID: se envía como texto
          })
        });
        return "Producto registrado.";
      });
    };
  }

  // Crear Donante / Beneficiario
  const formLugar = $("#form-lugar");
  if (formLugar) {
    const selectTipo = $("#tipo-lugar-select");
    if (selectTipo) {
      selectTipo.onchange = (e) => {
        $("#bf").style.display = e.target.value === 'beneficiario' ? 'block' : 'none';
      };
    }

    formLugar.onsubmit = e => {
      e.preventDefault();
      const f = e.target;
      const nec = [...f.querySelectorAll("[name=nec]:checked")].map(x => x.value);
      runAccion(async () => {
        const p = await api("/places", {
          method: "POST",
          body: JSON.stringify({
            nombre: f.nombre.value,
            tipo: f.tipo.value,
            direccion: f.direccion.value,
            personas: Math.round(+f.personas.value) || 0,
            capacidad_kg: Math.round(+f.cap.value) || 0,
            frio: f.frio.checked,
            necesidades: nec
          })
        });
        return `Lugar agregado en ${p.lat.toFixed(4)}, ${p.lng.toFixed(4)}.`;
      });
    };
  }

  // Asignar
  const btnAsignar = $("#btn-asignar");
  if (btnAsignar) {
    btnAsignar.onclick = () => runAccion(async () => {
      const r = await api("/asignar", { method: "POST" });
      return r.asignados + " productos asignados" + (r.sin_destino ? `, ${r.sin_destino} sin destinatario compatible.` : ".");
    });
  }

  // Flota
  const formVeh = $("#form-vehiculo");
  if (formVeh) {
    formVeh.onsubmit = e => {
      e.preventDefault();
      const f = e.target, id = f.dataset.id;
      runAccion(async () => {
        await api(id ? `/vehiculos/${id}` : "/vehiculos", {
          method: id ? "PUT" : "POST",
          body: JSON.stringify({
            nombre: f.nombre.value.trim(),
            patente: f.patente.value.trim() || null,
            capacidad_kg: Math.round(+f.cap.value),
            costo_km: +f.ckm.value,
            costo_fijo: +f.cfijo.value,
            turno_inicio: f.ini.value,
            turno_fin: f.fin.value,
            tiene_frio: f.frio.checked,
            activo: f.activo.checked
          })
        });
        state.editVeh = null;
        return id ? "Vehículo actualizado." : "Vehículo agregado.";
      });
    };
  }

  const btnCancelar = $("#btn-cancelar-veh");
  if (btnCancelar) btnCancelar.onclick = () => { state.editVeh = null; render(); };

  document.querySelectorAll(".btn-editar-veh").forEach(btn => {
    btn.onclick = () => {
      state.editVeh = state.vehiculos.find(v => v.id === btn.dataset.id) || null;
      render();
      window.scrollTo({ top: 0, behavior: "smooth" });
    };
  });

  document.querySelectorAll(".btn-borrar-veh").forEach(btn => {
    btn.onclick = () => {
      if (!confirm("¿Eliminar este vehículo?")) return;
      runAccion(async () => (await api(`/vehiculos/${btn.dataset.id}`, { method: "DELETE" })).mensaje);
    };
  });

  // Planificar y Simular
  const btnPlanificar = $("#btn-planificar");
  if (btnPlanificar) {
    btnPlanificar.onclick = () => runAccion(async () => {
      const r = await api("/rutas/planificar", { method: "POST" });
      const om = r.omitidos.length
        ? ` Sin atender (${r.omitidos.length}): ` + r.omitidos.slice(0, 3).map(o => `${o.producto} (${o.motivo})`).join("; ") + (r.omitidos.length > 3 ? "…" : ".")
        : "";
      return `Plan listo: ${r.rutas.length} vehículo(s), ${f1(r.km)} km.${om}`;
    });
  }

  const btnSimular = $("#btn-simular");
  if (btnSimular) {
    btnSimular.onclick = () => simularRecorrido(state.ruta);
  }

  // Entregar producto
  document.querySelectorAll(".btn-entregar").forEach(btn => {
    btn.onclick = () => {
      const id = btn.dataset.id; // UUID como texto
      runAccion(async () => {
        await api(`/productos/${id}/entregar`, { method: "POST" });
        return "Entrega registrada.";
      });
    };
  });
}

async function initApp() {
  $("#app-header").style.display = "flex";
  $("#btn-logout").onclick = handleLogout;
  try {
    await actualizarEstado();
    render();
  } catch (e) {
    $("#v").innerHTML = "";
    aviso("No se pudo conectar con la API: " + e.message, true);
  }
}

// Inicialización de arranque
document.addEventListener("DOMContentLoaded", () => {
  if (localStorage.getItem("token")) {
    initApp();
  } else {
    $("#v").innerHTML = vLogin();
    bindEvents();
  }
});