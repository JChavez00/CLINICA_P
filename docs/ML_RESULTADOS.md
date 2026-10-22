# Resultados reales · implementación ML

Versión: `v2-7ad78af56fe04e24`. Entrenamiento: 21 de octubre de 2026 (Perú).

Dataset local: 273 días, 1.000 atenciones, 2026-01-01 a 2026-09-30.
218 días para entrenamiento y validación; 55 para prueba reservada desde 2026-08-07.

## Validación temporal (selección)

| Objetivo | Modelo | F1 macro / MAE | Accuracy / RMSE |
|---|---|---:|---:|
| clasificacion | Random Forest | 0.391366 | 0.395062 |
| clasificacion | Decision Tree | 0.341310 | 0.370370 |
| clasificacion | Gradient Boosting | 0.331324 | 0.358025 |
| clasificacion | KNN | 0.347491 | 0.401235 |
| clasificacion | Logistic Regression | 0.283069 | 0.302469 |
| clasificacion | Referencia | 0.225850 | 0.512346 |
| regresion | Random Forest | 1.645126 | 2.011825 |
| regresion | Decision Tree | 1.726330 | 2.144923 |
| regresion | Gradient Boosting | 1.796444 | 2.211681 |
| regresion | KNN | 1.659259 | 2.071679 |
| regresion | Ridge | 1.711610 | 2.201721 |
| regresion | Referencia | 1.569709 | 1.934206 |

## Prueba final de ganadores

### clasificacion: Random Forest

Ganador: `{"accuracy": 0.38181818181818183, "precision_macro": 0.28308823529411764, "recall_macro": 0.30050505050505055, "f1_macro": 0.2837265577737447}`.

Referencia: `{"accuracy": 0.43636363636363634, "precision_macro": 0.14545454545454545, "recall_macro": 0.3333333333333333, "f1_macro": 0.20253164556962025}`.

Supera el criterio orientativo de mejora: sí. Sigue siendo experimental.

### regresion: Random Forest

Ganador: `{"mae": 1.6930483878144797, "rmse": 1.9922617820617066, "r2": -0.11834470007429698}`.

Referencia: `{"mae": 1.6682235195996666, "rmse": 1.8855545535255958, "r2": -0.001753988666295836}`.

Supera el criterio orientativo de mejora: no. Sigue siendo experimental.

Clasificación: recall de ALTA = 0; 9 casos reales de esa clase no fueron detectados.
La accuracy del ganador (38,18 %) es inferior a la referencia (43,64 %), pese a su mejor F1 macro.
Regresión: MAE 1,693 frente a 1,668; R² negativo. No demuestra mejora frente a la media.

## Verificaciones

- Suite final: 18 pruebas aprobadas con `python -m unittest discover -s tests -v`.
- Sintaxis JavaScript: `node --check static/js/demanda.js`.
- Dependencias: `python -m pip check`.
- Navegador: acceso con cuenta temporal local, dashboard, métricas, filtro de 30 días e inferencia de diez modelos comprobados.
- PostgreSQL: compilación de esquema; no se probó conexión productiva ni base de pruebas remota.
- El Random Forest v1 permanece sin cambios; no se desplegó a Render ni se modificó Supabase.

## Persistencia local

Pronósticos v2 guardados: 60 (30 fechas × 2 objetivos).
Grupos duplicados: 0.

Se ejecutaron horizontes 30, 7 y 15 el mismo día; siguen siendo 60 registros, sin duplicación.
El cron remoto está preparado como ejemplo y comando; su activación no se realizó.
