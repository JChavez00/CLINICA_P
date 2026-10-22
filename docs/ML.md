# CLINICA_P · módulo de demanda y cantidad de atenciones

## Estado y alcance

Implementación independiente de Gemini/Groq. Cinco clasificadores y cinco
regresores, comparación temporal, dos ganadores, inferencia manual, emisiones
automáticas persistidas y cuatro secciones de dashboard en `/demanda`.
No se desplegó ni se modificó Supabase. Se añadió exclusivamente la tabla
`ml_pronosticos_v2` a la base SQLite local, sin alterar las tablas anteriores.
El archivo `ml/modelo_demanda.joblib` original se conserva.

## Archivos

Nuevos:

- `ml/datos.py`: auditoría, fechas de Perú y características de calendario.
- `ml/algoritmos.py`: cinco familias de clasificadores y regresores.
- `ml/artefactos.py`: publicación versionada, metadatos, integridad y caché.
- `ml/pronosticos.py`: generación idempotente y comparación con observaciones.
- `ml/runtime.py`, `ml/cli.py`: comandos sin importar el servidor ni el chatbot.
- `ml/feriados.json`: calendario manual explícito, inicialmente vacío.
- `ml/modelos_entrenados/actual.json` y su carpeta de versión: diez modelos y métricas reales.
- `tests/test_ml.py`: pruebas con copia de agregados históricos existentes.
- `render.ml.yaml.example`: configuración revisable de cron; no activa servicios.
- `docs/ML.md`, `docs/ML_RESULTADOS.md`: operación y resultados de esta implementación.

Modificados:

- `ml/entrenar_modelo.py`, `ml/predecir_demanda.py`, `ml/demanda_web.py`.
- `models.py`: nuevo modelo `MLPronostico`, sin cambiar los anteriores.
- `templates/demanda.html`, `static/js/demanda.js`, `static/css/demanda.css`.
- `requirements.txt`: versiones del stack ML usadas para entrenar.
- `.gitignore`: entornos virtuales y temporales de pruebas.
- `README.md`: enlace a esta guía.

## Datos y prevención de fuga temporal

La fuente de entrenamiento es `MLDemandaDiaria`; se contrasta con conteos diarios
de `Atencion` sin leer nombres, DNI, teléfonos, motivos ni expedientes. Fechas
duplicadas, etiquetas desconocidas, cantidades negativas/nulas, indicadores
nulos y días no cerrados provocan errores. Se ordena por fecha. Las fechas
faltantes se reportan y NO se imputan como cero. Un cero explícito sí se conserva.

No se encontró la regla que generó las etiquetas. Se preservan los valores
existentes y se reportan rangos observados; NO se reinterpretan como umbrales
oficiales. Para añadir fechas nuevas al dataset debe documentarse primero la
regla original y el cierre de cada día. Registrar una atención no crea
automáticamente una etiqueta inventada en `MLDemandaDiaria`.

Características: día semanal, mes, indicador de feriado, fin de semana y día
del mes. Se omiten rezagos: no se conocen cantidades futuras durante un
pronóstico de 30 días. Los objetivos nunca se utilizan como entradas.

Los indicadores históricos de feriado son los del dataset. Para fechas futuras,
editar `ml/feriados.json`, por ejemplo con un mapa `fechas` de claves ISO y valores
booleanos **confirmados por el administrador**. No se incluye un calendario
oficial ni se asegura que una fecha ausente no sea feriado. Se asume `false`
y se advierte. El calendario queda congelado en los metadatos de cada versión;
para cambiar el calendario automático, publicar una nueva versión entrenada.
La consulta manual permite confirmar un feriado sin entrenar ni guardar.

## Entrenamiento y persistencia

Separación cronológica: primeros 80 % para desarrollo, últimos 20 % reservados.
Tres ventanas expansivas (`TimeSeriesSplit`) dentro del primer 80 %. Cada pipeline
ajusta `StandardScaler` sólo en su entrenamiento. No se hace búsqueda de
hiperparámetros ni selección sobre la prueba final.

Se comparan cinco familias y referencias sobre las mismas ventanas. Clasificación
selecciona F1 macro, con accuracy y recall como desempate. Regresión selecciona
MAE, con RMSE como desempate. Las métricas de validación se calculan sobre las
predicciones concatenadas fuera de muestra, y también se guardan por ventana.
La prueba final se ejecuta sólo para cada ganador y su referencia: el dashboard
no presenta los demás como si hubieran sido evaluados sobre ese conjunto.

Los diez modelos finales se ajustan con el 80 % inicial. Se conserva ese ajuste
para que las métricas reservadas correspondan al artefacto servido, en lugar de
reajustarlo después con los resultados que se acaban de evaluar. Reentrenar con
nuevos datos crea otra versión; no borra ni sobrescribe la anterior.

Referencias: clase más frecuente y media del entrenamiento. Mejora orientativa:
más de 0,02 puntos de F1 macro o reducción de MAE mayor al 5 %, en validación y
prueba. No es una prueba de significación. TODOS los pronósticos siguen siendo
experimentales, incluso si superan ese criterio.

