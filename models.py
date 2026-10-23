from datetime import datetime, date, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Paciente(db.Model):
    """Datos básicos del paciente. Se guarda una sola vez por DNI y se
    reutiliza en cada atención futura, para no volver a escribir todo."""

    __tablename__ = "pacientes"

    id = db.Column(db.Integer, primary_key=True)
    dni = db.Column(db.String(15), unique=True, nullable=False, index=True)
    nombres = db.Column(db.String(120), nullable=False)
    apellidos = db.Column(db.String(120), nullable=False)
    fecha_nacimiento = db.Column(db.String(20))  # texto libre: dd/mm/aaaa
    sexo = db.Column(db.String(20))
    telefono = db.Column(db.String(30))

    # --- Domicilio (para el mapa y futuros reportes por zona) ---
    departamento = db.Column(db.String(80))
    provincia = db.Column(db.String(80))
    distrito = db.Column(db.String(80), index=True)  # index: se filtrará seguido en reportes
    tipo_via = db.Column(db.String(30))
    nombre_via = db.Column(db.String(150))
    latitud = db.Column(db.Float)
    longitud = db.Column(db.Float)

    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    atenciones = db.relationship(
        "Atencion", back_populates="paciente", order_by="Atencion.creado_en.desc()"
    )

    @property
    def nombre_completo(self):
        return f"{self.nombres} {self.apellidos}".strip()

    @property
    def direccion_completa(self):
        via = f"{self.tipo_via or ''} {self.nombre_via or ''}".strip()
        partes = [p for p in [via, self.distrito, self.provincia, self.departamento] if p]
        return ", ".join(partes) if partes else ""

    @property
    def tiene_ubicacion(self):
        return self.latitud is not None and self.longitud is not None

    def to_dict(self):
        return {
            "dni": self.dni,
            "nombres": self.nombres,
            "apellidos": self.apellidos,
            "fecha_nacimiento": self.fecha_nacimiento,
            "sexo": self.sexo,
            "telefono": self.telefono,
            "departamento": self.departamento,
            "provincia": self.provincia,
            "distrito": self.distrito,
            "tipo_via": self.tipo_via,
            "nombre_via": self.nombre_via,
            "latitud": self.latitud,
            "longitud": self.longitud,
        }


class Atencion(db.Model):
    """Un registro de consulta/atención médica en una fecha específica."""

    __tablename__ = "atenciones"

    id = db.Column(db.Integer, primary_key=True)
    paciente_id = db.Column(db.Integer, db.ForeignKey("pacientes.id"), nullable=False)

    fecha = db.Column(db.Date, default=date.today, index=True)
    hora = db.Column(db.String(10))  # HH:MM, se guarda como texto para mostrar fácil

    motivo = db.Column(db.String(255))
    sintomas = db.Column(db.String(255))
    diagnostico = db.Column(db.String(255))
    receta = db.Column(db.Text)
    notas = db.Column(db.Text)
    estado = db.Column(db.String(20), default="Finalizado")  # Finalizado / En proceso

    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    paciente = db.relationship("Paciente", back_populates="atenciones")

    def to_dict(self):
        return {
            "fecha": self.fecha.strftime("%d/%m/%Y") if self.fecha else "",
            "hora": self.hora,
            "dni": self.paciente.dni if self.paciente else "",
            "paciente": self.paciente.nombre_completo if self.paciente else "",
            "motivo": self.motivo,
            "sintomas": self.sintomas,
            "diagnostico": self.diagnostico,
            "receta": self.receta,
            "notas": self.notas,
            "estado": self.estado,
        }


class MLDemandaDiaria(db.Model):
    __tablename__ = "ml_demanda_diaria"

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, unique=True, nullable=False)
    total_atenciones = db.Column(db.Integer, nullable=False, default=0)
    dia_semana = db.Column(db.Integer, nullable=False)
    mes = db.Column(db.Integer, nullable=False)
    es_feriado = db.Column(db.Boolean, default=False)
    nivel_demanda = db.Column(db.String(10))


