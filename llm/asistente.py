"""Adaptador legado: toda solicitud utiliza ahora la frontera de privacidad."""
def responder(pregunta,resumen=None):
    from .coordinador import ejecutar_agentes
    return ejecutar_agentes(pregunta)["respuesta"]
