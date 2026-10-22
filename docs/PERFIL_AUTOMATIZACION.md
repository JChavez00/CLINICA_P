# Perfil, automatización, archivos y notificaciones

Implementación local de la ampliación de CLINICA_P. No se crearon servicios,
buckets ni credenciales externos; no se desplegó ni modificó producción.

## Uso local

1. Instalar `requirements.txt` en el entorno del proyecto.
2. Respaldar la base y ejecutar `python -m llm.cli inicializar` contra la base
   **autorizada**. En esta computadora se verificó explícitamente la SQLite local.
3. Iniciar Flask e ingresar con el usuario y contraseña existentes.
4. Abrir **Mi perfil**, completar nombre, correo y zona `America/Lima`; guardar.
5. Configurar correo externo antes de solicitar verificación. Activar los avisos
   y elegir eventos. La verificación exige abrir el enlace, iniciar sesión y
   confirmar con un formulario CSRF. Caduca a los 30 minutos.
6. Crear una tarea en Automatización, revisar su próxima ejecución y confirmar.
7. Consultar resultados, descargas y Notificaciones; marcar los avisos leídos.

La autenticación continúa en `/login`, con la misma sesión Flask. Sólo existe
una cuenta principal, ID 1. La contraseña de entorno se valida y se migra a un
hash scrypt al primer acceso correcto. También puede inicializarse desde una
sesión heredada autenticada o al asociar tareas antiguas de esta misma cuenta.
No se cambia el usuario ni se generan contraseñas nuevas. Una vez persistido el
perfil, el hash es la autoridad: cambiar `APP_PASSWORD` no permite saltárselo.
Cambiar contraseña exige la actual, 12–128 caracteres nuevos y cierra las
sesiones mediante un número de versión. El login incorpora CSRF.

`APP_PASSWORD` sólo sirve para la transición inicial. Después de verificarla,
puede retirarse del entorno desplegado siguiendo el procedimiento operativo
de respaldo y recuperación de la clínica. No borrar el perfil para recuperar
acceso: restaurar una copia o aplicar un restablecimiento administrado autorizado.
La aplicación no implementa recuperación de contraseña por correo.

## Datos y migración

Se reutilizan `agente_tareas`, `agente_tarea_ejecuciones`, `agente_informes` y
`agente_ejecuciones`. Se añaden únicamente cinco tablas:

| Tabla | Contenido |
|---|---|
| `cuenta_perfil` | Cuenta principal, hash, preferencias y verificación |
| `cuenta_tareas` | Propietario, nombre, zona, próxima y última ejecución |
| `cuenta_notificaciones` | Bandeja, deduplicación y estado de correo |
| `cuenta_archivos` | PDF/Excel, hash, vínculo al informe/tarea y estado de réplica |
| `cuenta_programador` | Revisiones separadas por origen |

La migración crea tablas con comprobación previa; no elimina ni altera tablas
clínicas, ML o de agentes. Las tareas antiguas se asocian al perfil cuando éste
existe o al usarlas, sin perder su configuración ni historial. No crea la cuenta
durante `inicializar` si todavía no existe. Usa tipos y upserts de SQLite y
PostgreSQL. Respaldar antes de ejecutar contra producción autorizada.

Los informes antiguos conservan sus snapshots y siguen descargándose. Para
crear sus archivos persistentes o reintentar réplicas de Storage:

```sh
python -m llm.cli archivar-reportes
```

Este comando puede contactar Storage si está configurado. Usarlo primero con
informes sintéticos en una base de pruebas autorizada. No borra informes.

## Programación y recuperación

El perfil define la zona por defecto para tareas **nuevas**. Cambiarla no mueve
silenciosamente tareas existentes; editar cada programación y confirmar.
Se admiten horas enteras, diario, semanal y mensual (días 1–28). La vista previa
muestra el próximo instante futuro. Las fechas se guardan en UTC y se calculan
con `zoneinfo`; 08:00 en Lima equivale a 13:00 UTC. Las tablas muestran sus
instantes en horario de Perú y también la zona configurada de cada tarea.

