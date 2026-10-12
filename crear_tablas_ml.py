
from app import app
from models import db, MLDemandaDiaria, MLPrediccionDemanda
from sqlalchemy import inspect

with app.app_context():
    inspector = inspect(db.engine)

    print("TABLAS ANTES:")
    print(inspector.get_table_names())

    # Crear únicamente las dos tablas nuevas
    MLDemandaDiaria.__table__.create(
        bind=db.engine, checkfirst=True
    )

    MLPrediccionDemanda.__table__.create(
        bind=db.engine, checkfirst=True
    )

    inspector = inspect(db.engine)

    print("\nTABLAS DESPUÉS:")
    print(inspector.get_table_names())

    print("\nTablas de Machine Learning verificadas.")
