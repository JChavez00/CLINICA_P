"""Migración idempotente y aditiva, válida para SQLite y PostgreSQL."""
from models import (db, Perfil, TareaPerfil, Notificacion, ArchivoInforme, EstadoProgramador,
                    AgenteEjecucion, AgenteRecorrido, InformeIA, TareaIA, TareaIAEjecucion)


def migrar():
    # No crea cuentas ni cambia credenciales. La cuenta se migra al autenticar.
    for modelo in (AgenteEjecucion, AgenteRecorrido, InformeIA, TareaIA, TareaIAEjecucion,
                   Perfil, TareaPerfil, Notificacion, ArchivoInforme, EstadoProgramador):
        modelo.__table__.create(bind=db.engine, checkfirst=True)
    if db.session.get(Perfil, 1):
        from .programacion import asociar
        for tarea in TareaIA.query.all():
            asociar(tarea)
        db.session.commit()
    return {"tablas_verificadas": 10, "nota": "Migración aditiva; cuenta y tareas existentes conservadas."}
