
from datetime import date
from pathlib import Path

import joblib
import pandas as pd


RUTA_MODELO = (
    Path(__file__).parent / "modelo_demanda.joblib"
)


def predecir_demanda(fecha_objetivo, es_feriado=False):
    if not isinstance(fecha_objetivo, date):
        raise ValueError(
            "La fecha debe ser un objeto datetime.date."
        )

    if not RUTA_MODELO.exists():
        raise FileNotFoundError(
            "Primero debes entrenar el modelo."
        )

    paquete = joblib.load(RUTA_MODELO)
    modelo = paquete["modelo"]

    datos = pd.DataFrame(
        [{
            "dia_semana": fecha_objetivo.weekday(),
            "mes": fecha_objetivo.month,
            "es_feriado": int(bool(es_feriado))
        }],
        columns=paquete["caracteristicas"]
    )

    nivel = modelo.predict(datos)[0]

    probabilidades = modelo.predict_proba(datos)[0]

    probabilidad = max(probabilidades)

    return {
        "fecha": fecha_objetivo.isoformat(),
        "nivel": str(nivel),
        "probabilidad": round(float(probabilidad), 4),
        "version": paquete["version"]
    }


if __name__ == "__main__":
    fecha = date(2026, 10, 15)
    resultado = predecir_demanda(fecha)
    print(resultado)
