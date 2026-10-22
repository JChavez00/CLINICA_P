"""Dataset diario agregado. No consulta ni exporta fichas de pacientes."""
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import func

from models import db, Atencion, MLDemandaDiaria

ETIQUETAS = ["BAJA", "MEDIA", "ALTA"]
CARACTERISTICAS = ["dia_semana", "mes", "es_feriado", "fin_semana", "dia_mes"]
CALENDARIO = Path(__file__).with_name("feriados.json")


def hoy_peru():
    return datetime.now(timezone(timedelta(hours=-5))).date()


def validar_fecha(valor, futura=False):
    try:
        if isinstance(valor, str) and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", valor):
            raise ValueError()
        fecha = date.fromisoformat(valor) if isinstance(valor, str) else valor
        if type(fecha) is not date or not 2000 <= fecha.year <= 2100:
            raise ValueError()
        if futura and fecha <= hoy_peru():
            raise ValueError()
        return fecha
    except (ValueError, TypeError):
        raise ValueError("Fecha inválida: usa AAAA-MM-DD (2000–2100) y una fecha futura para inferencia manual.") from None


def calendario(ruta=None):
    contenido = json.loads(Path(ruta or CALENDARIO).read_text(encoding="utf-8"))
    fechas = contenido.get("fechas", {})
    if not isinstance(fechas, dict) or any(type(v) is not bool for v in fechas.values()):
        raise ValueError("El calendario debe contener fechas con valores booleanos.")
    for f in fechas:
        validar_fecha(f)
    return contenido


def caracteristicas(fecha, feriado):
    fecha = validar_fecha(fecha)
    return {"dia_semana": fecha.weekday(), "mes": fecha.month,
            "es_feriado": int(feriado), "fin_semana": int(fecha.weekday() >= 5),
            "dia_mes": fecha.day}


def preparar(registros, conteos=None, hoy=None):
    """Conserva etiquetas originales; no rellena ausencias con ceros."""
    hoy = hoy or hoy_peru()
    filas, vistas = [], set()
    for r in registros:
        f = validar_fecha(r["fecha"])
        if f in vistas:
            raise ValueError(f"Fecha duplicada: {f}")
        vistas.add(f)
        n = r["total_atenciones"]
        if n is None or isinstance(n, bool) or int(n) != n or n < 0:
            raise ValueError(f"Cantidad inválida: {f}")
        if r["nivel_demanda"] not in ETIQUETAS:
            raise ValueError(f"Etiqueta desconocida o nula: {f}")
        if r["es_feriado"] not in (True, False, 0, 1):
            raise ValueError(f"Indicador de feriado nulo: {f}")
        if f >= hoy:
            raise ValueError("El dataset contiene días sin cerrar (hoy o futuros).")
        filas.append({"fecha": f, "total_atenciones": int(n),
                      "nivel_demanda": r["nivel_demanda"],
                      **caracteristicas(f, bool(r["es_feriado"]))})
    if not filas:
        raise ValueError("No hay datos históricos de demanda.")
    df = pd.DataFrame(filas).sort_values("fecha").reset_index(drop=True)
    faltantes = (df.fecha.iloc[-1] - df.fecha.iloc[0]).days + 1 - len(df)
    discrepancias = sum(int(n) != int(conteos.get(f, 0)) for f, n in
                        zip(df.fecha, df.total_atenciones)) if conteos is not None else None
    rangos = {e: {"min": int(g.total_atenciones.min()), "max": int(g.total_atenciones.max())}
              for e, g in df.groupby("nivel_demanda")}
    return df, {"dias_faltantes": faltantes, "dias_cero_explicitos": int((df.total_atenciones == 0).sum()),
                "discrepancias_con_atenciones": discrepancias,
                "rangos_observados_por_etiqueta": rangos,
                "regla_etiquetas": "Etiquetas originales. No se encontró su regla generadora; los rangos observados no son umbrales oficiales.",
                "ausencias": "Días sin registro son desconocidos, nunca ceros imputados."}


def cargar_datos():
    filas = db.session.query(MLDemandaDiaria.fecha, MLDemandaDiaria.total_atenciones,
                             MLDemandaDiaria.nivel_demanda, MLDemandaDiaria.es_feriado).all()
    conteos = dict(db.session.query(Atencion.fecha, func.count(Atencion.id)).group_by(Atencion.fecha).all())
    return preparar([dict(r._mapping) for r in filas], conteos)
