"""Contratos estrictos: los proveedores no definen permisos ni SQL."""
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from ml.datos import validar_fecha


class Estricto(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Plan(Estricto):
    herramienta: str = Field(min_length=1, max_length=50)
    argumentos: dict


class Busqueda(Estricto):
    limite: int = Field(default=20, ge=1, le=20)


class Periodo(Estricto):
    desde: str
    hasta: str

    @model_validator(mode="after")
    def validar(self):
        a, b = validar_fecha(self.desde), validar_fecha(self.hasta)
        if a > b or (b-a).days > 365:
            raise ValueError("El rango debe estar ordenado y no superar 366 días.")
        return self


class Comparacion(Periodo):
    desde_anterior: str
    hasta_anterior: str

    @model_validator(mode="after")
    def validar_anterior(self):
        Periodo(desde=self.desde_anterior, hasta=self.hasta_anterior)
        return self


class Pronosticos(Estricto):
    inicio: str
    dias: Literal[7, 15, 30] = 7

    @model_validator(mode="after")
    def validar(self):
        validar_fecha(self.inicio)
        return self


class Reporte(Periodo):
    tipo: Literal["diario", "semanal", "mensual", "rango"] = "rango"
    secciones: list[Literal["atenciones", "servicios", "costos", "ml"]] = Field(default_factory=lambda: ["atenciones"], min_length=1, max_length=4)

    @model_validator(mode="after")
    def validar_tipo(self):
        import calendar
        a,b=date.fromisoformat(self.desde),date.fromisoformat(self.hasta)
        if self.tipo=="diario" and a!=b: raise ValueError("Un reporte diario requiere la misma fecha inicial y final.")
        if self.tipo=="semanal" and (b-a).days!=6: raise ValueError("Un reporte semanal requiere siete días.")
        if self.tipo=="mensual" and (a.day!=1 or a.year!=b.year or a.month!=b.month or b.day!=calendar.monthrange(a.year,a.month)[1]):
            raise ValueError("Un reporte mensual requiere un mes completo.")
        return self


class ConfiguracionTarea(Estricto):
    tipo: Literal["reporte", "estadisticas", "alerta_alta", "consulta_ml"]
    frecuencia: Literal["diaria", "semanal", "mensual"]
    hora: int = Field(default=8, ge=0, le=23)
    dia_semana: int = Field(default=0, ge=0, le=6)
    dia_mes: int = Field(default=1, ge=1, le=28)
    canal: Literal["panel"] = "panel"


class Interpretacion(Estricto):
    hechos: list[str] = Field(max_length=8)
    acciones: list[Literal["revisar_personal", "revisar_materiales", "revisar_completitud", "revisar_duplicados", "validar_ml"]] = Field(max_length=5)


class ErrorAgente(Exception):
    def __init__(self, codigo, estado=502):
        self.codigo, self.estado = codigo, estado
        super().__init__(codigo)
