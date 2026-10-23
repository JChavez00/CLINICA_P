-- CLINICA_P: tablas aditivas de agentes, perfil y ML v2.
-- Ejecutar en SQL Editor del proyecto Supabase correcto.
-- Los valores por defecto y los identificadores se asignan desde Python.
-- IF NOT EXISTS no corrige tablas existentes con otro esquema.
BEGIN;
SET LOCAL search_path TO public;

CREATE TABLE IF NOT EXISTS agente_ejecuciones (
	id VARCHAR(36) NOT NULL,
	agente VARCHAR(40) NOT NULL,
	modulo VARCHAR(30) NOT NULL,
	herramienta VARCHAR(50) NOT NULL,
	fecha TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	duracion_ms INTEGER NOT NULL,
	estado VARCHAR(20) NOT NULL,
	error_codigo VARCHAR(50),
	PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS ix_agente_ejecuciones_fecha ON agente_ejecuciones (fecha);

CREATE TABLE IF NOT EXISTS agente_informes (
	id VARCHAR(36) NOT NULL,
	generado_en TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	desde DATE NOT NULL,
	hasta DATE NOT NULL,
	contenido JSON NOT NULL,
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS agente_tareas (
	id VARCHAR(36) NOT NULL,
	configuracion JSON NOT NULL,
	creada_en TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	activa BOOLEAN NOT NULL,
	confirmada BOOLEAN NOT NULL,
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS agente_tarea_ejecuciones (
	id VARCHAR(36) NOT NULL,
	tarea_id VARCHAR(36) NOT NULL,
	periodo VARCHAR(30) NOT NULL,
	iniciada_en TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	estado VARCHAR(20) NOT NULL,
	intentos INTEGER NOT NULL,
	resultado JSON,
	error_codigo VARCHAR(50),
	PRIMARY KEY (id),
	CONSTRAINT uq_agente_tarea_periodo UNIQUE (tarea_id, periodo),
	FOREIGN KEY(tarea_id) REFERENCES agente_tareas (id)
);

CREATE TABLE IF NOT EXISTS cuenta_perfil (
	id SERIAL NOT NULL,
	usuario VARCHAR(120) NOT NULL,
	nombre VARCHAR(160) NOT NULL,
	clave_hash VARCHAR(512) NOT NULL,
	rol VARCHAR(40) NOT NULL,
	zona VARCHAR(80) NOT NULL,
	correo VARCHAR(254) NOT NULL,
	verificado BOOLEAN NOT NULL,
	avisos BOOLEAN NOT NULL,
	eventos JSON NOT NULL,
	sesion_version INTEGER NOT NULL,
	verificacion_hash VARCHAR(64),
	verificacion_hasta TIMESTAMP WITHOUT TIME ZONE,
	PRIMARY KEY (id),
	UNIQUE (usuario)
);

CREATE TABLE IF NOT EXISTS cuenta_tareas (
	tarea_id VARCHAR(36) NOT NULL,
	propietario_id INTEGER NOT NULL,
	nombre VARCHAR(160) NOT NULL,
	zona VARCHAR(80) NOT NULL,
	proxima TIMESTAMP WITHOUT TIME ZONE,
	ultima TIMESTAMP WITHOUT TIME ZONE,
	PRIMARY KEY (tarea_id),
	FOREIGN KEY(tarea_id) REFERENCES agente_tareas (id),
	FOREIGN KEY(propietario_id) REFERENCES cuenta_perfil (id)
);

CREATE TABLE IF NOT EXISTS cuenta_notificaciones (
	id VARCHAR(36) NOT NULL,
	propietario_id INTEGER NOT NULL,
	clave VARCHAR(200) NOT NULL,
	evento VARCHAR(40) NOT NULL,
	creada_en TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	leida BOOLEAN NOT NULL,
	informe_id VARCHAR(36),
	tarea_id VARCHAR(36),
	correo_estado VARCHAR(40) NOT NULL,
	correo_intentos INTEGER NOT NULL,
	correo_reclamado TIMESTAMP WITHOUT TIME ZONE,
	destinatario VARCHAR(254),
	PRIMARY KEY (id),
	FOREIGN KEY(propietario_id) REFERENCES cuenta_perfil (id),
	UNIQUE (clave),
	FOREIGN KEY(informe_id) REFERENCES agente_informes (id),
	FOREIGN KEY(tarea_id) REFERENCES agente_tareas (id)
);

CREATE TABLE IF NOT EXISTS cuenta_archivos (
	id VARCHAR(36) NOT NULL,
	informe_id VARCHAR(36) NOT NULL,
	propietario_id INTEGER NOT NULL,
	tarea_id VARCHAR(36),
	formato VARCHAR(8) NOT NULL,
	generado_en TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	estado VARCHAR(40) NOT NULL,
	objeto VARCHAR(200) NOT NULL,
	sha256 VARCHAR(64) NOT NULL,
	contenido BYTEA NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_cuenta_archivo_formato UNIQUE (informe_id, formato),
	FOREIGN KEY(informe_id) REFERENCES agente_informes (id),
	FOREIGN KEY(propietario_id) REFERENCES cuenta_perfil (id),
	FOREIGN KEY(tarea_id) REFERENCES agente_tareas (id)
);

CREATE TABLE IF NOT EXISTS cuenta_programador (
	origen VARCHAR(30) NOT NULL,
	revisado_en TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	ultima_tarea_en TIMESTAMP WITHOUT TIME ZONE,
	estado VARCHAR(20) NOT NULL,
	PRIMARY KEY (origen)
);

CREATE TABLE IF NOT EXISTS ml_pronosticos_v2 (
	id SERIAL NOT NULL,
	fecha_objetivo DATE NOT NULL,
	dia_generacion DATE NOT NULL,
	generado_en TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	objetivo VARCHAR(20) NOT NULL,
	modelo VARCHAR(50) NOT NULL,
	version VARCHAR(40) NOT NULL,
	resultado JSON NOT NULL,
	estado VARCHAR(20) NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_ml_pronostico_diario UNIQUE (fecha_objetivo, dia_generacion, objetivo, version)
);

CREATE INDEX IF NOT EXISTS ix_ml_pronosticos_v2_fecha_objetivo ON ml_pronosticos_v2 (fecha_objetivo);

-- Acceso mediante Flask + DATABASE_URL (rol PostgreSQL de backend).
-- No habilitar acceso directo anon/authenticated a hashes o archivos privados.

ALTER TABLE public.agente_ejecuciones ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.agente_informes ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.agente_tareas ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.agente_tarea_ejecuciones ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.cuenta_perfil ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.cuenta_tareas ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.cuenta_notificaciones ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.cuenta_archivos ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.cuenta_programador ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.ml_pronosticos_v2 ENABLE ROW LEVEL SECURITY;

REVOKE ALL PRIVILEGES ON TABLE
    public.agente_ejecuciones,
    public.agente_informes,
    public.agente_tareas,
    public.agente_tarea_ejecuciones,
    public.cuenta_perfil,
    public.cuenta_tareas,
    public.cuenta_notificaciones,
    public.cuenta_archivos,
    public.cuenta_programador,
    public.ml_pronosticos_v2
FROM anon, authenticated;

CREATE TABLE IF NOT EXISTS public.agente_recorridos (
    ejecucion_id VARCHAR(36) PRIMARY KEY REFERENCES public.agente_ejecuciones(id),
    flujo_id VARCHAR(36) NOT NULL,
    padre_id VARCHAR(36),
    proveedor VARCHAR(30) NOT NULL,
    modelo VARCHAR(120) NOT NULL,
    pasos JSON NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_agente_recorridos_flujo_id ON public.agente_recorridos(flujo_id);
ALTER TABLE public.agente_recorridos ENABLE ROW LEVEL SECURITY;
REVOKE ALL PRIVILEGES ON TABLE public.agente_recorridos FROM anon, authenticated;

COMMIT;
