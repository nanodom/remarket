-- ReMarket · Seeders de datos de prueba corregidos (idempotente)
-- Genera datos simulados coherentes para pruebas del sistema logístico.
-- Nota: La creación de usuarios se gestiona directamente desde el backend (scrypt) por seguridad.

BEGIN;

-- 1. CARGOS
INSERT INTO cargo (uuid_cargo, nombre_cargo, descripcion) VALUES
    ('11111111-1111-4111-a111-111111111111', 'Administrador Logístico', 'Gestión general de rutas, inventario y usuarios.'),
    ('11111111-1111-4111-a111-222222222222', 'Conductor / Transportista', 'Encargado del retiro y entrega de productos en ruta.'),
    ('11111111-1111-4111-a111-333333333333', 'Coordinador de Acopio', 'Recepción, clasificación y control de cadena de frío.')
ON CONFLICT (uuid_cargo) DO NOTHING;

-- 2. ROLES
INSERT INTO rol (uuid_rol, nombre_rol, descripcion) VALUES
    ('22222222-2222-4222-a222-111111111111', 'Admin', 'Acceso total al sistema y configuración.'),
    ('22222222-2222-4222-a222-222222222222', 'Operador Logistico', 'Gestión de rutas y despacho de donaciones.'),
    ('22222222-2222-4222-a222-333333333333', 'Auditor', 'Visualización de reportes e métricas de impacto.')
ON CONFLICT (uuid_rol) DO NOTHING;

-- 3. PERMISOS
INSERT INTO permiso (uuid_permiso, modulo, descripcion) VALUES
    ('33333333-3333-4333-a333-111111111111', 'RUTAS', 'Crear, optimizar y asignar rutas de transporte.'),
    ('33333333-3333-4333-a333-222222222222', 'INVENTARIO', 'Registrar y actualizar estado logístico de productos.'),
    ('33333333-3333-4333-a333-333333333333', 'LUGARES', 'Administrar puntos de donación y beneficiarios.'),
    ('33333333-3333-4333-a333-444444444444', 'USUARIOS', 'Gestión de credenciales y asignación de roles.')
ON CONFLICT (uuid_permiso) DO NOTHING;

-- 4. ROL PERMISO
INSERT INTO rol_permiso (uuid_rol, uuid_permiso) VALUES
    ('22222222-2222-4222-a222-111111111111', '33333333-3333-4333-a333-111111111111'),
    ('22222222-2222-4222-a222-111111111111', '33333333-3333-4333-a333-222222222222'),
    ('22222222-2222-4222-a222-111111111111', '33333333-3333-4333-a333-333333333333'),
    ('22222222-2222-4222-a222-111111111111', '33333333-3333-4333-a333-444444444444'),
    ('22222222-2222-4222-a222-222222222222', '33333333-3333-4333-a333-111111111111'),
    ('22222222-2222-4222-a222-222222222222', '33333333-3333-4333-a333-222222222222')
ON CONFLICT DO NOTHING;

-- 5. LUGARES (Base, Donantes y Beneficiarios)
INSERT INTO lugar (uuid_lugar, nombre, direccion, latitod, longitud, cuenta_con_frio, capacidad_recepcion, tipo, personas, necesidades) VALUES
    ('44444444-4444-4444-a444-111111111111', 'Centro Acopio Central', 'Av. Videla 450, Coquimbo', -29.95750000, -71.33940000, true, 5000, 'base', 0, '[]'::jsonb),
    ('44444444-4444-4444-a444-222222222222', 'Supermercado El Favorito', 'Balmaceda 2100, La Serena', -29.91250000, -71.25110000, true, 1200, 'donante', 0, '[]'::jsonb),
    ('44444444-4444-4444-a444-333333333333', 'Agrícola Valle Elqui', 'Ruta 41 Km 15, San Rafael', -29.98200000, -71.12000000, false, 3000, 'donante', 0, '[]'::jsonb),
    ('44444444-4444-4444-a444-444444444444', 'Comedor Social Esperanza', 'Calle Aldunate 890, Coquimbo', -29.95210000, -71.33650000, true, 450, 'beneficiario', 120, '["Lácteos", "Verduras", "Panadería"]'::jsonb),
    ('44444444-4444-4444-a444-555555555555', 'Hogar de Ancianos San Vicente', 'Las Compañías 340, La Serena', -29.89500000, -71.24000000, true, 300, 'beneficiario', 85, '["Abarrotes", "Frutas", "Lácteos"]'::jsonb)
