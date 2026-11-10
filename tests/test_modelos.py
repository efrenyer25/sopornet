"""Pruebas de reglas de negocio de los modelos."""
from datetime import timedelta

import pytest

from app.extensions import db
from app.models import Ticket, Usuario, ahora


def crear_ticket(**kwargs) -> Ticket:
    datos = {"titulo": "Prueba", "descripcion": "Descripción de prueba", "cliente_id": 1, "prioridad": "media"}
    datos.update(kwargs)
    ticket = Ticket(**datos)
    db.session.add(ticket)
    db.session.commit()
    return ticket


def test_password_se_guarda_cifrada(app):
    usuario = Usuario(nombre="X", email="x@test.com")
    usuario.set_password("secreto")
    assert usuario.password_hash != "secreto"
    assert usuario.check_password("secreto")
    assert not usuario.check_password("otra")


def test_codigo_del_ticket(app):
    assert crear_ticket().codigo == "TCK-00001"


def test_resolver_ticket_registra_fecha(app):
    ticket = crear_ticket()
    ticket.cambiar_estado("resuelto")
    assert ticket.resuelto_en is not None
    ticket.cambiar_estado("abierto")
    assert ticket.resuelto_en is None


def test_estado_invalido_lanza_error(app):
    with pytest.raises(ValueError):
        crear_ticket().cambiar_estado("inexistente")


def test_sla_vencido_segun_prioridad(app):
    critico = crear_ticket(prioridad="critica", creado_en=ahora() - timedelta(hours=5))
    bajo = crear_ticket(prioridad="baja", creado_en=ahora() - timedelta(hours=5))
    assert critico.sla_vencido  # crítica: máximo 4 horas
    assert not bajo.sla_vencido  # baja: máximo 72 horas


def test_eliminar_cliente_elimina_sus_tickets(app):
    from app.models import Cliente

    crear_ticket()
    db.session.delete(db.session.get(Cliente, 1))
    db.session.commit()
    assert Ticket.query.count() == 0