class MLPrediccionDemanda(db.Model):
    __tablename__ = "ml_predicciones_demanda"

    id = db.Column(db.Integer, primary_key=True)
    fecha_objetivo = db.Column(db.Date, nullable=False)
    fecha_prediccion = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )
    nivel_predicho = db.Column(db.String(10), nullable=False)
    probabilidad = db.Column(db.Float)
    modelo_version = db.Column(db.String(20))


class MLPronostico(db.Model):
    """Pronósticos v2; tabla nueva, no modifica los registros del modelo legado."""
    __tablename__ = "ml_pronosticos_v2"
    __table_args__ = (
        db.UniqueConstraint("fecha_objetivo", "dia_generacion", "objetivo", "version", name="uq_ml_pronostico_diario"),
    )
    id = db.Column(db.Integer, primary_key=True)
    fecha_objetivo = db.Column(db.Date, nullable=False, index=True)
    dia_generacion = db.Column(db.Date, nullable=False)
    generado_en = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    objetivo = db.Column(db.String(20), nullable=False)
    modelo = db.Column(db.String(50), nullable=False)
    version = db.Column(db.String(40), nullable=False)
    resultado = db.Column(db.JSON, nullable=False)
    estado = db.Column(db.String(20), nullable=False, default="generado")


def ahora_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AgenteEjecucion(db.Model):
    __tablename__ = "agente_ejecuciones"
    id = db.Column(db.String(36), primary_key=True)
    agente = db.Column(db.String(40), nullable=False)
    modulo = db.Column(db.String(30), nullable=False)
    herramienta = db.Column(db.String(50), nullable=False)
    fecha = db.Column(db.DateTime, default=ahora_utc, nullable=False, index=True)
    duracion_ms = db.Column(db.Integer, nullable=False)
    estado = db.Column(db.String(20), nullable=False)
    error_codigo = db.Column(db.String(50))


class AgenteRecorrido(db.Model):
    """Pasos técnicos medidos; nunca conserva consultas ni resultados clínicos."""
    __tablename__ = "agente_recorridos"
    ejecucion_id = db.Column(db.String(36), db.ForeignKey("agente_ejecuciones.id"), primary_key=True)
    flujo_id = db.Column(db.String(36), nullable=False, index=True)
    padre_id = db.Column(db.String(36))
    proveedor = db.Column(db.String(30), nullable=False)
    modelo = db.Column(db.String(120), nullable=False)
    pasos = db.Column(db.JSON, nullable=False)


class InformeIA(db.Model):
    __tablename__ = "agente_informes"
    id = db.Column(db.String(36), primary_key=True)
    generado_en = db.Column(db.DateTime, default=ahora_utc, nullable=False)
    desde = db.Column(db.Date, nullable=False)
    hasta = db.Column(db.Date, nullable=False)
    contenido = db.Column(db.JSON, nullable=False)  # sólo agregados y conclusiones controladas


class TareaIA(db.Model):
    __tablename__ = "agente_tareas"
    id = db.Column(db.String(36), primary_key=True)
    configuracion = db.Column(db.JSON, nullable=False)
    creada_en = db.Column(db.DateTime, default=ahora_utc, nullable=False)
    activa = db.Column(db.Boolean, default=True, nullable=False)
    confirmada = db.Column(db.Boolean, nullable=False, default=False)


class TareaIAEjecucion(db.Model):
    __tablename__ = "agente_tarea_ejecuciones"
    __table_args__ = (db.UniqueConstraint("tarea_id", "periodo", name="uq_agente_tarea_periodo"),)
    id = db.Column(db.String(36), primary_key=True)
    tarea_id = db.Column(db.String(36), db.ForeignKey("agente_tareas.id"), nullable=False)
    periodo = db.Column(db.String(30), nullable=False)
    iniciada_en = db.Column(db.DateTime, default=ahora_utc, nullable=False)
    estado = db.Column(db.String(20), nullable=False)
    intentos = db.Column(db.Integer, default=1, nullable=False)
    resultado = db.Column(db.JSON)
    error_codigo = db.Column(db.String(50))


