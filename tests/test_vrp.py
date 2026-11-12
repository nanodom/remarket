from app.routing import haversine
from app.routing_vrp import Envio, Vehiculo, _resolver


def _mat(pts):
    dist = [[haversine(a, b) * 1300 for b in pts] for a in pts]
    return [[d / (35 / 3.6) for d in f] for f in dist], dist


def test_envio_con_frio_va_en_vehiculo_refrigerado():
    pts = [(-29.95, -71.33), (-29.91, -71.25), (-29.90, -71.24), (-29.98, -71.12), (-29.89, -71.24)]
    dur, dist = _mat(pts)
    envios = [Envio([], 100, True, 40, "d1", "b1", pts[1], pts[2]),
              Envio([], 100, False, 20, "d2", "b2", pts[3], pts[4])]
    flota = [Vehiculo("A", 500, False, 450, 3000, (480, 1080)),
             Vehiculo("B", 500, True, 650, 8000, (480, 1080))]
    rutas, omitidos = _resolver(dur, dist, [0, 1, 2, 3, 4], envios, flota, 2)
    assert omitidos == []
    v_frio = next(v for v, seq in rutas if any(n in (1, 2) for n, *_ in seq))
    assert v_frio == 1


def test_envio_mas_pesado_que_la_flota_se_omite():
    pts = [(-29.95, -71.33), (-29.91, -71.25), (-29.90, -71.24)]
    dur, dist = _mat(pts)
    envios = [Envio([], 900, False, 20, "d", "b", pts[1], pts[2])]
    flota = [Vehiculo("A", 500, False, 450, 3000, (480, 1080))]
    rutas, omitidos = _resolver(dur, dist, [0, 1, 2], envios, flota, 2)
    assert rutas == [] and omitidos == [0]