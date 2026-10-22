"""La única cuenta existente; migración de credencial después de validarla."""
import hmac
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from flask import current_app
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from models import db, Perfil
from config import Config

EVENTOS = ("reporte_generado", "error_reporte", "demanda_alta", "resumen_mensual", "error_tarea")


def obtener():
    return db.session.get(Perfil, 1)


def crear():
    p = obtener()
    if p:
        return p
    insertar = {"sqlite": sqlite_insert, "postgresql": pg_insert}[db.engine.dialect.name]
    db.session.execute(insertar(Perfil).values(id=1, usuario=current_app.config.get("APP_USERNAME",Config.APP_USERNAME),
        nombre="Médico / administrador", clave_hash=generate_password_hash(current_app.config.get("APP_PASSWORD",Config.APP_PASSWORD)),
        rol="Médico / administrador", zona="America/Lima", correo="", verificado=False,
        avisos=False, eventos=list(EVENTOS), sesion_version=1).on_conflict_do_nothing(index_elements=["id"]))
    db.session.commit()
    return obtener()


def autenticar(usuario, clave):
    p = obtener()
    if p:
        return p if hmac.compare_digest(usuario.encode(), p.usuario.encode()) and check_password_hash(p.clave_hash, clave) else None
    if (hmac.compare_digest(usuario.encode(), current_app.config["APP_USERNAME"].encode())
            and hmac.compare_digest(clave.encode(), current_app.config["APP_PASSWORD"].encode())):
        return crear()
    return None


def correo_valido(valor):
    if not isinstance(valor, str) or len(valor) > 254 or not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+", valor):
        raise ValueError("Correo inválido")
    local, dominio = valor.rsplit("@", 1)
    if len(local) > 64 or local.startswith(".") or local.endswith(".") or ".." in local:
        raise ValueError("Correo inválido")
    return local + "@" + dominio.lower()


def zona_valida(valor):
    try:
        ZoneInfo(valor)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        raise ValueError("Zona horaria inválida") from None
    return valor


def actualizar(p, datos):
    nombre = datos.get("nombre", "").strip()
    if not nombre or len(nombre) > 160:
        raise ValueError("Nombre inválido")
    correo = correo_valido(datos["correo"].strip()) if datos.get("correo", "").strip() else ""
    zona = zona_valida(datos.get("zona", "America/Lima"))
    eventos = datos.get("eventos", [])
    if not isinstance(eventos, list) or any(e not in EVENTOS for e in eventos) or type(datos.get("avisos")) is not bool:
        raise ValueError("Preferencias inválidas")
    if correo != p.correo:
        p.verificado = False
        p.verificacion_hash = None
        p.verificacion_hasta = None
    p.nombre, p.correo, p.zona, p.eventos, p.avisos = nombre, correo, zona, eventos, datos["avisos"]
    db.session.commit()


def cambiar_clave(p, actual, nueva):
    if not isinstance(actual, str) or not check_password_hash(p.clave_hash, actual):
        raise ValueError("La contraseña actual es incorrecta")
    if not isinstance(nueva, str) or not 12 <= len(nueva) <= 128:
        raise ValueError("Usa una contraseña de 12 a 128 caracteres")
    p.clave_hash = generate_password_hash(nueva)
    p.sesion_version += 1
    db.session.commit()
