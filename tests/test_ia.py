"""Pruebas del clasificador de Inteligencia Artificial."""
from unittest.mock import patch

import pytest

from app.ia import clasificar_local, clasificar_ticket
from app.ia.servicio import normalizar


def test_normalizar_quita_acentos_y_signos():
    assert normalizar("¡Conexión LENTA!") == " conexion lenta "


@pytest.mark.parametrize(
    "titulo, descripcion, categoria",
    [
        ("Sin internet", "No tengo internet desde ayer, luz roja en el equipo", "conexion"),
        ("Internet lento", "La velocidad es muy baja, el speedtest marca 10 Mbps", "velocidad"),
        ("Cobro doble", "Me cobraron dos veces la factura del mes", "facturacion"),
        ("Mudanza", "Necesito el traslado del servicio por mudanza", "instalacion"),
        ("Router dañado", "El router no enciende, creo que está quemado", "equipos"),
        ("Hola", "Tengo una pregunta general", "otro"),
    ],
)
def test_clasificar_categoria(titulo, descripcion, categoria):
    assert clasificar_local(titulo, descripcion).categoria == categoria


def test_prioridad_critica_para_empresas_y_averias_masivas():
    resultado = clasificar_local("Empresa sin servicio", "Nuestra empresa no tiene internet, urgente")
    assert resultado.prioridad == "critica"


def test_prioridad_baja_para_consultas():
    resultado = clasificar_local("Consulta de factura", "Tengo una duda con el monto de la factura")
    assert resultado.categoria == "facturacion"
    assert resultado.prioridad == "baja"


def test_resultado_incluye_sugerencia_y_confianza():
    resultado = clasificar_local("Internet lento", "Muy lento en las noches")
    assert resultado.sugerencia
    assert 0 < resultado.confianza <= 1
    assert resultado.fuente == "local"


def test_sin_api_key_usa_modelo_local(app):
    with app.app_context():
        assert clasificar_ticket("Sin internet", "No hay internet").fuente == "local"


def test_si_falla_el_llm_usa_modelo_local(app):
    app.config["ANTHROPIC_API_KEY"] = "clave-falsa"
    with app.app_context(), patch("app.ia.servicio.clasificar_con_llm", side_effect=RuntimeError("sin red")):
        resultado = clasificar_ticket("Internet lento", "La velocidad es muy baja")
    assert resultado.fuente == "local"
    assert resultado.categoria == "velocidad"


def test_usa_llm_cuando_hay_api_key(app):
    from app.ia import ResultadoIA

    falso = ResultadoIA("equipos", "alta", "Reemplazar router", 0.9, "claude")
    app.config["ANTHROPIC_API_KEY"] = "clave"
    with app.app_context(), patch("app.ia.servicio.clasificar_con_llm", return_value=falso) as mock:
        resultado = clasificar_ticket("Router", "No enciende")
    mock.assert_called_once()
    assert resultado.fuente == "claude"
