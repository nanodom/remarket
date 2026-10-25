import os
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select

from . import chat, logic, routing
from .models import Base, Place, Producto, Ruta, SessionLocal, engine
from .security import verificar_ip_abuseipdb

NOMINATIM = os.getenv("NOMINATIM_URL", "https://nominatim.openstreetmap.org")
NOMINATIM_UA = os.getenv("NOMINATIM_UA", "ReMarket/2.0 (contacto@tudominio.cl)")


def get_db():
    with SessionLocal() as db:
        yield db


def seed(db):
    if db.scalars(select(Place)).first():
        return
    base = Place(nombre="Centro de acopio", tipo="base", lat=-29.93, lng=-71.30)
    don = [Place(nombre=n, tipo="donante", lat=a, lng=b) for n, a, b in [
        ("Supermercado Centro", -29.9027, -71.2519), ("Panadería Puerto", -29.965, -71.338),
        ("Distribuidora Norte", -29.92, -71.23), ("Tienda Textil Sur", -29.978, -71.32)]]
    P, N, H, A = "Alimentos perecibles", "Alimentos no perecibles", "Higiene y limpieza", "Abrigo y ropa"
    ben = [Place(nombre=n, tipo="beneficiario", personas=p, capacidad_kg=c, frio=f, necesidades=nec, lat=a, lng=b)
           for n, p, c, f, nec, a, b in [
        ("Comedor Solidario Las Compañías", 120, 200, True, [P, N], -29.91, -71.27),
        ("Junta de Vecinos Tierras Blancas", 80, 150, False, [N, H], -29.955, -71.35),
        ("Hogar de Ancianos San José", 35, 100, True, [H, A, P], -29.89, -71.24),
        ("Fundación Abrigo Sur", 60, 120, False, [A, H], -29.94, -71.29)]]
    db.add_all([base, *don, *ben])
    db.flush()
    hoy = date.today()
    db.add_all([Producto(nombre=n, categoria=c, kg=k, estado=e, vence=hoy + timedelta(days=d), donante_id=don[i].id)
                for n, c, k, e, d, i in [
        ("Lácteos próximos a vencer", P, 60, "Próximo a vencer", 2, 0), ("Pan del día", P, 25, "Bueno", 1, 1),
        ("Arroz y fideos", N, 140, "Regular", 180, 2), ("Detergente y jabón", H, 45, "Bueno", 365, 0),
        ("Chaquetas de temporada", A, 55, "Bueno", 900, 3)]])
    db.commit()


@asynccontextmanager
async def lifespan(_):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
    yield


async def chequear_reputacion_ip(request: Request):
    """
    Dependencia de FastAPI para bloquear IPs reportadas en AbuseIPDB.
    """
    client_ip = request.client.host
    
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()

    if client_ip in ["127.0.0.1", "localhost", "::1"]:
        return True

    resultado = await verificar_ip_abuseipdb(client_ip)
    
    if "error" in resultado:
        return True

    score = resultado.get("abuseConfidenceScore", 0)
    
    if score > 50:
        raise HTTPException(
            status_code=403, 
            detail=f"Acceso denegado: La IP {client_ip} presenta un puntaje de riesgo de abuso alto ({score}%)."
        )
    
    return True


app = FastAPI(title="ReMarket 2.0", lifespan=lifespan)


class PlaceIn(BaseModel):
    nombre: str
    tipo: str = Field(pattern="^(donante|beneficiario|base)$")
    lat: float | None = None
    lng: float | None = None
    direccion: str = ""
    personas: int = 0
    capacidad_kg: float = 0
    frio: bool = False
    necesidades: list[str] = []


class ProductoIn(BaseModel):
    nombre: str
    categoria: str
    kg: float = Field(gt=0)
    estado: str = Field(pattern="^(Bueno|Próximo a vencer|Regular)$")
    vence: date | None = None
    donante_id: int


def place_out(p):
    return {c.name: getattr(p, c.name) for c in Place.__table__.columns}


def prod_out(p):
    return {"id": p.id, "nombre": p.nombre, "categoria": p.categoria, "kg": p.kg, "estado": p.estado,
            "dias": logic.dias(p), "puntaje": logic.score(p), "prioridad": logic.prioridad(p),
            "donante_id": p.donante_id, "destino_id": p.destino_id, "status": p.status}


@app.get("/api/geocode")
async def geocode(q: str):
    """Dirección -> coordenadas (Nominatim)."""
    async with httpx.AsyncClient(timeout=10, headers={"User-Agent": NOMINATIM_UA}) as c:
        r = await c.get(f"{NOMINATIM}/search", params={"q": q, "format": "jsonv2", "countrycodes": "cl", "limit": 5})
    if r.status_code != 200:
        raise HTTPException(502, "Servicio de geocodificación no disponible")
    return [{"nombre": x["display_name"], "lat": float(x["lat"]), "lng": float(x["lon"])} for x in r.json()]


@app.get("/api/places")
def listar_places(db=Depends(get_db)):
    return [place_out(p) for p in db.scalars(select(Place))]


@app.post("/api/places", status_code=201)
async def crear_place(d: PlaceIn, db=Depends(get_db)):
    lat, lng = d.lat, d.lng
    if lat is None or lng is None:
        if not d.direccion:
            raise HTTPException(422, "Indica coordenadas o una dirección")
        res = await geocode(d.direccion)
        if not res:
            raise HTTPException(422, "No se encontró la dirección")
        lat, lng = res[0]["lat"], res[0]["lng"]
    p = Place(**{**d.model_dump(), "lat": lat, "lng": lng})
    db.add(p)
    db.commit()
    return place_out(p)


