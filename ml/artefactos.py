"""Registro local de artefactos confiables, inmutables y versionados."""
import hashlib
import json
import os
import re
from functools import lru_cache
from pathlib import Path

import joblib
import sklearn

RAIZ = Path(__file__).with_name("modelos_entrenados")


class ModeloIncompatible(ValueError):
    """Artefacto administrado ausente, corrupto o de otra versión de runtime."""


def directorio():
    return Path(os.getenv("ML_MODEL_DIR", str(RAIZ))).resolve()


def metadatos():
    raiz = directorio()
    try:
        puntero = json.loads((raiz / "actual.json").read_text(encoding="utf-8"))
        version = puntero["version"]
        if not re.fullmatch(r"v2-[a-f0-9]{16}", version):
            raise ModeloIncompatible("Versión de modelo inválida.")
        meta = json.loads((raiz / version / "metricas.json").read_text(encoding="utf-8"))
        if meta["schema"] != 2 or meta["version"] != version:
            raise ModeloIncompatible("Metadatos incompatibles.")
        if meta["caracteristicas"] != ["dia_semana", "mes", "es_feriado", "fin_semana", "dia_mes"]:
            raise ModeloIncompatible("Características incompatibles.")
        for objetivo in ("clasificacion", "regresion"):
            if meta["resultados"][objetivo]["ganador"] not in meta["resultados"][objetivo]["validacion"]:
                raise ModeloIncompatible("Selección de modelos incompatible.")
        return meta
    except FileNotFoundError:
        raise FileNotFoundError("No hay modelos v2. Ejecuta python -m ml.cli entrenar.") from None
    except (KeyError, TypeError, json.JSONDecodeError):
        raise ModeloIncompatible("El registro de modelos está incompleto o corrupto.") from None


@lru_cache(maxsize=4)
def _cargar(ruta, digest):
    archivo = Path(ruta)
    if hashlib.sha256(archivo.read_bytes()).hexdigest() != digest:
        raise ModeloIncompatible("El modelo no coincide con su registro de integridad.")
    # Sólo artefactos propios del directorio administrado. Joblib ejecuta código:
    # nunca aceptar cargas de usuarios ni modelos descargados de terceros.
    paquete = joblib.load(archivo)
    if paquete.get("schema") != 2:
        raise ModeloIncompatible("Formato de modelo incompatible.")
    return paquete


def cargar():
    meta = metadatos()
    if meta["sklearn"] != sklearn.__version__:
        raise ModeloIncompatible("Versión de scikit-learn incompatible; instala la versión registrada o reentrena.")
    ruta = directorio() / meta["version"] / "modelos.joblib"
    paquete = _cargar(str(ruta), meta["sha256"])
    if paquete.get("version") != meta["version"]:
        raise ModeloIncompatible("Versión del paquete incompatible.")
    for objetivo, resultados in meta["resultados"].items():
        familia = paquete.get("modelos", {}).get(objetivo, {})
        if len(familia) != 5 or resultados["ganador"] not in familia:
            raise ModeloIncompatible("El paquete no contiene los diez modelos esperados.")
    return paquete, meta


def publicar(paquete, meta):
    raiz = directorio()
    carpeta = raiz / meta["version"]
    carpeta.mkdir(parents=True, exist_ok=False)
    archivo = carpeta / "modelos.joblib"
    joblib.dump(paquete, archivo)
    meta["sha256"] = hashlib.sha256(archivo.read_bytes()).hexdigest()
    (carpeta / "metricas.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    temporal = raiz / (meta["version"] + ".tmp")
    temporal.write_text(json.dumps({"version": meta["version"]}), encoding="utf-8")
    temporal.replace(raiz / "actual.json")
    return meta
