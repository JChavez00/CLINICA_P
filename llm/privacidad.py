"""Frontera de datos: texto libre e identificadores se procesan sólo localmente."""
import calendar
import re
from datetime import date, timedelta

from ml.datos import hoy_peru
from .consultas import interpretar_busqueda, _normalizar
from .esquemas import Periodo

MESES = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"]


def periodo_local(texto):
    hoy = hoy_peru()
    normal = _normalizar(texto)
    fechas = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", texto)
    if fechas:
        p = Periodo(desde=fechas[0], hasta=fechas[1] if len(fechas)>1 else fechas[0])
        return p.model_dump()
    if "ayer" in normal:
        f = hoy-timedelta(days=1)
        return {"desde":f.isoformat(),"hasta":f.isoformat()}
    if "hoy" in normal:
        return {"desde":hoy.isoformat(),"hasta":hoy.isoformat()}
    if "semana" in normal:
        return {"desde":(hoy-timedelta(days=6)).isoformat(),"hasta":hoy.isoformat()}
    mes = next((i+1 for i,m in enumerate(MESES) if re.search(r"\b"+m+r"\b",normal)), hoy.month)
    anio = re.search(r"\b20\d{2}\b", normal)
    anio = int(anio.group()) if anio else hoy.year
    a, b = date(anio,mes,1), date(anio,mes,calendar.monthrange(anio,mes)[1])
    if "ultimo mes" in normal or "mes pasado" in normal:
        b = date(hoy.year,hoy.month,1)-timedelta(days=1); a=b.replace(day=1)
    return {"desde":a.isoformat(),"hasta":b.isoformat()}


def clasificar_chat(texto, seleccionado=False):
    """No envía texto a un router externo. Fuera de vocabulario, pedir precisión."""
    normal = _normalizar(texto)
    dni = re.search(r"(?<!\d)\d{8,9}(?!\d)", texto)
    clinico = bool(dni or re.search(r"\b(paciente|historial|historia clinica|expediente|diagnostico|receta|busca|buscame)\b",normal))
    agregado = bool(re.search(r"\b(cuantos|cuantas|cantidad|estadisticas|compara|comparar|atenciones|mes|mensual|demanda|ml|ingresos|costos|servicios|tendencias)\b",normal))
    if clinico or (seleccionado and any(x in normal for x in ["este paciente","sus atenciones","su historial","servicios recibio"])):
        busqueda = interpretar_busqueda(texto)
        if dni:
            busqueda = ("dni",dni.group(),True)
        referencia = {"tipo":busqueda[0],"valor":busqueda[1]} if busqueda and busqueda[0] in ("dni","nombre") else None
        no_disponible = any(x in normal for x in ["servicios", "medico", "costos", "costo", "responsable"])
        usar_contexto=seleccionado and bool(re.search(r"\b(este paciente|paciente seleccionado|su historial|sus atenciones|sus diagnosticos|su diagnostico|sus fechas)\b",normal))
        return {"agente":"consultor", "herramienta":"campos_no_disponibles" if no_disponible else "buscar_paciente" if referencia else "historial_paciente",
                "argumentos":{"limite":20}, "privado":{"referencia":referencia,"usar_contexto":usar_contexto},
                "seguro":{"intencion":"campos_no_disponibles" if no_disponible else "historial", "referencia_presente":bool(referencia), "contexto_seleccionado":seleccionado}}
    if not agregado:
        return None
    periodo = periodo_local(texto)
    herramienta = "estadisticas_periodo"
    if "servicio" in normal or "costo" in normal or "ingreso" in normal:
        herramienta = "campos_administrativos_no_disponibles"
    elif "ml" in normal or "demanda" in normal or "pronostico" in normal:
        dias = next((d for d in [30,15,7] if str(d) in normal),7)
        return {"agente":"analista", "herramienta":"consultar_pronosticos_ml", "argumentos":{"inicio":(hoy_peru()+timedelta(days=1)).isoformat(),"dias":dias}, "seguro":{"objetivo":"pronosticos_ml"}, "privado":{}}
    elif "compara" in normal:
        meses = [i+1 for i,m in enumerate(MESES) if m in normal]
        if len(meses)>=2:
            y=int(periodo["desde"][:4]); a,b=meses[:2]
            periodo={"desde":date(y,b,1).isoformat(),"hasta":date(y,b,calendar.monthrange(y,b)[1]).isoformat(),
                     "desde_anterior":date(y,a,1).isoformat(),"hasta_anterior":date(y,a,calendar.monthrange(y,a)[1]).isoformat()}
        else:
            a,b=date.fromisoformat(periodo["desde"]),date.fromisoformat(periodo["hasta"])
            largo=(b-a).days+1
            periodo.update(desde_anterior=(a-timedelta(days=largo)).isoformat(),hasta_anterior=(a-timedelta(days=1)).isoformat())
        herramienta="comparar_periodos"
    return {"agente":"analista", "herramienta":herramienta, "argumentos":periodo, "seguro":{"objetivo":herramienta}, "privado":{}}


def extraer_tarea(texto):
    n = _normalizar(texto)
    if not any(t in n for t in ("reporte","informe","resumen","estadistica","alerta","avisame","pronostico","ml")):
        raise ValueError("Indica un reporte, resumen, consulta ML o alerta administrativa.")
    tipo = "alerta_alta" if "alta" in n else "consulta_ml" if "pronostico" in n or "ml" in n else "estadisticas" if "estadistica" in n else "reporte"
    dias=["lunes","martes","miercoles","jueves","viernes","sabado","domingo"]
    indice=next((i for i,d in enumerate(dias) if d in n),0)
    frecuencia="mensual" if "mensual" in n or "cada mes" in n else "semanal" if "semanal" in n or any(d in n for d in dias) else "diaria"
    hora=re.search(r"\b([01]?\d|2[0-3]):00\b",n)
    dia_mes=re.search(r"\b(?:dia|los)\s+([1-9]|1[0-9]|2[0-8])\b",n)
    return {"tipo":tipo,"frecuencia":frecuencia,"hora":int(hora.group(1)) if hora else 8,"dia_semana":indice,"dia_mes":int(dia_mes.group(1)) if dia_mes else 1,"canal":"panel"}
