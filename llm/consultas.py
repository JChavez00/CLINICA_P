
"""Consultas estadísticas y búsqueda de pacientes.

- Las estadísticas agregadas pueden enviarse al LLM.
- Los datos individuales de pacientes se procesan en Flask.
- Compatible con SQLite (local) y PostgreSQL (Supabase).
"""

import re
import unicodedata
from datetime import timedelta

from sqlalchemy import func

from models import db, Paciente, Atencion, MLDemandaDiaria


# ============================================================
# 1. FUNCIONES DE COMPATIBILIDAD SQL
# ============================================================

def _motor_base_datos():
    """Identifica el motor de base de datos utilizado."""
    return db.session.get_bind().dialect.name


def _expresion_mes(columna_fecha):
    """Agrupa fechas por año y mes en SQLite o PostgreSQL."""
    motor = _motor_base_datos()

    if motor == "postgresql":
        return func.to_char(columna_fecha, "YYYY-MM")

    if motor == "sqlite":
        return func.strftime("%Y-%m", columna_fecha)

    raise RuntimeError(
        f"Motor de base de datos no compatible: {motor}"
    )


# ============================================================
# 2. CONSULTAS ESTADÍSTICAS AGREGADAS
# ============================================================

def obtener_resumen():
    """Compatibilidad: agregados seguros, sin texto libre ni metricas fijas."""
    from ml.datos import hoy_peru
    from .herramientas import estadisticas_periodo
    hoy = hoy_peru()
    return estadisticas_periodo({}, {"desde": hoy.replace(day=1).isoformat(), "hasta": hoy.isoformat()})


# ============================================================
# 3. NORMALIZACIÓN DE TEXTO
# ============================================================

def _normalizar(texto):
    """Elimina tildes y convierte a minúsculas."""

    texto = unicodedata.normalize(
        "NFKD",
        str(texto or "")
    )

    return "".join(
        caracter
        for caracter in texto
        if not unicodedata.combining(caracter)
    ).lower().strip()


# ============================================================
# 4. INTERPRETACIÓN DE BÚSQUEDA
# ============================================================

def interpretar_busqueda(pregunta):
    """Devuelve (tipo, valor, historial) o None.

    Las búsquedas individuales se procesan en Flask
    y no se envían a Gemini.
    """

    texto = str(pregunta or "").strip()
    normal = _normalizar(texto)

    # Aceptar DNI de 8 o 9 dígitos.
    dni = re.search(
        r"(?<!\d)\d{8,9}(?!\d)",
        texto
    )

    es_paciente = bool(
        re.search(
            r"\b("
            r"paciente|pacientes|dni|historial|"
            r"historia clinica|expediente|"
            r"ultima atencion|ultimo diagnostico|"
            r"receta|diagnostico|"
            r"busca(?:r|me)? al?|"
            r"muestra(?:me)? al?|"
            r"datos de|atenciones de"
            r")\b",
            normal
        )
    )

    if dni:
        return ("dni", dni.group(), True)

    if not es_paciente:
        return None

    patrones = [
        (
            r"(?:dni|paciente|historial|"
            r"historia clinica|expediente|"
            r"datos de|atenciones de|"
            r"diagnosticos? de|receta de|"
            r"ultima atencion de|"
            r"ultimo diagnostico de|"
            r"busca(?:r|me)? al?\b|"
            r"muestra(?:me)? al?\b)"
            r"\s*"
            r"(?:(?:del|de|al|a|con|por|"
            r"llamado|llamada|nombre)\s+)?"
            r"\s*(.*)$"
        )
    ]

    nombre = ""

    for patron in patrones:
        coincidencia = re.search(patron, normal)

        if coincidencia:
            nombre = coincidencia.group(1).strip(
                " ?.,:;!\"'"
            )
            break

    nombre = re.sub(
        r"^(?:(?:nombre|apellidos?|paciente|"
        r"del|de|al|a|con|por)\s+)+",
        "",
        nombre
    ).strip()

    if not nombre or nombre in {
        "hoy", "ayer", "todos", "todas",
        "los", "las", "septiembre"
    }:
        return ("ayuda", "", False)

    if len(nombre) < 3:
        return ("ayuda", "", False)

    return ("nombre", nombre, True)


# ============================================================
# 5. BÚSQUEDA DE PACIENTES
# ============================================================

