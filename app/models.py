"""Modelos de datos (ORM SQLAlchemy).

Entidades: Usuario, Cliente, Categoria, Ticket, Comentario.
Ver docs/requerimientos.md para el diagrama entidad-relación.
"""
from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager


def ahora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --------------------------------------------------------------------------- #
# Catálogos de valores permitidos
# --------------------------------------------------------------------------- #
ROLES = {"admin": "Administrador", "tecnico": "Técnico", "agente": "Agente de atención"}

ESTADOS = {
    "abierto": "Abierto",
    "en_progreso": "En progreso",
    "resuelto": "Resuelto",
    "cerrado": "Cerrado",
}

PRIORIDADES = {"baja": "Baja", "media": "Media", "alta": "Alta", "critica": "Crítica"}

# Horas máximas de resolución según prioridad (Acuerdo de Nivel de Servicio)
SLA_HORAS = {"baja": 72, "media": 48, "alta": 24, "critica": 4}


class Usuario(UserMixin, db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.String(20), nullable=False, default="agente")
    activo = db.Column(db.Boolean, nullable=False, default=True)
    creado_en = db.Column(db.DateTime, nullable=False, default=ahora)

    tickets_asignados = db.relationship(
        "Ticket", foreign_keys="Ticket.asignado_a_id", back_populates="asignado_a"
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def es_admin(self) -> bool:
        return self.rol == "admin"

    @property
    def rol_legible(self) -> str:
        return ROLES.get(self.rol, self.rol)

    @property
    def is_active(self) -> bool:  # usado por Flask-Login
        return self.activo

    def to_dict(self) -> dict:
        return {"id": self.id, "nombre": self.nombre, "email": self.email, "rol": self.rol}

    def __repr__(self) -> str:
        return f"<Usuario {self.email}>"


@login_manager.user_loader
def cargar_usuario(user_id: str):
    return db.session.get(Usuario, int(user_id))


class Cliente(db.Model):
    __tablename__ = "clientes"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    documento = db.Column(db.String(20), unique=True, nullable=False)  # Cédula o RIF
    email = db.Column(db.String(120))
    telefono = db.Column(db.String(30))
    direccion = db.Column(db.String(255))
    plan = db.Column(db.String(60))  # Ej.: "Fibra 300 Mbps"
    creado_en = db.Column(db.DateTime, nullable=False, default=ahora)

    tickets = db.relationship("Ticket", back_populates="cliente", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "nombre": self.nombre,
            "documento": self.documento,
            "email": self.email,
            "telefono": self.telefono,
            "direccion": self.direccion,
            "plan": self.plan,
        }


class Categoria(db.Model):
    __tablename__ = "categorias"

    id = db.Column(db.Integer, primary_key=True)
    clave = db.Column(db.String(30), unique=True, nullable=False)
    nombre = db.Column(db.String(60), nullable=False)
    descripcion = db.Column(db.String(255))

    tickets = db.relationship("Ticket", back_populates="categoria")

    def to_dict(self) -> dict:
        return {"id": self.id, "clave": self.clave, "nombre": self.nombre}


class Ticket(db.Model):
    __tablename__ = "tickets"

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(150), nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    estado = db.Column(db.String(20), nullable=False, default="abierto", index=True)
    prioridad = db.Column(db.String(20), nullable=False, default="media", index=True)

    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False)
    categoria_id = db.Column(db.Integer, db.ForeignKey("categorias.id"), nullable=True)
    creado_por_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True)
    asignado_a_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True)

    creado_en = db.Column(db.DateTime, nullable=False, default=ahora, index=True)
    actualizado_en = db.Column(db.DateTime, nullable=False, default=ahora, onupdate=ahora)
    resuelto_en = db.Column(db.DateTime, nullable=True)

    # Resultado del análisis de Inteligencia Artificial
    ia_sugerencia = db.Column(db.Text)
    ia_confianza = db.Column(db.Float)
    ia_fuente = db.Column(db.String(40))  # "claude" o "local"

    cliente = db.relationship("Cliente", back_populates="tickets")
    categoria = db.relationship("Categoria", back_populates="tickets")
    creado_por = db.relationship("Usuario", foreign_keys=[creado_por_id])
    asignado_a = db.relationship("Usuario", foreign_keys=[asignado_a_id], back_populates="tickets_asignados")
    comentarios = db.relationship(
        "Comentario", back_populates="ticket", cascade="all, delete-orphan", order_by="Comentario.creado_en"
    )

    # ---- Propiedades de negocio ------------------------------------------ #
    @property
    def codigo(self) -> str:
        return f"TCK-{self.id:05d}" if self.id else "TCK-nuevo"

    @property
    def estado_legible(self) -> str:
        return ESTADOS.get(self.estado, self.estado)

    @property
    def prioridad_legible(self) -> str:
        return PRIORIDADES.get(self.prioridad, self.prioridad)

    @property
    def horas_abierto(self) -> float:
        fin = self.resuelto_en or ahora()
        return round((fin - self.creado_en).total_seconds() / 3600, 1)

    @property
    def sla_vencido(self) -> bool:
        """True si el ticket superó el tiempo máximo de su prioridad."""
        return self.horas_abierto > SLA_HORAS.get(self.prioridad, 48)

    def cambiar_estado(self, nuevo_estado: str) -> None:
        if nuevo_estado not in ESTADOS:
            raise ValueError(f"Estado inválido: {nuevo_estado}")
        self.estado = nuevo_estado
        if nuevo_estado in ("resuelto", "cerrado"):
            self.resuelto_en = self.resuelto_en or ahora()
        else:
            self.resuelto_en = None

    def to_dict(self, detalle: bool = False) -> dict:
        datos = {
            "id": self.id,
            "codigo": self.codigo,
            "titulo": self.titulo,
            "estado": self.estado,
            "prioridad": self.prioridad,
            "categoria": self.categoria.clave if self.categoria else None,
            "cliente": {"id": self.cliente.id, "nombre": self.cliente.nombre} if self.cliente else None,
            "asignado_a": self.asignado_a.to_dict() if self.asignado_a else None,
            "creado_en": self.creado_en.isoformat(),
            "actualizado_en": self.actualizado_en.isoformat() if self.actualizado_en else None,
            "resuelto_en": self.resuelto_en.isoformat() if self.resuelto_en else None,
            "sla_vencido": self.sla_vencido,
        }
        if detalle:
            datos.update(
                {
                    "descripcion": self.descripcion,
                    "ia": {
                        "sugerencia": self.ia_sugerencia,
                        "confianza": self.ia_confianza,
                        "fuente": self.ia_fuente,
                    },
                    "comentarios": [c.to_dict() for c in self.comentarios],
                }
            )
        return datos


class Comentario(db.Model):
    __tablename__ = "comentarios"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True)
    contenido = db.Column(db.Text, nullable=False)
    creado_en = db.Column(db.DateTime, nullable=False, default=ahora)

    ticket = db.relationship("Ticket", back_populates="comentarios")
    usuario = db.relationship("Usuario")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "usuario": self.usuario.nombre if self.usuario else "Sistema",
            "contenido": self.contenido,
            "creado_en": self.creado_en.isoformat(),
        }
