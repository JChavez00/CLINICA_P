"""Herramientas de sólo lectura; agregados con claves cerradas hacia los LLM."""
from datetime import date
from collections import Counter, defaultdict

from sqlalchemy import func, or_

from models import db, Atencion, Paciente
from .consultas import buscar_pacientes, formatear_paciente, _normalizar
from .esquemas import ErrorAgente


def estadisticas_periodo(ctx, args):
    a,b=date.fromisoformat(args["desde"]),date.fromisoformat(args["hasta"])
    filtro=(Atencion.fecha>=a,Atencion.fecha<=b)
    total=db.session.query(func.count(Atencion.id)).filter(*filtro).scalar() or 0
    pacientes=db.session.query(func.count(func.distinct(Atencion.paciente_id))).filter(*filtro).scalar() or 0
    dias=db.session.query(Atencion.fecha,func.count(Atencion.id)).filter(*filtro).group_by(Atencion.fecha).order_by(Atencion.fecha).all()
    meses=Counter()
    for f,n in dias: meses[f.strftime("%Y-%m")]+=n
    return {"desde":args["desde"],"hasta":args["hasta"],"total_atenciones":total,"pacientes_unicos":pacientes,
            "por_dia":[{"fecha":f.isoformat(),"cantidad":n} for f,n in dias],
            "por_mes":[{"mes":m,"cantidad":n} for m,n in sorted(meses.items())],
            "advertencia":"Sin registro no equivale a cero atenciones confirmadas."}


def comparar_periodos(ctx,args):
    actual=estadisticas_periodo(ctx,args)
    previo=estadisticas_periodo(ctx,{"desde":args["desde_anterior"],"hasta":args["hasta_anterior"]})
    return {"actual":actual,"anterior":previo,"diferencia":actual["total_atenciones"]-previo["total_atenciones"]}


def campos_no_disponibles(ctx,args):
    return {"disponible":False,"campos_ausentes":["servicios","medico_responsable","costos","ingresos"],
            "mensaje":"El esquema actual no registra servicios, médicos responsables ni costos. No se inventan ni se deducen a partir del motivo clínico."}


def consultar_pronosticos_ml(ctx,args):
    from ml.artefactos import metadatos
    from ml.pronosticos import consultar
    from ml.presentacion import metadatos_para_presentacion
    try:
        meta=metadatos_para_presentacion(metadatos())
        dias=consultar(args["inicio"],args["dias"])
    except (FileNotFoundError,ValueError):
        return {"disponible":False,"mensaje":"No hay un paquete ML compatible disponible. No se inventan pronósticos."}
    # Sólo resultados y métricas existentes. Nunca inferencia o entrenamiento.
    return {"disponible":True,"version":meta["version"],"experimental":True,
            "resultados":[{"fecha":d["fecha"],"nivel":d["nivel"],"cantidad":d["cantidad"],"real":d["total"],"tipo":d["tipo"]} for d in dias],
            "modelos":{o:{"ganador":r["ganador"],"prueba":r["prueba"],"referencia":r["referencia_prueba"],"mejora_demostrada":r["mejora_demostrada"]} for o,r in meta["resultados"].items()},
            "advertencias":meta["limitaciones"]}


def buscar_paciente(ctx,args):
    referencia=ctx.get("referencia")
    if not referencia:
        return historial_paciente(ctx,args)
    try: resultados=buscar_pacientes(referencia["tipo"],referencia["valor"])
    except RuntimeError: raise ErrorAgente("busqueda_supera_limite_5000",400) from None
    if len(resultados)>8:
        return {"respuesta":"Hay más de ocho coincidencias. Precisa el nombre o DNI.","opciones":[]}
    if not resultados:
        return {"respuesta":"No encontré pacientes que coincidan con la búsqueda.","opciones":[]}
    if len(resultados)>1:
        return {"respuesta":"Selecciona un paciente para consultar sus atenciones.",
                "opciones":[{"id":p.id,"nombre":p.nombre_completo} for p in resultados]}
    return ficha(resultados[0],args["limite"])


