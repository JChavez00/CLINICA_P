from datetime import datetime, date
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
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)

    atenciones = db.relationship(
        "Atencion", back_populates="paciente", order_by="Atencion.creado_en.desc()"
    )

    @property
    def nombre_completo(self):
        return f"{self.nombres} {self.apellidos}".strip()

    def to_dict(self):
        return {
            "dni": self.dni,
            "nombres": self.nombres,
            "apellidos": self.apellidos,
            "fecha_nacimiento": self.fecha_nacimiento,
            "sexo": self.sexo,
            "telefono": self.telefono,
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
