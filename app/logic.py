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


def _cat(p: Producto) -> tuple[int, bool]:
    # Tolera categorías desconocidas (datos que ya existían en la BD).
    return CATEGORIAS.get(p.categoria, (1, False))


def dias(p: Producto) -> int:
    return 999 if p.vence is None else (p.vence - date.today()).days


def score(p: Producto) -> int:
    d = dias(p)
    s = _cat(p)[0] * 10
    s += 15 if d <= 2 else 8 if d <= 7 else 0
    s += {"Próximo a vencer": 10, "Regular": -3}.get(p.estado, 0)
    return s


def prioridad(p: Producto) -> str:
    s = score(p)
    return "Alta" if s >= 35 else "Media" if s >= 20 else "Baja"


def asignar(db) -> tuple[int, int]:
    """Asigna por prioridad al beneficiario compatible más cercano con capacidad."""
    lugares = {x.id: x for x in db.scalars(select(Place))}
    benef = [x for x in lugares.values() if x.tipo == "beneficiario" and x.lat is not None and x.lng is not None]
    carga = {b.id: 0.0 for b in benef}
    vigentes = select(Producto).where(Producto.destino_id.is_not(None), Producto.status != "Entregado")
    for p in db.scalars(vigentes):
        if p.destino_id in carga:
            carga[p.destino_id] += p.kg or 0
    ok = no = 0
    pend = db.scalars(select(Producto).where(Producto.status == "Disponible")).all()
    for p in sorted(pend, key=score, reverse=True):
        o = lugares.get(p.donante_id)
        if o is None or o.lat is None or o.lng is None:
            no += 1
            continue
        kg = p.kg or 0
        requiere_frio = _cat(p)[1]
        cands = [b for b in benef
                 if p.categoria in (b.necesidades or [])
                 and (not requiere_frio or b.frio)
                 and carga[b.id] + kg <= (b.capacidad_kg or 0)]
        if cands:
            b = min(cands, key=lambda b: haversine((o.lat, o.lng), (b.lat, b.lng)))
            p.destino_id, p.status = b.id, "Asignado"
            carga[b.id] += kg
            ok += 1
        else:
            no += 1
    db.commit()
    return ok, no