@app.get("/api/productos")
def listar_productos(db=Depends(get_db)):
    return sorted((prod_out(p) for p in db.scalars(select(Producto))), key=lambda x: -x["puntaje"])


@app.post("/api/productos", status_code=201)
def crear_producto(d: ProductoIn, db=Depends(get_db)):
    if d.categoria not in logic.CATEGORIAS:
        raise HTTPException(422, "Categoría no válida")
    if d.vence and d.vence <= date.today():
        raise HTTPException(422, "Producto vencido: no apto para distribución")
    donante = db.get(Place, d.donante_id)
    if not donante or donante.tipo != "donante":
        raise HTTPException(422, "Donante no válido")
    p = Producto(**d.model_dump())
    db.add(p)
    db.commit()
    return prod_out(p)


@app.post("/api/asignar")
def asignar(db=Depends(get_db)):
    ok, no = logic.asignar(db)
    return {"asignados": ok, "sin_destino": no}


@app.post("/api/rutas/planificar")
async def planificar(db=Depends(get_db)):
    items = db.scalars(select(Producto).where(Producto.status == "Asignado")).all()
    if not items:
        raise HTTPException(400, "No hay productos asignados para planificar")
    base = db.scalars(select(Place).where(Place.tipo == "base")).first()
    if not base:
        raise HTTPException(400, "Falta registrar la base logística")
    lug = {p.id: p for p in db.scalars(select(Place))}
    ids_d = sorted({p.donante_id for p in items})
    ids_b = sorted({p.destino_id for p in items})
    xy = lambda i: (lug[i].lat, lug[i].lng)
    r = await routing.planificar((base.lat, base.lng), [xy(i) for i in ids_d], [xy(i) for i in ids_b])
    paradas = [{"tipo": "retiro", "id": ids_d[i], "nombre": lug[ids_d[i]].nombre, "lat": lug[ids_d[i]].lat, "lng": lug[ids_d[i]].lng} for i in r["retiros"]]
    paradas += [{"tipo": "entrega", "id": ids_b[i], "nombre": lug[ids_b[i]].nombre, "lat": lug[ids_b[i]].lat, "lng": lug[ids_b[i]].lng} for i in r["entregas"]]
    costo = r["km"] * routing.COSTO_KM + len(ids_d) * routing.FIJO_RETIRO
    ruta = Ruta(km=r["km"], minutos=r["minutos"], costo=costo, retiros=len(ids_d), ahorro_km=r["ahorro_km"],
                fuente=r["fuente"], geometria=r["geometria"], paradas=paradas)
    db.add(ruta)
    db.flush()
    for p in items:
        p.status, p.ruta_id = "En ruta", ruta.id
    db.commit()
    return {"id": ruta.id, "km": ruta.km, "minutos": ruta.minutos, "costo": costo,
            "costo_por_retiro": costo / len(ids_d), "ahorro_km": ruta.ahorro_km,
            "fuente": ruta.fuente, "geometria": ruta.geometria, "paradas": paradas}


@app.post("/api/productos/{pid}/entregar")
def entregar(pid: int, db=Depends(get_db)):
    p = db.get(Producto, pid)
    if not p or p.status != "En ruta":
        raise HTTPException(400, "El producto debe estar En ruta")
    p.status, p.entregado = "Entregado", datetime.utcnow()
    db.commit()
    return prod_out(p)


@app.get("/api/rutas/ultima")
def ultima_ruta(db=Depends(get_db)):
    r = db.scalars(select(Ruta).order_by(Ruta.id.desc())).first()
    if not r:
        return None
    return {"id": r.id, "km": r.km, "minutos": r.minutos, "costo": r.costo, "retiros": r.retiros,
            "costo_por_retiro": r.costo / r.retiros, "ahorro_km": r.ahorro_km, "fuente": r.fuente,
            "geometria": r.geometria, "paradas": r.paradas}


@app.get("/api/indicadores")
def indicadores(db=Depends(get_db)):
    rutas = db.scalars(select(Ruta)).all()
    ent = db.scalars(select(Producto).where(Producto.status == "Entregado")).all()
    retiros = sum(r.retiros for r in rutas)
    horas = [(p.entregado - p.creado).total_seconds() / 3600 for p in ent if p.entregado]
    benef = {p.destino_id for p in ent}
    personas = sum(db.get(Place, b).personas for b in benef)
    return {"km_recorridos": round(sum(r.km for r in rutas), 1),
            "costo_por_retiro": round(sum(r.costo for r in rutas) / retiros) if retiros else 0,
            "tiempo_entrega_horas": round(sum(horas) / len(horas), 1) if horas else 0,
            "kg_recuperados": sum(p.kg for p in ent),
            "beneficiarios_org": len(benef), "beneficiarios_personas": personas,
            "costo_km": routing.COSTO_KM, "fijo_retiro": routing.FIJO_RETIRO}


app.include_router(chat.router) 


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    response.headers["Content-Security-Policy"] = (
        "default-src 'self' https://unpkg.com https://fonts.googleapis.com https://fonts.gstatic.com; "
        "style-src 'self' 'unsafe-inline' https://unpkg.com https://fonts.googleapis.com; "
        "script-src 'self' 'unsafe-inline' https://unpkg.com; "
        "img-src 'self' data: blob: https://*.openstreetmap.org https://tile.openstreetmap.org https://*.geoapify.com;"
        "connect-src 'self' https://*.geoapify.com;"
    )
    return response


# Archivos estáticos y ruta raíz
app.mount("/static", StaticFiles(directory=Path(__file__).resolve().parent / "../frontend/static"), name="static")

@app.get("/")
def read_index():
    return FileResponse(Path(__file__).resolve().parent / "../frontend/index.html")