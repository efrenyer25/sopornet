"""CRUD de clientes."""
import re

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy import or_

from ..auth import rol_requerido
from ..extensions import db
from ..models import Cliente

bp = Blueprint("clientes", __name__, url_prefix="/clientes")

CAMPOS = ("nombre", "documento", "email", "telefono", "direccion", "plan")
PATRON_DOCUMENTO = re.compile(r"^[VEJGP]-\d{6,9}(-\d)?$")


def validar_cliente(datos: dict, cliente_id: int | None = None) -> list[str]:
    errores = []
    if len(datos.get("nombre", "").strip()) < 3:
        errores.append("El nombre debe tener al menos 3 caracteres.")
    documento = datos.get("documento", "").strip().upper()
    if not PATRON_DOCUMENTO.match(documento):
        errores.append("Documento inválido. Usa el formato V-12345678 o J-12345678-9.")
    else:
        existente = Cliente.query.filter_by(documento=documento).first()
        if existente and existente.id != cliente_id:
            errores.append("Ya existe un cliente con ese documento.")
    email = datos.get("email", "").strip()
    if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        errores.append("Correo electrónico inválido.")
    return errores


def _obtener(cliente_id: int) -> Cliente:
    cliente = db.session.get(Cliente, cliente_id)
    if not cliente:
        abort(404)
    return cliente


@bp.route("/")
@login_required
def listar():
    q = request.args.get("q", "").strip()
    consulta = Cliente.query
    if q:
        consulta = consulta.filter(or_(Cliente.nombre.ilike(f"%{q}%"), Cliente.documento.ilike(f"%{q}%")))
    return render_template("clientes/lista.html", clientes=consulta.order_by(Cliente.nombre).all(), q=q)


@bp.route("/nuevo", methods=["GET", "POST"])
@bp.route("/<int:cliente_id>/editar", methods=["GET", "POST"])
@login_required
def formulario(cliente_id: int | None = None):
    cliente = _obtener(cliente_id) if cliente_id else None
    datos = cliente.to_dict() if cliente else {}

    if request.method == "POST":
        datos = {c: request.form.get(c, "").strip() for c in CAMPOS}
        datos["documento"] = datos["documento"].upper()
        errores = validar_cliente(datos, cliente_id)
        if errores:
            for error in errores:
                flash(error, "danger")
        else:
            cliente = cliente or Cliente()
            for campo in CAMPOS:
                setattr(cliente, campo, datos[campo] or None)
            db.session.add(cliente)
            db.session.commit()
            flash("Cliente guardado.", "success")
            return redirect(url_for("clientes.detalle", cliente_id=cliente.id))

    return render_template("clientes/formulario.html", datos=datos, cliente=cliente)


@bp.route("/<int:cliente_id>")
@login_required
def detalle(cliente_id: int):
    return render_template("clientes/detalle.html", cliente=_obtener(cliente_id))


@bp.route("/<int:cliente_id>/eliminar", methods=["POST"])
@login_required
@rol_requerido("admin")
def eliminar(cliente_id: int):
    cliente = _obtener(cliente_id)
    db.session.delete(cliente)
    db.session.commit()
    flash(f"Cliente «{cliente.nombre}» y sus tickets fueron eliminados.", "info")
    return redirect(url_for("clientes.listar"))
