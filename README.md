# ReMarket 2.0: backend con mapas y rutas reales

Stack: FastAPI + SQLAlchemy (SQLite en local, PostgreSQL en Docker) · OSRM (rutas por calle) · Nominatim (geocodificación) · Leaflet + OpenStreetMap (mapa).

## Arranque rápido (sin Docker)
```bash
pip install -r requirements.txt
# Para probar rutas reales sin instalar OSRM (servidor demo, solo desarrollo):
export OSRM_URL=https://router.project-osrm.org
uvicorn app.main:app --reload
```
Abre http://localhost:8000 (interfaz) o http://localhost:8000/docs (API). Sin OSRM disponible, el sistema usa distancias estimadas y lo indica en pantalla.

## Producción con OSRM propio (Docker)
```bash
mkdir osrm-data && cd osrm-data
wget https://download.geofabrik.de/south-america/chile-latest.osm.pbf
# Recomendado: recortar a tu zona para ahorrar memoria (requiere osmium-tool)
osmium extract -b -72.3,-30.7,-70.5,-29.4 chile-latest.osm.pbf -o region.osm.pbf
docker run -t -v "${PWD}:/data" osrm/osrm-backend osrm-extract -p /opt/car.lua /data/region.osm.pbf
docker run -t -v "${PWD}:/data" osrm/osrm-backend osrm-partition /data/region.osrm
docker run -t -v "${PWD}:/data" osrm/osrm-backend osrm-customize /data/region.osrm
cd .. && docker compose up --build
```

## Cómo funciona la ruta
1. `/table` de OSRM entrega la matriz real de tiempos y distancias entre base, donantes y beneficiarios.
2. Se ordenan los retiros y luego las entregas (vecino más cercano + 2-opt) sobre esa matriz.
3. `/route` de OSRM devuelve la geometría por calle, los km y los minutos finales.
4. Costo = km × `COSTO_KM` + retiros × `FIJO_RETIRO` (variables de entorno, CLP).

## Endpoints
`POST /api/login` · `GET/POST /api/places` · `GET /api/geocode?q=` · `GET/POST /api/productos` · `GET /api/productos/certificado/{donante_id}` · `POST /api/asignar` · `POST /api/productos/{id}/entregar` · `GET/POST /api/vehiculos` · `PUT/DELETE /api/vehiculos/{id}` · `POST /api/rutas/planificar` · `GET /api/rutas/ultima` · `GET /api/indicadores` · `POST /api/chat`

### Swagger interactivo

Abre `http://localhost:8000/docs` para consultar las operaciones agrupadas por área. Los modelos de solicitud incluyen ejemplos JSON. Para probar rutas protegidas, ejecuta `POST /api/login`, copia el valor de `token` y pulsa **Authorize**; pega el token sin escribir el prefijo `Bearer` (Swagger lo añade automáticamente). Los endpoints públicos de documentación no requieren inicio de sesión.

## Certificado de donación en PDF

`GET /api/productos/certificado/{donante_id}` genera y descarga un PDF para un donante. La ruta está bajo el router autenticado: envía `Authorization: Bearer <token>`. El identificador debe ser un UUID válido. El endpoint busca al donante y reúne sus productos cuyo estado logístico sea `Entregado`; responde `404` si el donante no existe y `400` si no tiene productos entregados.

La generación está implementada en `app/reports.py` con ReportLab. El endpoint de `app/main.py` prepara los datos, llama a `generar_pdf_certificado_bytes(...)` y devuelve los bytes con `Content-Type: application/pdf` y disposición de descarga. Para probarlo:

En la pestaña **Seguimiento**, al registrar una entrega, la fila del producto cambia a `Entregado` y aparece el botón **Descargar certificado**. El botón descarga el certificado del donante; este incluye todos sus productos entregados hasta ese momento.

1. Instala las dependencias con `pip install -r requirements.txt` e inicia la aplicación.
2. Inicia sesión en `POST /api/login` para obtener un token.
3. Consulta `GET /api/productos` y toma el `donante_id` de un producto con `status: "Entregado"`.
4. Descarga el archivo:

```bash
curl -H "Authorization: Bearer <token>" \
  -o certificado.pdf \
  "http://localhost:8000/api/productos/certificado/<donante_id>"
```

El archivo debe comenzar con la firma `%PDF-`; ábrelo con un lector PDF para revisar el diseño y los datos. Si no existen productos entregados, completa el flujo de asignación, planificación y entrega antes de probar este endpoint.

Instala también las herramientas de prueba con `pip install -r requirements-dev.txt` y ejecuta la suite con `python -m pytest`. Para probar solo la generación PDF: `python -m pytest tests/test_reports.py -q`.

### Estructura del documento

1. **Encabezado:** título del certificado y referencia legal.
2. **Datos generales:** folio, fecha de emisión, donante, beneficiario y operador logístico.
3. **Resumen de métricas:** kilos rescatados, costo estimado, impuesto calculado y CO₂ estimado.
4. **Detalle de productos:** nombre, categoría, peso, vencimiento e indicador de inspección.
5. **Declaración final:** texto de respaldo y monto calculado.

### Datos y consideraciones antes de usarlo oficialmente

- Los valores de cálculo están fijos en `app/reports.py`: `$4.500 CLP/kg`, tasa del `40%` y `1,5 kg de CO₂/kg`. Son supuestos del reporte, no valores obtenidos de libros contables ni cálculos tributarios o ambientales verificados.
- El endpoint usa RUT de donante y beneficiario, nombre del beneficiario y RUT del operador definidos actualmente en el código. Deben reemplazarse por datos verificados y asociados a cada operación antes de emitir documentos reales.
- El indicador de inspección aparece como aprobado, pero el modelo de productos no registra una inspección individual. No debe interpretarse como evidencia sanitaria hasta integrar una fuente de inspección verificable.
- El folio se genera aleatoriamente al descargar y no se persiste; descargar de nuevo produce otro folio. El reporte tampoco guarda una copia inmutable de los datos utilizados.
- La redacción tributaria y las referencias legales del PDF deben ser revisadas por profesionales contables y legales. No usarlo como certificado oficial ni como comprobante de deducción o exención hasta validar el tratamiento aplicable y los datos de respaldo.
- `reportlab` está declarado en `requirements.txt`; si se instala el proyecto con otro mecanismo, asegúrate de incluir esa dependencia.

## Antes de salir a producción
- Los servidores públicos de OSM (tiles, Nominatim) y el demo de OSRM tienen límites de uso: usa instancias propias o un proveedor de mapas.
- Agrega autenticación por tipo de actor y migraciones (Alembic).
- Para varios vehículos, capacidad o ventanas horarias, reemplaza el optimizador de `routing.py` por Google OR-Tools usando la misma matriz.
