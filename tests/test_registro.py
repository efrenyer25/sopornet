"""Pruebas del registro de usuarios y cambio de rol."""
from app.models import Usuario
from tests.conftest import iniciar_sesion

DATOS = {"nombre": "Nuevo Usuario", "email": "Nuevo@Correo.com", "password": "clave1234", "confirmar": "clave1234"}


def test_pagina_de_registro(client):
    respuesta = client.get("/registro")
    assert respuesta.status_code == 200
    assert "Crear cuenta" in respuesta.get_data(as_text=True)


def test_login_enlaza_al_registro(client):
    assert "/registro" in client.get("/login").get_data(as_text=True)


def test_registro_exitoso_crea_agente_e_inicia_sesion(app, client):
    respuesta = client.post("/registro", data=DATOS, follow_redirects=True)
    assert "Cuenta creada" in respuesta.get_data(as_text=True)
    with app.app_context():
        usuario = Usuario.query.filter_by(email="nuevo@correo.com").first()
        assert usuario is not None
        assert usuario.rol == "agente"
        assert usuario.check_password("clave1234")
    assert client.get("/").status_code == 200  # ya tiene sesión


def test_no_se_puede_elegir_rol_admin(app, client):
    client.post("/registro", data={**DATOS, "rol": "admin"})
    with app.app_context():
        assert Usuario.query.filter_by(email="nuevo@correo.com").first().rol == "agente"


def test_registro_con_errores(client):
    casos = [
        ({"email": "admin@test.com"}, "Ya existe una cuenta"),
        ({"email": "sin-arroba"}, "Correo electrónico inválido"),
        ({"password": "corta1", "confirmar": "corta1"}, "al menos 8 caracteres"),
        ({"password": "solotexto", "confirmar": "solotexto"}, "letras y números"),
        ({"confirmar": "otra12345"}, "no coinciden"),
        ({"nombre": "Al"}, "al menos 3 caracteres"),
    ]
    for cambios, mensaje in casos:
        respuesta = client.post("/registro", data={**DATOS, **cambios})
        assert mensaje in respuesta.get_data(as_text=True), mensaje


def test_registro_deshabilitado(app, client):
    app.config["REGISTRO_HABILITADO"] = False
    assert client.get("/registro").status_code == 404
    assert "/registro" not in client.get("/login").get_data(as_text=True)


def test_admin_cambia_rol(app, client):
    client.post("/registro", data=DATOS)
    client.post("/logout")
    iniciar_sesion(client)
    with app.app_context():
        usuario_id = Usuario.query.filter_by(email="nuevo@correo.com").first().id
    respuesta = client.post(f"/usuarios/{usuario_id}/rol", data={"rol": "tecnico"}, follow_redirects=True)
    assert "ahora es Técnico" in respuesta.get_data(as_text=True)


def test_agente_no_puede_cambiar_roles(client):
    client.post("/registro", data=DATOS)
    assert client.post("/usuarios/1/rol", data={"rol": "agente"}).status_code == 403


def test_url_postgres_usa_psycopg2(monkeypatch):
    from app.config import _database_url

    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host/db")
    assert _database_url() == "postgresql+psycopg2://u:p@host/db"
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@host/db")
    assert _database_url() == "postgresql+psycopg2://u:p@host/db"
