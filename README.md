# Registro Clínico — Consultorio

Sistema web para registrar atenciones diarias de un consultorio: buscas al
paciente por DNI (o lo registras si es nuevo), llenas los datos de la
consulta, y al final del día tienes la lista de todos los pacientes
atendidos con un botón para exportar todo a Excel.

## ¿Qué incluye?

- **Login** simple (usuario y clave configurables).
- **Dashboard** con el resumen del día y un mini-gráfico de los últimos 7 días.
- **Nueva atención**: busca por DNI (contra tu base local primero, y contra
  una API de RENIEC si la configuras), autocompleta los datos, y registra
  motivo, síntomas, diagnóstico, receta y notas.
- **Atendidos hoy**: lista de todo lo registrado en el día, con exportación
  a Excel de un clic.
- **Reportes**: filtra por rango de fechas y exporta ese rango también.
- Base de datos: **SQLite** en tu computadora (cero configuración) y
  **PostgreSQL** en producción (Render o Supabase), usando el mismo código.

---

## 1. Probarlo en tu computadora (5 minutos)

Necesitas tener Python instalado (3.10 o superior).

```bash
# 1. Entra a la carpeta del proyecto
cd clinica-app

# 2. Crea un entorno virtual
python3 -m venv venv

# En Windows: venv\Scripts\activate
# En Mac/Linux:
source venv/bin/activate

# 3. Instala las dependencias
pip install -r requirements.txt

# 4. Copia el archivo de configuración de ejemplo
cp .env.example .env
# Abre .env con cualquier editor de texto y, como mínimo, cambia
# APP_USERNAME y APP_PASSWORD por los que tú quieras usar.

# 5. Corre la aplicación
python app.py
```

Abre tu navegador en **http://localhost:5000**. Se crea automáticamente un
archivo `instance/clinica.db` (SQLite) con todas tus tablas — no necesitas
crear nada a mano.

Entra con el usuario y clave que pusiste en `.env` (por defecto:
`doctor` / `clinica123`, pero **cámbialos**).

---

## 2. Conseguir tu API de consulta de DNI (RENIEC) — opcional

El sistema funciona perfectamente **sin** esto (solo que tendrás que
escribir los datos del paciente a mano la primera vez que lo atiendes).
Si quieres autocompletar con RENIEC:

1. Regístrate en uno de estos proveedores (todos tienen un plan gratuito
   con un número limitado de consultas al mes, suficiente para un
   consultorio pequeño):
   - https://json.pe
   - https://apis.net.pe
   - https://apidni.com
2. Copia la URL del endpoint y tu token de acceso (bearer token).
3. En tu archivo `.env`, completa:
   ```
   DNI_API_URL=https://el-endpoint-que-te-dieron
   DNI_API_TOKEN=tu-token
   ```
4. Reinicia la aplicación. Ya debería autocompletar al buscar un DNI nuevo.

> Nota: distintos proveedores devuelven el JSON con nombres de campo
> ligeramente distintos. El archivo `services/reniec.py` ya intenta
> reconocer los formatos más comunes. Si tu proveedor usa nombres de campo
> diferentes, solo hay que ajustar esa función (está comentada para que
> sea fácil de encontrar).

---

## 3. Subirlo a internet gratis (Render + Supabase)

### Paso A — Crear la base de datos en Supabase (gratis, persistente)

1. Crea una cuenta en https://supabase.com
2. Crea un nuevo proyecto (elige una clave de base de datos segura y
   guárdala).
3. Ve a **Project Settings → Database → Connection string** y copia la
   cadena en modo **URI** (algo como
   `postgresql://postgres:[TU-CLAVE]@db.xxxxx.supabase.co:5432/postgres`).

### Paso B — Subir el código a GitHub

1. Crea un repositorio nuevo en GitHub.
2. Sube esta carpeta (sin el `.env`, ya está protegido por `.gitignore`):
   ```bash
   git init
   git add .
   git commit -m "Primera versión del sistema"
   git branch -M main
   git remote add origin https://github.com/TU-USUARIO/TU-REPOSITORIO.git
   git push -u origin main
   ```

### Paso C — Desplegar en Render (gratis)

1. Crea una cuenta en https://render.com (puedes entrar con GitHub).
2. Clic en **New → Web Service** y conecta tu repositorio.
3. Configura:
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app` (ya está en el `Procfile`, Render
     lo detecta solo)
   - **Instance Type:** Free
4. En la sección **Environment**, agrega las mismas variables que tienes en
   tu `.env` local:
   - `SECRET_KEY` (invéntate un texto largo y aleatorio, distinto al local)
   - `APP_USERNAME`, `APP_PASSWORD`
   - `NOMBRE_CLINICA`
   - `DATABASE_URL` → pega aquí la cadena de conexión de Supabase del Paso A
   - `DNI_API_URL`, `DNI_API_TOKEN` (si los tienes)
5. Clic en **Create Web Service**. Espera unos minutos a que compile.
6. Render te da una URL pública como `https://tu-app.onrender.com` — esa es
   tu página web, accesible desde cualquier lugar.

**Sobre el plan gratuito de Render:** el servidor "se duerme" después de
~15 minutos sin visitas, y la primera vez que alguien entra después de eso
tarda unos 30-50 segundos en despertar. Es normal, no es un error. Si eso
te molesta para el uso diario, la alternativa es pasar a un plan pagado
económico de Render (desde ~7 USD/mes) cuando decidas que vale la pena.

---

## 4. Estructura del proyecto

```
clinica-app/
├── app.py                  → Rutas y lógica principal de Flask
├── config.py                → Configuración (lee variables de entorno)
├── models.py                → Modelos de base de datos (Paciente, Atencion)
├── services/
│   └── reniec.py            → Conexión con la API de consulta de DNI
├── templates/                → Páginas HTML (Jinja2)
│   ├── base.html             → Plantilla con la barra lateral
│   ├── login.html
│   ├── dashboard.html
│   ├── nueva_atencion.html
│   ├── pacientes_hoy.html
│   └── reportes.html
├── static/css/style.css      → Todos los estilos
├── requirements.txt          → Librerías de Python necesarias
├── Procfile                  → Le dice a Render cómo arrancar la app
├── .env.example               → Plantilla de configuración
└── instance/                  → Aquí vive tu base de datos SQLite local
```

## 5. Seguridad — antes de usarlo con pacientes reales

Este proyecto es un punto de partida sólido, pero maneja datos de salud
reales. Antes de usarlo en producción con pacientes:

- Cambia `SECRET_KEY`, `APP_USERNAME` y `APP_PASSWORD` por valores propios
  y seguros — nunca dejes los valores de ejemplo.
- No compartas tu archivo `.env` ni lo subas a GitHub.
- Considera que el plan gratuito de Render/Supabase no incluye respaldos
  automáticos garantizados — exporta tus reportes a Excel periódicamente
  como respaldo.
- Si tu consultorio crece, evalúa un hosting pagado con mejores garantías
  de disponibilidad y respaldo, y revisa qué exige la Ley de Protección de
  Datos Personales del Perú para el manejo de historias clínicas.
