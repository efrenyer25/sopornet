"""Pruebas funcionales de las vistas web."""
from tests.conftest import iniciar_sesion


def test_redirige_a_login_sin_sesion(client):
    respuesta = client.get("/")
    assert respuesta.status_code == 302
    assert "/login" in respuesta.headers["Location"]


def test_login_incorrecto(client):
    respuesta = iniciar_sesion(client, password="mala")
    assert "incorrectos" in respuesta.get_data(as_text=True)


def test_login_y_dashboard(admin_client):
    respuesta = admin_client.get("/")
    assert respuesta.status_code == 200
    assert "Dashboard" in respuesta.get_data(as_text=True)


def test_login_no_permite_redireccion_externa(client):
    respuesta = client.post("/login?next=https://malicioso.com",
                            data={"email": "admin@test.com", "password": "admin123"})
    assert respuesta.headers["Location"] == "/"


def test_usuario_inactivo_no_entra(app, client):
    from app.extensions import db
    from app.models import Usuario

    with app.app_context():
        usuario = db.session.get(Usuario, 2)
        usuario.activo = False
        db.session.commit()
    respuesta = iniciar_sesion(client, "tecnico@test.com", "tecnico123")
    assert "incorrectos" in respuesta.get_data(as_text=True)


def test_flujo_completo_de_ticket(admin_client):
    # 1. Crear
    respuesta = admin_client.post("/tickets/nuevo", data={
        "cliente_id": "1", "titulo": "Internet lento",
        "descripcion": "La velocidad es muy baja en las noches, speedtest 5 Mbps",
    }, follow_redirects=True)
    html = respuesta.get_data(as_text=True)
    assert "TCK-00001" in html
    assert "Lentitud o intermitencia" in html

    # 2. Gestionar (cambiar estado) genera comentario automático
    respuesta = admin_client.post("/tickets/1/gestion", data={"estado": "en_progreso", "prioridad": "alta",
                                                              "asignado_a_id": "2"}, follow_redirects=True)
    assert "En progreso" in respuesta.get_data(as_text=True)

    # 3. Comentar
    respuesta = admin_client.post("/tickets/1/comentarios", data={"contenido": "Se revisó la potencia óptica"},
                                  follow_redirects=True)
    assert "potencia óptica" in respuesta.get_data(as_text=True)

    # 4. Regenerar IA
    assert admin_client.post("/tickets/1/ia", follow_redirects=True).status_code == 200

    # 5. Listado con filtro
    assert "Internet lento" in admin_client.get("/tickets?estado=en_progreso").get_data(as_text=True)
    assert "Internet lento" not in admin_client.get("/tickets?estado=cerrado").get_data(as_text=True)


def test_crear_ticket_con_datos_invalidos(admin_client):
    respuesta = admin_client.post("/tickets/nuevo", data={"cliente_id": "", "titulo": "x", "descripcion": "y"},
                                  follow_redirects=True)
    assert "al menos 5 caracteres" in respuesta.get_data(as_text=True)


def test_crud_cliente(admin_client):
    respuesta = admin_client.post("/clientes/nuevo", data={
        "nombre": "Nuevo Cliente", "documento": "v-87654321", "email": "nuevo@correo.com",
    }, follow_redirects=True)
    assert "Cliente guardado" in respuesta.get_data(as_text=True)

    duplicado = admin_client.post("/clientes/nuevo", data={"nombre": "Otro", "documento": "V-87654321"},
                                  follow_redirects=True)
    assert "Ya existe" in duplicado.get_data(as_text=True)

    invalido = admin_client.post("/clientes/nuevo", data={"nombre": "Otro", "documento": "123"},
                                 follow_redirects=True)
    assert "Documento inválido" in invalido.get_data(as_text=True)


def test_tecnico_no_accede_a_usuarios(tecnico_client):
    assert tecnico_client.get("/usuarios/").status_code == 403


def test_admin_crea_usuario(admin_client):
    respuesta = admin_client.post("/usuarios/nuevo", data={"nombre": "Nuevo Técnico", "email": "nt@test.com",
                                                           "rol": "tecnico", "password": "clave123"},
                                  follow_redirects=True)
    assert "Nuevo Técnico" in respuesta.get_data(as_text=True)


def test_pagina_404(admin_client):
    assert admin_client.get("/tickets/9999").status_code == 404


def test_csrf_activo_en_produccion():
    from app import create_app

    app = create_app("production")
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    respuesta = app.test_client().post("/login", data={"email": "a@b.com", "password": "x"})
    assert respuesta.status_code == 400
