# Verificación de perfil y automatización

Fecha: 22/10/2026. Entorno local Python 3.12, SQLite aislado y navegador local.

Resultado final: **76 pruebas aprobadas en 29,351 segundos**: 34 de agentes,
18 de ML y 24 de perfil/automatización. JavaScript, dependencias y comprobación
de espacios del diff también correctos.

Se verificaron autenticación conservada, migración a hash, actualización de
perfil, correo y zonas válidas, CSRF, contraseña actual, invalidación de otras
sesiones, confirmación de tareas, propietario, edición de programación,
próximas fechas Lima/UTC, reclamos, reintentos, recuperación de interrupciones
y ocurrencias omitidas. Se conservan las pruebas de agentes y ML anteriores.

Los archivos PDF y Excel se guardaron en DB, se compararon sus hashes y se
descargaron autenticadamente. Supabase Storage se probó con mocks: bucket
privado, rechazo de bucket público y conservación de bytes ante un fallo de red.
Correo se probó con mocks: consentimiento, dirección verificada, idempotencia,
aceptación del proveedor, ausencia de configuración y fallo sin entrega simulada.
Se verificaron bandeja leída/no leída y deduplicación de alertas ML.

No se hicieron envíos reales, subidas reales, llamadas nuevas a Gemini/Groq,
despliegues ni cambios en Supabase. El DDL PostgreSQL compila; no hay una base
PostgreSQL de pruebas autorizada con la que comprobar transacciones reales.

La revisión visual comprobó login CSRF, Mi perfil, guardado del nombre en una
base temporal sin pacientes, tabla de automatización y bandeja vacía. Capturas:
`perfil.png` y `automatizacion-perfil.png`. Esa cuenta temporal no se creó en la
base de la clínica.

En la SQLite clínica se verificó la migración aditiva: cinco tablas nuevas,
ningún perfil ni tarea de prueba creados. Conteos conservados: 420 pacientes,
1.000 atenciones, 273 observaciones ML y 60 pronósticos v2.

Comandos: `python -m unittest discover -s tests -q`, `python -m pip check`,
`node --check static/js/agentes.js`, `node --check static/js/cuenta.js` y
`git diff --check`. Las dependencias no presentan incompatibilidades.

Pendientes para producción: pruebas reales autorizadas de PostgreSQL y
concurrencia entre procesos, configurar y comprobar cron Render, bucket privado,
remitente/dominio Resend y destinatario, revisar respaldos/capacidad de DB y
realizar despliegue autorizado. La aceptación de correo por Resend no confirma
su entrega final; no se implementaron webhooks de entrega/rebote.
