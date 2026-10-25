import { aviso } from './config.js';

export async function api(endpoint, options) {
  const token = localStorage.getItem("token");
  const headers = {
    "Content-Type": "application/json",
    ...(token ? { "Authorization": `Bearer ${token}` } : {})
  };

  const response = await fetch("/api" + endpoint, options && { ...options, headers });
  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(typeof (data && data.detail) === "string" ? data.detail : "Revisa los datos ingresados.");
  }
  return data;
}

// Carga simultánea de datos principales
export async function cargarDatosAPI() {
  const [places, prods, ind, ruta] = await Promise.all([
    api("/places"),
    api("/productos"),
    api("/indicadores"),
    api("/rutas/ultima")
  ]);
  return { places, prods, ind, ruta };
}