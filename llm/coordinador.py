
"""Coordinador de los dos agentes LLM."""

from .asistente import responder
from .agente_groq import responder_groq


def ejecutar_agentes(pregunta, resumen):
    """Ejecuta Gemini y Groq de forma secuencial.

    Solo recibe datos agregados. Nunca expedientes.
    """

    # Agente 1: analiza la información
    analisis = responder(
        pregunta=pregunta,
        resumen=resumen
    )

    # Agente 2: revisa y redacta la respuesta final
    respuesta_final = responder_groq(
        pregunta=pregunta,
        resumen=resumen,
        analisis_gemini=analisis
    )

    return {
        "respuesta": respuesta_final,
        "origen": "multiagente",
        "agentes": ["gemini", "groq"]
    }
