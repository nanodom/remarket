export async function api(endpoint, options = {}) {
  const token = localStorage.getItem("token");
  const headers = {
    "Content-Type": "application/json",
    ...(token ? { "Authorization": `Bearer ${token}` } : {}),
    ...(options.headers || {})
  };

  // Antes, las peticiones GET (sin `options`) se enviaban sin cabeceras ni token.
  const response = await fetch("/api" + endpoint, { ...options, headers });

  if (response.status === 401 && endpoint !== "/login") {
    localStorage.removeItem("token");
    location.reload();
    throw new Error("Sesión expirada. Vuelve a ingresar.");
  }

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
