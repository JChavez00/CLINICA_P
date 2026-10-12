"""Estadísticas agregadas. Nunca envía registros individuales al LLM."""
from collections import Counter
from datetime import date, timedelta
from sqlalchemy import func
from models import db, Atencion, MLDemandaDiaria


def obtener_resumen():
    # Datos globales y últimos 90 días, agregados exclusivamente.
    ultima = db.session.query(func.max(Atencion.fecha)).scalar()
    total = db.session.query(func.count(Atencion.id)).scalar() or 0
    if not ultima:
        return {"total_atenciones": 0, "mensaje": "No hay atenciones registradas."}
    inicio = ultima - timedelta(days=89)
    por_mes = (db.session.query(func.strftime('%Y-%m', Atencion.fecha), func.count(Atencion.id))
               .group_by(func.strftime('%Y-%m', Atencion.fecha))
               .order_by(func.strftime('%Y-%m', Atencion.fecha).desc()).limit(12).all())
    por_dia = (db.session.query(Atencion.fecha, func.count(Atencion.id))
               .filter(Atencion.fecha >= inicio, Atencion.fecha <= ultima)
               .group_by(Atencion.fecha).order_by(Atencion.fecha.desc()).limit(90).all())
    motivos = (db.session.query(Atencion.motivo, func.count(Atencion.id))
               .filter(Atencion.fecha >= inicio, Atencion.fecha <= ultima)
               .group_by(Atencion.motivo).order_by(func.count(Atencion.id).desc()).limit(10).all())
    niveles = (db.session.query(MLDemandaDiaria.nivel_demanda, func.count(MLDemandaDiaria.id))
               .group_by(MLDemandaDiaria.nivel_demanda).all())
    return {
        "origen": "Base de datos local; historial simulado para demostración",
        "ultima_fecha_registrada": ultima.isoformat(),
        "periodo_reciente": {"desde": inicio.isoformat(), "hasta": ultima.isoformat()},
        "total_atenciones_historicas": total,
        "atenciones_por_mes": [{"mes": str(m), "cantidad": n} for m, n in por_mes],
        "atenciones_por_dia_recientes": [{"fecha": f.isoformat(), "cantidad": n} for f, n in por_dia],
        "motivos_frecuentes_recientes": [{"motivo": (str(m)[:100] if m else "Sin especificar"), "cantidad": n} for m, n in motivos],
        "dias_por_nivel_demanda": [{"nivel": str(n), "dias": c} for n, c in niveles],
        "modelo_ml": {"tipo": "Clasificador de demanda BAJA/MEDIA/ALTA", "exactitud_evaluada": "43.64 %", "limitacion": "Igual al modelo de referencia; no validado para decisiones reales"},
    }


# Consultas individuales: permanecen dentro de Flask/SQLite.
import re
import unicodedata
from sqlalchemy import or_
from models import Paciente


def _normalizar(texto):
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(c for c in texto if not unicodedata.combining(c)).lower().strip()


def interpretar_busqueda(pregunta):
    """Devuelve (tipo, valor, historial) o None para consultas estadísticas.

    Las consultas de pacientes se resuelven localmente, sin enviar el texto a Gemini.
    """
    texto = pregunta.strip()
    normal = _normalizar(texto)
    dni = re.search(r"(?<!\d)\d{8}(?!\d)", texto)
    es_paciente = bool(re.search(
        r"\b(paciente|pacientes|dni|historial|historia clinica|expediente|"
        r"ultima atencion|ultimo diagnostico|receta|diagnostico|"
        r"busca(?:r|me)? a|muestra(?:me)? a|datos de|atenciones de)\b", normal))
    if dni:
        return ("dni", dni.group(), True)
    if not es_paciente:
        return None
    # No devolver un listado completo sin criterio de búsqueda.
    patrones = [
        r"(?:dni|paciente|historial|historia clinica|expediente|datos de|"
        r"atenciones de|ultima atencion de|ultimo diagnostico de|"
        r"busca(?:r|me)? a|muestra(?:me)? a)\s*(?:de|del|al|a|con|por|llamado|llamada|nombre)?\s*(.*)$",
    ]
    nombre = ""
    for patron in patrones:
        m = re.search(patron, normal)
        if m:
            nombre = m.group(1).strip(" ?.,:;!\"'")
            break
    nombre = re.sub(r"^(?:nombre|apellidos?|paciente|de|del|al|a|con|por)\s+", "", nombre).strip()
    if not nombre or nombre in {"hoy", "ayer", "todos", "todas", "los", "las", "septiembre"}:
        return ("ayuda", "", False)
    if len(nombre) < 3:
        return ("ayuda", "", False)
    return ("nombre", nombre, True)


