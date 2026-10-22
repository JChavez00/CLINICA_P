# Verificación del sistema multiagente

Implementación y verificaciones del 22 de octubre de 2026, hora de Perú.

## Proveedores reales

Con las variables existentes, sin exponer claves:

- Gemini `gemini-3.5-flash-lite`: consulta del modelo y generación mínima correctas.
- GroqCloud `openai/gpt-oss-20b`: presente en el catálogo y generación mínima correcta.
- El nuevo cliente compartido de cada proveedor devolvió un plan JSON que pasó
  el contrato Pydantic con una solicitud genérica, sin datos del proyecto.
- No se cambió ningún identificador silenciosamente. La consulta individual de
  Groq con un identificador que contiene barra devolvió 404; se verificó después
  mediante el catálogo y la generación real, que sí funcionaron.

Las llamadas reales de verificación se hicieron separadamente de las pruebas
automatizadas. Estas últimas siempre usan mocks y no consumen APIs externas.

## Pruebas automatizadas

Resultado final: **52 pruebas aprobadas** (34 de agentes y 18 del ML), en
11,188 segundos. Sin llamadas externas durante la suite.

Comando:

```powershell
.\.ml-venv\Scripts\python.exe -m unittest discover -s tests -v
```

Cobertura: selección de agentes, DNI, nombres con tildes, coincidencias múltiples,
selección autorizada y contexto, paciente inexistente, datos sensibles ausentes
en argumentos de proveedores y auditoría, agregados, comparación de períodos,
campos inexistentes, reportes, PDF y Excel, colaboración opcional, confirmación
firmada y CSRF, tareas idempotentes, reintentos limitados, activación/desactivación,
ejecución manual, calidad/incompletitud/duplicados, fallos Gemini/Groq, planes
maliciosos, cambios de alcance rechazados, conclusiones no sustentadas, límites,
permisos, páginas independientes, DDL PostgreSQL y las pruebas existentes del ML.

Se utiliza SQLite en memoria y fixtures locales desechables. Los casos de
duplicados/incidencias no se insertaron en la base original. El módulo ML mantiene
sus 18 pruebas y no se modificaron entrenamiento, inferencia ni artefactos en
esta ampliación de agentes.

Comprobaciones adicionales:

```powershell
node --check static/js/agentes.js
node --check static/js/asistente_ia.js
.\.ml-venv\Scripts\python.exe -m pip check
git diff --check
```

## Navegador y documentos

Se usó una copia aislada de SQLite con los proveedores simulados para comprobar
la interfaz sin enviar datos ni crear tareas en la base original:

- Navegación y autenticación temporal local.
- Reporte 2026-01-01 a 2026-09-30: 1.000 atenciones y 373 pacientes distintos.
- Gráfico mensual y tabla diaria correctos; sección ML diferenciada del histórico.
- Vista previa de tarea sin persistencia, confirmación explícita y ejecución manual.
- Calidad: 1.420 registros revisados (420 pacientes + 1.000 atenciones), sin
  incidencias en las reglas implementadas para ese dataset. No equivale a
  certificar que cada expediente esté clínicamente completo.
- PDF exportado, extraído y renderizado: dos páginas, cifras correctas,
  gráfico vectorial y encabezado de pronósticos unido a su tabla.
- Excel exportado y vuelto a abrir: valores/cantidades tipadas y gráfico nativo.

Captura de la vista previa: `docs/agentes-reportes.png`.

## Base original y producción

Se crearon las cuatro tablas nuevas en la base SQLite local con creación aditiva.
No se alteraron pacientes, atenciones, historial diario ni pronósticos ML.
Se ejecutó el comando del programador local sin tareas confirmadas: no generó
informes ni tareas, y registró su revisión técnica. El cron remoto no se activó.

PostgreSQL: compilación del DDL y uso de su dialecto para reclamos idempotentes;
no hubo una prueba contra una instancia viva. No se conectó a Supabase, no se
desplegó a Render y no se modificaron datos productivos.

## Limitaciones confirmadas

Servicios, médicos responsables y costos/ingresos no existen en el esquema
actual: sus consultas y controles quedan explícitamente como no disponibles.
Notificaciones únicamente en el panel; no existe envío de correo o mensajería.
La cuenta sigue siendo compartida; los permisos son capacidades de configuración
globales. El cron externo y la prueba real de PostgreSQL requieren activación y
un entorno autorizado. Las conclusiones usan redacción controlada, sin prosa
numérica libre del modelo.
