# Coordinación y evidencia de ejecución

La página **Actividad de agentes** muestra las últimas 50 ejecuciones y permite
seleccionar una por su enlace permanente. Los indicadores corresponden a esa
ventana, no a todo el historial ni a un estudio comparativo de rendimiento.

Cada resultado nuevo del asistente, los reportes, la calidad y las vistas previas
de tareas incluye **Ver recorrido**. La confirmación de una tarea también enlaza
su operación local con el borrador firmado. La evidencia JSON se descarga desde
el detalle, con autenticación y permiso de auditoría. La vista ofrece impresión
para guardar una copia PDF o capturar el diagrama para el informe.

## Qué representa

El coordinador es código Python: selecciona un agente permitido según módulo e
intención. Cada agente consulta a su proveedor para proponer un plan. Python
valida la herramienta y sus argumentos, ejecuta la operación local y, cuando
corresponde, verifica la interpretación del proveedor contra hechos permitidos.
Los expedientes individuales permanecen dentro del sistema.

Se registran únicamente las etapas que se ejecutan. Los tiempos son diferencias
del reloj monotónico en milisegundos y abarcan la etapa y sus comprobaciones;
no son latencias puras de la API ni una medición del beneficio de usar agentes.
La duración global se mide hasta preparar el resultado, antes de persistir su auditoría.
Una ejecución finalizada con respaldo local se distingue de una respuesta que
superó la validación del proveedor. Los fallos muestran códigos controlados.

En **Reportes inteligentes**, activar **Solicitar revisión adicional del analista
Groq** produce dos ejecuciones enlazadas mediante `flujo_id` y `padre_id`: el
generador Gemini y el analista Groq. El analista vuelve a consultar estadísticas
del mismo período; no lee el PDF, no critica el texto del generador y no recibe
una conversación entre modelos. Es una revisión agregada complementaria bajo
coordinación de Python. Sin esa opción sólo participa el generador.

En tareas se distingue la preparación del borrador de la confirmación humana.
La segunda es una operación local, no una nueva llamada a un agente LLM. Una
tarea confirmada todavía requiere un programador externo para ejecutarse sola.
Los registros de cron y ejecución manual que sólo conservan duración/estado
se identifican como parciales; no se inventan etapas para ellos ni se enlazan
operaciones por simple proximidad de fechas.

## Persistencia y despliegue

La nueva tabla aditiva `agente_recorridos` guarda proveedor, modelo, vínculo de
flujo y etapas técnicas. Su clave referencia `agente_ejecuciones`. No almacena
preguntas, parámetros, DNI, nombres, resultados clínicos ni errores del proveedor.
Los registros anteriores conservan su información global y aparecen sin etapas.
La instrumentación requiere el mismo rol backend de las demás tablas de agentes.

Local: `python -m llm.cli inicializar` crea la tabla de forma idempotente.
La aplicación también la crea con el esquema al iniciar.
Supabase: ejecutar `docs/SUPABASE_RECORRIDOS_AGENTES.sql` antes de desplegar el
commit en Render. La tabla queda con RLS y sin permisos para `anon` ni
`authenticated`, siguiendo el acceso existente a través del backend Flask.
La migración completa `SUPABASE_MIGRACION.sql` ya incluye esta tabla.

## Evidencias sugeridas para el informe

1. Generar un reporte del mes con revisión Groq seleccionada, abrir su recorrido
   y capturar tanto sus etapas como los dos participantes enlazados.
2. Descargar el JSON de cada participante y registrar sus IDs, fecha, proveedor,
   modelo, herramienta, estado y duración junto a la captura.
3. Preparar una tarea, revisar el borrador y confirmarla; capturar el vínculo con
   la confirmación humana y explicar el límite del programador externo.
4. Documentar una ejecución con respaldo local o error, mostrando qué validación
   falló y qué información pudo devolverse de manera determinista.
5. Ejecutar una consulta individual de ficha y comprobar que el archivo de
   evidencia no contiene sus identificadores ni contenido clínico.

Estas capturas prueban trazabilidad y la coordinación implementada. No demuestran
por sí solas mayor exactitud, reducción de tiempo o superioridad frente a un
agente único. Para esas conclusiones se necesita un experimento comparativo.
Las pruebas automatizadas usan proveedores simulados; las evidencias para afirmar
funcionamiento de Gemini/Groq en producción deben obtenerse del despliegue real.

La captura `recorrido-agentes.png` ilustra la revisión visual local con proveedores
simulados; no debe presentarse como evidencia de latencia de las APIs reales.
`coordinacion-agentes.png` muestra el vínculo visual entre generador y analista
en esa misma comprobación. Se aprobaron 91 pruebas en la revisión completa,
incluidas privacidad de la exportación, autenticación/permisos, orden temporal
de etapas, respaldo ante fallos, vínculos entre agentes y confirmación humana.
