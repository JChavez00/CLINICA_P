# Revisión de CLINICA_P para el informe técnico

> Esta revisión describe el diagnóstico anterior a la sustitución del historial.
> La base local principal ahora contiene 1.000 pacientes, 9.569 atenciones y
> 726 días agregados, con nuevos modelos activos. Las métricas y limitaciones
> vigentes están en [DATOS_SINTETICOS.md](DATOS_SINTETICOS.md).

Fecha de revisión: 23 de octubre de 2026, Perú.
Referencia: Esquema_Informe_Tecnico_Agentes_ML_Cloud.docx suministrado por el usuario.
Alcance: repositorio local, esquema y métricas persistidas, lectura agregada de
SQLite local y capturas de Render aportadas por el usuario. No se accedió ni
se modificó la base productiva; no se hicieron nuevas llamadas a proveedores.

## Dictamen

La propuesta es lógica como prototipo de automatización administrativa con
pronóstico supervisado. La aplicación ya ofrece componentes suficientes para
redactar un informe académico. Todavía no está completa como demostración
científica de mejora predictiva ni como demostración cuantificada de beneficio
multiagente. El documento recibido es una plantilla de estructura y criterios,
no un informe de resultados ya redactado ni una rúbrica con ponderaciones.
No se puede calcular una calificación ni garantizar aprobación.

La contribución defendible es una arquitectura reproducible que integra registro,
herramientas autorizadas, predicción, reportes, confirmación humana, persistencia
y auditoría. No está demostrado que reduzca tiempos de trabajo, que una IA
supere a un flujo determinista ni que el ML anticipe de forma fiable días ALTA.

## Correspondencia con el esquema de evaluación

| Criterio del esquema | Evidencia actual | Estado y trabajo necesario |
|---|---|---|
| Problema y aporte | Registro clínico y tareas administrativas delimitadas | Parcial: medir proceso actual y describir necesidad; no definir el problema como falta de una aplicación |
| Arquitectura cloud | Flask, Render, PostgreSQL, LLM, ML, sesiones y auditoría | Implementada; falta Figura 1 y registro verificable del despliegue/commit |
| Datos y variables | 273 días y cinco características; auditoría de consistencia | Parcial: declarar procedencia, selección y regla de etiquetas |
| Modelo e hiperparámetros | Cinco clasificadores y cinco regresores, configuración persistida | Implementado; explicar pertinencia y selección, no sólo enumerar algoritmos |
| Métricas y referencia | F1, accuracy, precision, recall, MAE, RMSE, R² y dos referencias | Implementado; interpretar fallos y evaluación de ALTA; AUC no está calculada |
| Roles multiagente | Cinco roles y coordinador por módulo | Implementado; autonomía acotada, no un ReAct abierto |
| Dependencias entre agentes | Programación confirmada que termina en reporte; revisión Groq opcional | Parcial: documentar un caso completo y mejorar trazabilidad entre etapas |
| Revisión humana | Confirmación de tareas, revisión de informes y sospechas de calidad | Implementada; definir responsable y criterio de aceptación |
| Pruebas | Suite automatizada, mocks, casos de privacidad y fallos | Implementada; falta tabla de pruebas reales con muestra y tiempos por caso |
| Desempeño | Duración por ejecución registrada | Parcial: medir latencia y tasa de éxito con casos y versión definidos |
| Ética y fuentes | Identificadores locales no enviados al LLM; documentación de límites | Declarar datos sintéticos y fuentes, evitar identidades reales en fichas inventadas |
| Escritura científica | Hay documentación técnica y evidencia de implementación | Pendiente: redactar informe con resumen, antecedentes, resultados y conclusiones |
| Entrega técnica | Repositorio, README, comandos y ejemplos de configuración | Completar enlace/commit de entrega, evidencias reales y requisitos reproducibles |

## Machine Learning

### Qué está bien planteado

La unidad es un día; los objetivos son cantidad de atenciones y nivel de demanda.
Se usan día de semana, mes, feriado, fin de semana y día del mes, sin identificadores
personales. Nombres y DNI no influyen en las predicciones. El conjunto local
contiene 273 días del 01/01/2026 al 30/09/2026 y 1.000 atenciones. Se comprobó
que sus conteos diarios coinciden con las atenciones locales: cero discrepancias.

La separación cronológica usa 218 días de desarrollo y 55 de prueba. Dentro del
desarrollo hay tres ventanas expansivas. El escalado está en los pipelines de
KNN y de los modelos lineales. El entrenamiento está separado de la inferencia
y de los agentes. Se conservan versión, hash, configuración y comparación con
referencias. Las fechas ausentes no se convierten automáticamente en cero.

