"""Fechas UTC persistidas y horarios IANA por tarea, sin depender del navegador."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from models import db, TareaPerfil, EstadoProgramador, ahora_utc
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from .perfil import crear


def utc(valor):
    return (valor.replace(tzinfo=timezone.utc) if valor.tzinfo is None else valor).astimezone(timezone.utc)


def proxima(config, zona="America/Lima", despues=None):
    despues = utc(despues or ahora_utc())
    local = despues.astimezone(ZoneInfo(zona))
    for i in range(370):
        fecha = local.date() + timedelta(days=i)
        if config["frecuencia"] == "semanal" and fecha.weekday() != config["dia_semana"]:
            continue
        if config["frecuencia"] == "mensual" and fecha.day != config["dia_mes"]:
            continue
        candidato = datetime(fecha.year, fecha.month, fecha.day, config["hora"], tzinfo=ZoneInfo(zona)).astimezone(timezone.utc)
        if candidato.astimezone(ZoneInfo(zona)).hour != config["hora"]:
            continue  # Hora inexistente durante un cambio de horario estacional.
        if candidato > despues:
            return candidato.replace(tzinfo=None)
    raise ValueError("Programación inválida")


def asociar(tarea, zona=None, nombre=None, ahora=None):
    meta = db.session.get(TareaPerfil, tarea.id)
    if meta:
        return meta
    p = crear()
    meta = TareaPerfil(tarea_id=tarea.id, propietario_id=p.id,
        nombre=nombre or {"reporte":"Reporte administrativo", "estadisticas":"Resumen de estadísticas",
        "alerta_alta":"Alerta de posible demanda ALTA", "consulta_ml":"Consulta ML"}[tarea.configuracion["tipo"]],
        zona=zona or p.zona)
    # Tareas anteriores: primera ocurrencia desde su creación, admite recuperación.
    meta.proxima = proxima(tarea.configuracion, meta.zona, ahora or tarea.creada_en - timedelta(seconds=1))
    insertar={"sqlite":sqlite_insert,"postgresql":pg_insert}[db.engine.dialect.name]
    db.session.execute(insertar(TareaPerfil).values(tarea_id=meta.tarea_id,propietario_id=meta.propietario_id,
        nombre=meta.nombre,zona=meta.zona,proxima=meta.proxima).on_conflict_do_nothing(index_elements=["tarea_id"]))
    return db.session.get(TareaPerfil,tarea.id)


def estado():
    filas = EstadoProgramador.query.all()
    externo = next((e for e in filas if e.origen == "render_cron"), None)
    reciente = bool(externo and externo.revisado_en > ahora_utc() - timedelta(minutes=20))
    return {"evidencia_cron_reciente": reciente,
        "mensaje": "Hay evidencia reciente del cron de Render." if reciente else "Sin evidencia reciente del cron de Render. Una ejecución manual no acredita automatización activa.",
        "revisiones": [{"origen":e.origen,"fecha":e.revisado_en.isoformat()+"Z", "estado":e.estado,
                        "ultima_tarea":e.ultima_tarea_en.isoformat()+"Z" if e.ultima_tarea_en else None} for e in filas]}
