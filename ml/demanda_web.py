"""Dashboard ML autenticado. Persistencia sólo por POST explícito o cron."""
import hmac
import secrets
from datetime import timedelta
from functools import wraps

from flask import Blueprint, render_template, jsonify, request, session, redirect, url_for, current_app
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func
from models import db, MLPronostico

from ml.artefactos import metadatos, ModeloIncompatible
from ml.datos import hoy_peru, validar_fecha, cargar_datos
from ml.predecir_demanda import predecir
from ml.pronosticos import consultar, validar_periodo
from ml.presentacion import metadatos_para_presentacion

bp_demanda = Blueprint("demanda", __name__)


@bp_demanda.before_request
def proteger():
    if not session.get("autenticado"):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Inicia sesión para consultar Machine Learning."}), 401
        return redirect(url_for("login"))


@bp_demanda.after_request
def cabeceras(respuesta):
    respuesta.headers["Cache-Control"]="no-store"
    respuesta.headers["X-Content-Type-Options"]="nosniff"
    return respuesta


def api(vista):
    @wraps(vista)
    def ejecutar(*args, **kwargs):
        try:
            return jsonify(vista(*args, **kwargs))
        except (FileNotFoundError, ModeloIncompatible) as exc:
            return jsonify({"error": str(exc)}), 503
        except (ValueError, TypeError) as exc:
            return jsonify({"error": str(exc)}), 400
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("Error de persistencia ML")
            return jsonify({"error": "No se pudo leer ML. Verifica la base y ejecuta python -m ml.cli inicializar."}), 503
    return ejecutar


@bp_demanda.route("/demanda")
def pagina():
    session.setdefault("ml_csrf",secrets.token_urlsafe(32))
    return render_template("demanda.html", manana=(hoy_peru() + timedelta(days=1)).isoformat(),ml_csrf=session["ml_csrf"])


@bp_demanda.route("/api/ml/pronosticos/generar",methods=["POST"])
def generar_guardados():
    token=request.headers.get("X-CSRF-Token","")
    esperado=session.get("ml_csrf","")
    if not esperado or not hmac.compare_digest(token.encode(),esperado.encode()):
        return jsonify(error="Recarga la página antes de generar pronósticos."),403
    if request.content_length and request.content_length>2048:
        return jsonify(error="Solicitud demasiado extensa."),413
    return _generar_guardados()


@api
def _generar_guardados():
    datos=request.get_json(silent=True)
    if not isinstance(datos,dict) or set(datos)!={"fecha","dias","confirmar"} or datos.get("confirmar") is not True:
        raise ValueError("Se requiere confirmar la generación con fecha y horizonte.")
    fecha=validar_fecha(datos["fecha"],futura=True)
    dias=validar_periodo(datos["dias"])
    from ml.pronosticos import generar
    resultado=generar(dias,fecha)
    return {**resultado,"pronosticos":consultar(fecha,dias),
            "mensaje":"Pronósticos guardados. Repetir el mismo día y versión conserva la emisión existente. Son estimaciones experimentales."}


@bp_demanda.route("/api/ml/modelos")
@bp_demanda.route("/api/ml/comparacion")
@bp_demanda.route("/api/ml/metricas")
@api
def modelos():
    return metadatos_para_presentacion(metadatos())


@bp_demanda.route("/api/ml/predecir")
@api
def manual():
    fecha = validar_fecha(request.args.get("fecha"), futura=True)
    feriado = request.args.get("feriado")
    if feriado not in (None, "true", "false"):
        raise ValueError("feriado debe ser true o false.")
    return predecir(fecha, None if feriado is None else feriado == "true")


@bp_demanda.route("/api/ml/pronosticos")
@api
def pronosticos():
    fecha = validar_fecha(request.args.get("fecha", (hoy_peru() + timedelta(days=1)).isoformat()))
    dias = validar_periodo(request.args.get("dias", "7"))
    return {"pronosticos": consultar(fecha, dias)}


@bp_demanda.route("/api/demanda")
@api
def datos():
    fecha = validar_fecha(request.args.get("fecha", (hoy_peru() + timedelta(days=1)).isoformat()))
    dias = validar_periodo(request.args.get("dias", "7"))
    df, auditoria = cargar_datos()
    meta = metadatos_para_presentacion(metadatos())
    serie = [{"fecha": r.fecha.isoformat(), "total": int(r.total_atenciones), "nivel": r.nivel_demanda}
             for r in df.tail(45).itertuples()]
    actualizacion = db.session.query(func.max(MLPronostico.generado_en)).scalar()
    return {"pronosticos": consultar(fecha, dias), "serie": serie, "motivos": [],
            "ultima_actualizacion": actualizacion.isoformat() + "Z" if actualizacion else None,
            "manana": consultar(hoy_peru() + timedelta(days=1), 7)[0],
            "resumen": {str(k): int(v) for k, v in df.nivel_demanda.value_counts().items()},
            "historial": {"desde": df.fecha.iloc[0].isoformat(), "hasta": df.fecha.iloc[-1].isoformat(),
                          "dias": len(df), "atenciones": int(df.total_atenciones.sum())},
            "auditoria": auditoria, "entrenamiento": meta,
            "aviso": "Experimental. Consulta las métricas reales y compara con la referencia. Las emisiones se guardan mediante generación manual explícita o la tarea programada."}
