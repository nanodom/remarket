"""VRP con recogida y entrega, capacidad, flota heterogénea y envíos opcionales (OR-Tools).
Fase 1: sin ventanas horarias. La duración del turno acota la jornada de cada vehículo."""
import asyncio
import math
import os
from dataclasses import dataclass

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from .routing import MIN_PARADA, _ruta_final, matrices

PENALIZACION_BASE = int(os.getenv("PENALIZACION_BASE", 500_000))        # CLP
PENALIZACION_POR_PUNTO = int(os.getenv("PENALIZACION_POR_PUNTO", 10_000))  # CLP por punto de puntaje
SEGUNDOS_SOLVER = int(os.getenv("SEGUNDOS_SOLVER", 10))


@dataclass
class Vehiculo:
    id: str
    cap_kg: int
    frio: bool
    costo_km: float
    costo_fijo: float
    turno: tuple[int, int]      # minutos desde las 00:00; en fase 1 solo importa su duración


@dataclass
class Envio:                    # un donante -> un beneficiario
    productos: list
    kg: int
    frio: bool
    prioridad: int              # puntaje de logic.score (máximo del grupo)
    donante_id: str
    destino_id: str
    donante: tuple              # (lat, lng)
    destino: tuple


def _resolver(dur, dist, loc, envios, flota, segundos):
    """loc[nodo] -> índice en las matrices. Nodo 0 = base; retiro k = 1+2k; entrega k = 2+2k."""
    n = 1 + 2 * len(envios)
    mgr = pywrapcp.RoutingIndexManager(n, len(flota), 0)
    rt = pywrapcp.RoutingModel(mgr)
    N = mgr.IndexToNode

    carga = [0]
    for e in envios:
        carga += [e.kg, -e.kg]
    serv = [0] + [int(MIN_PARADA)] * (n - 1)

    # Costo por vehículo (CLP enteros) + costo fijo por usarlo
    for v, veh in enumerate(flota):
        cb = rt.RegisterTransitCallback(
            lambda i, j, k=veh.costo_km: int(dist[loc[N(i)]][loc[N(j)]] / 1000 * k))
        rt.SetArcCostEvaluatorOfVehicle(cb, v)
        rt.SetFixedCostOfVehicle(int(veh.costo_fijo), v)

    # Capacidad: el retiro suma, la entrega resta
    cd = rt.RegisterUnaryTransitCallback(lambda i: carga[N(i)])
    rt.AddDimensionWithVehicleCapacity(cd, 0, [int(v.cap_kg) for v in flota], True, "Carga")

    # Tiempo = viaje + servicio en el nodo de origen, acotado por la duración del turno
    ct = rt.RegisterTransitCallback(
        lambda i, j: math.ceil(dur[loc[N(i)]][loc[N(j)]] / 60) + serv[N(i)])
    rt.AddDimensionWithVehicleCapacity(
        ct, 0, [max(1, v.turno[1] - v.turno[0]) for v in flota], True, "Tiempo")
    tm = rt.GetDimensionOrDie("Tiempo")

    solver = rt.solver()
    con_frio = [v for v, veh in enumerate(flota) if veh.frio]
    for k, e in enumerate(envios):
        p, d = mgr.NodeToIndex(1 + 2 * k), mgr.NodeToIndex(2 + 2 * k)
        rt.AddPickupAndDelivery(p, d)
        solver.Add(rt.VehicleVar(p) == rt.VehicleVar(d))      # mismo camión
        solver.Add(rt.ActiveVar(p) == rt.ActiveVar(d))        # se atiende completo o no se atiende
        solver.Add(tm.CumulVar(p) <= tm.CumulVar(d))          # retiro antes que entrega
        if e.frio:
            rt.SetAllowedVehiclesForIndex(con_frio, p)        # el llamador garantiza que no esté vacía
            rt.SetAllowedVehiclesForIndex(con_frio, d)
        pen = PENALIZACION_BASE + e.prioridad * PENALIZACION_POR_PUNTO
        rt.AddDisjunction([p], pen // 2)
        rt.AddDisjunction([d], pen // 2)

    prm = pywrapcp.DefaultRoutingSearchParameters()
    prm.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
    prm.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    prm.time_limit.seconds = segundos
    sol = rt.SolveWithParameters(prm)
    if not sol:
        return None

    rutas = []
    for v in range(len(flota)):
        if not rt.IsVehicleUsed(sol, v):
            continue
        idx, seq, a_bordo = rt.Start(v), [], 0
        while True:
            nodo = N(idx)
            a_bordo += carga[nodo]
            seq.append((nodo, sol.Min(tm.CumulVar(idx)), a_bordo))   # (nodo, minuto, kg a bordo)
            if rt.IsEnd(idx):
                break
            idx = sol.Value(rt.NextVar(idx))
        rutas.append((v, seq))
    omitidos = [k for k in range(len(envios))
                if sol.Value(rt.NextVar(mgr.NodeToIndex(1 + 2 * k))) == mgr.NodeToIndex(1 + 2 * k)]
    return rutas, omitidos


async def planificar_flota(base, envios, flota, segundos=SEGUNDOS_SOLVER):
    """Retorna None si el solver no encuentra solución, o (rutas, omitidos).
    Cada ruta: {veh, seq, envios, geometria, km, minutos, ahorro_km, fuente}."""
    # Ubicaciones únicas: un donante con varios envíos entra una sola vez a la matriz OSRM.
    pts, idx, loc = [base], {}, [0]
    for e in envios:
        for clave, xy in ((e.donante_id, e.donante), (e.destino_id, e.destino)):
            if clave not in idx:
                idx[clave] = len(pts)
                pts.append(xy)
            loc.append(idx[clave])

    dur, dist, fuente = await matrices(pts)
    sol = await asyncio.to_thread(_resolver, dur, dist, loc, envios, flota, segundos)
    if sol is None:
        return None
    rutas_sol, omitidos = sol

    rutas = []
    for v, seq in rutas_sol:
        nodos = [n for n, _, _ in seq]
        locs = [loc[n] for n in nodos]
        # Sin puntos consecutivos repetidos (dos retiros en el mismo donante)
        unicos = [locs[0]] + [b for a, b in zip(locs, locs[1:]) if a != b]
        sub = lambda m: [[m[a][b] for b in unicos] for a in unicos]
        geom, km, minutos, fg = await _ruta_final([pts[i] for i in unicos], fuente, sub(dist), sub(dur))

        ks = [(n - 1) // 2 for n in nodos if n % 2 == 1]        # envíos de esta ruta (nodos de retiro)
        km_opt = sum(dist[a][b] for a, b in zip(locs, locs[1:])) / 1000
        km_ing = sum(dist[0][loc[1 + 2 * k]] + dist[loc[1 + 2 * k]][loc[2 + 2 * k]] + dist[loc[2 + 2 * k]][0]
                     for k in ks) / 1000
        rutas.append({
            "veh": v, "seq": seq, "envios": ks, "geometria": geom, "km": km,
            "minutos": minutos + MIN_PARADA * (len(nodos) - 2),
            "ahorro_km": max(0.0, km_ing - km_opt),
            "fuente": "osrm" if fuente == "osrm" and fg == "osrm" else "estimado",
        })
    return rutas, omitidos