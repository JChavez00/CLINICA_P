"""python -m ml.cli --help; tareas independientes del servidor web."""
import argparse
import json

from ml.runtime import contexto


def main(argv=None):
    parser = argparse.ArgumentParser(description="ML de demanda y cantidades (sin LLM)")
    parser.add_argument("comando", choices=["auditar", "entrenar", "inicializar", "pronosticar"])
    parser.add_argument("--database", help="URI SQLAlchemy; si se omite usa configuración existente")
    parser.add_argument("--dias", type=int, choices=[7, 15, 30], default=30)
    parser.add_argument("--inicio", help="AAAA-MM-DD futura; por defecto mañana en Perú")
    args = parser.parse_args(argv)
    app = contexto(args.database)
    try:
        with app.app_context():
            if args.comando == "inicializar":
                from models import db, MLPronostico
                MLPronostico.__table__.create(bind=db.engine, checkfirst=True)
                resultado = {"tabla_verificada": MLPronostico.__tablename__}
            elif args.comando == "entrenar":
                from ml.entrenar_modelo import entrenar
                meta = entrenar()
                resultado = {"version": meta["version"], "registros": meta["registros"],
                             "resultados": meta["resultados"]}
            elif args.comando == "auditar":
                from ml.datos import cargar_datos
                df, auditoria = cargar_datos()
                resultado = {"dias": len(df), "auditoria": auditoria}
            else:
                from ml.pronosticos import generar
                resultado = generar(args.dias, args.inicio)
        print(json.dumps(resultado, ensure_ascii=False, indent=2, allow_nan=False))
    except (ValueError, FileNotFoundError) as exc:
        parser.exit(1, str(exc) + "\n")


if __name__ == "__main__":
    main()
