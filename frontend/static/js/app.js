import { TABS, $, aviso } from './config.js';
import { api, cargarDatosAPI } from './api.js';
import { initMap, simularRecorrido, destroyMap } from './map.js';
import { vLogin, vRegistrar, vClasificar, vAsignar, vRutas, vSeg, vInd } from './views.js';

// Estado global de la aplicación
let state = {
  tab: 0,
  places: [],
  prods: [],
  ind: {},
  ruta: null
};

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
    if (f.username.value === "admin" && f.password.value === "remarket2026") {
      localStorage.setItem("token", "mock-token-company");
      initApp();
    } else {
      throw new Error("Credenciales inválidas o usuario no autorizado.");
    }
  } catch (err) {
    aviso(err.message, true);
  }
}

function handleLogout() {
  localStorage.removeItem("token");
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
  const vistas = [
    () => vRegistrar(state.places),
    () => vClasificar(state.prods),
    () => vAsignar(state.places, state.prods),
    () => vRutas(state.ruta),
    () => vSeg(state.prods, state.places),
    () => vInd(state.ind, state.prods)
  ];

  $("#v").innerHTML = vistas[state.tab]();

  if (state.tab === 3) {
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
            donante_id: +f.don.value
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
            personas: +f.personas.value || 0,
            capacidad_kg: +f.cap.value || 0,
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

  // Planificar y Simular
  const btnPlanificar = $("#btn-planificar");
  if (btnPlanificar) {
    btnPlanificar.onclick = () => runAccion(async () => {
      await api("/rutas/planificar", { method: "POST" });
      return "Ruta planificada. Los productos quedaron En ruta.";
    });
  }

  const btnSimular = $("#btn-simular");
  if (btnSimular) {
    btnSimular.onclick = () => simularRecorrido(state.ruta);
  }

  // Entregar producto
  document.querySelectorAll(".btn-entregar").forEach(btn => {
    btn.onclick = () => {
      const id = btn.dataset.id;
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