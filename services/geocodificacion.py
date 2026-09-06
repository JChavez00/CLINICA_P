"""
Servicio de geocodificación (dirección -> coordenadas) usando Nominatim,
el buscador gratuito de OpenStreetMap. No necesita clave ni facturación.

Se llama SIEMPRE desde el backend (nunca directo desde el navegador del
usuario) por dos razones:
  1. La política de uso de Nominatim pide identificar la aplicación con un
     User-Agent propio, y limitar a máximo 1 solicitud por segundo.
  2. Centralizando aquí, controlamos ese límite en un solo lugar sin
     importar cuántas personas usen el sistema al mismo tiempo.

Atribución obligatoria por la licencia de OpenStreetMap: en cualquier
pantalla que use estos datos debe mostrarse un texto visible del estilo
"© OpenStreetMap contributors" (ya está en la plantilla nueva_atencion.html).
"""
import time
import threading
import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# Identifica tu app ante Nominatim. Cambia el correo por uno real tuyo:
# es parte de su política de uso para poder contactarte si hay abuso.
USER_AGENT = "RegistroClinico-Consultorio/1.0 (contacto@tu-correo.pe)"

_ultimo_request_lock = threading.Lock()
_ultimo_request_ts = 0.0
_INTERVALO_MINIMO = 1.1  # segundos, Nominatim pide máx. 1 req/seg


def _esperar_turno():
    """Asegura que nunca se llame a Nominatim más de una vez por segundo,
    sin importar cuántos usuarios lo disparen casi al mismo tiempo."""
    global _ultimo_request_ts
    with _ultimo_request_lock:
        ahora = time.monotonic()
        espera = _INTERVALO_MINIMO - (ahora - _ultimo_request_ts)
        if espera > 0:
            time.sleep(espera)
        _ultimo_request_ts = time.monotonic()


def buscar_direccion(consulta: str):
    """
    Busca una dirección en texto libre y devuelve la mejor coincidencia.

    Devuelve:
        {"ok": True, "latitud": ..., "longitud": ..., "direccion_encontrada": "..."}
        {"ok": False, "error": "mensaje"}
    """
    consulta = (consulta or "").strip()
    if not consulta:
        return {"ok": False, "error": "Dirección vacía."}

    _esperar_turno()

    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={
                "format": "json",
                "q": consulta,
                "limit": 1,
                "countrycodes": "pe",  # limita resultados a Perú
            },
            headers={"User-Agent": USER_AGENT},
            timeout=6,
        )
    except requests.exceptions.Timeout:
        return {"ok": False, "error": "El buscador de direcciones tardó demasiado en responder."}
    except requests.exceptions.RequestException:
        return {"ok": False, "error": "No se pudo conectar con el buscador de direcciones."}

    if resp.status_code != 200:
        return {"ok": False, "error": f"El buscador respondió con error ({resp.status_code})."}

    try:
        datos = resp.json()
    except ValueError:
        return {"ok": False, "error": "Respuesta inesperada del buscador de direcciones."}

    if not datos:
        return {"ok": False, "error": "No se encontró esa dirección. Ajusta el pin manualmente."}

    resultado = datos[0]
    try:
        return {
            "ok": True,
            "latitud": float(resultado["lat"]),
            "longitud": float(resultado["lon"]),
            "direccion_encontrada": resultado.get("display_name", consulta),
        }
    except (KeyError, ValueError):
        return {"ok": False, "error": "El buscador devolvió datos incompletos."}