def ficha(paciente,limite):
    # La ficha se entrega directamente al navegador autenticado, jamás al LLM.
    return {"respuesta":formatear_paciente(paciente),"seleccionado":paciente.id,"opciones":[],
            "campos_no_disponibles":["servicios","medico_responsable","costos"]}


def historial_paciente(ctx,args):
    identificador=ctx.get("seleccionado")
    if not identificador:
        return {"respuesta":"Indica un DNI o un nombre para seleccionar primero al paciente.","opciones":[]}
    paciente=db.session.get(Paciente,identificador)
    if not paciente:
        return {"respuesta":"El paciente seleccionado ya no está disponible.","opciones":[]}
    return ficha(paciente,args["limite"])


def analizar_calidad(ctx,args):
    """Sin alterar registros; incidencias locales y resumen sin identificadores."""
    filtro=or_(Atencion.fecha.between(date.fromisoformat(args["desde"]),date.fromisoformat(args["hasta"])),Atencion.fecha.is_(None))
    # Límites explícitos, sin resultados parciales presentados como revisión completa.
    if Paciente.query.count()>5000 or Atencion.query.filter(filtro).count()>5000:
        raise ErrorAgente("calidad_supera_limite_5000",400)
    pacientes=Paciente.query.order_by(Paciente.id).all()
    atenciones=Atencion.query.filter(filtro).order_by(Atencion.id).all()
    incidencias=[]; incompletos=set(); grupos=defaultdict(list)
    def registrar(entidad,identificador,categoria):
        incompletos.add((entidad,identificador))
        incidencias.append({"entidad":entidad,"id":identificador,"categoria":categoria,"requiere_revision":True})
    for p in pacientes:
        if not all(str(v or "").strip() for v in [p.dni,p.nombres,p.apellidos]): registrar("paciente",p.id,"campos_obligatorios")
        if not p.dni or not p.dni.isdigit() or len(p.dni) not in (8,9): registrar("paciente",p.id,"dni_formato")
        if p.fecha_nacimiento:
            from datetime import datetime
            f=None
            for formato in ("%Y-%m-%d","%d/%m/%Y"):
                try: f=datetime.strptime(p.fecha_nacimiento,formato).date(); break
                except ValueError: pass
            from ml.datos import hoy_peru
            if not f or f>hoy_peru(): registrar("paciente",p.id,"fecha_nacimiento")
        clave=(_normalizar(p.nombres),_normalizar(p.apellidos),str(p.fecha_nacimiento or ""))
        if clave[0] and clave[1]: grupos[clave].append(p.id)
    duplicados=0
    for ids in grupos.values():
        if len(ids)>1:
            duplicados+=len(ids)
            for identificador in ids: registrar("paciente",identificador,"posible_duplicado")
    from ml.datos import hoy_peru
    for a in atenciones:
        if not a.fecha or not a.paciente_id or not str(a.motivo or "").strip(): registrar("atencion",a.id,"atencion_incompleta")
        if a.estado not in ("Finalizado","En proceso"): registrar("atencion",a.id,"estado_invalido")
        if a.fecha and a.fecha>hoy_peru(): registrar("atencion",a.id,"fecha_futura")
    total=len(pacientes)+len(atenciones)
    agregado={"desde":args["desde"],"hasta":args["hasta"],"total":total,"pacientes_evaluados":len(pacientes),"atenciones_evaluadas":len(atenciones),
              "completos":total-len(incompletos),"incompletos":len(incompletos),"posibles_duplicados":duplicados,
              "categorias":dict(Counter(i["categoria"] for i in incidencias)),"incidencias":len(incidencias),
              "alcance":"Pacientes: padrón completo (no hay fecha de actualización). Atenciones: rango seleccionado y registros sin fecha, cuya pertenencia al período es desconocida.",
              "atenciones_fecha_nula":Atencion.query.filter(Atencion.fecha.is_(None)).count(),
              "costos":"No evaluables: campo inexistente.","duplicados":"Sospechas por nombre normalizado y fecha de nacimiento; requieren revisión humana."}
    return {"agregado":agregado,"incidencias_locales":incidencias[:200],"incidencias_truncadas":len(incidencias)>200}
