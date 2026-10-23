"""Auditoría técnica: sin mensajes, identificadores clínicos ni errores crudos."""
import os
import logging
from datetime import timedelta
from uuid import uuid4

from flask import current_app
from models import db, AgenteEjecucion, AgenteRecorrido, ahora_utc
from .esquemas import ErrorAgente


def permiso(capacidad):
    permitidos=current_app.config.get("AGENTES_PERMISOS")
    if permitidos is None:
        permitidos=os.getenv("AGENTES_PERMISOS","pacientes,estadisticas,reportes,tareas,calidad,auditoria").split(",")
    if capacidad not in permitidos:
        raise ErrorAgente("permiso_denegado",403)


def limite():
    maximo=max(1,min(100,int(os.getenv("AGENTES_POR_MINUTO","12"))))
    recientes=AgenteEjecucion.query.filter(AgenteEjecucion.fecha>=ahora_utc()-timedelta(minutes=1)).count()
    if recientes>=maximo: raise ErrorAgente("limite_de_consultas",429)


def registrar(agente,modulo,herramienta,duracion,estado,error=None,recorrido=None):
    ejecucion=AgenteEjecucion(id=str(uuid4()),agente=agente,modulo=modulo,herramienta=herramienta,
                             duracion_ms=max(round(duracion*1000), max((p['fin_ms'] for p in recorrido['pasos']), default=0) if recorrido else 0),estado=estado,error_codigo=error)
    db.session.add(ejecucion)
    if recorrido is not None:
        db.session.flush()
        db.session.add(AgenteRecorrido(ejecucion_id=ejecucion.id,
            flujo_id=recorrido.get("flujo_id") or ejecucion.id,
            padre_id=recorrido.get("padre_id"), proveedor=recorrido["proveedor"],
            modelo=recorrido["modelo"][:120], pasos=recorrido["pasos"]))
    db.session.commit()
    if error:
        # Gunicorn/Render recibe el código controlado, nunca prompts, fichas,
        # credenciales ni el texto de la excepción del proveedor.
        logging.getLogger("clinica.agentes").warning(
            "agente=%s modulo=%s herramienta=%s estado=%s error_codigo=%s ejecucion=%s",
            agente, modulo, herramienta, estado, error, ejecucion.id)
    return ejecucion.id
