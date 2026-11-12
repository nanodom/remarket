import os
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import inspect, select

from . import auth, chat, logic, routing
from datetime import date, time, timedelta
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.exc import IntegrityError
from .models import Base, Place, Producto, Ruta, SessionLocal, Usuario, Vehiculo, ahora, engine
from .security import verificar_ip_abuseipdb

NOMINATIM = os.getenv("NOMINATIM_URL", "https://nominatim.openstreetmap.org")
NOMINATIM_UA = os.getenv("NOMINATIM_UA", "ReMarket/2.0 (contacto@tudominio.cl)")

GESTION = auth.requiere_rol(*auth.ROLES_GESTION)

def get_db():
    with SessionLocal() as db:
        yield db


def verificar_esquema():
    """Falla con un mensaje claro si la BD existente no tiene las columnas que usa la app."""
    insp = inspect(engine)
    faltan = []
    for t in Base.metadata.sorted_tables:
        if insp.has_table(t.name):
            existentes = {c["name"] for c in insp.get_columns(t.name)}
            faltan += [f"{t.name}.{c.name}" for c in t.columns if c.name not in existentes]
    if faltan:
        raise RuntimeError(
            "La base de datos no tiene estas columnas: " + ", ".join(faltan)
            + ". Ejecuta db/01_schema_remarket.sql sobre tu base PostgreSQL."
        )


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
    Base.metadata.create_all(engine)  # crea solo tablas que no existan (no altera las existentes)
    verificar_esquema()
    with SessionLocal() as db:
        if os.getenv("SEED_DEMO", "1") == "1":
            seed(db)
        auth.asegurar_admin(db)
    yield


async def chequear_reputacion_ip(request: Request):
    """Dependencia de FastAPI para bloquear IPs reportadas en AbuseIPDB (se usa en el login)."""
    client_ip = request.client.host if request.client else ""

    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()

    if client_ip in ["127.0.0.1", "localhost", "::1", ""]:
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
# Todo lo que cuelga de `api` exige sesión válida.
api = APIRouter(prefix="/api", dependencies=[Depends(auth.usuario_actual)])


class LoginIn(BaseModel):
    username: str = Field(max_length=50)
    password: str = Field(max_length=200)


class PlaceIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    tipo: str = Field(pattern="^(donante|beneficiario|base)$")
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    direccion: str = Field(default="", max_length=255)
    personas: int = Field(default=0, ge=0)
    capacidad_kg: int = Field(default=0, ge=0)
    frio: bool = False
    necesidades: list[str] = []


class ProductoIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    categoria: str
    kg: float = Field(gt=0, lt=1_000_000)
    estado: str = Field(pattern="^(Bueno|Próximo a vencer|Regular)$")
    vence: date | None = None
    donante_id: UUID


def place_out(p):
    return {"id": str(p.id), "nombre": p.nombre, "tipo": p.tipo, "lat": p.lat, "lng": p.lng,
            "direccion": p.direccion or "", "personas": p.personas or 0,
            "capacidad_kg": p.capacidad_kg or 0, "frio": bool(p.frio),
            "necesidades": p.necesidades or []}


def prod_out(p):
    return {"id": str(p.id), "nombre": p.nombre, "categoria": p.categoria, "kg": float(p.kg or 0),
            "estado": p.estado, "dias": logic.dias(p), "puntaje": logic.score(p),
            "prioridad": logic.prioridad(p),
            "donante_id": str(p.donante_id) if p.donante_id else None,
            "destino_id": str(p.destino_id) if p.destino_id else None,
            "status": p.status or "Disponible"}


# ------------------------------------------------------------------ Autenticación

@app.post("/api/login", dependencies=[Depends(chequear_reputacion_ip)])
def login(d: LoginIn, db=Depends(get_db)):
    u = db.scalars(select(Usuario).where(Usuario.nombre_usuario == d.username)).first()
    ok = auth.verificar_password(d.password, u.contrasena_hash if u else auth.HASH_FALSO)
    if not (u and ok and u.estado_activo):
        raise HTTPException(401, "Credenciales inválidas o usuario no autorizado.")
    roles = [r.nombre_rol for r in u.roles]
    return {"token": auth.crear_token(str(u.id), u.nombre_usuario, roles),
            "usuario": u.nombre_usuario, "roles": roles}


