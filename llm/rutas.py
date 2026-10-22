"""Chat y tres módulos independientes con autenticación y confirmación explícita."""
import hmac
import secrets
from functools import wraps
from uuid import uuid4

from flask import (Blueprint, jsonify, render_template, request, session,
                   current_app, redirect, url_for, send_file)
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from models import db, InformeIA, TareaIA, TareaIAEjecucion, AgenteEjecucion
from ml.datos import hoy_peru
from .auditoria import permiso
from .coordinador import ejecutar_agentes, coordinar
from .esquemas import ErrorAgente, Reporte, Periodo, ConfiguracionTarea
from .privacidad import extraer_tarea

bp_asistente=Blueprint("asistente_ia",__name__)


@bp_asistente.before_request
def verificar_sesion():
    if not session.get("autenticado"):
        if request.path.startswith("/api/"): return jsonify({"error":"Inicia sesión para usar los agentes."}),401
        return redirect(url_for("login"))
    if request.content_length and request.content_length>16000:
        return jsonify({"error":"Solicitud demasiado extensa."}),413


@bp_asistente.after_request
def privacidad_http(respuesta):
    respuesta.headers["Cache-Control"]="no-store"
    respuesta.headers["X-Content-Type-Options"]="nosniff"
    return respuesta


def protegido(capacidad=None,csrf=False):
    def decorar(vista):
        @wraps(vista)
        def ejecutar(*args,**kwargs):
            try:
                if capacidad: permiso(capacidad)
                if csrf:
                    token=request.headers.get("X-CSRF-Token","")
                    if not token or not hmac.compare_digest(token,session.get("ia_csrf","")):
                        raise ErrorAgente("csrf_invalido",403)
                return vista(*args,**kwargs)
            except ErrorAgente as exc:
                mensajes={"permiso_denegado":"Tu configuración no permite esta operación.",
                          "limite_de_consultas":"Se alcanzó el límite de consultas; inténtalo más tarde.",
                          "csrf_invalido":"Recarga la página y vuelve a intentarlo.",
                          "confirmacion_requerida":"Debes confirmar explícitamente la programación.",
                          "base_no_disponible":"La base de datos no está disponible.",
                          "calidad_supera_limite_5000":"La revisión excede el límite de 5000 registros; reduce el período o utiliza un proceso por lotes."}
                return jsonify({"error":mensajes.get(exc.codigo,"No se pudo completar la operación: "+exc.codigo),"codigo":exc.codigo}),exc.estado
            except (ValidationError,ValueError,TypeError,KeyError):
                return jsonify({"error":"Parámetros inválidos. Verifica fechas, campos y tipos de datos."}),400
            except SQLAlchemyError:
                db.session.rollback()
                return jsonify({"error":"No se pudo acceder a los datos. Verifica la conexión y ejecuta python -m llm.cli inicializar."}),503
        return ejecutar
    return decorar


def cuerpo():
    r=request.get_json(silent=True)
    if not isinstance(r,dict): raise ErrorAgente("json_invalido",400)
    return r


def texto(valor):
    if not isinstance(valor,str) or not valor.strip() or len(valor)>500:
        raise ErrorAgente("texto_invalido_maximo_500",400)
    return valor.strip()


def pagina_modulo(modulo):
    session.setdefault("ia_csrf",secrets.token_urlsafe(32))
    return render_template("agentes.html",modulo=modulo,csrf=session["ia_csrf"],hoy=hoy_peru().isoformat())


@bp_asistente.route("/asistente-ia")
def pagina():
    return render_template("asistente_ia.html")


@bp_asistente.route("/api/asistente-ia",methods=["POST"])
@protegido()
def preguntar():
    r=cuerpo()
    pregunta=texto(r.get("pregunta","Selección de paciente" if "seleccion" in r else ""))
    return jsonify(ejecutar_agentes(pregunta,seleccion=r.get("seleccion")))


@bp_asistente.route("/reportes-inteligentes")
@protegido("reportes")
def reportes_pagina(): return pagina_modulo("reportes")


@bp_asistente.route("/automatizacion-tareas")
@protegido("tareas")
def tareas_pagina(): return pagina_modulo("tareas")


@bp_asistente.route("/calidad-datos")
@protegido("calidad")
def calidad_pagina(): return pagina_modulo("calidad")


@bp_asistente.route("/actividad-agentes")
@protegido("auditoria")
def actividad_pagina(): return pagina_modulo("auditoria")