El comando independiente `python -m llm.cli ejecutar` revisa vencimientos sin
servidor web. Conserva una ocurrencia pendiente por tarea y revisión, incluyendo
las omitidas durante una interrupción. Un atraso extenso se recupera
progresivamente. Al reactivar una tarea pausada se calcula la siguiente hora
futura, sin ejecutar el tiempo en que estuvo desactivada.

El reclamo atómico conserva la clave única tarea/fecha. Reintenta hasta tres
veces, recupera un reclamo interrumpido después de diez minutos y comprueba el
número de intento antes de finalizar para que un proceso antiguo no sustituya
un resultado recuperado. Si agotó intentos, conserva el error y avanza a la
siguiente ocurrencia en la próxima revisión. Los informes tienen ID determinista.
Después de una caída entre resultado y actualización de calendario, una revisión
posterior completa las notificaciones y el avance sin repetir el informe.

**Ejecutar ahora** utiliza la misma clave diaria: repetirlo ese día no fuerza
otra copia. No cambia por sí solo la próxima fecha automática; la revisión
programada reconoce el resultado ya completado. No editar mientras hay un
reclamo en curso. Las duraciones se conservan en el resultado de la ejecución.

El reporte diario cubre el día anterior; el semanal los siete días cerrados
anteriores y el mensual el mes anterior completo, relativos a la ocurrencia.
Las alertas leen emisiones ML guardadas; no entrenan ni generan pronósticos.
Se deduplican por cuenta/fecha objetivo aunque existan varias tareas. Son
avisos experimentales, sin convertir predicciones en certezas.

## Render: activación pendiente

1. Preparar una base PostgreSQL de pruebas de Supabase, respaldos y variables.
2. Instalar dependencias y ejecutar `python -m llm.cli inicializar` en esa base.
3. Mantener el servicio web `gunicorn app:app`, Python 3.12 y el mismo repositorio.
4. Revisar `render.agentes.yaml.example`. Crear un **Cron Job** separado sólo
   después de autorizar el recurso y sus cargos en Render.
5. Build: `pip install -r requirements.txt`. Comando: `python -m llm.cli ejecutar`.
   Schedule: `*/5 * * * *`. Render interpreta el cron en UTC; Python convierte
   los horarios. La demora normal puede alcanzar cinco minutos más el tiempo
   de arranque/ejecución; no garantiza puntualidad al segundo.
6. Compartir con el cron `DATABASE_URL`, credenciales de proveedores, modelos,
   configuración de correo/Storage y artefactos ML. Definir `RENDER_CRON_JOB=true`
   **sólo** en ese servicio. El comando rechaza SQLite bajo esa marca.
7. Crear y confirmar una tarea de prueba con datos sintéticos. Revisar Runs,
   logs, archivos y Notificaciones. Comprobar dos ejecuciones naturales sucesivas
   antes de afirmar que el cron funciona de forma continua.
8. Tras validar PostgreSQL, correo y Storage, repetir migración/despliegue contra
   producción únicamente con autorización. No copiar bases de pruebas sobre ella.

El panel muestra por separado `render_cron`, `comando_manual` e `interfaz_manual`.
Una marca Render de más de 20 minutos produce advertencia de falta de evidencia
reciente. `RENDER_CRON_JOB` es una declaración del entorno, no una consulta a la
API de Render: una ejecución disparada manualmente desde el propio servicio de
cron también porta esa marca. Revisar el historial real de Runs para confirmar
su cadencia. Render no ofrece disco persistente a los cron jobs; por eso ni
calendario ni archivos dependen del sistema de archivos del proceso.

