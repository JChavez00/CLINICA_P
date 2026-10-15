
"""Rutas del asistente multiagente."""

import re

from flask import (
    Blueprint,
    jsonify,
    render_template,
    request,
    session,
    current_app
)

from .consultas import (
    obtener_resumen,
    interpretar_busqueda,
    respuesta_busqueda
)

from .coordinador import ejecutar_agentes


bp_asistente = Blueprint(
    "asistente_ia",
    __name__
)


@bp_asistente.before_request
def verificar_sesion():
    if not session.get("autenticado"):
        return jsonify({
            "error": "Inicia sesión para usar el asistente."
        }), 401


@bp_asistente.route("/asistente-ia")
def pagina():
    return render_template("asistente_ia.html")


@bp_asistente.route(
    "/api/asistente-ia",
    methods=["POST"]
)
def preguntar():

    cuerpo = request.get_json(silent=True)

    if not isinstance(cuerpo, dict):
        return jsonify({
            "error": "Envía un JSON válido."
        }), 400

    pregunta = cuerpo.get("pregunta", "")

    if not isinstance(pregunta, str):
        return jsonify({
            "error": "La pregunta debe ser texto."
        }), 400

    pregunta = pregunta.strip()

    if not pregunta:
        return jsonify({
            "error": "Escribe una pregunta."
        }), 400

    if len(pregunta) > 500:
        return jsonify({
            "error": (
                "La pregunta debe tener "
                "como máximo 500 caracteres."
            )
        }), 400

    try:
        # ------------------------------------------------
        # 1. BÚSQUEDAS DE PACIENTES: SOLO FLASK
        # ------------------------------------------------

        busqueda = interpretar_busqueda(pregunta)

        if busqueda is not None:
            tipo, valor, _ = busqueda

            respuesta = respuesta_busqueda(
                tipo,
                valor
            )

            return jsonify({
                "respuesta": respuesta,
                "origen": "base_local"
            })

        # Protección adicional contra el envío de
        # posibles consultas individuales a las API.
        if re.search(
            r"\b(?:\d{8,9}|"
            r"historia\s+cl[ií]nica|"
            r"expediente|"
            r"diagn[oó]stico\s+de|"
            r"receta\s+de|"
            r"tel[eé]fono\s+de)\b",
            pregunta,
            flags=re.IGNORECASE
        ):
            return jsonify({
                "respuesta": (
                    "Para consultar información individual "
                    "de un paciente, indica su DNI o "
                    "utiliza una búsqueda por nombre. "
                    "Los expedientes no se envían "
                    "a servicios externos."
                ),
                "origen": "base_local"
            })

        # ------------------------------------------------
        # 2. ESTADÍSTICAS AGREGADAS DE SUPABASE
        # ------------------------------------------------

        resumen = obtener_resumen()

        # ------------------------------------------------
        # 3. COORDINACIÓN DE GEMINI Y GROQ
        # ------------------------------------------------

        resultado = ejecutar_agentes(
            pregunta=pregunta,
            resumen=resumen
        )

        return jsonify(resultado)

    except Exception:
        # No registrar el contenido de la pregunta.
        current_app.logger.exception(
            "Error interno en el asistente multiagente"
        )

        return jsonify({
            "error": (
                "No se pudo completar la consulta. "
                "Revisa los registros del servidor."
            )
        }), 502
