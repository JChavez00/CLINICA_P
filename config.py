import os
from datetime import timedelta

from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, ".env"))


class Config:
    # Clave secreta para sesiones/login. En producción SIEMPRE cámbiala
    # definiendo la variable de entorno SECRET_KEY.
    SECRET_KEY = os.environ.get("SECRET_KEY", "cambia-esta-clave-en-produccion")

    # Base de datos:
    # - Si existe DATABASE_URL (Render/Supabase la proveen), se usa esa (Postgres).
    # - Si no, se usa SQLite local, ideal para desarrollo en tu computadora.
    _database_url = os.environ.get("DATABASE_URL", "")
    if _database_url.startswith("postgres://"):
        # SQLAlchemy moderno requiere "postgresql://" en vez de "postgres://"
        _database_url = _database_url.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_DATABASE_URI = _database_url or (
        "sqlite:///" + os.path.join(basedir, "instance", "clinica.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Credenciales del usuario que ingresa al sistema (login simple, un solo usuario).
    # Cámbialas con variables de entorno en producción.
    APP_USERNAME = os.environ.get("APP_USERNAME", "doctor")
    APP_PASSWORD = os.environ.get("APP_PASSWORD", "clinica123")

    # Duración de la sesión iniciada
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    # API de consulta DNI (RENIEC vía intermediario). Configúrala con tu propio
    # proveedor (json.pe, apis.net.pe, apidni.com, etc). Si no la configuras,
    # el sistema simplemente permite ingresar los datos del paciente a mano.
    DNI_API_URL = os.environ.get("DNI_API_URL", "")
    DNI_API_TOKEN = os.environ.get("DNI_API_TOKEN", "")
    # Nombre del proveedor, solo para mostrar en el mensaje si falla la consulta.
    DNI_API_PROVIDER = os.environ.get("DNI_API_PROVIDER", "API de Consulta DNI")

    # Nombre del consultorio / clínica, se muestra en la interfaz.
    NOMBRE_CLINICA = os.environ.get("NOMBRE_CLINICA", "Consultorio Médico")

    # Clave de Google Maps (solo se usa para DIBUJAR el mapa y el pin
    # arrastrable). La búsqueda de direcciones NO usa Google, usa Nominatim
    # (gratis, ver services/geocodificacion.py), así que esta clave solo
    # necesita tener habilitada "Maps JavaScript API".
    # Si la dejas vacía, el formulario sigue funcionando pero sin el mapa
    # visual (se puede seguir escribiendo la dirección igual).
    GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")

    # Centro por defecto del mapa cuando aún no hay ninguna dirección
    # escrita. Por defecto: Tarma, Junín. Ajusta a la ciudad de tu consultorio.
    MAPA_LAT_DEFECTO = float(os.environ.get("MAPA_LAT_DEFECTO", "-11.4189"))
    MAPA_LNG_DEFECTO = float(os.environ.get("MAPA_LNG_DEFECTO", "-75.6910"))