def buscar_pacientes(tipo, valor, limite=8):
    """Busca pacientes por DNI o nombre.

    No distingue tildes ni mayúsculas.

    Compatible con SQLite y PostgreSQL.
    """

    if tipo == "dni":
        return (
            Paciente.query
            .filter(
                Paciente.dni == str(valor).strip()
            )
            .limit(1)
            .all()
        )

    if tipo != "nombre":
        return []

    palabras = _normalizar(valor).split()[:6]

    if not palabras:
        return []

    total = Paciente.query.count()

    if total > 5000:
        raise RuntimeError(
            "La búsqueda sin tildes requiere un "
            "índice de nombres normalizados para "
            "bases de más de 5000 pacientes."
        )

    candidatos = (
        Paciente.query
        .order_by(
            Paciente.apellidos,
            Paciente.nombres
        )
        .all()
    )

    encontrados = []

    for paciente in candidatos:

        nombre_completo = _normalizar(
            f"{paciente.nombres or ''} "
            f"{paciente.apellidos or ''}"
        )

        tokens = nombre_completo.split()

        coincide = all(
            any(
                palabra in token
                for token in tokens
            )
            for palabra in palabras
        )

        if coincide:
            encontrados.append(paciente)

            if len(encontrados) > limite:
                break

    return encontrados


# ============================================================
# 6. FORMATO DE FECHAS
# ============================================================

def _fecha(valor):
    """Convierte fechas a texto para mostrarlas."""

    if valor is None:
        return "No registrado"

    if hasattr(valor, "isoformat"):
        return valor.isoformat()

    return str(valor)


# ============================================================
# 7. FORMATEAR FICHA DEL PACIENTE
# ============================================================

def formatear_paciente(
    paciente,
    incluir_historial=True
):
    """Construye una ficha clínica en Flask.

    No envía datos individuales a Gemini.
    """

    campos = [
        (
            "Paciente",
            (
                f"{paciente.nombres or ''} "
                f"{paciente.apellidos or ''}"
            ).strip()
        ),
        ("DNI", paciente.dni),
        (
            "Fecha de nacimiento",
            _fecha(paciente.fecha_nacimiento)
        ),
        ("Sexo", paciente.sexo),
        ("Teléfono", paciente.telefono),
        ("Departamento", paciente.departamento),
        ("Provincia", paciente.provincia),
        ("Distrito", paciente.distrito),
        (
            "Dirección",
            " ".join(
                str(x)
                for x in (
                    paciente.tipo_via,
                    paciente.nombre_via
                )
                if x
            )
        )
    ]

    lineas = ["**Ficha del paciente**"]

    lineas.extend(
        f"**{etiqueta}:** "
        f"{valor if valor else 'No registrado'}"
        for etiqueta, valor in campos
    )

    if incluir_historial:

        total = (
            Atencion.query
            .filter_by(paciente_id=paciente.id)
            .count()
        )

        atenciones = (
            Atencion.query
            .filter_by(paciente_id=paciente.id)
            .order_by(
                Atencion.fecha.desc(),
                Atencion.id.desc()
            )
            .limit(20)
            .all()
        )

        lineas.append(
            f"\n**Historial de atenciones:** "
            f"{total} registro(s)."
        )

        if total > len(atenciones):
            lineas.append(
                "Se muestran las 20 atenciones "
                "más recientes."
            )

        for i, atencion in enumerate(
            atenciones, 1
        ):
            lineas.extend([
                (
                    f"\n**Atención {i} — "
                    f"{_fecha(atencion.fecha)}**"
                ),
                (
                    f"- Hora: "
                    f"{atencion.hora or 'No registrada'}"
                ),
                (
                    f"- Motivo: "
                    f"{atencion.motivo or 'No registrado'}"
                ),
                (
                    f"- Síntomas: "
                    f"{atencion.sintomas or 'No registrados'}"
                ),
                (
                    f"- Diagnóstico: "
                    f"{atencion.diagnostico or 'No registrado'}"
                ),
                (
                    f"- Receta: "
                    f"{atencion.receta or 'No registrada'}"
                ),
                (
                    f"- Notas: "
                    f"{atencion.notas or 'No registradas'}"
                ),
                (
                    f"- Estado: "
                    f"{atencion.estado or 'No registrado'}"
                )
            ])

    return "\n".join(lineas)


# ============================================================
# 8. RESPUESTA A BÚSQUEDAS INDIVIDUALES
# ============================================================

def respuesta_busqueda(tipo, valor):
    """Responde búsquedas sin llamar a Gemini."""

    if tipo == "ayuda":
        return (
            "Para consultar una ficha, indica el DNI "
            "de 8 o 9 dígitos o el nombre del paciente. "
            "Ejemplo: «Historial del DNI 12345678» "
            "o «Busca al paciente Juan Pérez»."
        )

    resultados = buscar_pacientes(
        tipo,
        valor
    )

    if not resultados:
        return (
            "No encontré pacientes que coincidan "
            "con la búsqueda en la base de datos actual."
        )

    if len(resultados) > 8:
        return (
            "Hay más de 8 coincidencias. "
            "Especifica el DNI o un nombre "
            "y apellido más completos."
        )

    if len(resultados) > 1:

        lineas = [
            "Encontré varios pacientes. "
            "Indica el DNI para abrir "
            "el expediente correcto:"
        ]

        lineas.extend(
            (
                f"- {p.nombres} {p.apellidos} "
                f"— DNI: {p.dni}"
            )
            for p in resultados
        )

        return "\n".join(lineas)

    return formatear_paciente(
        resultados[0]
    )