# ------------------------------------------------------------------ Lugares

@api.get("/geocode")
async def geocode(q: str):
    """Dirección -> coordenadas (Nominatim)."""
    async with httpx.AsyncClient(timeout=10, headers={"User-Agent": NOMINATIM_UA}) as c:
        r = await c.get(f"{NOMINATIM}/search", params={"q": q, "format": "jsonv2", "countrycodes": "cl", "limit": 5})
    if r.status_code != 200:
        raise HTTPException(502, "Servicio de geocodificación no disponible")
    return [{"nombre": x["display_name"], "lat": float(x["lat"]), "lng": float(x["lon"])} for x in r.json()]


@api.get("/places")
def listar_places(db=Depends(get_db)):
    return [place_out(p) for p in db.scalars(select(Place).order_by(Place.nombre))]


@api.post("/places", status_code=201)
async def crear_place(d: PlaceIn, db=Depends(get_db)):
    lat, lng = d.lat, d.lng
    if lat is None or lng is None:
        if not d.direccion:
            raise HTTPException(422, "Indica coordenadas o una dirección")
        res = await geocode(d.direccion)
        if not res:
            raise HTTPException(422, "No se encontró la dirección")
        lat, lng = res[0]["lat"], res[0]["lng"]
    for c in d.necesidades:
        if c not in logic.CATEGORIAS:
            raise HTTPException(422, f"Categoría no válida: {c}")
    p = Place(**{**d.model_dump(), "lat": lat, "lng": lng})
    db.add(p)
    db.commit()
    return place_out(p)


# ------------------------------------------------------------------ Productos

@api.get("/productos")
def listar_productos(db=Depends(get_db)):
    return sorted((prod_out(p) for p in db.scalars(select(Producto))), key=lambda x: -x["puntaje"])


@api.post("/productos", status_code=201)
def crear_producto(d: ProductoIn, db=Depends(get_db)):
    if d.categoria not in logic.CATEGORIAS:
        raise HTTPException(422, "Categoría no válida")
    if d.vence and d.vence <= date.today():
        raise HTTPException(422, "Producto vencido: no apto para distribución")
    donante = db.get(Place, d.donante_id)
    if not donante or donante.tipo != "donante":
        raise HTTPException(422, "Donante no válido")
    p = Producto(**d.model_dump(), status="Disponible")
    db.add(p)
    db.commit()
    return prod_out(p)


@api.post("/asignar")
def asignar(db=Depends(get_db)):
    ok, no = logic.asignar(db)
    return {"asignados": ok, "sin_destino": no}


@api.post("/productos/{pid}/entregar")
def entregar(pid: UUID, db=Depends(get_db)):
    p = db.get(Producto, pid)
    if not p or p.status != "En ruta":
        raise HTTPException(400, "El producto debe estar En ruta")
    p.status, p.entregado = "Entregado", ahora()
    db.commit()
    return prod_out(p)


# ------------------------------------------------------------------ Rutas

class VehiculoIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    patente: str | None = Field(default=None, max_length=20)
    capacidad_kg: int = Field(gt=0, le=50_000)
    tiene_frio: bool = False
    costo_km: float = Field(ge=0, le=100_000)
    costo_fijo: float = Field(default=0, ge=0, le=10_000_000)
    turno_inicio: time = time(8, 0)
    turno_fin: time = time(18, 0)
    activo: bool = True

    @model_validator(mode="after")
    def _turno(self):
        if self.turno_fin <= self.turno_inicio:
            raise ValueError("El fin del turno debe ser posterior al inicio")
        return self


