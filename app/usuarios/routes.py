"""Gestión de usuarios del sistema (solo administradores)."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..auth import rol_requerido
from ..extensions import db
from ..models import ROLES, Usuario

bp = Blueprint("usuarios", __name__, url_prefix="/usuarios")


@bp.route("/")
@login_required
@rol_requerido("admin")
def listar():
    return render_template("usuarios/lista.html", usuarios=Usuario.query.order_by(Usuario.nombre).all(), roles=ROLES)


@bp.route("/nuevo", methods=["POST"])
@login_required
@rol_requerido("admin")
def crear():
    nombre = request.form.get("nombre", "").strip()
    email = request.form.get("email", "").strip().lower()
    rol = request.form.get("rol", "agente")
    password = request.form.get("password", "")

    if len(nombre) < 3 or "@" not in email or rol not in ROLES or len(password) < 6:
        flash("Datos inválidos: nombre (mín. 3), correo válido y contraseña (mín. 6).", "danger")
    elif Usuario.query.filter_by(email=email).first():
        flash("Ya existe un usuario con ese correo.", "danger")
    else:
        usuario = Usuario(nombre=nombre, email=email, rol=rol)
        usuario.set_password(password)
        db.session.add(usuario)
        db.session.commit()
        flash(f"Usuario {nombre} creado.", "success")
    return redirect(url_for("usuarios.listar"))


@bp.route("/<int:usuario_id>/rol", methods=["POST"])
@login_required
@rol_requerido("admin")
def cambiar_rol(usuario_id: int):
    usuario = db.session.get(Usuario, usuario_id) or abort(404)
    rol = request.form.get("rol", "")
    if rol not in ROLES:
        flash("Rol inválido.", "danger")
    elif usuario.id == current_user.id:
        flash("No puedes cambiar tu propio rol.", "danger")
    else:
        usuario.rol = rol
        db.session.commit()
        flash(f"{usuario.nombre} ahora es {usuario.rol_legible}.", "success")
    return redirect(url_for("usuarios.listar"))


@bp.route("/<int:usuario_id>/estado", methods=["POST"])
@login_required
@rol_requerido("admin")
def alternar_estado(usuario_id: int):
    usuario = db.session.get(Usuario, usuario_id) or abort(404)
    if usuario.id == current_user.id:
        flash("No puedes desactivar tu propio usuario.", "danger")
    else:
        usuario.activo = not usuario.activo
        db.session.commit()
        flash(f"Usuario {'activado' if usuario.activo else 'desactivado'}.", "info")
    return redirect(url_for("usuarios.listar"))
