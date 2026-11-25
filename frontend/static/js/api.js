export async function api(endpoint, options = {}) {
  const token = localStorage.getItem("token");
  const headers = {
    "Content-Type": "application/json",
    ...(token ? { "Authorization": `Bearer ${token}` } : {}),
    ...(options.headers || {})
  };

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

export async function descargarCertificado(donanteId) {
  const token = localStorage.getItem("token");
  const response = await fetch(
    `/api/productos/certificado/${encodeURIComponent(donanteId)}`,
    {
      headers: token ? { "Authorization": `Bearer ${token}` } : {}
    }
  );

  if (response.status === 401) {
    localStorage.removeItem("token");
    location.reload();
    throw new Error("Sesión expirada. Vuelve a ingresar.");
  }

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(
      typeof (data && data.detail) === "string"
        ? data.detail
        : "No se pudo descargar el certificado."
    );
  }

  if (!response.headers.get("Content-Type")?.includes("application/pdf")) {
    throw new Error("La API no devolvió un archivo PDF válido.");
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `Certificado_Donacion_${donanteId}.pdf`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// Carga simultánea de datos principales
export async function cargarDatosAPI() {
  const [places, prods, ind, ruta, vehiculos] = await Promise.all([
    api("/places"),
    api("/productos"),
    api("/indicadores"),
    api("/rutas/ultima"),
    api("/vehiculos")
  ]);
  return { places, prods, ind, ruta, vehiculos };
}