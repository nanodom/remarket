"""Modelos mapeados al esquema PostgreSQL de Remarket (tablas y columnas en español, PK UUID).

Los atributos de Python conservan los nombres que usa el resto del código
(Place.lat, Producto.kg, Ruta.km...) y `mapped_column("nombre_real", ...)` los enlaza
con la columna real de la base de datos.
"""
import os
import uuid
from datetime import date, datetime, timezone

from dotenv import load_dotenv
from sqlalchemy import (JSON, Boolean, Column, Date, DateTime, ForeignKey, Integer,
                        Numeric, String, Table, Text, Uuid, create_engine)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./remarket.db")
# Con PostgreSQL: postgresql+psycopg://usuario:clave@host:5432/remarket
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(engine, expire_on_commit=False)

JSONType = JSON().with_variant(JSONB(), "postgresql")


def num(precision: int, scale: int) -> Numeric:
    """NUMERIC que llega como float (no Decimal), para poder operar con km, kg y coordenadas."""
    return Numeric(precision, scale, asdecimal=False)


def ahora() -> datetime:
    """UTC sin zona horaria (las columnas son TIMESTAMP)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------- Logística

class Place(Base):
    """Base logística, donante o beneficiario (tabla `lugar`)."""
    __tablename__ = "lugar"
    id: Mapped[uuid.UUID] = mapped_column("uuid_lugar", Uuid, primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(100))
    tipo: Mapped[str] = mapped_column(String(20), default="donante")  # base | donante | beneficiario
    direccion: Mapped[str | None] = mapped_column(String(255), default="")
    lat: Mapped[float | None] = mapped_column("latitod", num(10, 8))
    lng: Mapped[float | None] = mapped_column("longitud", num(11, 8))
    frio: Mapped[bool | None] = mapped_column("cuenta_con_frio", Boolean, default=False)
    capacidad_kg: Mapped[int | None] = mapped_column("capacidad_recepcion", Integer, default=0)
    personas: Mapped[int] = mapped_column(Integer, default=0)
    necesidades: Mapped[list | None] = mapped_column(JSONType, default=list)


class Ruta(Base):
    __tablename__ = "ruta"
    id: Mapped[uuid.UUID] = mapped_column("uuid_ruta", Uuid, primary_key=True, default=uuid.uuid4)
    km: Mapped[float | None] = mapped_column("distancia_km", num(8, 2))
    minutos: Mapped[int | None] = mapped_column("tiempo_minutos", Integer)
    retiros: Mapped[int | None] = mapped_column("cantidad_retiros", Integer)
    creada: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    costo: Mapped[float] = mapped_column(num(12, 2), default=0)
    ahorro_km: Mapped[float] = mapped_column(num(8, 2), default=0)
    fuente: Mapped[str] = mapped_column(String(20), default="osrm")
    geometria: Mapped[dict | None] = mapped_column(JSONType)
    paradas: Mapped[list | None] = mapped_column(JSONType)


class Producto(Base):
    __tablename__ = "producto"
    id: Mapped[uuid.UUID] = mapped_column("uuid_producto", Uuid, primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(100))
    categoria: Mapped[str | None] = mapped_column(String(50))
    kg: Mapped[float | None] = mapped_column("peso_kg", num(8, 2))
    vence: Mapped[date | None] = mapped_column("fecha_vencimiento", Date)
    status: Mapped[str | None] = mapped_column("status_logistico", String(50), default="Disponible")
    # Disponible | Asignado | En ruta | Entregado
    estado: Mapped[str] = mapped_column(String(30), default="Bueno")  # Bueno | Próximo a vencer | Regular
    donante_id: Mapped[uuid.UUID | None] = mapped_column(
        "uuid_donante", Uuid, ForeignKey("lugar.uuid_lugar", ondelete="SET NULL"))
    destino_id: Mapped[uuid.UUID | None] = mapped_column(
        "uuid_destino", Uuid, ForeignKey("lugar.uuid_lugar", ondelete="SET NULL"))
    ruta_id: Mapped[uuid.UUID | None] = mapped_column(
        "uuid_ruta", Uuid, ForeignKey("ruta.uuid_ruta", ondelete="SET NULL"))
    creado: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    entregado: Mapped[datetime | None] = mapped_column(DateTime)


# ---------------------------------------------------- Usuarios y control de acceso

usuario_rol = Table(
    "usuario_rol", Base.metadata,
    Column("uuid_usuario", Uuid, ForeignKey("usuario.uuid_usuario", ondelete="CASCADE"), primary_key=True),
    Column("uuid_rol", Uuid, ForeignKey("rol.uuid_rol", ondelete="CASCADE"), primary_key=True),
)

rol_permiso = Table(
    "rol_permiso", Base.metadata,
    Column("uuid_rol", Uuid, ForeignKey("rol.uuid_rol", ondelete="CASCADE"), primary_key=True),
    Column("uuid_permiso", Uuid, ForeignKey("permiso.uuid_permiso", ondelete="CASCADE"), primary_key=True),
)


class Cargo(Base):
    __tablename__ = "cargo"
    id: Mapped[uuid.UUID] = mapped_column("uuid_cargo", Uuid, primary_key=True, default=uuid.uuid4)
    nombre_cargo: Mapped[str] = mapped_column(String(100))
    descripcion: Mapped[str | None] = mapped_column(Text)


class Empleado(Base):
    __tablename__ = "empleado"
    id: Mapped[uuid.UUID] = mapped_column("uuid_empleado", Uuid, primary_key=True, default=uuid.uuid4)
    cargo_id: Mapped[uuid.UUID | None] = mapped_column(
        "uuid_cargo", Uuid, ForeignKey("cargo.uuid_cargo", ondelete="SET NULL"))
    nombre: Mapped[str] = mapped_column(String(100))
    apellido: Mapped[str] = mapped_column(String(100))
    correo_electronico: Mapped[str] = mapped_column(String(150), unique=True)
    telefono: Mapped[str | None] = mapped_column(String(30))


class Rol(Base):
    __tablename__ = "rol"
    id: Mapped[uuid.UUID] = mapped_column("uuid_rol", Uuid, primary_key=True, default=uuid.uuid4)
    nombre_rol: Mapped[str] = mapped_column(String(50))
    descripcion: Mapped[str | None] = mapped_column(Text)
    permisos: Mapped[list["Permiso"]] = relationship(secondary=rol_permiso, lazy="selectin")


class Permiso(Base):
    __tablename__ = "permiso"
    id: Mapped[uuid.UUID] = mapped_column("uuid_permiso", Uuid, primary_key=True, default=uuid.uuid4)
    modulo: Mapped[str] = mapped_column(String(50))
    descripcion: Mapped[str | None] = mapped_column(Text)


class Usuario(Base):
    __tablename__ = "usuario"
    id: Mapped[uuid.UUID] = mapped_column("uuid_usuario", Uuid, primary_key=True, default=uuid.uuid4)
    empleado_id: Mapped[uuid.UUID | None] = mapped_column(
        "uuid_empleado", Uuid, ForeignKey("empleado.uuid_empleado", ondelete="CASCADE"), unique=True)
    nombre_usuario: Mapped[str] = mapped_column(String(50), unique=True)
    contrasena_hash: Mapped[str] = mapped_column(String(255))
    estado_activo: Mapped[bool | None] = mapped_column(Boolean, default=True)
    fecha_creacion: Mapped[datetime | None] = mapped_column(DateTime, default=ahora)
    roles: Mapped[list[Rol]] = relationship(secondary=usuario_rol, lazy="selectin")