La métrica de selección de clasificación es F1 macro, razonable para comparar
clases con frecuencias distintas. Para cantidades se selecciona por MAE. Estas
decisiones metodológicas son más importantes que tener muchos algoritmos.
La plantilla no exige cinco familias: la cantidad no reemplaza una evaluación.

### Qué dicen realmente los resultados

Artefacto revisado: v2-7ad78af56fe04e24; prueba de 55 días.

| Indicador de prueba | Random Forest seleccionado | Referencia | Interpretación |
|---|---:|---:|---|
| F1 macro | 0,2837 | 0,2025 | Mejora descriptiva en esta métrica |
| Accuracy | 38,18 % | 43,64 % | Peor que la clase más frecuente |
| Recall ALTA | 0 de 9 casos | Consultar reporte por clase | No sustenta una alerta operativa fiable |
| MAE | 1,6930 atenciones/día | 1,6682 | No supera la predicción de la media |
| RMSE | 1,9923 | 1,8856 | Peor que la referencia |
| R² | −0,1183 | −0,0018 | No explica bien la variación reservada |

La bandera `mejora_demostrada` de clasificación refleja un criterio orientativo
de F1 definido en el código; no significa significación estadística, validación
clínica, detección adecuada de ALTA ni superioridad en todas las métricas.
Los resultados negativos son válidos académicamente si se explican, no se ocultan.

### Mejoras por prioridad

1. **Fuente y objetivo.** Documentar qué datos se generaron, con qué procedimiento
   y qué se pretende validar. Para demostrar valor operativo, obtener una serie
   real de conteos diarios, autorizada o publicada, con establecimiento y período
   definidos. No atribuir datos de otra institución al policlínico.
2. **Regla de BAJA/MEDIA/ALTA.** Los rangos locales observados son 1–2, 3–5 y
   6–10, pero no se encontró la regla generadora. Definirla y justificarla antes
   de añadir etiquetas. Preferible vincular nivel a capacidad diaria documentada
   si se pretende hablar de saturación. No presentar esos rangos como oficiales.
3. **Coherencia de objetivos.** La clasificación y la regresión son independientes
   y pueden discrepar. Elegir una regla de presentación para esa discrepancia o
   derivar niveles de una estimación de carga con umbrales justificados. Cualquier
   cambio de objetivo requiere nueva evaluación; no retocar etiquetas sólo para
   mejorar el resultado.
4. **Comparaciones temporales.** Añadir referencia del mismo día de la semana
   anterior y media móvil calculada sólo con el pasado. No alcanza con superar
   una referencia constante para justificar un sistema de series temporales.
5. **Variables.** Evaluar rezagos de 1/7 días y promedios móviles desplazados, sólo
   con datos disponibles al emitir. Para 7/15/30 días decidir pronóstico recursivo
   o directo por horizonte. No introducir conteos futuros como si fueran conocidos.
6. **Calendario y cobertura.** El calendario futuro manual está vacío; completar
   con fuentes verificadas. Nueve meses no cubren un ciclo anual. Evaluar códigos
   cíclicos de día/mes y no prometer extrapolación anual con esta muestra.
7. **Validación por riesgo.** Priorizar recall ALTA y falsos negativos junto con
   precision/F1. Si se incluye AUC como pide la tabla orientativa del esquema,
   definir multiclase y reportar su método; no inventar su valor. Para cantidades,
   mostrar residuales y errores por horizonte. Calibración e intervalos son mejoras
   posteriores, no capacidades actuales.
8. **Nueva evaluación.** Congelar protocolo antes de ajustar hiperparámetros y
   usar nuevas ventanas/reserva temporal. La prueba actual ya fue examinada;
   seleccionar iterativamente con ella y seguir llamándola intocable sería incorrecto.

La documentación oficial de scikit-learn muestra cómo usar rezagos y divisiones
temporales sin fuga. Esto respalda una mejora a evaluar, no garantiza que funcione
sobre datos sintéticos sin señal temporal:
https://scikit-learn.org/stable/auto_examples/applications/plot_time_series_lagged_features.html

## Sistema multiagente

### Diseño defendible

| Agente | Entrada y función | Salida y control |
|---|---|---|
| Consultor clínico Gemini | Intención canónica; referencia identificable sólo local | Ficha local, selección controlada, lectura sin consejo diagnóstico |
| Analista Groq | Período y agregados permitidos | Estadísticas/conclusiones por códigos; no SQL ni cifras nuevas |
| Generador Gemini | Período y secciones de informe | Snapshot agregado, PDF/Excel generados por Python |
| Automatizador Gemini | Configuración administrativa canónica | Borrador firmado; requiere confirmación humana para persistir |
| Calidad Groq | Categorías agregadas calculadas por reglas | Incidencias locales y conclusiones sin corrección automática |

