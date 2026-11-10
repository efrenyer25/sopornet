"""Lógica de negocio de tickets (reutilizada por las vistas web y la API REST)."""
from collections import Counter
from datetime import timedelta

from sqlalchemy import or_

from ..extensions import db
from ..ia import clasificar_ticket
from ..models import ESTADOS, PRIORIDADES, Categoria, Cliente, Ticket, Usuario, ahora


class ErrorValidacion(ValueError):
    """Datos de entrada inválidos (se muestra al usuario)."""


def filtrar_tickets(estado=None, prioridad=None, categoria=None, asignado=None, q=None):
    consulta = Ticket.query
    if estado:
        consulta = consulta.filter(Ticket.estado == estado)
    if prioridad:
        consulta = consulta.filter(Ticket.prioridad == prioridad)
    if categoria:
        consulta = consulta.join(Categoria).filter(Categoria.clave == categoria)
    if asignado == "sin":
        consulta = consulta.filter(Ticket.asignado_a_id.is_(None))
    elif asignado:
        consulta = consulta.filter(Ticket.asignado_a_id == _entero(asignado, "Filtro de técnico inválido."))
    if q:
        patron = f"%{q.strip()}%"
        consulta = consulta.join(Cliente).filter(
            or_(Ticket.titulo.ilike(patron), Ticket.descripcion.ilike(patron), Cliente.nombre.ilike(patron))
        )
    return consulta.order_by(Ticket.creado_en.desc())


def _entero(valor, mensaje: str) -> int:
    try:
        return int(valor)
    except (TypeError, ValueError):
        raise ErrorValidacion(mensaje) from None


def _validar(datos: dict, parcial: bool = False) -> None:
    if not parcial or "titulo" in datos:
        if len((datos.get("titulo") or "").strip()) < 5:
            raise ErrorValidacion("El título debe tener al menos 5 caracteres.")
    if not parcial or "descripcion" in datos:
        if len((datos.get("descripcion") or "").strip()) < 10:
            raise ErrorValidacion("La descripción debe tener al menos 10 caracteres.")
    if not parcial or "cliente_id" in datos:
        cliente_id = _entero(datos.get("cliente_id"), "Debes seleccionar un cliente válido.")
        if not db.session.get(Cliente, cliente_id):
            raise ErrorValidacion("Debes seleccionar un cliente válido.")
    if datos.get("prioridad") and datos["prioridad"] not in PRIORIDADES:
        raise ErrorValidacion("Prioridad inválida.")
    if datos.get("estado") and datos["estado"] not in ESTADOS:
        raise ErrorValidacion("Estado inválido.")


def _categoria_por_clave(clave):
    return Categoria.query.filter_by(clave=clave).first() if clave else None


def _usuario_asignado(valor):
    if valor in (None, "", "0"):
        return None
    usuario = db.session.get(Usuario, _entero(valor, "El técnico asignado no es válido."))
    if not usuario:
        raise ErrorValidacion("El técnico asignado no existe.")
    return usuario


def crear_ticket(datos: dict, creado_por: Usuario | None) -> Ticket:
    """Crea un ticket. La IA completa categoría y prioridad si no se indican."""
    _validar(datos)
    ia = clasificar_ticket(datos["titulo"], datos["descripcion"])

    ticket = Ticket(
        titulo=datos["titulo"].strip(),
        descripcion=datos["descripcion"].strip(),
        cliente_id=int(datos["cliente_id"]),
        categoria=_categoria_por_clave(datos.get("categoria") or ia.categoria),
        prioridad=datos.get("prioridad") or ia.prioridad,
        creado_por=creado_por,
        asignado_a=_usuario_asignado(datos.get("asignado_a_id")),
        ia_sugerencia=ia.sugerencia,
        ia_confianza=ia.confianza,
        ia_fuente=ia.fuente,
    )
    db.session.add(ticket)
    db.session.commit()
    return ticket


def actualizar_ticket(ticket: Ticket, datos: dict) -> Ticket:
    _validar(datos, parcial=True)
    for campo in ("titulo", "descripcion"):
        if campo in datos:
            setattr(ticket, campo, datos[campo].strip())
    if "cliente_id" in datos:
        ticket.cliente_id = int(datos["cliente_id"])
    if datos.get("prioridad"):
        ticket.prioridad = datos["prioridad"]
    if "categoria" in datos:
        ticket.categoria = _categoria_por_clave(datos["categoria"])
    if "asignado_a_id" in datos:
        ticket.asignado_a = _usuario_asignado(datos["asignado_a_id"])
    if datos.get("estado"):
        ticket.cambiar_estado(datos["estado"])
    db.session.commit()
    return ticket


def reanalizar_con_ia(ticket: Ticket) -> Ticket:
    ia = clasificar_ticket(ticket.titulo, ticket.descripcion)
    ticket.ia_sugerencia, ticket.ia_confianza, ticket.ia_fuente = ia.sugerencia, ia.confianza, ia.fuente
    db.session.commit()
    return ticket


def estadisticas(dias: int = 14) -> dict:
    """Indicadores para el dashboard."""
    tickets = Ticket.query.all()
    abiertos = [t for t in tickets if t.estado in ("abierto", "en_progreso")]
    resueltos = [t for t in tickets if t.resuelto_en]

    hoy = ahora().date()
    fechas = [hoy - timedelta(days=i) for i in range(dias - 1, -1, -1)]
    creados_por_dia = Counter(t.creado_en.date() for t in tickets)
    resueltos_por_dia = Counter(t.resuelto_en.date() for t in resueltos)

    por_categoria = Counter(t.categoria.nombre if t.categoria else "Sin categoría" for t in tickets)
    por_tecnico = Counter(t.asignado_a.nombre for t in abiertos if t.asignado_a)

    promedio = (
        round(sum(t.horas_abierto for t in resueltos) / len(resueltos), 1) if resueltos else 0
    )
    dentro_sla = sum(1 for t in resueltos if not t.sla_vencido)

    return {
        "totales": {
            "total": len(tickets),
            "abiertos": len(abiertos),
            "criticos": sum(1 for t in abiertos if t.prioridad == "critica"),
            "sla_vencidos": sum(1 for t in abiertos if t.sla_vencido),
            "sin_asignar": sum(1 for t in abiertos if not t.asignado_a_id),
            "horas_promedio_resolucion": promedio,
            "cumplimiento_sla": round(100 * dentro_sla / len(resueltos)) if resueltos else 100,
        },
        "por_estado": {ESTADOS[k]: sum(1 for t in tickets if t.estado == k) for k in ESTADOS},
        "por_prioridad": {PRIORIDADES[k]: sum(1 for t in abiertos if t.prioridad == k) for k in PRIORIDADES},
        "por_categoria": dict(por_categoria.most_common()),
        "por_tecnico": dict(por_tecnico.most_common()),
        "tendencia": {
            "fechas": [f.strftime("%d/%m") for f in fechas],
            "creados": [creados_por_dia.get(f, 0) for f in fechas],
            "resueltos": [resueltos_por_dia.get(f, 0) for f in fechas],
        },
    }
