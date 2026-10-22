"""Inferencia sin reentrenamiento ni llamadas a LLM."""
import math
from pathlib import Path

import joblib
import pandas as pd

from ml.artefactos import cargar, directorio
from ml.datos import caracteristicas, validar_fecha

RUTA_MODELO = Path(__file__).with_name("modelo_demanda.joblib")


def predecir(fecha, es_feriado=None):
    fecha = validar_fecha(fecha)
    paquete, meta = cargar()
    configurado = fecha.isoformat() in meta["calendario"]["fechas"]
    feriado = meta["calendario"]["fechas"].get(fecha.isoformat(), False) if es_feriado is None else es_feriado
    if type(feriado) is not bool:
        raise ValueError("es_feriado debe ser booleano.")
    x = pd.DataFrame([caracteristicas(fecha, feriado)], columns=meta["caracteristicas"])
    resultados = {"clasificacion": {}, "regresion": {}}
    for objetivo, familia in paquete["modelos"].items():
        for nombre, modelo in familia.items():
            valor = modelo.predict(x)[0]
            if objetivo == "clasificacion":
                probs = dict(zip(map(str, modelo.classes_), map(float, modelo.predict_proba(x)[0])))
                resultados[objetivo][nombre] = {"nivel": str(valor), "probabilidad": max(probs.values()), "probabilidades": probs}
            else:
                valor = max(0., float(valor))
                resultados[objetivo][nombre] = {"cantidad": math.floor(valor + .5), "estimacion": round(valor, 3)}
    ganadores = {o: meta["resultados"][o]["ganador"] for o in resultados}
    return {"fecha": fecha.isoformat(), "version": meta["version"], "ganadores": ganadores,
            "nivel": resultados["clasificacion"][ganadores["clasificacion"]]["nivel"],
            "probabilidad": resultados["clasificacion"][ganadores["clasificacion"]]["probabilidad"],
            "cantidad": resultados["regresion"][ganadores["regresion"]]["cantidad"],
            "resultados": resultados, "experimental": True,
            "feriado": {"valor": feriado, "confirmado": configurado or es_feriado is not None},
            "explicacion": "Ganadores por validación temporal (F1 macro y MAE). Probabilidad sin calibrar; cantidad estimada redondeada. "
                           + ("Feriado configurado." if configurado or es_feriado is not None else "Feriado no confirmado: se supone no feriado.")}


def predecir_demanda(fecha_objetivo, es_feriado=None):
    """Contrato histórico; respaldo v1 sólo si aún no existe registro v2."""
    fecha_objetivo = validar_fecha(fecha_objetivo)
    if (directorio() / "actual.json").exists():
        return predecir(fecha_objetivo, es_feriado)
    if not RUTA_MODELO.exists():
        raise FileNotFoundError("Primero debes entrenar el modelo.")
    # Legado propio del repositorio; nunca un fichero recibido por HTTP.
    paquete = joblib.load(RUTA_MODELO)
    x = pd.DataFrame([caracteristicas(fecha_objetivo, bool(es_feriado))], columns=paquete["caracteristicas"])
    modelo = paquete["modelo"]
    return {"fecha": fecha_objetivo.isoformat(), "nivel": str(modelo.predict(x)[0]),
            "probabilidad": float(max(modelo.predict_proba(x)[0])), "version": paquete["version"]}
