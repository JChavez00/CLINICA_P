from flask import Blueprint, jsonify, render_template, request, session, current_app
from .consultas import obtener_resumen, interpretar_busqueda, respuesta_busqueda
from .asistente import responder

bp_asistente = Blueprint('asistente_ia', __name__)


@bp_asistente.before_request
def verificar_sesion():
    if not session.get('autenticado'):
        return jsonify({'error': 'Inicia sesión para usar el asistente.'}), 401


@bp_asistente.route('/asistente-ia')
def pagina():
    return render_template('asistente_ia.html')


@bp_asistente.route('/api/asistente-ia', methods=['POST'])
def preguntar():
    cuerpo = request.get_json(silent=True)
    if not isinstance(cuerpo, dict):
        return jsonify({'error': 'Envía un JSON válido.'}), 400
    pregunta = cuerpo.get('pregunta', '')
    if not isinstance(pregunta, str) or not pregunta.strip():
        return jsonify({'error': 'Escribe una pregunta.'}), 400
    pregunta = pregunta.strip()
    if len(pregunta) > 500:
        return jsonify({'error': 'La pregunta debe tener como máximo 500 caracteres.'}), 400

    current_app.logger.info(
    "Pregunta recibida: %r", pregunta
    )

    try:
        busqueda = interpretar_busqueda(pregunta)
        if busqueda is not None:
            tipo, valor, _ = busqueda
            # Datos identificables y clínicos: SOLO Flask/SQLite, NUNCA Gemini.
            respuesta = respuesta_busqueda(tipo, valor)
            current_app.logger.info('Consulta local de expediente: tipo=%s', tipo)
            return jsonify({'respuesta': respuesta, 'origen': 'base_local'})

        resumen = obtener_resumen()
        respuesta = responder(pregunta, resumen)
        return jsonify({'respuesta': respuesta, 'origen': 'gemini'})
    except Exception:
        current_app.logger.exception('Error en el asistente IA')
        return jsonify({'error': 'No se pudo completar la consulta. Revisa la terminal del servidor.'}), 502
