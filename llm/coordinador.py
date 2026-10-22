"""Enrutamiento por módulo y capacidades; el chat sólo admite dos agentes."""
from flask import session

from .base import ConsultorClinico, AnalistaInteligente, GeneradorReportes, AutomatizadorTareas, ControlCalidad
from .esquemas import ErrorAgente
from .privacidad import clasificar_chat

AGENTES={"consultor":ConsultorClinico(),"analista":AnalistaInteligente(),
         "reportes":GeneradorReportes(),"tareas":AutomatizadorTareas(),"calidad":ControlCalidad()}
MODULOS={"chat":{"consultor","analista"},"reportes":{"reportes"},"tareas":{"tareas"},"calidad":{"calidad"}}


def coordinar(modulo,agente,solicitud,contexto=None):
    if agente not in MODULOS.get(modulo,set()): raise ErrorAgente("agente_fuera_de_modulo",403)
    return AGENTES[agente].ejecutar(solicitud,contexto,modulo)


def ejecutar_agentes(pregunta,resumen=None,seleccion=None):
    # resumen legado no se transmite: podría contener texto clínico libre.
    if seleccion is not None:
        if type(seleccion) is not int or seleccion not in session.get("ia_candidatos",[]):
            raise ErrorAgente("seleccion_paciente_no_autorizada",403)
        session["ia_paciente"]=seleccion; session.pop("ia_candidatos",None)
        solicitud={"agente":"consultor","herramienta":"historial_paciente","argumentos":{"limite":20},
                   "seguro":{"intencion":"historial","contexto_seleccionado":True},"privado":{"usar_contexto":True}}
    else:
        solicitud=clasificar_chat(pregunta,bool(session.get("ia_paciente")))
    if solicitud is None:
        return {"respuesta":"Puedo buscar fichas por DNI o nombre, consultar estadísticas por fechas y revisar pronósticos ML existentes. Precisa una de esas consultas. El texto libre no se envía a proveedores.",
                "agente":"coordinador","origen":"local","estado":"orientacion"}
    privado=solicitud.get("privado",{})
    if privado.get("referencia"):
        session.pop("ia_paciente",None); session.pop("ia_candidatos",None)
    privado["seleccionado"]=session.get("ia_paciente") if privado.get("usar_contexto") else None
    r=coordinar("chat",solicitud["agente"],solicitud,privado)
    datos=r["datos"]
    if datos.get("opciones"): session["ia_candidatos"]=[p["id"] for p in datos["opciones"]]
    if datos.get("seleccionado"): session["ia_paciente"]=datos["seleccionado"]
    r["opciones"]=datos.get("opciones",[])
    r["origen"]="base_local" if solicitud["agente"]=="consultor" else "estadisticas_agregadas"
    return r