def veh_out(v):
    return {"id": str(v.id), "nombre": v.nombre, "patente": v.patente or "",
            "capacidad_kg": v.capacidad_kg, "tiene_frio": bool(v.tiene_frio),
            "costo_km": float(v.costo_km or 0), "costo_fijo": float(v.costo_fijo or 0),
            "turno_inicio": v.turno_inicio.strftime("%H:%M"),
            "turno_fin": v.turno_fin.strftime("%H:%M"), "activo": bool(v.activo)}


def _datos_vehiculo(d: VehiculoIn) -> dict:
    datos = d.model_dump()
    datos["patente"] = (d.patente or "").strip().upper() or None
    return datos


def _commit_vehiculo(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Ya existe un vehículo con esa patente")


def _en_ruta(db, vid) -> bool:
    """¿Tiene productos En ruta asignados a una de sus rutas?"""
    return db.scalars(
        select(Producto.id).join(Ruta, Producto.ruta_id == Ruta.id)
        .where(Ruta.vehiculo_id == vid, Producto.status == "En ruta").limit(1)).first() is not None

@api.post("/rutas/planificar")
async def planificar(db=Depends(get_db)):
    items = db.scalars(select(Producto).where(
        Producto.status == "Asignado",
        Producto.donante_id.is_not(None),
        Producto.destino_id.is_not(None))).all()
    if not items:
        raise HTTPException(400, "No hay productos asignados para planificar")
    base = db.scalars(select(Place).where(Place.tipo == "base")).first()
    if not base:
        raise HTTPException(400, "Falta registrar la base logística")
    lug = {p.id: p for p in db.scalars(select(Place))}
    ids_d = sorted({p.donante_id for p in items}, key=str)
    ids_b = sorted({p.destino_id for p in items}, key=str)

    sin_coord = [lug[i].nombre for i in (base.id, *ids_d, *ids_b) if lug[i].lat is None or lug[i].lng is None]
    if sin_coord:
        raise HTTPException(400, "Lugares sin coordenadas: " + ", ".join(sin_coord))

    xy = lambda i: (lug[i].lat, lug[i].lng)
    r = await routing.planificar((base.lat, base.lng), [xy(i) for i in ids_d], [xy(i) for i in ids_b])

    def parada(tipo, i):
        return {"tipo": tipo, "id": str(i), "nombre": lug[i].nombre, "lat": lug[i].lat, "lng": lug[i].lng}

    # El camión sale y vuelve a la base: se muestra al inicio y al final del recorrido.
    inicio = parada("base", base.id)
    paradas = ([inicio]
               + [parada("retiro", ids_d[i]) for i in r["retiros"]]
               + [parada("entrega", ids_b[i]) for i in r["entregas"]]
               + [inicio])

    costo = r["km"] * routing.COSTO_KM + len(ids_d) * routing.FIJO_RETIRO
    ruta = Ruta(km=round(r["km"], 2), minutos=round(r["minutos"]), costo=round(costo, 2),
                retiros=len(ids_d), ahorro_km=round(r["ahorro_km"], 2), fuente=r["fuente"],
                geometria=r["geometria"], paradas=paradas)
    db.add(ruta)
    db.flush()
    for p in items:
        p.status, p.ruta_id = "En ruta", ruta.id
    db.commit()
    return {"id": str(ruta.id), "km": ruta.km, "minutos": ruta.minutos, "costo": ruta.costo,
            "costo_por_retiro": ruta.costo / len(ids_d), "ahorro_km": ruta.ahorro_km,
            "fuente": ruta.fuente, "geometria": ruta.geometria, "paradas": paradas}


@api.get("/rutas/ultima")
def ultima_ruta(db=Depends(get_db)):
    """Última ruta que todavía tiene productos En ruta; si ya se entregó todo, no hay ruta activa."""
    r = db.scalars(select(Ruta).order_by(Ruta.creada.desc())).first()
    if not r:
        return None
    activa = db.scalars(select(Producto.id).where(
        Producto.ruta_id == r.id, Producto.status == "En ruta").limit(1)).first()
    if activa is None:
        return None
    costo = r.costo or 0
    return {"id": str(r.id), "km": r.km or 0, "minutos": r.minutos or 0, "costo": costo,
            "retiros": r.retiros or 0, "costo_por_retiro": costo / r.retiros if r.retiros else 0,
            "ahorro_km": r.ahorro_km or 0, "fuente": r.fuente,
            "geometria": r.geometria, "paradas": r.paradas or []}


# ------------------------------------------------------------------ Indicadores

@api.get("/indicadores")
def indicadores(db=Depends(get_db)):
    rutas = db.scalars(select(Ruta)).all()
    ent = db.scalars(select(Producto).where(Producto.status == "Entregado")).all()
    retiros = sum(r.retiros or 0 for r in rutas)
    horas = [(p.entregado - p.creado).total_seconds() / 3600 for p in ent if p.entregado and p.creado]
    benef = {p.destino_id for p in ent if p.destino_id}
    personas = sum((db.get(Place, b).personas or 0) for b in benef if db.get(Place, b))
    return {"km_recorridos": round(sum(r.km or 0 for r in rutas), 1),
            "costo_por_retiro": round(sum(r.costo or 0 for r in rutas) / retiros) if retiros else 0,
            "tiempo_entrega_horas": round(sum(horas) / len(horas), 1) if horas else 0,
            "kg_recuperados": float(sum(p.kg or 0 for p in ent)),
            "beneficiarios_org": len(benef), "beneficiarios_personas": personas,
            "costo_km": routing.COSTO_KM, "fijo_retiro": routing.FIJO_RETIRO}


app.include_router(api)
app.include_router(chat.router, dependencies=[Depends(auth.usuario_actual)])


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

# ------------------------------------------------------------------ Flota

@api.get("/vehiculos")
def listar_vehiculos(db=Depends(get_db)):
    return [veh_out(v) for v in db.scalars(select(Vehiculo).order_by(Vehiculo.nombre))]


@api.post("/vehiculos", status_code=201, dependencies=[Depends(GESTION)])
def crear_vehiculo(d: VehiculoIn, db=Depends(get_db)):
    v = Vehiculo(**_datos_vehiculo(d))
    db.add(v)
    _commit_vehiculo(db)
    return veh_out(v)


@api.put("/vehiculos/{vid}", dependencies=[Depends(GESTION)])
def editar_vehiculo(vid: UUID, d: VehiculoIn, db=Depends(get_db)):
    v = db.get(Vehiculo, vid)
    if not v:
        raise HTTPException(404, "Vehículo no encontrado")
    if not d.activo and _en_ruta(db, vid):
        raise HTTPException(409, "No se puede desactivar: tiene productos En ruta")
    for k, val in _datos_vehiculo(d).items():
        setattr(v, k, val)
    _commit_vehiculo(db)
    return veh_out(v)


@api.delete("/vehiculos/{vid}", dependencies=[Depends(GESTION)])
def borrar_vehiculo(vid: UUID, db=Depends(get_db)):
    v = db.get(Vehiculo, vid)
    if not v:
        raise HTTPException(404, "Vehículo no encontrado")
    if _en_ruta(db, vid):
        raise HTTPException(409, "No se puede eliminar: tiene productos En ruta")
    if db.scalars(select(Ruta.id).where(Ruta.vehiculo_id == vid).limit(1)).first():
        # Tiene historial: se desactiva para no perder la trazabilidad de rutas e indicadores.
        v.activo = False
        db.commit()
        return {"mensaje": "Tiene rutas en el historial: se desactivó en lugar de eliminarse."}
    db.delete(v)
    db.commit()
    return {"mensaje": "Vehículo eliminado."}

# Archivos estáticos y ruta raíz
app.mount("/static", StaticFiles(directory=Path(__file__).resolve().parent / "../frontend/static"), name="static")

@app.get("/")
def read_index():
    return FileResponse(Path(__file__).resolve().parent / "../frontend/index.html")
