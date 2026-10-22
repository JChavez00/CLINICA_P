"""Comandos administrativos independientes del servidor y del cron ML."""
import argparse
import json

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from ml.runtime import contexto
from .esquemas import ErrorAgente


def operar(args):
    with contexto(args.database).app_context():
        if args.comando=="inicializar":
            from .migraciones import migrar
            return migrar()
        if args.comando=="ejecutar":
            from .tareas import ejecutar_programadas
            import os
            from models import db
            origen="render_cron" if os.getenv("RENDER_CRON_JOB") else "comando_manual"
            if origen=="render_cron" and db.engine.dialect.name!="postgresql":
                raise ErrorAgente("render_requiere_postgresql",400)
            return {"ejecuciones":ejecutar_programadas(origen=origen)}
        if args.comando=="estado":
            from .tareas import listar
            from .programacion import estado
            from .notificaciones import configurado as correo
            from .almacenamiento import configurado as storage
            return {"tareas":listar(),"programador":estado(),"correo_configurado":correo(),"storage_configurado":storage()}
        if args.comando=="archivar-reportes":
            from models import db, InformeIA
            from .almacenamiento import conservar
            cantidad=0
            identificadores=[i for (i,) in db.session.query(InformeIA.id).order_by(InformeIA.generado_en).all()]
            for identificador in identificadores:
                conservar(db.session.get(InformeIA,identificador));cantidad+=1
            return {"informes_archivados":cantidad}
        from .clientes import solicitar,modelo
        from .esquemas import Plan,Periodo
        estados=[]
        for proveedor in ("gemini","groq"):
            try:
                plan=Plan.model_validate(solicitar(proveedor,"Prueba de contrato: elige estadisticas_periodo con los parámetros proporcionados.",
                    {"parametros":{"desde":"2026-09-01","hasta":"2026-09-30"}},Plan.model_json_schema()))
                Periodo.model_validate(plan.argumentos)
                estado="ok" if plan.herramienta=="estadisticas_periodo" else "plan_no_valido"
            except (ErrorAgente,ValidationError) as exc:
                estado=exc.codigo if isinstance(exc,ErrorAgente) else "plan_no_valido"
            estados.append({"proveedor":proveedor,"modelo":modelo(proveedor),"estado":estado})
        return {"proveedores":estados}


def main(argv=None):
    parser=argparse.ArgumentParser(description="Agentes administrativos CLINICA_P")
    parser.add_argument("comando",choices=["inicializar","ejecutar","estado","archivar-reportes","verificar-proveedores"])
    parser.add_argument("--database",help="URI SQLAlchemy explícita; por defecto usa configuración existente")
    args=parser.parse_args(argv)
    try: resultado=operar(args)
    except SQLAlchemyError: parser.exit(1,"No se pudo acceder a las tablas de agentes. Verifica la conexión y ejecuta inicializar en una base autorizada.\n")
    except ErrorAgente as exc: parser.exit(1,"No se pudo completar la operación: "+exc.codigo+"\n")
    except (ValueError,ValidationError): parser.exit(1,"Configuración o parámetros inválidos.\n")
    print(json.dumps(resultado,ensure_ascii=False,indent=2))
    if args.comando=="ejecutar" and any(e["estado"]=="error" for e in resultado["ejecuciones"]):
        parser.exit(1,"Hay tareas con error; consulta sus códigos técnicos y reintentos en el panel.\n")
    if args.comando=="verificar-proveedores" and any(e["estado"]!="ok" for e in resultado["proveedores"]):
        parser.exit(1,"Hay proveedores sin verificar. No se cambiaron modelos.\n")


if __name__=="__main__": main()