@bp_asistente.route("/api/agentes/reportes",methods=["POST"])
@protegido("reportes",csrf=True)
def generar_reporte():
    from .reportes import guardar, publico
    r=cuerpo(); args=Reporte.model_validate(r.get("configuracion",{})).model_dump()
    resultado=coordinar("reportes","reportes",{"herramienta":"construir_reporte","argumentos":args,"seguro":{"objetivo":"informe_administrativo"}})
    # Colaboración adicional sólo cuando el usuario la selecciona expresamente.
    if r.get("revision_groq") is True:
        revision=coordinar("chat","analista",{"herramienta":"estadisticas_periodo","argumentos":{"desde":args["desde"],"hasta":args["hasta"]},"seguro":{"objetivo":"revision_agregada"}})
        resultado["datos"]["revision_adicional"]={"agente":revision["agente"],"estado":revision["estado"],"conclusiones":revision["datos"]["conclusiones"]}
    informe=guardar(resultado)
    from .notificaciones import registrar, procesar
    registrar("resumen_mensual" if args["tipo"]=="mensual" else "reporte_generado", "informe:"+informe.id, informe_id=informe.id)
    procesar()
    return jsonify(publico(informe)),201


@bp_asistente.route("/api/agentes/reportes",methods=["GET"])
@protegido("reportes")
def listar_reportes():
    from models import ArchivoInforme
    return jsonify({"informes":[{"id":i.id,"desde":i.desde.isoformat(),"hasta":i.hasta.isoformat(),"generado_en":i.generado_en.isoformat()+"Z",
                                 "archivos":[{"formato":a.formato,"estado":a.estado} for a in ArchivoInforme.query.filter_by(informe_id=i.id,propietario_id=1).all()]}
                                for i in InformeIA.query.order_by(InformeIA.generado_en.desc()).limit(20).all()]})


