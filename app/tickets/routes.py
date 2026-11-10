"""Vistas web de tickets y dashboard."""
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..auth import rol_requerido
from ..extensions import db
from ..models import Categoria, Cliente, Comentario, Ticket, Usuario
from . import servicios

bp = Blueprint("tickets", __name__)


def _opciones_formulario() -> dict:
    return {
        "clientes": Cliente.query.order_by(Cliente.nombre).all(),
        "categorias": Categoria.query.order_by(Categoria.nombre).all(),
        "tecnicos": Usuario.query.filter(Usuario.rol.in_(["tecnico", "admin"]), Usuario.activo)
        .order_by(Usuario.nombre).all(),
    }


def _obtener_ticket(ticket_id: int) -> Ticket:
    ticket = db.session.get(Ticket, ticket_id)
    if not ticket:
        abort(404)
    return ticket


@bp.route("/")
@login_required
def dashboard():
    recientes = Ticket.query.filter(Ticket.estado.in_(["abierto", "en_progreso"])) \
        .order_by(Ticket.creado_en.desc()).limit(6).all()
    return render_template("tickets/dashboard.html", stats=servicios.estadisticas(), recientes=recientes)


@bp.route("/tickets")
@login_required
def listar():
    filtros = {k: request.args.get(k, "") for k in ("estado", "prioridad", "categoria", "asignado", "q")}
    pagina = request.args.get("pagina", 1, type=int)
    paginacion = servicios.filtrar_tickets(**{k: v or None for k, v in filtros.items()}).paginate(
        page=pagina, per_page=current_app.config["TICKETS_POR_PAGINA"], error_out=False
    )
    return render_template("tickets/lista.html", paginacion=paginacion, filtros=filtros, **_opciones_formulario())


@bp.route("/tickets/mios")
@login_required
def mios():
    return redirect(url_for("tickets.listar", asignado=current_user.id))


@bp.route("/tickets/nuevo", methods=["GET", "POST"])
@login_required
def nuevo():
    datos = {}
    if request.method == "POST":
        datos = request.form.to_dict()
        try:
            ticket = servicios.crear_ticket(datos, creado_por=current_user)
        except servicios.ErrorValidacion as error:
            flash(str(error), "danger")
        else:
            flash(f"Ticket {ticket.codigo} creado. La IA lo clasificó como "
                  f"«{ticket.categoria.nombre}» con prioridad {ticket.prioridad_legible}.", "success")
            return redirect(url_for("tickets.detalle", ticket_id=ticket.id))
    elif request.args.get("cliente_id"):
        datos["cliente_id"] = request.args["cliente_id"]
    return render_template("tickets/formulario.html", datos=datos, ticket=None, **_opciones_formulario())


@bp.route("/tickets/<int:ticket_id>")
@login_required
def detalle(ticket_id: int):
    return render_template("tickets/detalle.html", ticket=_obtener_ticket(ticket_id), **_opciones_formulario())


@bp.route("/tickets/<int:ticket_id>/editar", methods=["GET", "POST"])
@login_required
def editar(ticket_id: int):
    ticket = _obtener_ticket(ticket_id)
    datos = {
        "titulo": ticket.titulo, "descripcion": ticket.descripcion, "cliente_id": str(ticket.cliente_id),
        "categoria": ticket.categoria.clave if ticket.categoria else "", "prioridad": ticket.prioridad,
        "asignado_a_id": str(ticket.asignado_a_id or ""),
    }
    if request.method == "POST":
        datos = request.form.to_dict()
        try:
            servicios.actualizar_ticket(ticket, datos)
        except servicios.ErrorValidacion as error:
            flash(str(error), "danger")
        else:
            flash("Ticket actualizado.", "success")
            return redirect(url_for("tickets.detalle", ticket_id=ticket.id))
    return render_template("tickets/formulario.html", datos=datos, ticket=ticket, **_opciones_formulario())


@bp.route("/tickets/<int:ticket_id>/gestion", methods=["POST"])
@login_required
def gestionar(ticket_id: int):
    """Cambio rápido de estado, prioridad y técnico desde el detalle."""
    ticket = _obtener_ticket(ticket_id)
    datos = {k: v for k, v in request.form.items() if k in ("estado", "prioridad", "asignado_a_id")}
    estado_anterior = ticket.estado_legible
    try:
        servicios.actualizar_ticket(ticket, datos)
    except servicios.ErrorValidacion as error:
        flash(str(error), "danger")
    else:
        if ticket.estado_legible != estado_anterior:
            db.session.add(Comentario(ticket=ticket, usuario=current_user,
                                      contenido=f"Estado cambiado de «{estado_anterior}» a «{ticket.estado_legible}»."))
            db.session.commit()
        flash("Cambios guardados.", "success")
    return redirect(url_for("tickets.detalle", ticket_id=ticket.id))


@bp.route("/tickets/<int:ticket_id>/comentarios", methods=["POST"])
@login_required
def comentar(ticket_id: int):
    ticket = _obtener_ticket(ticket_id)
    contenido = request.form.get("contenido", "").strip()
    if not contenido:
        flash("El comentario no puede estar vacío.", "danger")
    else:
        db.session.add(Comentario(ticket=ticket, usuario=current_user, contenido=contenido))
        db.session.commit()
        flash("Comentario agregado.", "success")
    return redirect(url_for("tickets.detalle", ticket_id=ticket.id) + "#comentarios")


@bp.route("/tickets/<int:ticket_id>/ia", methods=["POST"])
@login_required
def reanalizar(ticket_id: int):
    ticket = servicios.reanalizar_con_ia(_obtener_ticket(ticket_id))
    flash(f"Sugerencia regenerada (motor: {ticket.ia_fuente}).", "info")
    return redirect(url_for("tickets.detalle", ticket_id=ticket.id))


@bp.route("/tickets/<int:ticket_id>/eliminar", methods=["POST"])
@login_required
@rol_requerido("admin")
def eliminar(ticket_id: int):
    ticket = _obtener_ticket(ticket_id)
    codigo = ticket.codigo
    db.session.delete(ticket)
    db.session.commit()
    flash(f"Ticket {codigo} eliminado.", "info")
    return redirect(url_for("tickets.listar"))
