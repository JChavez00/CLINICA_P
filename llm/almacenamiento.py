"""Archivo durable en DB; réplica opcional en bucket privado, sin URLs públicas."""
import hashlib
import io
import os
from uuid import uuid4
from urllib.parse import quote
import requests
from models import db, ArchivoInforme
from .perfil import crear

MIME = {"pdf":"application/pdf", "xlsx":"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}


def configurado():
    return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY") and os.getenv("REPORTES_BUCKET"))


def replicar(archivo):
    if not configurado():
        return
    try:
        base = os.environ["SUPABASE_URL"].rstrip("/")
        if not base.startswith("https://"):
            raise ValueError()
        clave = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        cab = {"Authorization":"Bearer "+clave, "apikey":clave}
        bucket = quote(os.environ["REPORTES_BUCKET"], safe="")
        info = requests.get(base+"/storage/v1/bucket/"+bucket, headers=cab, timeout=15)
        info.raise_for_status()
        if info.json().get("public") is not False:
            archivo.estado = "error_bucket_no_privado"
            return
        url = base+"/storage/v1/object/"+bucket+"/"+quote(archivo.objeto, safe="/")
        r = requests.post(url, headers={**cab, "Content-Type":MIME[archivo.formato], "x-upsert":"false"}, data=archivo.contenido, timeout=25)
        if r.status_code in (400, 409):
            # Recuperación tras caída entre upload y commit: verificar, no sobrescribir.
            previo = requests.get(base+"/storage/v1/object/authenticated/"+bucket+"/"+quote(archivo.objeto, safe="/"), headers=cab, timeout=25)
            previo.raise_for_status()
            if hashlib.sha256(previo.content).hexdigest() != archivo.sha256:
                raise ValueError()
        else:
            r.raise_for_status()
        archivo.estado = "supabase_y_base"
    except Exception:
        archivo.estado = "base_replica_pendiente"


def conservar(informe, tarea_id=None):
    from .reportes import pdf, excel
    propietario = crear()
    for formato, generar in (("pdf", pdf), ("xlsx", excel)):
        archivo = ArchivoInforme.query.filter_by(informe_id=informe.id, formato=formato).first()
        if archivo is None:
            contenido = generar(informe).getvalue()
            archivo = ArchivoInforme(id=str(uuid4()), informe_id=informe.id, propietario_id=propietario.id,
                tarea_id=tarea_id, formato=formato, objeto=f"{propietario.id}/{informe.id}/{uuid4()}.{formato}",
                contenido=contenido, sha256=hashlib.sha256(contenido).hexdigest(), estado="base_persistente")
            db.session.add(archivo)
            db.session.commit()  # Primero conservar, luego contactar servicios externos.
        if tarea_id and not archivo.tarea_id:
            archivo.tarea_id = tarea_id
        if archivo.estado != "supabase_y_base":
            replicar(archivo)
        db.session.commit()


def descargar(informe, formato):
    conservar(informe)
    archivo = ArchivoInforme.query.filter_by(informe_id=informe.id, formato=formato, propietario_id=1).first()
    if not archivo or hashlib.sha256(archivo.contenido).hexdigest() != archivo.sha256:
        raise ValueError("Archivo no disponible o integridad incorrecta")
    return io.BytesIO(archivo.contenido)
