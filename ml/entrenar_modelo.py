"""Selección temporal en el 80 % inicial; prueba reservada sólo para ganadores."""
if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime, timezone
from uuid import uuid4

import numpy as np
import sklearn
from sklearn.base import clone
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.metrics import (accuracy_score, precision_score, recall_score, f1_score,
                             classification_report, confusion_matrix,
                             mean_absolute_error, mean_squared_error, r2_score)
from sklearn.model_selection import TimeSeriesSplit

from ml.algoritmos import candidatos
from ml.artefactos import publicar
from ml.datos import CARACTERISTICAS, ETIQUETAS, cargar_datos, calendario


def medir(objetivo, real, predicho):
    if objetivo == "clasificacion":
        return {"accuracy": float(accuracy_score(real, predicho)),
                "precision_macro": float(precision_score(real, predicho, labels=ETIQUETAS, average="macro", zero_division=0)),
                "recall_macro": float(recall_score(real, predicho, labels=ETIQUETAS, average="macro", zero_division=0)),
                "f1_macro": float(f1_score(real, predicho, labels=ETIQUETAS, average="macro", zero_division=0))}
    predicho = np.maximum(0, predicho)
    return {"mae": float(mean_absolute_error(real, predicho)),
            "rmse": float(np.sqrt(mean_squared_error(real, predicho))),
            "r2": float(r2_score(real, predicho)) if len(real) > 1 and np.var(real) > 0 else None}


