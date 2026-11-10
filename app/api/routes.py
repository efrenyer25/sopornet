"""API REST (JSON).

Endpoints
---------
GET    /api/tickets                 Lista (filtros: estado, prioridad, categoria, q, pagina)
POST   /api/tickets                 Crea un ticket (la IA clasifica)
GET    /api/tickets/<id>            Detalle con comentarios
PATCH  /api/tickets/<id>            Actualiza campos
DELETE /api/tickets/<id>            Elimina (solo admin)
POST   /api/tickets/<id>/comentarios
GET    /api/clientes                Lista de clientes
POST   /api/ia/clasificar           Clasifica un texto sin guardar
GET    /api/estadisticas            Indicadores del dashboard
GET    /api/salud                   Verificación de estado (sin autenticación)
"""
from functools import wraps

from flask import Blueprint, jsonify, request
from flask_login import current_user

from ..extensions import db
from ..ia import clasificar_ticket
from ..models import Cliente, Comentario, Ticket
from ..tickets import servicios

bp = Blueprint("api", __name__)


def api_login_requerido(vista):
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"error": "Autenticación requerida"}), 401
        return vista(*args, **kwargs)

    return envoltura


def _json() -> dict:
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        raise servicios.ErrorValidacion("El cuerpo debe ser un objeto JSON.")
    return datos


def _ticket_o_404(ticket_id: int):
    return db.session.get(Ticket, ticket_id)


@bp.errorhandler(servicios.ErrorValidacion)
def manejar_validacion(error):
    return jsonify({"error": str(error)}), 400


@bp.get("/salud")
def salud():
    db.session.execute(db.text("SELECT 1"))
    return jsonify({"estado": "ok"})


@bp.get("/tickets")
@api_login_requerido
def listar_tickets():
    filtros = {k: request.args.get(k) for k in ("estado", "prioridad", "categoria", "asignado", "q")}
    pagina = request.args.get("pagina", 1, type=int)
    por_pagina = min(request.args.get("por_pagina", 20, type=int), 100)
    resultado = servicios.filtrar_tickets(**filtros).paginate(page=pagina, per_page=por_pagina, error_out=False)
    return jsonify({
        "items": [t.to_dict() for t in resultado.items],
        "total": resultado.total,
        "pagina": resultado.page,
        "paginas": resultado.pages,
    })


@bp.post("/tickets")
@api_login_requerido
def crear_ticket():
    ticket = servicios.crear_ticket(_json(), creado_por=current_user)
    return jsonify(ticket.to_dict(detalle=True)), 201


@bp.get("/tickets/<int:ticket_id>")
@api_login_requerido
def obtener_ticket(ticket_id: int):
    ticket = _ticket_o_404(ticket_id)
    if not ticket:
        return jsonify({"error": "Ticket no encontrado"}), 404
    return jsonify(ticket.to_dict(detalle=True))


@bp.patch("/tickets/<int:ticket_id>")
@api_login_requerido
def actualizar_ticket(ticket_id: int):
    ticket = _ticket_o_404(ticket_id)
    if not ticket:
        return jsonify({"error": "Ticket no encontrado"}), 404
    servicios.actualizar_ticket(ticket, _json())
    return jsonify(ticket.to_dict(detalle=True))


@bp.delete("/tickets/<int:ticket_id>")
@api_login_requerido
def eliminar_ticket(ticket_id: int):
    if not current_user.es_admin:
        return jsonify({"error": "Solo un administrador puede eliminar tickets"}), 403
    ticket = _ticket_o_404(ticket_id)
    if not ticket:
        return jsonify({"error": "Ticket no encontrado"}), 404
    db.session.delete(ticket)
    db.session.commit()
    return "", 204


@bp.post("/tickets/<int:ticket_id>/comentarios")
@api_login_requerido
def comentar(ticket_id: int):
    ticket = _ticket_o_404(ticket_id)
    if not ticket:
        return jsonify({"error": "Ticket no encontrado"}), 404
    contenido = str(_json().get("contenido", "")).strip()
    if not contenido:
        return jsonify({"error": "El comentario no puede estar vacío"}), 400
    comentario = Comentario(ticket=ticket, usuario=current_user, contenido=contenido)
    db.session.add(comentario)
    db.session.commit()
    return jsonify(comentario.to_dict()), 201


@bp.get("/clientes")
@api_login_requerido
def listar_clientes():
    return jsonify([c.to_dict() for c in Cliente.query.order_by(Cliente.nombre).all()])


@bp.post("/ia/clasificar")
@api_login_requerido
def clasificar():
    datos = _json()
    titulo, descripcion = str(datos.get("titulo", "")), str(datos.get("descripcion", ""))
    if len(f"{titulo} {descripcion}".strip()) < 5:
        return jsonify({"error": "Escribe un título o descripción para analizar"}), 400
    return jsonify(clasificar_ticket(titulo, descripcion).to_dict())


@bp.get("/estadisticas")
@api_login_requerido
def estadisticas():
    return jsonify(servicios.estadisticas(dias=request.args.get("dias", 14, type=int)))
