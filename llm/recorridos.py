"""Registro estructurado de etapas y consulta de evidencia sin datos de pacientes."""
from time import monotonic
from models import db, AgenteEjecucion, AgenteRecorrido


class Recorrido:
    def __init__(self, proveedor, modelo, flujo_id=None, padre_id=None):
        self.inicio = monotonic()
        self.anterior = 0
        self.datos = dict(proveedor=proveedor, modelo=modelo, flujo_id=flujo_id,
                          padre_id=padre_id, pasos=[])

    def paso(self, codigo, titulo, detalle, estado="ok"):
        fin = max(self.anterior, round((monotonic()-self.inicio)*1000))
        self.datos['pasos'].append(dict(codigo=codigo, titulo=titulo, detalle=detalle,
            estado=estado, inicio_ms=self.anterior, fin_ms=fin, duracion_ms=fin-self.anterior))
        self.anterior = fin


def resumen(e, r=...):
    if r is ...:
        r = db.session.get(AgenteRecorrido, e.id)
    return dict(id=e.id, agente=e.agente, modulo=e.modulo, herramienta=e.herramienta,
        fecha=e.fecha.isoformat()+"Z", duracion_ms=e.duracion_ms, estado=e.estado,
        error_codigo=e.error_codigo, detalle_disponible=r is not None,
        flujo_id=r.flujo_id if r else e.id, padre_id=r.padre_id if r else None,
        proveedor=r.proveedor if r else None, modelo=r.modelo if r else None)


def detalle(identificador):
    e = db.session.get(AgenteEjecucion, identificador)
    if e is None:
        return None
    salida = resumen(e)
    r = db.session.get(AgenteRecorrido, e.id)
    salida['pasos'] = r.pasos if r else []
    salida['alcance'] = ("Etapas registradas durante la ejecución. Los tiempos miden cada etapa, incluida su validación local."
        if r else "Registro anterior o proceso sin instrumentación por etapas. Sólo constan el resultado y la duración total; no se reconstruyen pasos.")
    relacionados = (AgenteEjecucion.query.join(AgenteRecorrido,
        AgenteRecorrido.ejecucion_id==AgenteEjecucion.id)
        .filter(AgenteRecorrido.flujo_id==r.flujo_id)
        .order_by(AgenteEjecucion.fecha, AgenteEjecucion.id).limit(20).all()) if r else [e]
    salida['participantes'] = [resumen(x) for x in relacionados]
    salida['privacidad'] = "Sin preguntas, parámetros, identificadores de pacientes ni contenido clínico."
    return salida