def entrenar(df=None, auditoria=None, *, calendario_config=None, procedencia=None):
    if df is None:
        df, auditoria = cargar_datos()
    if len(df) < 60:
        raise ValueError("Se requieren al menos 60 días históricos cerrados.")
    if not df.fecha.is_monotonic_increasing or df.fecha.duplicated().any():
        raise ValueError("El dataset debe estar ordenado y sin fechas duplicadas.")
    corte = int(len(df) * .8)
    train, test = df.iloc[:corte], df.iloc[corte:]
    splits = list(TimeSeriesSplit(n_splits=3).split(train))
    if any(train.iloc[a].nivel_demanda.nunique() < 2 for a, _ in splits):
        raise ValueError("Faltan al menos dos clases en una ventana temporal de entrenamiento.")
    version = "v2-" + uuid4().hex[:16]
    meta = {"schema": 2, "version": version, "sklearn": sklearn.__version__,
            "fecha_entrenamiento": datetime.now(timezone.utc).isoformat(),
            "caracteristicas": CARACTERISTICAS, "etiquetas": ETIQUETAS,
            "periodo": {"desde": df.fecha.iloc[0].isoformat(), "hasta": df.fecha.iloc[-1].isoformat()},
            "registros": len(df), "atenciones": int(df.total_atenciones.sum()),
            "auditoria": auditoria or {}, "calendario": calendario_config if calendario_config is not None else calendario(),
            "metodo": "80/20 cronológico; 3 ventanas expansivas dentro del 80 %. Selección por validación. Prueba final sólo ganadores y referencias. Sin ajuste de hiperparámetros.",
            "corte": {"fin_entrenamiento": train.fecha.iloc[-1].isoformat(), "inicio_prueba": test.fecha.iloc[0].isoformat(), "dias_prueba": len(test)},
            "ventanas": [{"fin_entrenamiento": train.iloc[a[-1]].fecha.isoformat(),
                          "inicio_validacion": train.iloc[b[0]].fecha.isoformat(),
                          "fin_validacion": train.iloc[b[-1]].fecha.isoformat()} for a, b in splits],
            "resultados": {}}
    modelos = candidatos()
    configuracion = {}
    for objetivo, familia in modelos.items():
        configuracion[objetivo] = {n: {k: str(v) for k, v in m.get_params().items()} for n, m in familia.items()}
        ycol = "nivel_demanda" if objetivo == "clasificacion" else "total_atenciones"
        dummy = DummyClassifier(strategy="most_frequent") if objetivo == "clasificacion" else DummyRegressor(strategy="mean")
        comparacion = {}
        for nombre, estimador in {**familia, "Referencia": dummy}.items():
            reales, predicciones, folds = [], [], []
            for a, b in splits:
                m = clone(estimador).fit(train.iloc[a][CARACTERISTICAS], train.iloc[a][ycol])
                p = m.predict(train.iloc[b][CARACTERISTICAS])
                reales.extend(train.iloc[b][ycol].tolist())
                predicciones.extend(p.tolist())
                folds.append(medir(objetivo, train.iloc[b][ycol], p))
            comparacion[nombre] = {**medir(objetivo, reales, predicciones), "ventanas": folds}
        if objetivo == "clasificacion":
            ganador = max(familia, key=lambda n: (comparacion[n]["f1_macro"], comparacion[n]["accuracy"], comparacion[n]["recall_macro"]))
        else:
            ganador = min(familia, key=lambda n: (comparacion[n]["mae"], comparacion[n]["rmse"]))
        for nombre, estimador in familia.items():
            familia[nombre] = clone(estimador).fit(train[CARACTERISTICAS], train[ycol])
        p = familia[ganador].predict(test[CARACTERISTICAS])
        ref = clone(dummy).fit(train[CARACTERISTICAS], train[ycol]).predict(test[CARACTERISTICAS])
        final, base = medir(objetivo, test[ycol], p), medir(objetivo, test[ycol], ref)
        if objetivo == "clasificacion":
            mejora = (comparacion[ganador]["f1_macro"] > comparacion["Referencia"]["f1_macro"] + .02
                      and final["f1_macro"] > base["f1_macro"] + .02)
            detalle = {"matriz_confusion": confusion_matrix(test[ycol], p, labels=ETIQUETAS).tolist(),
                       "reporte_clases": classification_report(test[ycol], p, labels=ETIQUETAS, output_dict=True, zero_division=0)}
        else:
            mejora = (comparacion[ganador]["mae"] < comparacion["Referencia"]["mae"] * .95
                      and final["mae"] < base["mae"] * .95)
            detalle = {"real_vs_predicho": [{"fecha": f.isoformat(), "real": int(r), "predicho": round(max(0, float(v)), 3)}
                                            for f, r, v in zip(test.fecha, test[ycol], p)]}
        modelo = familia[ganador]
        importancia = dict(zip(CARACTERISTICAS, map(float, modelo.feature_importances_))) if hasattr(modelo, "feature_importances_") else None
        meta["resultados"][objetivo] = {"ganador": ganador, "validacion": comparacion,
                                      "prueba": final, "referencia_prueba": base,
                                      "mejora_demostrada": bool(mejora), "experimental": True,
                                      "importancia": importancia, **detalle}
    meta["configuracion"] = configuracion
    meta["limitaciones"] = [
        "Experimental: el historial local se describe como ficticio; no demuestra validez operativa.",
        "Modelos ajustados con el 80 % inicial: la prueba describe exactamente el artefacto servido.",
        "Sólo calendario; sin rezagos, tendencia, capacidad ni disponibilidad de personal.",
        "Probabilidades sin calibrar; no son garantía de acierto. Sin intervalos de regresión.",
        "Mejora orientativa: >0.02 F1 o reducción de MAE >5 % en validación y prueba; no es significación estadística.",
        "Feriados futuros manuales; fechas no configuradas se suponen no feriadas.",
        "Clasificación y cantidad independientes: pueden discrepar; no se inventan umbrales."]
    if procedencia is not None:
        meta["procedencia"]=procedencia
        meta["limitaciones"][0]="Escenario sintético documentado; los resultados no acreditan rendimiento sobre atenciones reales."
        if calendario_config is not None:
            meta["limitaciones"][5]=calendario_config.get("limitacion","Calendario del escenario; comprobar cobertura antes de inferir.")
    return publicar({"schema": 2, "version": version, "modelos": modelos}, meta)


if __name__ == "__main__":
    from ml.cli import main
    main(["entrenar"])
