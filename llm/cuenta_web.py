import hashlib
import hmac
import secrets
from flask import Blueprint, request, session, redirect, url_for, render_template, jsonify
from models import db, Notificacion, ahora_utc
from .perfil import crear, actualizar, cambiar_clave, EVENTOS
from .rutas import protegido, cuerpo
from .notificaciones import TITULOS

bp_cuenta = Blueprint("cuenta", __name__)


@bp_cuenta.before_request
def acceso():
    if request.content_length and request.content_length>16000:
        return jsonify(error="Solicitud demasiado extensa"),413
    if not session.get("autenticado"):
        return (jsonify(error="Inicia sesión"), 401) if request.path.startswith("/api/") else redirect(url_for("login"))
    session.setdefault("ia_csrf", secrets.token_urlsafe(32))


@bp_cuenta.after_request
def cabeceras(r):
    r.headers["Cache-Control"] = "no-store"
    r.headers["Referrer-Policy"] = "no-referrer"
    r.headers["X-Content-Type-Options"] = "nosniff"
    return r


@bp_cuenta.route("/mi-perfil")
def pagina():
    from .notificaciones import configurado
    return render_template("perfil.html", perfil=crear(), eventos=EVENTOS, titulos=TITULOS,
                           csrf=session["ia_csrf"], correo_configurado=configurado())


@bp_cuenta.route("/api/perfil", methods=["POST"])
@protegido(csrf=True)
def guardar():
    actualizar(crear(), cuerpo())
    return jsonify(ok=True)


@bp_cuenta.route("/api/perfil/clave", methods=["POST"])
@protegido(csrf=True)
def clave():
    p = crear()
    datos = cuerpo()
    cambiar_clave(p, datos.get("actual"), datos.get("nueva"))
    session.clear()  # Invalida esta sesión y las anteriores por versión.
    return jsonify(ok=True, mensaje="Contraseña actualizada. Inicia sesión de nuevo.")


@bp_cuenta.route("/api/perfil/verificar", methods=["POST"])
@protegido(csrf=True)
def solicitar_verificacion():
    from .notificaciones import verificar_correo
    return jsonify(estado=verificar_correo(crear()))


@bp_cuenta.route("/mi-perfil/verificar", methods=["GET", "POST"])
def verificar():
    p = crear()
    token = request.values.get("token", "")
    valido = bool(p.verificacion_hash and p.verificacion_hasta and p.verificacion_hasta > ahora_utc()
        and hmac.compare_digest(p.verificacion_hash, hashlib.sha256(token.encode()).hexdigest()))
    if request.method == "POST":
        if not valido or not hmac.compare_digest(request.form.get("csrf", ""), session["ia_csrf"]):
            return "Enlace inválido o caducado", 400
        p.verificado = True
        p.verificacion_hash = None
        p.verificacion_hasta = None
        db.session.commit()
        return redirect(url_for("cuenta.pagina"))
    return render_template("verificar_correo.html", valido=valido, token=token, csrf=session["ia_csrf"])


@bp_cuenta.route("/notificaciones")
def bandeja():
    return render_template("notificaciones.html", csrf=session["ia_csrf"])


@bp_cuenta.route("/api/notificaciones")
def listar():
    return jsonify(notificaciones=[{"id":n.id, "titulo":TITULOS[n.evento]+(" · "+n.clave.rsplit(":",1)[-1] if n.evento=="demanda_alta" else ""), "fecha":n.creada_en.isoformat()+"Z",
        "leida":n.leida, "correo":n.correo_estado, "informe_id":n.informe_id}
        for n in Notificacion.query.filter_by(propietario_id=1).order_by(Notificacion.creada_en.desc()).limit(100).all()])


@bp_cuenta.route("/api/notificaciones/<uuid:identificador>/leer", methods=["POST"])
@protegido(csrf=True)
def leer(identificador):
    n = Notificacion.query.filter_by(id=str(identificador), propietario_id=1).first_or_404()
    n.leida = True
    db.session.commit()
    return jsonify(ok=True)
