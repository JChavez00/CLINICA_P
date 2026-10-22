"""Un cliente reutilizable por proveedor/proceso, timeout y errores sin secretos."""
import json
import os
from functools import lru_cache

from google import genai
from google.genai import types
from groq import Groq

from .esquemas import ErrorAgente


def modelo(proveedor):
    return os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite") if proveedor == "gemini" else os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")


@lru_cache(maxsize=4)
def _cliente(proveedor, clave, timeout):
    if proveedor == "gemini":
        return genai.Client(api_key=clave, http_options=types.HttpOptions(
            timeout=timeout*1000, retry_options=types.HttpRetryOptions(attempts=1)))
    return Groq(api_key=clave, timeout=timeout, max_retries=0)


def solicitar(proveedor, instrucciones, datos, esquema):
    """Sólo recibe contratos sanitizados; nunca preguntas crudas ni fichas."""
    clave = os.getenv("GEMINI_API_KEY" if proveedor == "gemini" else "GROQ_API_KEY", "").strip()
    if not clave:
        raise ErrorAgente("proveedor_sin_clave", 503)
    timeout = max(3, min(30, int(os.getenv("AGENTES_TIMEOUT", "15"))))
    sistema = instrucciones + "\nDevuelve exclusivamente JSON conforme a este contrato: " + json.dumps(esquema, ensure_ascii=False)
    mensaje = json.dumps(datos, ensure_ascii=False, allow_nan=False)
    if len(mensaje) > 60000:
        raise ErrorAgente("contexto_demasiado_grande", 400)
    try:
        cliente = _cliente(proveedor, clave, timeout)
        if proveedor == "gemini":
            r = cliente.models.generate_content(model=modelo(proveedor), contents=mensaje,
                config=types.GenerateContentConfig(system_instruction=sistema, response_mime_type="application/json", temperature=.1, max_output_tokens=1400))
            texto = r.text
        else:
            r = cliente.chat.completions.create(model=modelo(proveedor),
                messages=[{"role":"system", "content":sistema}, {"role":"user", "content":mensaje}],
                response_format={"type":"json_object"}, temperature=.1,
                reasoning_effort="low", max_completion_tokens=1800)
            texto = r.choices[0].message.content
        if not texto or len(texto) > 20000:
            raise ErrorAgente("respuesta_llm_vacia_o_extensa")
        salida = json.loads(texto)
        if not isinstance(salida, dict):
            raise ErrorAgente("respuesta_llm_invalida")
        return salida
    except ErrorAgente:
        raise
    except Exception as exc:
        estado = getattr(exc, "status_code", getattr(exc, "code", None))
        codigo = {429:"limite_proveedor", 404:"modelo_no_disponible", 401:"credenciales_proveedor", 403:"acceso_proveedor"}.get(estado, "proveedor_no_disponible")
        # No propagar str(exc), cuerpos HTTP, parámetros SQL ni trazas con prompts.
        raise ErrorAgente(codigo, 503 if estado in (429,404) else 502) from None
