import os
from datetime import date, datetime
from sqlalchemy import JSON, ForeignKey, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./remarket.db")
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Place(Base):
    """Base logística, donante o beneficiario, con coordenadas."""
    __tablename__ = "places"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str]
    tipo: Mapped[str]  # base | donante | beneficiario
    lat: Mapped[float]
    lng: Mapped[float]
    direccion: Mapped[str] = mapped_column(default="")
    personas: Mapped[int] = mapped_column(default=0)
    capacidad_kg: Mapped[float] = mapped_column(default=0)
    frio: Mapped[bool] = mapped_column(default=False)
    necesidades: Mapped[list] = mapped_column(JSON, default=list)


class Producto(Base):
    __tablename__ = "productos"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str]
    categoria: Mapped[str]
    kg: Mapped[float]
    estado: Mapped[str]
    vence: Mapped[date | None] = mapped_column(default=None)
    donante_id: Mapped[int] = mapped_column(ForeignKey("places.id"))
    destino_id: Mapped[int | None] = mapped_column(ForeignKey("places.id"), default=None)
    status: Mapped[str] = mapped_column(default="Disponible")  # Disponible|Asignado|En ruta|Entregado
    ruta_id: Mapped[int | None] = mapped_column(default=None)
    creado: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    entregado: Mapped[datetime | None] = mapped_column(default=None)


class Ruta(Base):
    __tablename__ = "rutas"
    id: Mapped[int] = mapped_column(primary_key=True)
    creada: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    km: Mapped[float]
    minutos: Mapped[float]
    costo: Mapped[float]
    retiros: Mapped[int]
    ahorro_km: Mapped[float] = mapped_column(default=0)
    fuente: Mapped[str] = mapped_column(default="osrm")
    geometria: Mapped[dict] = mapped_column(JSON)
    paradas: Mapped[list] = mapped_column(JSON)
