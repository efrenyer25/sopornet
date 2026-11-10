"""Comandos de consola: `flask init-db` y `flask seed`."""
import random
from datetime import timedelta

import click
from flask import Flask

from .extensions import db
from .ia import CATEGORIAS, clasificar_local
from .models import Categoria, Cliente, Comentario, Ticket, Usuario, ahora

CASOS_EJEMPLO = [
    ("Sin internet desde ayer", "Desde ayer en la tarde no tengo internet, la luz LOS del equipo está en rojo."),
    ("Internet muy lento en las noches", "En las noches el internet está muy lento, el speedtest da 20 Mbps y contraté 300."),
    ("Doble cobro en la factura", "Me cobraron dos veces la mensualidad de octubre, adjunto el comprobante de pago."),
    ("Solicitud de mudanza del servicio", "Me voy a mudar el próximo mes y quisiera hacer el traslado del servicio."),
    ("Router no enciende", "El router no enciende desde que se fue la luz, creo que está quemado."),
    ("Conexión intermitente", "La conexión es intermitente, se corta cada 10 minutos y vuelve sola."),
    ("Cambio de plan", "Quisiera saber cómo hacer un cambio de plan a 500 Mbps."),
    ("Caída masiva en el sector", "Todo el sector está sin servicio, varios clientes reportan fibra cortada en la calle."),
    ("Olvidé la clave WiFi", "Necesito cambiar la contraseña del WiFi del router, no la recuerdo."),
    ("Empresa sin servicio", "Nuestra empresa está sin internet y no funcionan los puntos de venta, es urgente."),
    ("Ping alto en juegos", "La latencia es muy alta, el ping pasa de 200 ms en juegos en línea."),
    ("Servicio suspendido por pago", "Pagué por transferencia y el servicio sigue suspendido por pago."),
    ("Consulta de factura", "Tengo una duda con el monto de la factura de este mes."),
    ("Decodificador dañado", "El decodificador se reinicia solo y muestra pantalla negra."),
    ("Nueva instalación", "Quiero contratar un nuevo servicio de fibra para mi casa, ¿cuándo pueden instalar?"),
]

NOMBRES = ["María González", "José Rodríguez", "Ana Pérez", "Luis Hernández", "Carmen Díaz",
           "Pedro Martínez", "Inversiones Caribe C.A.", "Clínica Los Andes", "Rosa Medina",
           "Carlos Ramírez", "Farmacia Central", "Daniela Torres"]
ZONAS = ["Chacao", "Baruta", "El Hatillo", "Los Palos Grandes", "La Candelaria", "Altamira", "El Cafetal"]
PLANES = ["Fibra 100 Mbps", "Fibra 300 Mbps", "Fibra 500 Mbps", "Empresarial 1 Gbps"]


def crear_categorias() -> dict[str, Categoria]:
    categorias = {}
    for clave, nombre in CATEGORIAS.items():
        cat = Categoria.query.filter_by(clave=clave).first()
        if not cat:
            cat = Categoria(clave=clave, nombre=nombre)
            db.session.add(cat)
        categorias[clave] = cat
    db.session.commit()
    return categorias


def registrar_comandos(app: Flask) -> None:
    @app.cli.command("init-db")
    def init_db():
        """Crea las tablas y las categorías base (alternativa rápida a `flask db upgrade`)."""
        db.create_all()
        crear_categorias()
        click.echo("Base de datos inicializada.")

    @app.cli.command("seed-si-vacio")
    @click.pass_context
    def seed_si_vacio(ctx):
        """Carga datos de demostración solo si la base de datos está vacía (útil en Docker)."""
        if Usuario.query.first():
            click.echo("La base de datos ya tiene datos; no se cargan ejemplos.")
        else:
            ctx.invoke(seed, tickets=60)

    @app.cli.command("seed")
    @click.option("--tickets", default=60, help="Cantidad de tickets de ejemplo.")
    def seed(tickets: int):
        """Carga datos de demostración (usuarios, clientes y tickets)."""
        db.create_all()
        categorias = crear_categorias()
        random.seed(42)

        usuarios = []
        for nombre, email, rol, clave in [
            ("Administrador", "admin@soportenet.local", "admin", "admin123"),
            ("Andrea Técnico", "andrea@soportenet.local", "tecnico", "tecnico123"),
            ("Miguel Técnico", "miguel@soportenet.local", "tecnico", "tecnico123"),
            ("Laura Agente", "laura@soportenet.local", "agente", "agente123"),
        ]:
            usuario = Usuario.query.filter_by(email=email).first()
            if not usuario:
                usuario = Usuario(nombre=nombre, email=email, rol=rol)
                usuario.set_password(clave)
                db.session.add(usuario)
            usuarios.append(usuario)

        clientes = []
        for i, nombre in enumerate(NOMBRES):
            documento = f"V-{12000000 + i * 734521}" if "C.A." not in nombre and "Clínica" not in nombre \
                and "Farmacia" not in nombre else f"J-{40000000 + i * 1234}-{i}"
            cliente = Cliente.query.filter_by(documento=documento).first()
            if not cliente:
                cliente = Cliente(
                    nombre=nombre,
                    documento=documento,
                    email=f"cliente{i + 1}@correo.com",
                    telefono=f"0412-{random.randint(1000000, 9999999)}",
                    direccion=f"Av. Principal, {random.choice(ZONAS)}, Caracas",
                    plan=random.choice(PLANES),
                )
                db.session.add(cliente)
            clientes.append(cliente)
        db.session.commit()

        tecnicos = [u for u in usuarios if u.rol == "tecnico"]
        for _ in range(tickets):
            titulo, descripcion = random.choice(CASOS_EJEMPLO)
            ia = clasificar_local(titulo, descripcion)
            creado = ahora() - timedelta(days=random.randint(0, 29), hours=random.randint(0, 23))
            ticket = Ticket(
                titulo=titulo,
                descripcion=descripcion,
                cliente=random.choice(clientes),
                categoria=categorias[ia.categoria],
                prioridad=ia.prioridad,
                creado_por=usuarios[3],
                asignado_a=random.choice(tecnicos + [None]),
                creado_en=creado,
                ia_sugerencia=ia.sugerencia,
                ia_confianza=ia.confianza,
                ia_fuente=ia.fuente,
            )
            # Los tickets antiguos tienen más probabilidad de estar resueltos
            dias = (ahora() - creado).days
            estado = random.choices(
                ["abierto", "en_progreso", "resuelto", "cerrado"],
                weights=[max(1, 10 - dias), 4, 2 + dias // 3, 1 + dias // 5],
            )[0]
            ticket.estado = estado
            if estado in ("resuelto", "cerrado"):
                ticket.resuelto_en = creado + timedelta(hours=random.randint(1, 60))
                ticket.comentarios.append(
                    Comentario(usuario=ticket.asignado_a or tecnicos[0],
                               contenido="Caso atendido y verificado con el cliente.",
                               creado_en=ticket.resuelto_en)
                )
            db.session.add(ticket)

        db.session.commit()
        click.echo(f"Datos de demostración cargados: {len(usuarios)} usuarios, "
                   f"{len(clientes)} clientes, {tickets} tickets.")
        click.echo("Ingresa con admin@soportenet.local / admin123")
