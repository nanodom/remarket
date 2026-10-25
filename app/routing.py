"""Rutas reales con OSRM (tabla de matrices + ruta final). Si OSRM no responde, usa estimaciones."""
import math
import os
import httpx

#OSRM_URL = os.getenv("OSRM_URL", "http://localhost:5000")
OSRM_URL = os.getenv("OSRM_URL", "https://router.project-osrm.org")
COSTO_KM = float(os.getenv("COSTO_KM", 450))        # CLP por km
FIJO_RETIRO = float(os.getenv("FIJO_RETIRO", 3500))  # CLP por retiro
MIN_PARADA = float(os.getenv("MIN_PARADA", 10))      # minutos por parada
VEL_FALLBACK = 35 / 3.6                              # m/s


def haversine(a, b) -> float:
    """Distancia en línea recta en km entre (lat, lng)."""
    r = math.radians
    dl, dn = r(b[0] - a[0]), r(b[1] - a[1])
    h = math.sin(dl / 2) ** 2 + math.cos(r(a[0])) * math.cos(r(b[0])) * math.sin(dn / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def _coords(pts):
    return ";".join(f"{lng},{lat}" for lat, lng in pts)


async def matrices(pts):
    """Devuelve (duraciones s, distancias m, fuente)."""
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(f"{OSRM_URL}/table/v1/driving/{_coords(pts)}",
                            params={"annotations": "duration,distance"})
            r.raise_for_status()
            j = r.json()
        fix = lambda m: [[1e9 if x is None else x for x in f] for f in m]
        return fix(j["durations"]), fix(j["distances"]), "osrm"
    except Exception as e:
        print(f"[!] Error de OSRM (matrices): {e}")
        dist = [[haversine(a, b) * 1300 for b in pts] for a in pts]
        return [[d / VEL_FALLBACK for d in f] for f in dist], dist, "estimado"


def _nn(cost, start, nodes):
    orden, resto, cur = [], list(nodes), start
    while resto:
        cur = min(resto, key=lambda j: cost[cur][j])
        resto.remove(cur)
        orden.append(cur)
    return orden


def _largo(cost, start, orden):
    return sum(cost[a][b] for a, b in zip([start] + orden, orden))


def _dos_opt(cost, start, orden):
    mejor, mejora = orden, True
    while mejora:
        mejora = False
        for i in range(len(mejor) - 1):
            for j in range(i + 1, len(mejor)):
                cand = mejor[:i] + mejor[i:j + 1][::-1] + mejor[j + 1:]
                if _largo(cost, start, cand) < _largo(cost, start, mejor) - 1e-9:
                    mejor, mejora = cand, True
    return mejor


async def _ruta_final(pts, fuente, dist):
    if fuente == "osrm":
        try:
            async with httpx.AsyncClient(timeout=20) as c:
                r = await c.get(f"{OSRM_URL}/route/v1/driving/{_coords(pts)}",
                                params={"overview": "full", "geometries": "geojson"})
                r.raise_for_status()
                ro = r.json()["routes"][0]
            return ro["geometry"], ro["distance"] / 1000, ro["duration"] / 60
        except Exception as e:
            print(f"[!] Error de OSRM (ruta final): {e}")
            pass
    km = sum(dist[i][i + 1] for i in range(len(pts) - 1)) / 1000
    geom = {"type": "LineString", "coordinates": [[lng, lat] for lat, lng in pts]}
    return geom, km, km * 1000 / VEL_FALLBACK / 60


async def planificar(base, donantes, beneficiarios):
    """base: (lat,lng); donantes/beneficiarios: listas de (lat,lng).
    Un vehículo: primero todos los retiros, luego las entregas, y vuelve a la base.
    Retorna orden de retiros y entregas (índices en cada lista) y la ruta real."""
    pts = [base] + donantes + beneficiarios
    dur, dist, fuente = await matrices(pts)
    idx_d = list(range(1, 1 + len(donantes)))
    idx_b = list(range(1 + len(donantes), len(pts)))
    o_d = _dos_opt(dur, 0, _nn(dur, 0, idx_d))
    o_b = _dos_opt(dur, o_d[-1], _nn(dur, o_d[-1], idx_b))
    seq = [0] + o_d + o_b + [0]
    ingenuo = [0] + idx_d + idx_b + [0]
    geom, km, minutos = await _ruta_final([pts[i] for i in seq], fuente, [[dist[a][b] for b in seq] for a in seq])
    km_ing = sum(dist[a][b] for a, b in zip(ingenuo, ingenuo[1:])) / 1000
    return {
        "retiros": [i - 1 for i in o_d],
        "entregas": [i - 1 - len(donantes) for i in o_b],
        "geometria": geom, "km": km,
        "minutos": minutos + MIN_PARADA * (len(seq) - 2),
        "ahorro_km": max(0.0, km_ing - sum(dist[a][b] for a, b in zip(seq, seq[1:])) / 1000),
        "fuente": fuente,
    }
