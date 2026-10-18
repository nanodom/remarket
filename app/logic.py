from datetime import date
from sqlalchemy import select
from .models import Place, Producto
from .routing import haversine

# categoría -> (peso de prioridad, requiere cadena de frío)
CATEGORIAS = {
    "Alimentos perecibles": (3, True),
    "Alimentos no perecibles": (2, False),
    "Higiene y limpieza": (2, False),
    "Abrigo y ropa": (1, False),
}


def dias(p: Producto) -> int:
    return 999 if p.vence is None else (p.vence - date.today()).days


def score(p: Producto) -> int:
    d = dias(p)
    s = CATEGORIAS[p.categoria][0] * 10
    s += 15 if d <= 2 else 8 if d <= 7 else 0
    s += {"Próximo a vencer": 10, "Regular": -3}.get(p.estado, 0)
    return s


def prioridad(p: Producto) -> str:
    s = score(p)
    return "Alta" if s >= 35 else "Media" if s >= 20 else "Baja"


def asignar(db) -> tuple[int, int]:
    """Asigna por prioridad al beneficiario compatible más cercano con capacidad."""
    lugares = {x.id: x for x in db.scalars(select(Place))}
    benef = [x for x in lugares.values() if x.tipo == "beneficiario"]
    carga = {b.id: 0.0 for b in benef}
    for p in db.scalars(select(Producto).where(Producto.destino_id.is_not(None), Producto.status != "Entregado")):
        carga[p.destino_id] += p.kg
    ok = no = 0
    pend = db.scalars(select(Producto).where(Producto.status == "Disponible")).all()
    for p in sorted(pend, key=score, reverse=True):
        o = lugares[p.donante_id]
        cands = [b for b in benef
                 if p.categoria in b.necesidades
                 and (not CATEGORIAS[p.categoria][1] or b.frio)
                 and carga[b.id] + p.kg <= b.capacidad_kg]
        if cands:
            b = min(cands, key=lambda b: haversine((o.lat, o.lng), (b.lat, b.lng)))
            p.destino_id, p.status = b.id, "Asignado"
            carga[b.id] += p.kg
            ok += 1
        else:
            no += 1
    db.commit()
    return ok, no