class Perfil(db.Model):
    __tablename__ = "cuenta_perfil"
    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(120), unique=True, nullable=False)
    nombre = db.Column(db.String(160), nullable=False)
    clave_hash = db.Column(db.String(512), nullable=False)
    rol = db.Column(db.String(40), default="Médico / administrador", nullable=False)
    zona = db.Column(db.String(80), default="America/Lima", nullable=False)
    correo = db.Column(db.String(254), default="", nullable=False)
    verificado = db.Column(db.Boolean, default=False, nullable=False)
    avisos = db.Column(db.Boolean, default=False, nullable=False)
    eventos = db.Column(db.JSON, default=list, nullable=False)
    sesion_version = db.Column(db.Integer, default=1, nullable=False)
    verificacion_hash = db.Column(db.String(64))
    verificacion_hasta = db.Column(db.DateTime)


class TareaPerfil(db.Model):
    """Extensión aditiva: conserva intactas las tareas anteriores."""
    __tablename__ = "cuenta_tareas"
    tarea_id = db.Column(db.String(36), db.ForeignKey("agente_tareas.id"), primary_key=True)
    propietario_id = db.Column(db.Integer, db.ForeignKey("cuenta_perfil.id"), nullable=False)
    nombre = db.Column(db.String(160), nullable=False)
    zona = db.Column(db.String(80), default="America/Lima", nullable=False)
    proxima = db.Column(db.DateTime)
    ultima = db.Column(db.DateTime)


class Notificacion(db.Model):
    __tablename__ = "cuenta_notificaciones"
    id = db.Column(db.String(36), primary_key=True)
    propietario_id = db.Column(db.Integer, db.ForeignKey("cuenta_perfil.id"), nullable=False)
    clave = db.Column(db.String(200), unique=True, nullable=False)
    evento = db.Column(db.String(40), nullable=False)
    creada_en = db.Column(db.DateTime, default=ahora_utc, nullable=False)
    leida = db.Column(db.Boolean, default=False, nullable=False)
    informe_id = db.Column(db.String(36), db.ForeignKey("agente_informes.id"))
    tarea_id = db.Column(db.String(36), db.ForeignKey("agente_tareas.id"))
    correo_estado = db.Column(db.String(40), default="pendiente", nullable=False)
    correo_intentos = db.Column(db.Integer, default=0, nullable=False)
    correo_reclamado = db.Column(db.DateTime)
    destinatario = db.Column(db.String(254))


class ArchivoInforme(db.Model):
    __tablename__ = "cuenta_archivos"
    __table_args__ = (db.UniqueConstraint("informe_id", "formato", name="uq_cuenta_archivo_formato"),)
    id = db.Column(db.String(36), primary_key=True)
    informe_id = db.Column(db.String(36), db.ForeignKey("agente_informes.id"), nullable=False)
    propietario_id = db.Column(db.Integer, db.ForeignKey("cuenta_perfil.id"), nullable=False)
    tarea_id = db.Column(db.String(36), db.ForeignKey("agente_tareas.id"))
    formato = db.Column(db.String(8), nullable=False)
    generado_en = db.Column(db.DateTime, default=ahora_utc, nullable=False)
    estado = db.Column(db.String(40), nullable=False)
    objeto = db.Column(db.String(200), nullable=False)
    sha256 = db.Column(db.String(64), nullable=False)
    contenido = db.Column(db.LargeBinary, nullable=False)


class EstadoProgramador(db.Model):
    __tablename__ = "cuenta_programador"
    origen = db.Column(db.String(30), primary_key=True)
    revisado_en = db.Column(db.DateTime, nullable=False)
    ultima_tarea_en = db.Column(db.DateTime)
    estado = db.Column(db.String(20), nullable=False)
