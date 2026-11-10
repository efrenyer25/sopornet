"""Autenticación: inicio y cierre de sesión."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..models import Usuario

bp = Blueprint("auth", __name__)


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