Referencia: [Cron Jobs de Render](https://render.com/docs/cronjobs).

## Almacenamiento y Supabase

Los nuevos PDF y Excel se generan una vez y se guardan como bytes en
`cuenta_archivos`, con SHA-256 y metadatos. En SQLite sobreviven a reinicios de
la aplicación mientras se conserve la base local. En producción deben vivir
en PostgreSQL persistente, con respaldos. Los bytes en DB son también la copia
de recuperación si falla Storage; esto incrementa el tamaño de la base y debe
incluirse en su planificación de capacidad. No se configura borrado automático.

Para activar la réplica en Supabase Storage:

1. Crear manualmente un bucket llamado `clinica-reportes` con **Public desactivado**.
2. Permitir MIME PDF y XLSX y un límite de tamaño adecuado a los informes.
3. Guardar `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` y `REPORTES_BUCKET` en los
   entornos web y cron. La clave de servicio se utiliza sólo desde Python y
   tiene privilegios elevados; nunca ponerla en HTML, JavaScript ni un repositorio.
4. No crear políticas públicas de lectura. Esta aplicación usa su propia sesión
   Flask, no Supabase Auth: la autorización se realiza antes de la descarga.
5. Probar con un reporte sintético, comprobar objetos y estado `supabase_y_base`.
6. Ejecutar `archivar-reportes` para informes anteriores o réplicas pendientes.

Antes de subir se consulta la configuración del bucket; se rechaza si es público.
Cada objeto utiliza UUID, `x-upsert=false` y ruta privada. En un reintento con
objeto existente se compara su hash sin sobrescribirlo. No se crean buckets
automáticamente ni se devuelven URLs públicas o claves al cliente.

Las descargas pasan por las rutas autenticadas existentes, validan capacidad de
reportes y propietario de archivos y comprueban SHA-256. Se sirven desde la
copia durable de DB. Los estados distinguen `base_persistente`,
`base_replica_pendiente`, `error_bucket_no_privado` y `supabase_y_base`.

Referencia: [Buckets privados de Supabase](https://supabase.com/docs/guides/storage/buckets/fundamentals).

## Correo con Resend

No se encontró SMTP ni otro proveedor en el repositorio. Se implementó una
interfaz `enviar()` con Resend mediante HTTPS y `requests`, ya instalado.
Esta elección evita depender de puertos SMTP que Render bloquea en servicios
gratuitos. Cambiar de proveedor requiere implementar esa interfaz y preservar
la idempotencia, no modificar los cinco agentes.

1. Crear/configurar la cuenta del proveedor con autorización.
2. Verificar el dominio remitente y publicar los registros DNS requeridos.
3. Crear una clave de envío y configurar `RESEND_API_KEY`, `MAIL_FROM` y
   `APP_PUBLIC_URL=https://...` en web y cron. Usar la URL pública propia de la
   clínica; no una URL de Storage ni una dirección externa arbitraria.
4. Guardar el destinatario desde Mi perfil y solicitar su enlace de verificación.
5. Confirmar el enlace iniciando sesión; activar avisos y eventos deseados.
6. Generar un reporte sintético para comprobar aceptación y entrega. Revisar
   los eventos del proveedor y la bandeja del destinatario.

Avisos: reporte disponible, error de reporte, posible demanda ALTA, resumen
mensual y error de tarea. Los correos sólo contienen un título administrativo y
un enlace a la bandeja autenticada. No incluyen cifras clínicas, DNI, nombres
de pacientes, diagnósticos, domicilios, historias ni adjuntos. El mensaje de
verificación sólo contiene el enlace de confirmación.

El outbox reclama mensajes atómicamente, utiliza `Idempotency-Key` y registra
`aceptado_proveedor` únicamente si Resend devuelve un identificador. Eso no
acredita entrega final: no se integraron webhooks de rebote o entrega.
Reintentos: máximo tres, separados por un reclamo de cinco minutos y sólo
dentro de las primeras 23 horas del aviso. La ventana es deliberadamente menor
que la retención de 24 horas de idempotencia de Resend. Después se marca
`agotado` para evitar duplicados tardíos. Los avisos pendientes no se reenvían
a otro correo si cambia el destinatario tras un primer intento.

Sin claves, destinatario verificado o consentimiento, el aviso conserva el
estado pendiente/desactivado y la tarea sigue funcionando. El comando de tareas
procesa el outbox aun sin tareas vencidas. No se envía correo simplemente por
abrir la página de perfil. No se hicieron envíos reales durante las pruebas.

Fuentes: [idempotencia de Resend](https://resend.com/docs/dashboard/emails/idempotency-keys),
[restricción SMTP de Render](https://render.com/changelog/free-web-services-will-no-longer-allow-outbound-traffic-to-smtp-ports).

## Variables

| Variable | Uso |
|---|---|
| `DATABASE_URL` | SQLite local / PostgreSQL Supabase en producción, compartida con cron |
| `SECRET_KEY` | Sesiones y firma de borradores; fuerte, privada y estable |
| `APP_USERNAME`, `APP_PASSWORD` | Cuenta existente; bootstrap, nunca contraseñas nuevas automáticas |
| `APP_PUBLIC_URL` | Origen HTTPS propio para correo y verificación |
| `RESEND_API_KEY`, `MAIL_FROM` | Clave y remitente verificado de correo |
| `SUPABASE_URL` | URL HTTPS del proyecto, no la URI PostgreSQL |
| `SUPABASE_SERVICE_ROLE_KEY` | Clave de servicio sólo de servidor |
| `REPORTES_BUCKET` | Bucket privado, sugerido `clinica-reportes` |
| `RENDER_CRON_JOB` | `true` sólo en el cron; distingue su origen y exige PostgreSQL |
| `GEMINI_API_KEY`, `GROQ_API_KEY` | Credenciales existentes de agentes |
| `GEMINI_MODEL`, `GROQ_MODEL` | Modelos existentes; sin cambio de proveedor |
| `ML_MODEL_DIR` | Artefactos ML ya versionados |
| `AGENTES_TIMEOUT`, `AGENTES_PERMISOS` | Límites/capacidades existentes |

Ejemplos sin secretos: `perfil.env.example` y `render.agentes.yaml.example`.

## Pruebas y límites comprobados

Ejecutar `python -m unittest discover -s tests -v`, `python -m pip check`,
`node --check static/js/agentes.js` y `node --check static/js/cuenta.js`.
Las pruebas aíslan SQLite y simulan correo y Storage. Las pruebas anteriores
de ML y agentes permanecen. Se ajustó exclusivamente el reloj de la fixture de
tareas para que su creación preceda al vencimiento congelado; las comprobaciones
de idempotencia y tres reintentos se mantienen.

Se compila el DDL PostgreSQL; falta ejecutar la migración, reclamos concurrentes
y descarga/subida contra una instancia PostgreSQL de pruebas autorizada.
También falta validar servicios reales de Render, Supabase Storage y Resend.
La comprobación visual usa una base temporal sin pacientes, otra cuenta de
pruebas y el navegador local. No se usan sus credenciales en la base clínica.

## Archivos de esta ampliación

Nuevos: `llm/perfil.py`, `llm/cuenta_web.py`, `llm/migraciones.py`,
`llm/programacion.py`, `llm/almacenamiento.py`, `llm/notificaciones.py`,
`templates/perfil.html`, `templates/notificaciones.html`,
`templates/verificar_correo.html`, `static/js/cuenta.js`, `tests/test_cuenta.py`,
`perfil.env.example`, esta guía y `docs/PERFIL_RESULTADOS.md`.
Capturas: `docs/perfil.png`, `docs/automatizacion-perfil.png`.

Modificados: `app.py`, `models.py`, `llm/tareas.py`, `llm/reportes.py`,
`llm/rutas.py`, `llm/cli.py`, `templates/base.html`, `templates/login.html`,
`templates/agentes.html`, `static/js/agentes.js`, `static/css/agentes.css`,
`requirements.txt`, `render.agentes.yaml.example`, `tests/test_agentes.py`,
`README.md` y `docs/AGENTES.md`. No se modifican los modelos/entrenamiento ML,
prompts ni proveedores de los cinco agentes.
