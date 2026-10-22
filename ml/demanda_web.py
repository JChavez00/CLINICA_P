"""Dashboard ML autenticado. GET sólo lee: el cron genera los pronósticos."""
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

bp_demanda = Blueprint("demanda", __name__)


@bp_demanda.before_request
def proteger():
    if not session.get("autenticado"):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Inicia sesión para consultar Machine Learning."}), 401
        return redirect(url_for("login"))


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
            current_app.logger.exception("Error de persistencia ML")
            return jsonify({"error": "No se pudo leer ML. Verifica la base y ejecuta python -m ml.cli inicializar."}), 503
    return ejecutar


@bp_demanda.route("/demanda")
def pagina():
    return render_template("demanda.html", manana=(hoy_peru() + timedelta(days=1)).isoformat())


@bp_demanda.route("/api/ml/modelos")
@bp_demanda.route("/api/ml/comparacion")
@bp_demanda.route("/api/ml/metricas")
@api
def modelos():
    return metadatos()


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
    meta = metadatos()
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
            "aviso": "Experimental. Consulta las métricas reales y compara con la referencia. Los pronósticos automáticos son emisiones guardadas por la tarea programada."}
