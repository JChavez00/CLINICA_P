"""Auditoría técnica: sin mensajes, identificadores clínicos ni errores crudos."""
import os
from datetime import timedelta
from uuid import uuid4

from flask import current_app
from models import db, AgenteEjecucion, ahora_utc
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


def registrar(agente,modulo,herramienta,duracion,estado,error=None):
    ejecucion=AgenteEjecucion(id=str(uuid4()),agente=agente,modulo=modulo,herramienta=herramienta,
                             duracion_ms=int(duracion*1000),estado=estado,error_codigo=error)
    db.session.add(ejecucion); db.session.commit()
    return ejecucion.id
