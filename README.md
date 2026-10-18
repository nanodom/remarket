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
`GET/POST /api/places` · `GET /api/geocode?q=` · `GET/POST /api/productos` · `POST /api/asignar` · `POST /api/rutas/planificar` · `POST /api/productos/{id}/entregar` · `GET /api/indicadores`

## Antes de salir a producción
- Los servidores públicos de OSM (tiles, Nominatim) y el demo de OSRM tienen límites de uso: usa instancias propias o un proveedor de mapas.
- Agrega autenticación por tipo de actor y migraciones (Alembic).
- Para varios vehículos, capacidad o ventanas horarias, reemplaza el optimizador de `routing.py` por Google OR-Tools usando la misma matriz.
