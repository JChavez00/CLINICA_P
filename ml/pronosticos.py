"""Persistencia idempotente: dos objetivos por fecha, versión y día de emisión."""
from datetime import timedelta

from sqlalchemy import func
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert

from models import db, MLPronostico, MLDemandaDiaria, Atencion
from ml.datos import hoy_peru, validar_fecha
from ml.predecir_demanda import predecir


def validar_periodo(dias):
    if isinstance(dias, bool) or str(dias) not in ("7", "15", "30"):
        raise ValueError("El horizonte debe ser 7, 15 o 30 días.")
    return int(dias)


def generar(dias=30, inicio=None, hoy=None):
    dias = validar_periodo(dias)
    hoy = hoy or hoy_peru()
    inicio = validar_fecha(inicio or (hoy + timedelta(days=1)))
    if inicio <= hoy:
        raise ValueError("Los pronósticos automáticos deben comenzar en una fecha futura.")
    reales = set(f for f, in db.session.query(MLDemandaDiaria.fecha).filter(MLDemandaDiaria.fecha >= inicio).all())
    reales.update(f for f, in db.session.query(Atencion.fecha).filter(Atencion.fecha >= inicio).distinct().all())
    filas = []
    for i in range(dias):
        fecha = inicio + timedelta(days=i)
        if fecha in reales:
            continue
        p = predecir(fecha)
        for objetivo in ("clasificacion", "regresion"):
            modelo = p["ganadores"][objetivo]
            filas.append({"fecha_objetivo": fecha, "dia_generacion": hoy,
                          "objetivo": objetivo, "modelo": modelo, "version": p["version"],
                          "resultado": {**p["resultados"][objetivo][modelo], "feriado": p["feriado"],
                                        "experimental": True}, "estado": "generado"})
    motor = db.session.get_bind().dialect.name
    insertar = {"sqlite": sqlite_insert, "postgresql": pg_insert}.get(motor)
    if insertar is None:
        raise ValueError("Motor no compatible con pronósticos idempotentes.")
    if filas:
        stmt = insertar(MLPronostico).values(filas).on_conflict_do_nothing(
            index_elements=["fecha_objetivo", "dia_generacion", "objetivo", "version"])
        db.session.execute(stmt)
        db.session.commit()
    return {"dias_solicitados": dias, "resultados_procesados": len(filas),
            "nota": "Repetir el mismo día/versión conserva la emisión existente. Otro día conserva una nueva emisión."}


def consultar(inicio, dias):
    inicio, dias = validar_fecha(inicio), validar_periodo(dias)
    fin = inicio + timedelta(days=dias - 1)
    validar_fecha(fin)
    historial = {r.fecha: r for r in MLDemandaDiaria.query.filter(MLDemandaDiaria.fecha.between(inicio, fin)).all()}
    conteos = dict(db.session.query(Atencion.fecha, func.count(Atencion.id))
                   .filter(Atencion.fecha.between(inicio, fin)).group_by(Atencion.fecha).all())
    guardados = MLPronostico.query.filter(MLPronostico.fecha_objetivo.between(inicio, fin))\
        .order_by(MLPronostico.generado_en.desc(), MLPronostico.id.desc()).all()
    por_fecha = {}
    for r in guardados:
        por_fecha.setdefault(r.fecha_objetivo, []).append(r)
    salida = []
    for i in range(dias):
        fecha = inicio + timedelta(days=i)
        r = historial.get(fecha)
        hay_real = r is not None or fecha in conteos
        anteriores = [{"objetivo": p.objetivo, "modelo": p.modelo, "version": p.version,
                       "generado_en": p.generado_en.isoformat() + "Z", "resultado": p.resultado,
                       "estado": "observado" if hay_real else ("vencido_sin_observacion" if fecha < hoy_peru() else p.estado)}
                      for p in por_fecha.get(fecha, [])]
        # Emparejar ambos objetivos de la misma emisión, sin mezclar versiones.
        pareja = {}
        if anteriores:
            emision = por_fecha[fecha][0]
            pareja = {p.objetivo: p for p in por_fecha[fecha]
                      if p.dia_generacion == emision.dia_generacion and p.version == emision.version}
        c, g = pareja.get("clasificacion"), pareja.get("regresion")
        salida.append({"fecha": fecha.isoformat(), "tipo": "histórico" if hay_real else "predicción" if c and g else "sin pronóstico",
                       "nivel": r.nivel_demanda if r else (None if hay_real else c.resultado["nivel"] if c else None),
                       "total": r.total_atenciones if r else conteos.get(fecha),
                       "cantidad": g.resultado["cantidad"] if g else None,
                       "probabilidad": c.resultado["probabilidad"] if c else None,
                       "pronosticos_anteriores": anteriores})
    return salida
