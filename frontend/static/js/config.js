// Constantes del sistema
export const CAT = ["Alimentos perecibles", "Alimentos no perecibles", "Higiene y limpieza", "Abrigo y ropa"];
export const TABS = ["Registrar", "Clasificar", "Asignar", "Flota", "Rutas", "Seguimiento", "Indicadores"];
export const COLORES_RUTA = ["#2a62c9", "#d1495b", "#edae49", "#00798c", "#8e44ad", "#3d9970"];
export const GEOAPIFY_API_KEY = "5d12bffca3f746979886cc49eec9a159";

// Selectores y Helpers
export const $ = selector => document.querySelector(selector);
export const esc = str => String(str).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
export const clp = num => "$" + Math.round(num).toLocaleString("es-CL");
export const f1 = num => (Math.round(num * 10) / 10).toLocaleString("es-CL");
export const stc = str => str.replace(" ", "");

// Mensajes en pantalla
export function aviso(texto, esError = false) {
  const msgEl = $("#msg");
  if (msgEl) {
    msgEl.innerHTML = texto ? `<div class="${esError ? "err" : ""}">${esc(texto)}</div>` : "";
  }
}