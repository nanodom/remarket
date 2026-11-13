"""Autenticación contra las tablas `usuario`, `rol` y `empleado`.

- Contraseñas: scrypt (stdlib), guardadas como  scrypt$<sal_hex>$<hash_hex>  en `contrasena_hash`.
- Sesión: token firmado con HMAC-SHA256 (sin dependencias extra), con vencimiento.
- Crear un usuario:  python -m app.auth admin
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select

from .models import Empleado, Rol, SessionLocal, Usuario

SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    SECRET_KEY = secrets.token_hex(32)
    print("[!] SECRET_KEY no está definida: se generó una temporal y las sesiones se pierden al reiniciar.")
TOKEN_HORAS = int(os.getenv("TOKEN_HORAS", 8))

# "Admin" es el rol que crea el seeder SQL; "Administrador" se mantiene por compatibilidad.
ROLES_GESTION = ("Admin", "Administrador", "Operador Logistico")

_SCRYPT = dict(n=2**14, r=8, p=1, dklen=32)


def hash_password(password: str) -> str:
    sal = secrets.token_bytes(16)
    h = hashlib.scrypt(password.encode(), salt=sal, **_SCRYPT)
    return f"scrypt${sal.hex()}${h.hex()}"


def verificar_password(password: str, almacenado: str) -> bool:
    try:
        alg, sal, h = almacenado.split("$")
        if alg != "scrypt":
            return False
        calc = hashlib.scrypt(password.encode(), salt=bytes.fromhex(sal), **_SCRYPT)
        return hmac.compare_digest(calc.hex(), h)
    except Exception:
        return False


# Hash de relleno: el login tarda lo mismo exista o no el usuario.
HASH_FALSO = hash_password(secrets.token_hex(8))


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _firma(cuerpo: str) -> str:
    return _b64(hmac.new(SECRET_KEY.encode(), cuerpo.encode(), hashlib.sha256).digest())


def crear_token(uid: str, usuario: str, roles: list[str]) -> str:
    datos = {"sub": uid, "usr": usuario, "roles": roles, "exp": int(time.time()) + TOKEN_HORAS * 3600}
    cuerpo = _b64(json.dumps(datos).encode())
    return f"{cuerpo}.{_firma(cuerpo)}"


def usuario_actual(request: Request) -> dict:
    """Dependencia de FastAPI: exige `Authorization: Bearer <token>` válido."""
    cab = request.headers.get("Authorization", "")
    if not cab.startswith("Bearer "):
        raise HTTPException(401, "Sesión requerida")
    try:
        cuerpo, firma = cab[7:].split(".")
        if not hmac.compare_digest(firma, _firma(cuerpo)):
            raise ValueError("firma")
        datos = json.loads(_unb64(cuerpo))
        if datos["exp"] < time.time():
            raise ValueError("vencido")
        return datos
    except Exception:
        raise HTTPException(401, "Sesión inválida o expirada")


def requiere_rol(*permitidos):
    def dep(u: dict = Depends(usuario_actual)):
        if not set(u.get("roles", [])) & set(permitidos):
            raise HTTPException(403, "No tienes permisos para esta acción")
        return u
    return dep


def crear_usuario(db, username: str, password: str, nombre: str = "Admin",
                  apellido: str = "ReMarket", correo: str | None = None, rol: str = "Admin"):
    r = db.scalars(select(Rol).where(Rol.nombre_rol == rol)).first()
    if not r:
        r = Rol(nombre_rol=rol, descripcion=f"Rol {rol}")
        db.add(r)
    emp = Empleado(nombre=nombre, apellido=apellido, correo_electronico=correo or f"{username}@remarket.local")
    db.add(emp)
    db.flush()
    u = Usuario(empleado_id=emp.id, nombre_usuario=username,
                contrasena_hash=hash_password(password), roles=[r])
    db.add(u)
    db.commit()
    return u


def asegurar_admin(db):
    """Si no hay usuarios y existe ADMIN_PASSWORD, crea el primer administrador."""
    pw = os.getenv("ADMIN_PASSWORD")
    if pw and not db.scalars(select(Usuario)).first():
        crear_usuario(db, os.getenv("ADMIN_USER", "admin"), pw)
        print("[i] Usuario administrador inicial creado.")


if __name__ == "__main__":
    import getpass
    import sys
    nombre_usuario = sys.argv[1] if len(sys.argv) > 1 else input("Usuario: ")
    with SessionLocal() as sesion:
        crear_usuario(sesion, nombre_usuario, getpass.getpass("Contraseña: "))
    print("Usuario creado.")