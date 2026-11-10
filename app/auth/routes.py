"""Autenticación: registro, inicio y cierre de sesión."""
import re

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..extensions import db
from ..models import Usuario

bp = Blueprint("auth", __name__)

PATRON_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validar_registro(datos: dict) -> list[str]:
    """Devuelve la lista de errores del formulario de registro (vacía si es válido)."""
    errores = []
    if len(datos["nombre"]) < 3:
        errores.append("El nombre debe tener al menos 3 caracteres.")
    if not PATRON_EMAIL.match(datos["email"]):
        errores.append("Correo electrónico inválido.")
    elif Usuario.query.filter_by(email=datos["email"]).first():
        errores.append("Ya existe una cuenta con ese correo.")
    if len(datos["password"]) < 8:
        errores.append("La contraseña debe tener al menos 8 caracteres.")
    elif not (re.search(r"[A-Za-z]", datos["password"]) and re.search(r"\d", datos["password"])):
        errores.append("La contraseña debe combinar letras y números.")
    if datos["password"] != datos["confirmar"]:
        errores.append("Las contraseñas no coinciden.")
    return errores


@bp.route("/registro", methods=["GET", "POST"])
def registro():
    if not current_app.config.get("REGISTRO_HABILITADO", True):
        abort(404)
    if current_user.is_authenticated:
        return redirect(url_for("tickets.dashboard"))

    datos = {"nombre": "", "email": ""}
    if request.method == "POST":
        datos = {
            "nombre": request.form.get("nombre", "").strip(),
            "email": request.form.get("email", "").strip().lower(),
            "password": request.form.get("password", ""),
            "confirmar": request.form.get("confirmar", ""),
        }
        errores = validar_registro(datos)
        if errores:
            for error in errores:
                flash(error, "danger")
        else:
            # Por seguridad, las cuentas nuevas siempre son "agente";
            # un administrador puede cambiar el rol después.
            usuario = Usuario(nombre=datos["nombre"], email=datos["email"], rol="agente")
            usuario.set_password(datos["password"])
            db.session.add(usuario)
            db.session.commit()
            login_user(usuario)
            flash(f"¡Cuenta creada! Bienvenido(a), {usuario.nombre}.", "success")
            return redirect(url_for("tickets.dashboard"))

    return render_template("auth/registro.html", datos=datos)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("tickets.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        usuario = Usuario.query.filter_by(email=email).first()

        if usuario and usuario.activo and usuario.check_password(password):
            login_user(usuario, remember=bool(request.form.get("recordar")))
            flash(f"Bienvenido(a), {usuario.nombre}.", "success")
            siguiente = request.args.get("next")
            # Solo se permiten redirecciones internas (evita open redirect)
            if not siguiente or not siguiente.startswith("/") or siguiente.startswith("//"):
                siguiente = url_for("tickets.dashboard")
            return redirect(siguiente)

        flash("Correo o contraseña incorrectos.", "danger")

    return render_template("auth/login.html")


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("auth.login"))