def buscar_pacientes(tipo, valor, limite=8):
    """Busca pacientes sin distinguir tildes ni mayúsculas.

    Implementación para la base académica pequeña (420 pacientes).
    Para bases grandes, crear un campo de nombre normalizado e indexado.
    """
    if tipo == "dni":
        return Paciente.query.filter(Paciente.dni == str(valor).strip()).limit(1).all()
    if tipo != "nombre":
        return []

    palabras = _normalizar(valor).split()[:6]
    if not palabras:
        return []

    # Limitar el conjunto para no cargar indefinidamente expedientes.
    # No se accede a historiales clínicos durante esta búsqueda.
    total = Paciente.query.count()
    if total > 5000:
        raise RuntimeError(
            "La búsqueda sin tildes requiere un índice de nombres normalizados "
            "para bases de más de 5000 pacientes."
        )
    candidatos = Paciente.query.order_by(Paciente.apellidos, Paciente.nombres).all()
    encontrados = []
    for paciente in candidatos:
        nombre_completo = _normalizar(
            f"{paciente.nombres or ''} {paciente.apellidos or ''}"
        )
        if all(palabra in nombre_completo.split() or any(
            palabra in token for token in nombre_completo.split()
        ) for palabra in palabras):
            encontrados.append(paciente)
            if len(encontrados) > limite:
                break
    return encontrados


def _fecha(valor):
    return valor.isoformat() if valor is not None and hasattr(valor, "isoformat") else str(valor or "No registrado")


def formatear_paciente(paciente, incluir_historial=True):
    campos = [
        ("Paciente", f"{paciente.nombres or ''} {paciente.apellidos or ''}".strip()),
        ("DNI", paciente.dni),
        ("Fecha de nacimiento", _fecha(paciente.fecha_nacimiento)),
        ("Sexo", paciente.sexo),
        ("Teléfono", paciente.telefono),
        ("Departamento", paciente.departamento),
        ("Provincia", paciente.provincia),
        ("Distrito", paciente.distrito),
        ("Dirección", " ".join(str(x) for x in (paciente.tipo_via, paciente.nombre_via) if x)),
    ]
    lineas = ["**Ficha del paciente**"]
    lineas.extend(f"**{etiqueta}:** {valor if valor else 'No registrado'}" for etiqueta, valor in campos)
    if incluir_historial:
        # Máximo 20 atenciones por respuesta; no incluirlas en llamadas a Gemini.
        total = Atencion.query.filter_by(paciente_id=paciente.id).count()
        atenciones = (Atencion.query.filter_by(paciente_id=paciente.id)
                      .order_by(Atencion.fecha.desc(), Atencion.id.desc()).limit(20).all())
        lineas.append(f"\n**Historial de atenciones:** {total} registro(s).")
        if total > len(atenciones):
            lineas.append("Se muestran las 20 atenciones más recientes.")
        for i, a in enumerate(atenciones, 1):
            lineas.extend([
                f"\n**Atención {i} — {_fecha(a.fecha)}**",
                f"- Hora: {a.hora or 'No registrada'}",
                f"- Motivo: {a.motivo or 'No registrado'}",
                f"- Síntomas: {a.sintomas or 'No registrados'}",
                f"- Diagnóstico: {a.diagnostico or 'No registrado'}",
                f"- Receta: {a.receta or 'No registrada'}",
                f"- Notas: {a.notas or 'No registradas'}",
                f"- Estado: {a.estado or 'No registrado'}",
            ])
    return "\n".join(lineas)


def respuesta_busqueda(tipo, valor):
    if tipo == "ayuda":
        return "Para consultar una ficha, indica el DNI de 8 o 9 dígitos o el nombre del paciente. Ejemplo: «Historial del DNI 12345678» o «Busca al paciente Juan Pérez»."
    resultados = buscar_pacientes(tipo, valor)
    if not resultados:
        return "No encontré pacientes que coincidan con la búsqueda en la base de datos actual."
    if len(resultados) > 8:
        return "Hay más de 8 coincidencias. Especifica el DNI o un nombre y apellido más completos."
    if len(resultados) > 1:
        lineas = ["Encontré varios pacientes. Indica el DNI para abrir el expediente correcto:"]
        lineas.extend(f"- {p.nombres} {p.apellidos} — DNI: {p.dni}" for p in resultados)
        return "\n".join(lineas)
    return formatear_paciente(resultados[0])
