-- Migración aditiva. No modifica el historial, la cuenta ni ejecuciones anteriores.
BEGIN;
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
