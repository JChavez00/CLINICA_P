"""Bandeja persistente y outbox de correo HTTPS sin contenido clínico."""
import hashlib
import os
import secrets
from datetime import timedelta
from uuid import uuid4
import requests
from sqlalchemy import update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from models import db, Notificacion, ahora_utc
from .perfil import crear, obtener

TITULOS = {"reporte_generado":"Reporte disponible", "error_reporte":"No se pudo generar un reporte",
    "demanda_alta":"Pronóstico experimental de posible demanda ALTA", "resumen_mensual":"Resumen mensual disponible",
    "error_tarea":"Una tarea automática requiere revisión"}


def configurado():
    return bool(os.getenv("RESEND_API_KEY") and os.getenv("MAIL_FROM") and os.getenv("APP_PUBLIC_URL", "").startswith("https://"))


def enviar(destino, asunto, texto, identificador):
    if not configurado():
        return "pendiente_configuracion"
    try:
        r = requests.post("https://api.resend.com/emails", headers={"Authorization":"Bearer "+os.environ["RESEND_API_KEY"],
            "Idempotency-Key":identificador}, json={"from":os.environ["MAIL_FROM"], "to":[destino], "subject":asunto, "text":texto}, timeout=20)
        r.raise_for_status()
        return "aceptado_proveedor" if r.json().get("id") else "error_proveedor"
    except Exception:
        return "error_proveedor"


def verificar_correo(p):
    if not p.correo or not configurado():
        return "pendiente_configuracion"
    if p.verificacion_hasta and p.verificacion_hasta > ahora_utc()+timedelta(minutes=29):
        return "espera_un_minuto"
    token = secrets.token_urlsafe(32)
    p.verificacion_hash = hashlib.sha256(token.encode()).hexdigest()
    p.verificacion_hasta = ahora_utc()+timedelta(minutes=30)
    db.session.commit()
    enlace = os.environ["APP_PUBLIC_URL"].rstrip("/")+"/mi-perfil/verificar?token="+token
    return enviar(p.correo, "Verifica tu correo de CLINICA_P", "Confirma tu dirección iniciando sesión y abriendo este enlace (30 minutos):\n"+enlace, "verificar-"+str(uuid4()))


def registrar(evento, clave, tarea_id=None, informe_id=None):
    p = crear()
    insertar = {"sqlite":sqlite_insert,"postgresql":pg_insert}[db.engine.dialect.name]
    db.session.execute(insertar(Notificacion).values(id=str(uuid4()), propietario_id=p.id, clave=clave,
        evento=evento, tarea_id=tarea_id, informe_id=informe_id, leida=False, correo_estado="pendiente", correo_intentos=0)
        .on_conflict_do_nothing(index_elements=["clave"]))
    db.session.commit()


def procesar():
    p = obtener()
    if not p:
        return
    consulta = Notificacion.query.filter(Notificacion.correo_estado.notin_(["aceptado_proveedor", "agotado"])).order_by(Notificacion.creada_en)
    for n in consulta.limit(100).all():
        if not p.avisos or n.evento not in p.eventos:
            n.correo_estado = "desactivado"
        elif not p.verificado or not p.correo:
            n.correo_estado = "pendiente_verificacion"
        elif not configurado():
            n.correo_estado = "pendiente_configuracion"
        else:
            # Reclamo atómico y límite temporal igual a retención de idempotencia de Resend.
            if n.correo_intentos >= 3 or n.creada_en < ahora_utc()-timedelta(hours=23):
                n.correo_estado = "agotado"
                db.session.commit()
                continue
            if n.correo_reclamado and n.correo_reclamado > ahora_utc()-timedelta(minutes=5):
                continue
            reclamo = db.session.execute(update(Notificacion).where(Notificacion.id==n.id,
                Notificacion.correo_intentos==n.correo_intentos, Notificacion.correo_reclamado==n.correo_reclamado)
                .values(correo_intentos=n.correo_intentos+1, correo_reclamado=ahora_utc(), destinatario=n.destinatario or p.correo))
            db.session.commit()
            if reclamo.rowcount != 1:
                continue
            if n.destinatario != p.correo:
                n.correo_estado = "agotado"
            else:
                enlace = os.environ["APP_PUBLIC_URL"].rstrip("/")+"/notificaciones"
                n.correo_estado = enviar(n.destinatario, TITULOS[n.evento], "Hay una actualización administrativa en CLINICA_P. Inicia sesión para consultarla:\n"+enlace, "notificacion-"+n.id)
        db.session.commit()


def eventos_ejecucion(tarea, ejecucion):
    if ejecucion.estado == "error":
        evento = "error_reporte" if tarea.configuracion["tipo"] == "reporte" else "error_tarea"
        registrar(evento, ejecucion.id+":error", tarea.id)
        if evento=="error_reporte": registrar("error_tarea",ejecucion.id+":error_tarea",tarea.id)
        return
    r = ejecucion.resultado or {}
    if r.get("informe_id"):
        evento = "resumen_mensual" if tarea.configuracion["frecuencia"] == "mensual" else "reporte_generado"
        registrar(evento, ejecucion.id+":reporte", tarea.id, r["informe_id"])
    for alerta in r.get("alertas", []):
        # Una alerta por fecha y cuenta aunque varias tareas consulten el mismo pronóstico.
        registrar("demanda_alta", "alta:1:"+alerta["fecha"], tarea.id)
