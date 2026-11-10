"""SoporteNet — Mesa de ayuda con IA para proveedores de internet.

Fábrica de la aplicación Flask (patrón Application Factory).
"""
import os
import secrets
from datetime import timezone
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, render_template, request, session

from .config import config_por_nombre
from .extensions import db, login_manager, migrate
from .models import ESTADOS, PRIORIDADES

load_dotenv()


def create_app(nombre_config: str | None = None) -> Flask:
    nombre_config = nombre_config or os.getenv("FLASK_ENV_CONFIG", "development")
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_por_nombre[nombre_config])
    app.json.sort_keys = False  # conserva el orden lógico (Baja → Crítica) en la API
    os.makedirs(app.instance_path, exist_ok=True)

    # Extensiones
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # Blueprints (módulos de la aplicación)
    from .api.routes import bp as api_bp
    from .auth.routes import bp as auth_bp
    from .clientes.routes import bp as clientes_bp
    from .tickets.routes import bp as tickets_bp
    from .usuarios.routes import bp as usuarios_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(tickets_bp)
    app.register_blueprint(clientes_bp)
    app.register_blueprint(usuarios_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    _registrar_csrf(app)
    _registrar_errores(app)
    _registrar_contexto(app)

    from .cli import registrar_comandos

    registrar_comandos(app)
    return app


def _registrar_csrf(app: Flask) -> None:
    """Protección CSRF sencilla para formularios HTML (la API usa JSON + sesión)."""

    def obtener_token() -> str:
        if "_csrf" not in session:
            session["_csrf"] = secrets.token_hex(16)
        return session["_csrf"]

    app.jinja_env.globals["csrf_token"] = obtener_token

    @app.before_request
    def validar_csrf():
        if not app.config.get("CSRF_HABILITADO", True):
            return
        if request.method == "POST" and not request.path.startswith("/api/"):
            token = request.form.get("_csrf")
            if not token or token != session.get("_csrf"):
                abort(400, description="Token CSRF inválido. Recarga la página e intenta de nuevo.")


def _registrar_errores(app: Flask) -> None:
    def respuesta(codigo: int, mensaje: str):
        if request.path.startswith("/api/"):
            return jsonify({"error": mensaje}), codigo
        return render_template("errores/error.html", codigo=codigo, mensaje=mensaje), codigo

    @app.errorhandler(400)
    def error_400(e):
        return respuesta(400, getattr(e, "description", "Solicitud inválida"))

    @app.errorhandler(403)
    def error_403(e):
        return respuesta(403, "No tienes permiso para realizar esta acción.")

    @app.errorhandler(404)
    def error_404(e):
        return respuesta(404, "El recurso solicitado no existe.")

    @app.errorhandler(500)
    def error_500(e):
        db.session.rollback()
        return respuesta(500, "Ocurrió un error interno. Intenta de nuevo.")


def _registrar_contexto(app: Flask) -> None:
    from .ia import CATEGORIAS

    @app.context_processor
    def variables_globales():
        return {"ESTADOS": ESTADOS, "PRIORIDADES": PRIORIDADES, "CATEGORIAS_IA": CATEGORIAS}

    zona = ZoneInfo(app.config["ZONA_HORARIA"])

    @app.template_filter("fecha")
    def formatear_fecha(valor, formato="%d/%m/%Y %H:%M"):
        """Las fechas se guardan en UTC y se muestran en la hora local."""
        if not valor:
            return "—"
        return valor.replace(tzinfo=timezone.utc).astimezone(zona).strftime(formato)
