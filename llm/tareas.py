"""Cron externo con reclamo atómico, emisión por período y reintentos limitados."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4, uuid5, NAMESPACE_URL

from sqlalchemy import update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert

from models import db, TareaIA, TareaIAEjecucion, ahora_utc
from .esquemas import ConfiguracionTarea, ErrorAgente


def listar():
    from .programacion import asociar
    salida=[]
    for t in TareaIA.query.order_by(TareaIA.creada_en.desc()).limit(100).all():
        m=asociar(t)
        salida.append({"id":t.id,"configuracion":t.configuracion,"activa":t.activa,"confirmada":t.confirmada,
            "nombre":m.nombre,"propietario":m.propietario_id,"zona":m.zona,
            "proxima":m.proxima.isoformat()+"Z" if m.proxima and t.activa else None,
            "ultima":m.ultima.isoformat()+"Z" if m.ultima else None,"creada_en":t.creada_en.isoformat()+"Z"})
    db.session.commit()
    return salida


def confirmar(configuracion,identificador,zona=None,nombre=None):
    configuracion=ConfiguracionTarea.model_validate(configuracion).model_dump()
    existente=db.session.get(TareaIA,identificador)
    if existente: return existente
    if TareaIA.query.count()>=100: raise ErrorAgente("limite_de_tareas",400)
    t=TareaIA(id=identificador,configuracion=configuracion,confirmada=True,activa=True)
    db.session.add(t); db.session.commit()
    from .programacion import asociar
    asociar(t,zona,nombre); db.session.commit(); return t


def vencimiento(config,ahora):
    if ahora.hour<config["hora"]: return None
    if config["frecuencia"]=="semanal" and ahora.weekday()!=config["dia_semana"]: return None
    if config["frecuencia"]=="mensual" and ahora.day!=config["dia_mes"]: return None
    return ahora.date().isoformat()


def reclamar(tarea,periodo):
    motor=db.session.get_bind().dialect.name
    insertar={"sqlite":sqlite_insert,"postgresql":pg_insert}.get(motor)
    if not insertar: raise ErrorAgente("motor_no_compatible",503)
    identificador=str(uuid4())
    stmt=insertar(TareaIAEjecucion).values(id=identificador,tarea_id=tarea.id,periodo=periodo,estado="ejecutando",intentos=1)\
        .on_conflict_do_nothing(index_elements=["tarea_id","periodo"]).returning(TareaIAEjecucion.id)
    creado=db.session.execute(stmt).scalar_one_or_none(); db.session.commit()
    if creado: return db.session.get(TareaIAEjecucion,creado)
    previo=TareaIAEjecucion.query.filter_by(tarea_id=tarea.id,periodo=periodo).first()
    if previo.intentos>=3 or previo.estado in ("ok","degradado"): return None
    if previo.estado=="ejecutando" and previo.iniciada_en>ahora_utc()-timedelta(minutes=10): return None
    # Compare-and-swap: dos procesos no pueden reclamar el mismo reintento.
    stmt=update(TareaIAEjecucion).where(TareaIAEjecucion.id==previo.id,TareaIAEjecucion.intentos==previo.intentos,
        TareaIAEjecucion.iniciada_en==previo.iniciada_en).values(estado="ejecutando",intentos=previo.intentos+1,iniciada_en=ahora_utc())
    cambio=db.session.execute(stmt); db.session.commit()
    if cambio.rowcount==1:
        db.session.expire_all(); return db.session.get(TareaIAEjecucion,previo.id)
    return None


def ejecutar_una(tarea,fecha):
    from .herramientas import estadisticas_periodo, consultar_pronosticos_ml
    config=ConfiguracionTarea.model_validate(tarea.configuracion).model_dump()
    fin=fecha-timedelta(days=1)
    if config["frecuencia"]=="mensual":
        fin=fecha.replace(day=1)-timedelta(days=1); inicio=fin.replace(day=1)
    else: inicio=fin-timedelta(days=6 if config["frecuencia"]=="semanal" else 0)
    periodo={"desde":inicio.isoformat(),"hasta":fin.isoformat()}
    if config["tipo"]=="reporte":
        from .coordinador import coordinar
        from .reportes import guardar
        identificador=str(uuid5(NAMESPACE_URL,tarea.id+fecha.isoformat()))
        from models import InformeIA
        existente=db.session.get(InformeIA,identificador)
        if existente:
            from .almacenamiento import conservar
            conservar(existente,tarea.id)
            return {"informe_id":existente.id,"estado_ia":existente.contenido["estado"]}
        args={**periodo,"tipo":"rango","secciones":["atenciones"]}
        r=coordinar("reportes","reportes",{"herramienta":"construir_reporte","argumentos":args,"seguro":{"objetivo":"informe_programado"}})
        informe=guardar(r,identificador)
        from .almacenamiento import conservar
        conservar(informe,tarea.id)
        return {"informe_id":informe.id,"estado_ia":r["estado"]}
    if config["tipo"]=="estadisticas": return estadisticas_periodo({},periodo)
    ml=consultar_pronosticos_ml({},{"inicio":(fecha+timedelta(days=1)).isoformat(),"dias":7})
    if config["tipo"]=="alerta_alta":
        emisiones=[d for d in ml.get("resultados",[]) if d["tipo"]=="predicción"]
        return {"alertas":[d for d in emisiones if d["nivel"]=="ALTA"],"emisiones_evaluadas":len(emisiones),
                "canal":"panel","disponible":ml.get("disponible"),"experimental":True,
                "mensaje":"Aviso disponible en el panel. No se enviaron notificaciones externas."}
    return ml


def ejecutar_programadas(ahora=None,tarea_id=None,manual=False,origen="comando_manual"):
    from .auditoria import permiso, registrar
    from time import monotonic
    permiso("tareas")
    ahora=ahora or datetime.now(timezone(timedelta(hours=-5)))
    from zoneinfo import ZoneInfo
    from .programacion import asociar, proxima, utc
    from .notificaciones import eventos_ejecucion, procesar
    from models import EstadoProgramador
    instante=utc(ahora).replace(tzinfo=None)
    salida=[]; inicio_lote=monotonic()
    consulta=TareaIA.query.filter_by(activa=True,confirmada=True)
    if tarea_id: consulta=consulta.filter_by(id=tarea_id)
    for t in consulta.order_by(TareaIA.id).limit(100).all():
        config=ConfiguracionTarea.model_validate(t.configuracion).model_dump()
        meta=asociar(t); db.session.commit()
        local=utc(ahora).astimezone(ZoneInfo(meta.zona))
        # Una ocurrencia pendiente por revisión; conserva las omitidas para futuros ciclos.
        pendiente=meta.proxima
        fecha_programada=utc(pendiente).astimezone(ZoneInfo(meta.zona)).date() if pendiente else local.date()
        periodo=local.date().isoformat() if manual else (fecha_programada.isoformat() if pendiente and pendiente<=instante else None)
        if periodo is None: continue
        ejecucion=reclamar(t,periodo)
        if ejecucion is None:
            anterior=TareaIAEjecucion.query.filter_by(tarea_id=t.id,periodo=periodo).first()
            if not manual and anterior and (anterior.estado in ("ok","degradado") or (anterior.estado=="error" and anterior.intentos>=3)):
                # Recupera también una caída después del commit del resultado.
                eventos_ejecucion(t,anterior)
                meta.proxima=proxima(config,meta.zona,pendiente)
                db.session.commit()
            continue
        inicio=monotonic()
        intento=ejecucion.intentos
        ejecucion_id=ejecucion.id
        try:
            resultado=ejecutar_una(t,local.date() if manual else fecha_programada)
            estado_resultado="degradado" if resultado.get("estado_ia")=="degradado" else "ok"
            error_resultado=None
        except Exception as exc:
            db.session.rollback()
            resultado={}; estado_resultado="error"
            error_resultado=exc.codigo if isinstance(exc,ErrorAgente) else "ejecucion_fallida"
        cambio=db.session.execute(update(TareaIAEjecucion).where(TareaIAEjecucion.id==ejecucion_id,
            TareaIAEjecucion.intentos==intento,TareaIAEjecucion.estado=="ejecutando").values(
            resultado={**resultado,"duracion_ms":round((monotonic()-inicio)*1000)},
            estado=estado_resultado,error_codigo=error_resultado))
        db.session.commit()
        if cambio.rowcount!=1: continue  # Un proceso recuperado ya tiene el reclamo.
        db.session.expire_all(); ejecucion=db.session.get(TareaIAEjecucion,ejecucion_id)
        eventos_ejecucion(t,ejecucion)
        meta.ultima=instante
        if not manual and ejecucion.estado in ("ok","degradado"):
            meta.proxima=proxima(config,meta.zona,pendiente)
        db.session.commit()
        registrar("automatizador_tareas","manual" if manual else "cron",config["tipo"],monotonic()-inicio,ejecucion.estado,ejecucion.error_codigo)
        salida.append({"ejecucion":ejecucion.id,"estado":ejecucion.estado,"intentos":ejecucion.intentos})
    if not manual:
        hay_error=any(r["estado"]=="error" for r in salida)
        registrar("automatizador_tareas","programador","revisar_vencimientos",monotonic()-inicio_lote,"error" if hay_error else "ok","tareas_con_error" if hay_error else None)
    marca="interfaz_manual" if manual else origen
    insertar={"sqlite":sqlite_insert,"postgresql":pg_insert}[db.engine.dialect.name]
    valores={"revisado_en":ahora_utc(),"estado":"error" if any(r["estado"]=="error" for r in salida) else "ok"}
    if salida: valores["ultima_tarea_en"]=ahora_utc()
    db.session.execute(insertar(EstadoProgramador).values(origen=marca,**valores)
        .on_conflict_do_update(index_elements=["origen"],set_=valores))
    db.session.commit()
    procesar()
    return salida