Cada carpeta `v2-...` guarda `modelos.joblib` y `metricas.json`: algoritmos,
configuración, características, período, cantidad de registros, entrenamiento,
ventanas, métricas, clases, ganadores, importancia de árboles y SHA-256. El
puntero `actual.json` cambia mediante reemplazo atómico. Se valida versión de
scikit-learn e integridad al cargar y se cachean paquetes por ruta y hash.
Joblib puede ejecutar código: usar exclusivamente artefactos propios y confiables.
No hay endpoint para subir modelos. El hash detecta alteraciones, no sustituye
la confianza en el origen de los archivos.

`predecir_demanda()` conserva el contrato antiguo y usa v2 si hay puntero actual;
en instalaciones todavía sin v2 puede usar el archivo v1 original. La nueva
comparación de diez modelos requiere v2 y responde 503 si falta.

## Instalar y ejecutar localmente (PowerShell)

Se probó con Python 3.12.14. Los antiguos `venv` y `.venv` no se alteraron; se
creó `.ml-venv`. Para una instalación nueva:

```powershell
py -3.12 -m venv .ml-venv
.\.ml-venv\Scripts\python.exe -m pip install -r requirements.txt
```

Los comandos usan la configuración existente de `.env`. Para operar sobre una
base específica, añadir `--database` con su URI SQLAlchemy. Ejemplo explícito de
la base local analizada (sin utilizar credenciales productivas):

```powershell
.\.ml-venv\Scripts\python.exe -m ml.cli auditar --database sqlite:///C:/Users/USER/Downloads/clinica-app/clinica-app/instance/policlinico_ficticio.db
.\.ml-venv\Scripts\python.exe -m ml.cli entrenar --database sqlite:///C:/Users/USER/Downloads/clinica-app/clinica-app/instance/policlinico_ficticio.db
.\.ml-venv\Scripts\python.exe -m ml.cli inicializar --database sqlite:///C:/Users/USER/Downloads/clinica-app/clinica-app/instance/policlinico_ficticio.db
.\.ml-venv\Scripts\python.exe -m ml.cli pronosticar --dias 30 --database sqlite:///C:/Users/USER/Downloads/clinica-app/clinica-app/instance/policlinico_ficticio.db
```

`inicializar` sólo crea la tabla nueva con `checkfirst=True`. Es una migración
aditiva inicial; no elimina ni transforma tablas existentes. No hay `drop_all`.
Entrenar y auditar son operaciones de lectura sobre la base; escriben artefactos
sólo en el directorio ML. Generar pronósticos escribe sólo la tabla nueva.

Horizontes explícitos con la base ya configurada:

```powershell
.\.ml-venv\Scripts\python.exe -m ml.cli pronosticar --dias 7
.\.ml-venv\Scripts\python.exe -m ml.cli pronosticar --dias 15
.\.ml-venv\Scripts\python.exe -m ml.cli pronosticar --dias 30
```

`--inicio AAAA-MM-DD` es opcional, debe ser futuro. Por defecto empieza mañana,
según Perú (UTC-5). El cron de 30 días cubre también las vistas de 7 y 15.
La clave única es fecha objetivo + día de generación + objetivo + versión.
`ON CONFLICT DO NOTHING` protege SQLite y PostgreSQL incluso ante concurrencia.
Repetir el mismo día no cambia emisiones existentes; un nuevo día conserva una
nueva emisión, sin perder lo que se había pronosticado antes.

## Render y Supabase (preparado, no desplegado)

1. Mantener `DATABASE_URL` actual y las credenciales fuera del repositorio.
2. Usar Python 3.12 y `pip install -r requirements.txt` en web y cron.
3. Incluir en el mismo commit de ambos servicios la carpeta de artefactos propios,
   `actual.json`, métricas y modelos. Tamaño actual del Joblib: aproximadamente
   1,8 MB. No se comparte un disco local entre servicios.
4. Ejecutar, con autorización en producción, una vez:
   `python -m ml.cli inicializar` sobre la base correspondiente.
5. Mantener el arranque web `gunicorn app:app`.
6. Crear un Cron Job con el mismo repositorio, commit y `DATABASE_URL`. Comando:
   `python -m ml.cli pronosticar --dias 30`.
7. Programación propuesta: `0 6 * * *` (06:00 UTC = 01:00 de Perú).
8. Opcional: `ML_MODEL_DIR=./ml/modelos_entrenados` en ambos servicios.
9. Probar el cron con ejecución manual y consultar `/demanda` autenticado.

El ejemplo `render.ml.yaml.example` no activa recursos ni implica contratación.
Los cron jobs de Render no acceden a discos persistentes: las emisiones se
guardan en PostgreSQL. Los artefactos se distribuyen junto al código, no se
entrenan durante cada visita ni se confía en archivos efímeros del cron. Para
actualizar modelos, entrenar en un entorno autorizado y publicar la nueva
carpeta y el puntero en ambos servicios. No activar cron hasta tener la misma
versión en web y tarea.