@bp_asistente.route("/api/agentes/reportes/<uuid:identificador>/<formato>")
@protegido("reportes")
def descargar_reporte(identificador,formato):
    from .reportes import pdf,excel
    if formato not in ("pdf","xlsx"): raise ErrorAgente("formato_invalido",400)
    informe=db.session.get(InformeIA,str(identificador))
    if not informe: raise ErrorAgente("informe_no_encontrado",404)
    from .almacenamiento import descargar
    buffer=descargar(informe,formato)
    return send_file(buffer,as_attachment=True,download_name=f"reporte_{informe.desde}_{informe.hasta}.{formato}",
                     mimetype="application/pdf" if formato=="pdf" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def firmador(): return URLSafeTimedSerializer(current_app.secret_key,salt="agentes-tareas-v1")


@bp_asistente.route("/api/agentes/tareas/preview",methods=["POST"])
@protegido("tareas",csrf=True)
def tarea_preview():
    r=cuerpo()
    args=r.get("configuracion") or extraer_tarea(texto(r.get("solicitud")))
    args=ConfiguracionTarea.model_validate(args).model_dump()
    resultado=coordinar("tareas","tareas",{"herramienta":"preparar_tarea","argumentos":args,"seguro":{"objetivo":"configurar_borrador"}})
    nonce=str(uuid4()); session["ia_borrador"]=nonce
    from .perfil import crear
    from .programacion import proxima
    p=crear()
    resultado["zona"]=p.zona
    resultado["proxima"]=proxima(args,p.zona).isoformat()+"Z"
    resultado["avisos"]="Panel y correo verificado según preferencias" if p.avisos and p.verificado else "Panel; correo desactivado o pendiente de verificación"
    resultado["confirmacion_token"]=firmador().dumps({"id":nonce,"configuracion":args,"zona":p.zona})
    return jsonify(resultado)


@bp_asistente.route("/api/agentes/tareas/confirmar",methods=["POST"])
@protegido("tareas",csrf=True)
def tarea_confirmar():
    from .tareas import confirmar
    r=cuerpo()
    if r.get("confirmar") is not True: raise ErrorAgente("confirmacion_requerida",400)
    try: plan=firmador().loads(r.get("token",""),max_age=600)
    except (BadSignature,SignatureExpired): raise ErrorAgente("borrador_invalido_o_caducado",400) from None
    existente=db.session.get(TareaIA,plan["id"])
    if not existente and session.get("ia_borrador")!=plan["id"]: raise ErrorAgente("borrador_no_autorizado",403)
    t=confirmar(plan["configuracion"],plan["id"],zona=plan.get("zona","America/Lima")); session.pop("ia_borrador",None)
    return jsonify({"id":t.id,"confirmada":t.confirmada,"activa":t.activa}),201


@bp_asistente.route("/api/agentes/tareas",methods=["GET"])
@protegido("tareas")
def tareas_listar():
    from .tareas import listar
    ejecuciones=TareaIAEjecucion.query.order_by(TareaIAEjecucion.iniciada_en.desc()).limit(50).all()
    ultimo=AgenteEjecucion.query.filter_by(modulo="programador").order_by(AgenteEjecucion.fecha.desc()).first()
    from .programacion import estado
    return jsonify({"tareas":listar(),"programador":estado(),"programador_ultima_revision":ultimo.fecha.isoformat()+"Z" if ultimo else None,
                    "ejecuciones":[{"id":e.id,"tarea_id":e.tarea_id,"fecha":e.iniciada_en.isoformat()+"Z","periodo":e.periodo,"estado":e.estado,"intentos":e.intentos,"resultado":e.resultado,"error_codigo":e.error_codigo} for e in ejecuciones]})


@bp_asistente.route("/api/agentes/tareas/<uuid:identificador>",methods=["POST"])
@protegido("tareas",csrf=True)
def tarea_activar(identificador):
    r=cuerpo()
    tarea=db.session.get(TareaIA,str(identificador))
    if not tarea: raise ErrorAgente("tarea_no_encontrada",404)
    if "configuracion" in r:
        if r.get("confirmar") is not True: raise ErrorAgente("confirmacion_requerida",400)
        if TareaIAEjecucion.query.filter_by(tarea_id=tarea.id,estado="ejecutando").first():
            raise ErrorAgente("tarea_en_ejecucion",409)
        from .programacion import asociar,proxima
        from .perfil import zona_valida
        config=ConfiguracionTarea.model_validate(r["configuracion"]).model_dump()
        if config["tipo"]!=tarea.configuracion["tipo"]: raise ValueError()
        nombre=texto(r.get("nombre"))
        if len(nombre)>160: raise ValueError()
        zona=zona_valida(r.get("zona"))
        meta=asociar(tarea)
        meta.nombre=nombre; meta.zona=zona; meta.proxima=proxima(config,zona)
        tarea.configuracion=config; db.session.commit()
        return jsonify(ok=True)
    activa=r.get("activa")
    if type(activa) is not bool: raise ErrorAgente("activa_debe_ser_booleano",400)
    if activa and not tarea.activa:
        from .programacion import asociar,proxima
        meta=asociar(tarea); meta.proxima=proxima(tarea.configuracion,meta.zona)
    tarea.activa=activa; db.session.commit()
    return jsonify({"id":tarea.id,"activa":tarea.activa})


@bp_asistente.route("/api/agentes/calidad",methods=["POST"])
@protegido("calidad",csrf=True)
def calidad():
    args=Periodo.model_validate(cuerpo()).model_dump()
    return jsonify(coordinar("calidad","calidad",{"herramienta":"analizar_calidad","argumentos":args,"seguro":{"objetivo":"validaciones_administrativas"}}))


@bp_asistente.route("/api/agentes/tareas/<uuid:identificador>/ejecutar",methods=["POST"])
@protegido("tareas",csrf=True)
def tarea_ejecutar(identificador):
    from .tareas import ejecutar_programadas
    if cuerpo().get("ejecutar") is not True: raise ErrorAgente("ejecucion_requiere_solicitud",400)
    tarea=db.session.get(TareaIA,str(identificador))
    if not tarea or not tarea.activa or not tarea.confirmada: raise ErrorAgente("tarea_no_activa",400)
    return jsonify({"ejecuciones":ejecutar_programadas(tarea_id=tarea.id,manual=True)})


@bp_asistente.route("/api/agentes/ejecuciones")
@protegido("auditoria")
def ejecuciones():
    return jsonify({"ejecuciones":[{"id":e.id,"agente":e.agente,"modulo":e.modulo,"herramienta":e.herramienta,"fecha":e.fecha.isoformat()+"Z","duracion_ms":e.duracion_ms,"estado":e.estado,"error_codigo":e.error_codigo}
                    for e in AgenteEjecucion.query.order_by(AgenteEjecucion.fecha.desc()).limit(50).all()]})
