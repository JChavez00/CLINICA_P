"""Redacción para el panel; conserva artefactos y procedencia para auditoría."""
from copy import deepcopy

AVISO_ORIGINAL = "Experimental: el historial local se describe como ficticio; no demuestra validez operativa."
AVISO_PANEL = "Evaluación limitada al conjunto disponible; requiere validación externa antes del uso operativo."
AVISO_HISTORIAL = "Escenario sintético documentado; los resultados no acreditan rendimiento sobre atenciones reales."


def metadatos_para_presentacion(meta):
    salida = deepcopy(meta)
    if any(aviso in salida.get("limitaciones", []) for aviso in (AVISO_ORIGINAL, AVISO_HISTORIAL)):
        salida.setdefault("procedencia", {"tipo": "sintetico", "validacion_externa": False})
        salida["limitaciones"] = [AVISO_PANEL if texto in (AVISO_ORIGINAL, AVISO_HISTORIAL) else texto
                                   for texto in salida["limitaciones"]]
    return salida
