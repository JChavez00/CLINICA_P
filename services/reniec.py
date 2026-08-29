"""
Servicio de consulta de DNI (RENIEC vía proveedor intermediario).

RENIEC no ofrece una API pública oficial gratuita: se usa un proveedor
intermediario (json.pe, apis.net.pe, apidni.com, etc). Este módulo está
escrito para que cambiar de proveedor sea editar SOLO esta función,
sin tocar el resto de la aplicación.

Configura las credenciales en tu archivo .env:
    DNI_API_URL=https://api.tu-proveedor.pe/api/dni
    DNI_API_TOKEN=tu_token_bearer

Si no configuras nada, la consulta simplemente no se hace y el doctor
llena los datos del paciente a mano (el sistema sigue funcionando igual).
"""
import requests

def consultar_dni(dni: str, api_url: str, api_token: str):
    """
    Consulta un DNI contra el proveedor configurado.
    Adaptado para soportar proveedores GET (apis.net.pe) y POST (json.pe).
    """
    if not api_url or not api_token:
        return {
            "ok": False,
            "error": "no_configurado",
        }

    if not dni or not dni.isdigit() or len(dni) != 8:
        return {"ok": False, "error": "El DNI debe tener 8 dígitos numéricos."}

    headers = {
        "Authorization": f"Bearer {api_token}",
        "Accept": "application/json",
    }

    try:
        # Detectamos si el proveedor es json.pe para cambiar el método a POST
        if "json.pe" in api_url:
            # json.pe exige POST y el DNI en el body como JSON
            resp = requests.post(
                api_url,
                json={"dni": dni}, 
                headers=headers,
                timeout=8,
            )
        else:
            # Para la mayoría de proveedores (como apis.net.pe) se usa GET
            resp = requests.get(
                api_url,
                params={"numero": dni, "dni": dni},
                headers=headers,
                timeout=8,
            )
            
    except requests.exceptions.Timeout:
        return {"ok": False, "error": "El servicio de consulta tardó demasiado en responder."}
    except requests.exceptions.RequestException:
        return {"ok": False, "error": "No se pudo conectar con el servicio de consulta de DNI."}

    if resp.status_code in (401, 403):
        return {"ok": False, "error": "Token inválido o vencido para la API de DNI."}
    if resp.status_code == 404:
        return {"ok": False, "error": "No se encontró información para ese DNI."}
    if resp.status_code != 200:
        return {"ok": False, "error": f"El servicio respondió con error ({resp.status_code})."}

    try:
        data = resp.json()
    except ValueError:
        return {"ok": False, "error": "Respuesta inesperada del servicio de consulta."}

    # json.pe suele devolver los datos directamente o anidados bajo un campo "data" (por si acaso evaluamos ambos)
    info = data.get("data", data) if isinstance(data.get("data"), dict) else data

    # --- Parseo de respuesta: cubre formatos comunes ---
    nombres = info.get("nombres") or info.get("first_name") or ""
    apellido_paterno = (
        info.get("apellido_paterno") or info.get("apellidoPaterno") or info.get("first_last_name") or ""
    )
    apellido_materno = (
        info.get("apellido_materno") or info.get("apellidoMaterno") or info.get("second_last_name") or ""
    )
    fecha_nacimiento = info.get("fecha_nacimiento") or info.get("fechaNacimiento") or ""

    if not nombres and not apellido_paterno:
        return {"ok": False, "error": "El proveedor no devolvió datos reconocibles para ese DNI."}

    return {
        "ok": True,
        "nombres": nombres.strip().title(),
        "apellidos": f"{apellido_paterno} {apellido_materno}".strip().title(),
        "fecha_nacimiento": fecha_nacimiento,
    }
