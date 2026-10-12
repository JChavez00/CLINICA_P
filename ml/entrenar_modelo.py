
from pathlib import Path
import sys

import joblib
import pandas as pd

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix
)

# Permite ejecutar este archivo desde la carpeta ml/
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from app import app
from models import db, MLDemandaDiaria


CARACTERISTICAS = [
    "dia_semana",
    "mes",
    "es_feriado"
]

ETIQUETAS = ["BAJA", "MEDIA", "ALTA"]
RUTA_MODELO = Path(__file__).parent / "modelo_demanda.joblib"


def entrenar():
    with app.app_context():
        registros = (
            db.session.query(MLDemandaDiaria)
            .order_by(MLDemandaDiaria.fecha)
            .all()
        )

        datos = [
            {
                "fecha": r.fecha,
                "dia_semana": r.fecha.weekday(),
                "mes": r.fecha.month,
                "es_feriado": int(bool(r.es_feriado)),
                "nivel_demanda": r.nivel_demanda,
            }
            for r in registros
        ]

    df = pd.DataFrame(datos)

    if len(df) < 60:
        raise ValueError(
            "Se necesitan al menos 60 días para entrenar."
        )

    if df["nivel_demanda"].isna().any():
        raise ValueError("Hay días sin nivel de demanda.")

    if not df["nivel_demanda"].isin(ETIQUETAS).all():
        raise ValueError("Existen etiquetas desconocidas.")

    corte = int(len(df) * 0.80)

    entrenamiento = df.iloc[:corte]
    prueba = df.iloc[corte:]

    X_train = entrenamiento[CARACTERISTICAS]
    y_train = entrenamiento["nivel_demanda"]

    X_test = prueba[CARACTERISTICAS]
    y_test = prueba["nivel_demanda"]

    if y_train.nunique() < 2:
        raise ValueError(
            "El entrenamiento necesita al menos dos clases."
        )

    modelo = RandomForestClassifier(
        n_estimators=200,
        max_depth=6,
        min_samples_leaf=4,
        class_weight="balanced",
        random_state=42
    )

    modelo.fit(X_train, y_train)

    predicciones = modelo.predict(X_test)

    exactitud = accuracy_score(y_test, predicciones)

    # Referencia: predecir la clase más frecuente
    clase_frecuente = y_train.mode().iloc[0]
    referencia = [clase_frecuente] * len(y_test)
    exactitud_referencia = accuracy_score(
        y_test, referencia
    )

    print("\n===== RESULTADOS DEL MODELO =====")
    print("Días totales:", len(df))
    print("Días entrenamiento:", len(X_train))
    print("Días prueba:", len(X_test))

    print(f"\nExactitud Random Forest: {exactitud:.2%}")
    print(
        "Exactitud referencia:",
        f"{exactitud_referencia:.2%}"
    )

    print("\nREPORTE DE CLASIFICACIÓN")
    print(
        classification_report(
            y_test,
            predicciones,
            labels=ETIQUETAS,
            zero_division=0
        )
    )

    print("\nMATRIZ DE CONFUSIÓN")
    print(
        confusion_matrix(
            y_test,
            predicciones,
            labels=ETIQUETAS
        )
    )

    # Guardamos también las columnas y las clases.
    joblib.dump(
        {
            "modelo": modelo,
            "caracteristicas": CARACTERISTICAS,
            "etiquetas": ETIQUETAS,
            "version": "v1.0",
        },
        RUTA_MODELO
    )

    print("\nModelo guardado en:")
    print(RUTA_MODELO)


if __name__ == "__main__":
    entrenar()
