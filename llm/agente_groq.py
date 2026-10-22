"""Adaptador legado al coordinador; no transmite resúmenes arbitrarios."""
def responder_groq(pregunta,resumen=None,analisis_gemini=None):
    from .coordinador import ejecutar_agentes
    return ejecutar_agentes(pregunta)["respuesta"]