Son agentes especializados con selección de herramientas y salidas restringidas.
El coordinador es determinista por intención y módulo. No hay debate libre,
memoria autónoma de largo plazo, negociación ni un bucle ReAct de varias iteraciones.
El chat usa uno de dos agentes por solicitud, no los cinco simultáneamente.
No se usa LangGraph/CrewAI y no debe citarse su implementación como propia.

La planificación exige coincidir con la herramienta y parámetros ya autorizados
por Python. La redacción consiste en seleccionar y ordenar hechos controlados;
no es una generación libre de contenido clínico. Esta restricción debe explicarse
como decisión de diseño, con su beneficio de seguridad y su autonomía limitada.

### Qué falta para demostrar mejor la coordinación

El recorrido tarea preparada → confirmación → cron → agente generador → informe
es una secuencia utilizable en la defensa, pero hay que aportar evidencia de las
etapas. La revisión Groq opcional consulta de nuevo las estadísticas del período;
actualmente no inspecciona el PDF ni audita el texto de Gemini. No describirla
como crítica del documento completo. Una mejora concreta sería pasar un snapshot
agregado e inmutable del informe al revisor y conservar el vínculo entre ambos.

Añadir un identificador de proceso compartido entre borrador, tarea, ejecuciones,
informe y revisión facilitaría demostrar dependencias reales. Ya hay asociaciones
de tarea e informe en el historial; falta una correlación uniforme entre todos
los registros técnicos. La arquitectura no necesita más agentes antes de eso.

Para demostrar utilidad del LLM, comparar tareas equivalentes con el flujo
determinista y con el agente, usando aceptación correcta, latencia, fallos y
trabajo humano. No afirmar ahorro de tiempo o mejor calidad sin medirlo.

## Datos reales e identificadores

En la base **local** se encontraron 420 pacientes con identificadores numéricos
de nueve dígitos y prefijo 90. No se inspeccionó la distribución de Supabase.
El DNI peruano tiene ocho dígitos; no se justifica tratar todos los identificadores
actuales como DNI válidos. La regla de calidad actual acepta 8 o 9: esa tolerancia
heredada debe revisarse si el campo queda definido exclusivamente como DNI.

Se puede preparar una base de demostración con identificadores sintéticos de
ocho cifras y prefijos 60, 70 o 71, conservando claves y relaciones, pero esos
prefijos no certifican identidad, validez ni correspondencia con una edad.
Un número generado puede coincidir con uno asignado: no consultarlo en RENIEC
para inventar fichas ni asociarlo a nombres/historias de personas reales.
Para datos públicos anonimizados, conservar el identificador anonimizado o un
ID interno, no reconstruir un DNI.

No se modificaron DNI, pacientes, atenciones ni datos productivos en esta revisión.
Antes de una eventual normalización debe existir respaldo, mapeo único, prueba
de colisiones, revisión de exportaciones/snapshots y aplicación sólo sobre una
base de demostración identificada. Cambiar prefijos no mejora la predicción.

Se localizaron estos candidatos oficiales de datos:

- **EsSalud, Atenciones en Consulta Externa 2015–2022.** El catálogo publica CSV,
  diccionario y metadatos. Es un candidato para evaluar una serie agregada por
  establecimiento/período. Falta comprobar granularidad de fecha, completitud y
  campos antes de decidir si sirve para pronóstico diario. El acceso directo
  devolvió 403 durante la revisión; no se descargaron ni validaron los registros.
  https://www.datosabiertos.gob.pe/dataset/atenciones-en-consulta-externa-essalud
- **INEN, Pacientes Nuevos enero 2022–septiembre 2026.** La ficha indica fecha de
  filiación y cantidad acumulada de consultas. Eso no equivale a fechas de todas
  las atenciones; no sirve automáticamente para reconstruir demanda diaria.
  Sólo sería pertinente para un problema de nuevas admisiones con su definición
  y cobertura. No se importaron registros individuales.
  https://www.datosabiertos.gob.pe/dataset/listado-de-pacientes-nuevos-enero-2022-setiembre-2026-instituto-nacional-de-enfermedades-0

Fuente oficial del formato DNI:
https://www.gob.pe/13432-encontrar-d-gito-verificador-en-el-dni

La mejor alternativa para la validez externa sigue siendo el conteo diario
autorizado de la institución objetivo, sin DNI, nombres ni diagnósticos.

## Textos y rutas revisados

Se encontró una advertencia de procedencia dentro de `metricas.json`, visible
porque el panel lista las limitaciones del artefacto. Se añadió una capa de
presentación que muestra: “Evaluación limitada al conjunto disponible; requiere
validación externa antes del uso operativo”. No afirma que los datos sean reales.
La descripción original se conserva en el artefacto y en la documentación; la
respuesta de metadatos conserva procedencia sintética para auditoría.

