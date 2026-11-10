"""Pruebas de integración de la API REST."""


def test_salud_no_requiere_login(client):
    respuesta = client.get("/api/salud")
    assert respuesta.status_code == 200
    assert respuesta.json == {"estado": "ok"}


def test_api_requiere_autenticacion(client):
    assert client.get("/api/tickets").status_code == 401


def test_crear_ticket_clasifica_con_ia(admin_client, ticket_json):
    respuesta = admin_client.post("/api/tickets", json=ticket_json)
    assert respuesta.status_code == 201
    datos = respuesta.json
    assert datos["codigo"] == "TCK-00001"
    assert datos["categoria"] == "conexion"
    assert datos["prioridad"] in ("alta", "critica")
    assert datos["ia"]["fuente"] == "local"
    assert datos["ia"]["sugerencia"]


def test_prioridad_manual_tiene_precedencia(admin_client, ticket_json):
    respuesta = admin_client.post("/api/tickets", json={**ticket_json, "prioridad": "baja"})
    assert respuesta.json["prioridad"] == "baja"


def test_validaciones_al_crear(admin_client, ticket_json):
    assert admin_client.post("/api/tickets", json={**ticket_json, "titulo": "ab"}).status_code == 400
    assert admin_client.post("/api/tickets", json={**ticket_json, "cliente_id": 999}).status_code == 400
    assert admin_client.post("/api/tickets", json={**ticket_json, "cliente_id": "abc"}).status_code == 400
    assert admin_client.post("/api/tickets", data="no es json").status_code == 400


def test_listar_y_filtrar(admin_client, ticket_json):
    admin_client.post("/api/tickets", json=ticket_json)
    admin_client.post("/api/tickets", json={**ticket_json, "titulo": "Factura con doble cobro",
                                            "descripcion": "Me cobraron dos veces la factura"})
    assert admin_client.get("/api/tickets").json["total"] == 2
    filtrado = admin_client.get("/api/tickets?categoria=facturacion").json
    assert filtrado["total"] == 1
    assert admin_client.get("/api/tickets?q=doble").json["total"] == 1


def test_actualizar_estado_y_asignar(admin_client, ticket_json):
    ticket_id = admin_client.post("/api/tickets", json=ticket_json).json["id"]
    respuesta = admin_client.patch(f"/api/tickets/{ticket_id}", json={"estado": "resuelto", "asignado_a_id": 2})
    assert respuesta.status_code == 200
    assert respuesta.json["estado"] == "resuelto"
    assert respuesta.json["resuelto_en"] is not None
    assert respuesta.json["asignado_a"]["id"] == 2


def test_estado_invalido(admin_client, ticket_json):
    ticket_id = admin_client.post("/api/tickets", json=ticket_json).json["id"]
    assert admin_client.patch(f"/api/tickets/{ticket_id}", json={"estado": "volando"}).status_code == 400


def test_comentarios(admin_client, ticket_json):
    ticket_id = admin_client.post("/api/tickets", json=ticket_json).json["id"]
    assert admin_client.post(f"/api/tickets/{ticket_id}/comentarios", json={"contenido": "Visita agendada"}).status_code == 201
    assert len(admin_client.get(f"/api/tickets/{ticket_id}").json["comentarios"]) == 1


def test_solo_admin_elimina(client, ticket_json):
    from tests.conftest import iniciar_sesion

    iniciar_sesion(client, "tecnico@test.com", "tecnico123")
    ticket_id = client.post("/api/tickets", json=ticket_json).json["id"]
    assert client.delete(f"/api/tickets/{ticket_id}").status_code == 403

    client.post("/logout")
    iniciar_sesion(client)
    assert client.delete(f"/api/tickets/{ticket_id}").status_code == 204
    assert client.get(f"/api/tickets/{ticket_id}").status_code == 404


def test_endpoint_clasificar(admin_client):
    respuesta = admin_client.post("/api/ia/clasificar", json={"titulo": "Internet lento",
                                                              "descripcion": "Intermitencia en las noches"})
    assert respuesta.status_code == 200
    assert respuesta.json["categoria"] == "velocidad"


def test_estadisticas(admin_client, ticket_json):
    admin_client.post("/api/tickets", json=ticket_json)
    datos = admin_client.get("/api/estadisticas").json
    assert datos["totales"]["total"] == 1
    assert datos["totales"]["abiertos"] == 1
    assert len(datos["tendencia"]["fechas"]) == 14
    assert list(datos["por_prioridad"]) == ["Baja", "Media", "Alta", "Crítica"]