ON CONFLICT (uuid_lugar) DO NOTHING;

-- 6. RUTAS (Con datos de geometría y paradas en JSONB para OSRM)
INSERT INTO ruta (uuid_ruta, distancia_km, tiempo_minutos, cantidad_retiros, costo, ahorro_km, fuente, geometria, paradas, creada) VALUES
    ('55555555-5555-4555-a555-111111111111', 24.50, 45, 2, 18500.00, 5.20, 'osrm', 
     '{"type": "LineString", "coordinates": [[-71.3394, -29.9575], [-71.2511, -29.9125], [-71.3365, -29.9521]]}'::jsonb, 
     '[{"orden": 1, "tipo": "donante", "nombre": "Supermercado El Favorito"}, {"orden": 2, "tipo": "beneficiario", "nombre": "Comedor Social Esperanza"}]'::jsonb, 
     NOW() - INTERVAL '1 day'),
    ('55555555-5555-4555-a555-222222222222', 48.00, 70, 1, 32000.00, 12.80, 'osrm', 
     '{"type": "LineString", "coordinates": [[-71.3394, -29.9575], [-71.1200, -29.9820], [-71.2400, -29.8950]]}'::jsonb, 
     '[{"orden": 1, "tipo": "donante", "nombre": "Agrícola Valle Elqui"}, {"orden": 2, "tipo": "beneficiario", "nombre": "Hogar de Ancianos San Vicente"}]'::jsonb, 
     NOW())
ON CONFLICT (uuid_ruta) DO NOTHING;

-- 7. EMPLEADOS
INSERT INTO empleado (uuid_empleado, uuid_cargo, nombre, apellido, correo_electronico, telefono) VALUES
    ('66666666-6666-4666-a666-111111111111', '11111111-1111-4111-a111-111111111111', 'Julia', 'Morales', 'julia.morales@remarket.cl', '+56912345678'),
    ('66666666-6666-4666-a666-222222222222', '11111111-1111-4111-a111-222222222222', 'Carlos', 'Tapia', 'carlos.tapia@remarket.cl', '+56987654321'),
    ('66666666-6666-4666-a666-333333333333', '11111111-1111-4111-a111-333333333333', 'Constanza', 'Ríos', 'constanza.rios@remarket.cl', '+56955554444')
ON CONFLICT (uuid_empleado) DO NOTHING;

-- 8. PRODUCTOS (Con estados logísticos, donantes, destinos y rutas asociadas)
INSERT INTO producto (uuid_producto, nombre, categoria, peso_kg, fecha_vencimiento, status_logistico, estado, uuid_donante, uuid_destino, uuid_ruta, creado, entregado) VALUES
    ('88888888-8888-4888-a888-111111111111', 'Yogurt Batido Frutilla 1L (Pack x12)', 'Lácteos', 12.50, CURRENT_DATE + INTERVAL '5 days', 'En ruta', 'Bueno', 
     '44444444-4444-4444-a444-222222222222', '44444444-4444-4444-a444-444444444444', '55555555-5555-4555-a555-111111111111', NOW() - INTERVAL '2 hours', NULL),
    
    ('88888888-8888-4888-a888-222222222222', 'Caja Tomates Selectos', 'Verduras', 20.00, CURRENT_DATE + INTERVAL '3 days', 'Entregado', 'Excelente', 
     '44444444-4444-4444-a444-333333333333', '44444444-4444-4444-a444-555555555555', '55555555-5555-4555-a555-222222222222', NOW() - INTERVAL '1 day', NOW() - INTERVAL '4 hours'),
    
    ('88888888-8888-4888-a888-333333333333', 'Sacos de Arroz 5kg (x10)', 'Abarrotes', 50.00, CURRENT_DATE + INTERVAL '180 days', 'Disponible', 'Bueno', 
     '44444444-4444-4444-a444-222222222222', NULL, NULL, NOW() - INTERVAL '5 hours', NULL),

    ('88888888-8888-4888-a888-444444444444', 'Queso Mantecoso 500g (Pack x20)', 'Lácteos', 10.00, CURRENT_DATE + INTERVAL '12 days', 'Asignado', 'Excelente', 
     '44444444-4444-4444-a444-222222222222', '44444444-4444-4444-a444-444444444444', NULL, NOW() - INTERVAL '1 hour', NULL)
ON CONFLICT (uuid_producto) DO NOTHING;

COMMIT;