Referencias oficiales:
- https://render.com/docs/cronjobs (horarios UTC y almacenamiento externo).
- https://render.com/docs/disks (discos no compartidos con cron).
- https://scikit-learn.org/stable/modules/cross_validation.html#time-series-split

## API y navegador

Todas las rutas del blueprint requieren sesión; las API responden 401 en JSON.

- `/demanda`: dashboard y explicaciones.
- `/api/demanda?fecha=AAAA-MM-DD&dias=7`: resumen y emisiones guardadas.
- `/api/ml/modelos`, `/api/ml/comparacion`, `/api/ml/metricas`: metadatos reales.
- `/api/ml/pronosticos?fecha=AAAA-MM-DD&dias=30`: emisiones e históricos.
- `/api/ml/predecir?fecha=AAAA-MM-DD`: los diez modelos, sin guardar ni entrenar.
- Parámetro manual opcional `feriado=true` o `feriado=false`.
- Se mantiene `/ml/predecir/<fecha_str>` y el nombre del blueprint original.

Iniciar la aplicación sin debug:

```powershell
.\.ml-venv\Scripts\python.exe -m flask --app app run --host 127.0.0.1 --port 5000
```

Abrir `http://127.0.0.1:5000/login`, entrar con las credenciales ya configuradas
y elegir **Predicción de demanda**. Revisar:

1. Tarjetas: historial, dos ganadores, mañana y última emisión en hora de Perú.
2. Filtros 7/15/30, calendario y detalle de cada fecha. Cambiar a un período
   observado para consultar datos reales y pronósticos anteriores, si existen.
3. Tablas y gráficos de F1/MAE, prueba reservada, matriz de confusión y clases.
4. Reglas administrativas y advertencias de confiabilidad.
5. Consulta manual futura: cinco resultados de cada objetivo, probabilidades y
   ganadores. Cambiar feriado y comparar sin reentrenar.
6. Sección de explicaciones y métricas del entrenamiento actual.

Chart.js 4.4.8 se carga desde CDN. Si no está disponible, se informa el problema
y las tablas mantienen accesibles los resultados; no se requiere framework.
La inferencia manual no guarda un pronóstico automático. Las lecturas HTTP
tampoco generan emisiones. La tabla conserva estado `generado`; al consultar,
se deriva `observado` o `vencido_sin_observacion` según los datos disponibles.
Los históricos se distinguen siempre de las emisiones anteriores. Un día
observado en `Atencion` sin etiqueta diaria muestra cantidad real y nivel
desconocido, sin presentar una etiqueta predicha como observada.

## Pruebas

```powershell
.\.ml-venv\Scripts\python.exe -m unittest discover -s tests -v
.\.ml-venv\Scripts\python.exe -m pip check
node --check static/js/demanda.js
```

Las pruebas utilizan SQLite en memoria, modelos en carpeta temporal y una copia
de agregados del dataset local existente. No llaman a proveedores ni modifican
la base original. Si falta ese dataset, las pruebas dependientes se marcan como
omitidas; no se fabrica historial para reemplazarlo. Se compila el DDL PostgreSQL
y la escritura usa su dialecto, pero no se ha certificado contra una instancia
PostgreSQL viva: no se proporcionó un entorno de pruebas autorizado.

## Limitaciones y siguientes pasos

- Historial ficticio: el resultado técnico no valida decisiones operativas.
- Clasificación y cantidad son objetivos independientes y pueden discrepar.
- Regresión no supera la referencia; clasificación tiene baja exactitud y no
  detectó ALTA en la prueba actual. Ver el informe de resultados.
- Probabilidades sin calibrar y sin intervalos de regresión.
- Datos sólo de enero a septiembre; extrapolar a otros meses es incierto.
- La regla original de etiquetas y el calendario oficial siguen pendientes.
- No se añadieron atenciones ni etiquetas nuevas al historial; el administrador
  debe establecer un proceso de cierre diario y etiquetado documentado.
- Para mejorar: datos reales autorizados, cobertura anual, variables operativas
  conocidas por adelantado y evaluación temporal repetida en nuevas ventanas.
- Activación real del cron y validación en PostgreSQL requieren un entorno
  autorizado; no se realizaron operaciones productivas.
# Generar emisiones desde la web

El panel permite guardar pronósticos sin usar la terminal de Render: seleccionar
fecha futura y horizonte 7, 15 o 30 días y pulsar **Generar y guardar pronósticos
del período seleccionado**. Es un POST autenticado con CSRF y confirmación
explícita, limitado a los horizontes existentes. Reutiliza los diez modelos
guardados y la persistencia idempotente del cron; no reentrena ni usa LLM.
`POST /api/ml/pronosticos/generar` recibe `fecha`, `dias` y `confirmar: true`.
Las consultas GET siguen sin guardar emisiones. El cron diario es independiente
y debe configurarse para renovar automáticamente el horizonte.