La misma presentación se reutiliza en las advertencias ML hacia agentes y en
los nuevos reportes. Los archivos y snapshots anteriores permanecen intactos;
pueden contener el texto anterior y no se reescribieron silenciosamente.

También se retiró `/tareaPruebaApi` y su plantilla: esa ruta pública simulaba
guardar correctamente sin persistencia. Se exigió sesión para buscar DNI y
direcciones, porque esas rutas estaban públicas. No se cambió la estructura
clínica. El título “Demanda y capacidad de atención” se ajustó a “Pronóstico de
demanda de atención”: el sistema no modela aún dotación, turnos ni capacidad.

Se conservan “prueba final” y “conjunto de prueba”: son términos de evaluación
ML y no significan que el software simule resultados. También se conservan las
advertencias experimentales, limitaciones de rendimiento y referencias.

## Plan mínimo de evidencias para la entrega

1. Definir un objetivo observable y alcance: prototipo administrativo, sin
   automatización diagnóstica ni eficacia predictiva no demostrada.
2. Preparar Figura 1 con frontend, Flask, Render, PostgreSQL, almacenamiento,
   sesiones/secretos, ML, coordinador, proveedores y auditoría.
3. Preparar Tabla 1 de datos/variables y Tabla 2 de algoritmos/hiperparámetros.
   Usar valores del artefacto y citar la versión, no parámetros genéricos.
4. Preparar Tabla 3 con los 55 días de prueba, referencias, F1/recall por clase,
   MAE/RMSE/R² y una interpretación de los resultados desfavorables.
5. Usar matriz de confusión y real frente a predicho como Figura 2, con fuente
   propia y lectura técnica. Añadir residuales si se evalúan.
6. Diseñar al menos un caso normal por agente y casos de error de proveedor,
   salida inválida, consulta sin sesión, CSRF, ambigüedad de paciente, privacidad
   y cron repetido. Una muestra sugerida es 15–20 casos definidos previamente;
   no es un número exigido por la plantilla.
7. Registrar entrada sanitizada, resultado esperado/observado, agentes invocados,
   herramienta, aceptación, duración, estado, fecha, commit e ID de evidencia.
   Distinguir mocks de proveedores reales y ejecución manual de cron real.
8. Medir éxito completo, degradación, errores, latencia mediana/p95 y número de
   casos. No usar la duración total de unittest como latencia de la IA.
9. Mostrar un flujo dependiente completo como Figura 3 y su confirmación humana.
   Publicar capturas/logs sin nombres, DNI, claves ni historias.
10. Redactar antecedentes con fuentes verificadas y conclusiones que respondan
    a los objetivos. Verificar cada referencia sugerida por la plantilla antes
    de citarla; una referencia incluida en una plantilla no prueba su existencia.

## Reglas editoriales a cumplir

La plantilla propone 7–18 páginas, A4, Times New Roman 11, interlineado sencillo,
texto justificado y dos columnas separadas por 5 mm. Márgenes: superior,
inferior e izquierdo 20 mm; derecho 18 mm. Título máximo 15 palabras, resumen
de 150–200 palabras en un párrafo, 3–5 palabras clave y citas APA 7 para el curso.
Las figuras y tablas deben mencionarse antes en el texto, numerarse y llevar
fuente. No copiar archivos extensos de código dentro del informe.

Título posible de 14 palabras:
“Aplicación en la nube para automatización administrativa y predicción de demanda
en un policlínico”. Contar y ajustar el título definitivo antes de entregar.

Objetivo posible: “Implementar y evaluar un prototipo en la nube que integre
pronóstico de demanda y agentes especializados para apoyar tareas administrativas
de un policlínico, mediante métricas predictivas, pruebas funcionales y controles
de privacidad”. No anticipa una mejora que todavía no esté medida.

## Orden recomendado

Primero cerrar fuente/regla de objetivos y protocolo de evaluación. Después
documentar un flujo dependiente de agentes y medir sus casos. Finalmente
completar informe, figuras y referencias. Pulir los identificadores sintéticos
puede ayudar a la presentación, pero es secundario frente a estos tres puntos.
No se recomienda reentrenar ni añadir más agentes sólo para exhibir mejores cifras.

## Verificación de los cambios de esta revisión

84 pruebas aprobadas en 26,947 segundos con `python -m unittest discover -s tests -q`.
Los dos casos añadidos comprueban que la presentación no altere los artefactos
ni pierda la procedencia y que las consultas exijan sesión con la ruta de
simulación retirada. `git diff --check` no detecta errores de espacios.
No se entrenaron modelos, modificaron métricas, normalizaron DNI ni importaron
datos reales. Los cambios están locales y necesitan subirse a GitHub para Render.
