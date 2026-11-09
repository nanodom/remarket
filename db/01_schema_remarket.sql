-- ReMarket · esquema PostgreSQL (idempotente).
-- Sirve para una BD nueva (docker-entrypoint-initdb.d) y para migrar la que ya tienes:
--   psql -U remarket -d remarket -f db/01_schema_remarket.sql
-- No borra ni renombra nada. Solo crea lo que falta.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============ Esquema original ============
CREATE TABLE IF NOT EXISTS cargo (
    uuid_cargo UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre_cargo VARCHAR(100) NOT NULL,
    descripcion TEXT
);

CREATE TABLE IF NOT EXISTS rol (
    uuid_rol UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre_rol VARCHAR(50) NOT NULL,
    descripcion TEXT
);

CREATE TABLE IF NOT EXISTS permiso (
    uuid_permiso UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    modulo VARCHAR(50) NOT NULL,
    descripcion TEXT
);

CREATE TABLE IF NOT EXISTS lugar (
    uuid_lugar UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre VARCHAR(100) NOT NULL,
    direccion VARCHAR(255),
    latitod NUMERIC(10, 8),      -- (sic) nombre original; el modelo ORM lo mapea tal cual
    longitud NUMERIC(11, 8),
    cuenta_con_frio BOOLEAN,
    capacidad_recepcion INT
);

CREATE TABLE IF NOT EXISTS producto (
    uuid_producto UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre VARCHAR(100) NOT NULL,
    categoria VARCHAR(50),
    peso_kg NUMERIC(8, 2),
    fecha_vencimiento DATE,
    status_logistico VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS ruta (
    uuid_ruta UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    distancia_km NUMERIC(8, 2),
    tiempo_minutos INT,
    cantidad_retiros INT
);

CREATE TABLE IF NOT EXISTS empleado (
    uuid_empleado UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uuid_cargo UUID REFERENCES cargo(uuid_cargo) ON DELETE SET NULL,
    nombre VARCHAR(100) NOT NULL,
    apellido VARCHAR(100) NOT NULL,
    correo_electronico VARCHAR(150) UNIQUE NOT NULL,
    telefono VARCHAR(30)
);

CREATE TABLE IF NOT EXISTS usuario (
    uuid_usuario UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uuid_empleado UUID UNIQUE REFERENCES empleado(uuid_empleado) ON DELETE CASCADE,
    nombre_usuario VARCHAR(50) UNIQUE NOT NULL,
    contrasena_hash VARCHAR(255) NOT NULL,
    estado_activo BOOLEAN DEFAULT TRUE,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS usuario_rol (
    uuid_usuario UUID REFERENCES usuario(uuid_usuario) ON DELETE CASCADE,
    uuid_rol UUID REFERENCES rol(uuid_rol) ON DELETE CASCADE,
    PRIMARY KEY (uuid_usuario, uuid_rol)
);

CREATE TABLE IF NOT EXISTS rol_permiso (
    uuid_rol UUID REFERENCES rol(uuid_rol) ON DELETE CASCADE,
    uuid_permiso UUID REFERENCES permiso(uuid_permiso) ON DELETE CASCADE,
    PRIMARY KEY (uuid_rol, uuid_permiso)
);

-- ============ Ampliación que necesita la aplicación ============

-- lugar: tipo de actor, personas atendidas y categorías que necesita
ALTER TABLE lugar
    ADD COLUMN IF NOT EXISTS tipo VARCHAR(20) NOT NULL DEFAULT 'donante',
    ADD COLUMN IF NOT EXISTS personas INT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS necesidades JSONB NOT NULL DEFAULT '[]'::jsonb;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'lugar_tipo_chk') THEN
        ALTER TABLE lugar ADD CONSTRAINT lugar_tipo_chk
            CHECK (tipo IN ('base', 'donante', 'beneficiario'));
    END IF;
END $$;

-- ruta: costo, ahorro, origen del cálculo, geometría y paradas
ALTER TABLE ruta
    ADD COLUMN IF NOT EXISTS creada TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ADD COLUMN IF NOT EXISTS costo NUMERIC(12, 2) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS ahorro_km NUMERIC(8, 2) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS fuente VARCHAR(20) NOT NULL DEFAULT 'osrm',
    ADD COLUMN IF NOT EXISTS geometria JSONB,
    ADD COLUMN IF NOT EXISTS paradas JSONB;

-- producto: condición, donante, destino, ruta y fechas de seguimiento
ALTER TABLE producto
    ADD COLUMN IF NOT EXISTS estado VARCHAR(30) NOT NULL DEFAULT 'Bueno',
    ADD COLUMN IF NOT EXISTS uuid_donante UUID REFERENCES lugar(uuid_lugar) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS uuid_destino UUID REFERENCES lugar(uuid_lugar) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS uuid_ruta UUID REFERENCES ruta(uuid_ruta) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS creado TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ADD COLUMN IF NOT EXISTS entregado TIMESTAMP;

-- Estados que usa la app: Disponible | Asignado | En ruta | Entregado
ALTER TABLE producto ALTER COLUMN status_logistico SET DEFAULT 'Disponible';
UPDATE producto SET status_logistico = 'Disponible' WHERE status_logistico IS NULL;

CREATE INDEX IF NOT EXISTS idx_producto_status ON producto(status_logistico);
CREATE INDEX IF NOT EXISTS idx_producto_ruta ON producto(uuid_ruta);
CREATE INDEX IF NOT EXISTS idx_ruta_creada ON ruta(creada DESC);

-- IMPORTANTE si ya tenías filas en `lugar`: todas quedaron como 'donante'.
-- Ajusta la base y los beneficiarios, por ejemplo:
--   UPDATE lugar SET tipo = 'base' WHERE nombre = 'Centro de acopio';
--   UPDATE lugar SET tipo = 'beneficiario' WHERE nombre IN ('...');
