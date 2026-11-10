"""Fixtures compartidas de pytest."""
import pytest

from app import create_app
from app.cli import crear_categorias
from app.extensions import db
from app.models import Cliente, Usuario


@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        crear_categorias()
        admin = Usuario(nombre="Admin", email="admin@test.com", rol="admin")
        admin.set_password("admin123")
        tecnico = Usuario(nombre="Técnico", email="tecnico@test.com", rol="tecnico")
        tecnico.set_password("tecnico123")
        cliente = Cliente(nombre="Cliente Prueba", documento="V-12345678", plan="Fibra 300 Mbps")
        db.session.add_all([admin, tecnico, cliente])
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


def iniciar_sesion(client, email="admin@test.com", password="admin123"):
    return client.post("/login", data={"email": email, "password": password}, follow_redirects=True)


@pytest.fixture
def admin_client(client):
    iniciar_sesion(client)
    return client


@pytest.fixture
def tecnico_client(client):
    iniciar_sesion(client, "tecnico@test.com", "tecnico123")
    return client


@pytest.fixture
def ticket_json():
    return {
        "titulo": "Sin internet desde ayer",
        "descripcion": "No tengo internet y la luz LOS del equipo está en rojo.",
        "cliente_id": 1,
    }
