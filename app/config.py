"""Configuración de la aplicación por entorno.

Los valores sensibles se leen de variables de entorno (archivo .env en desarrollo).
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'soportenet.db'}")
    # Algunos proveedores (Render, Heroku) entregan "postgres://", SQLAlchemy exige "postgresql://"
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "cambia-esta-clave-en-produccion")
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Inteligencia Artificial
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    IA_MODELO = os.getenv("IA_MODELO", "claude-haiku-4-5")
    IA_HABILITADA = os.getenv("IA_HABILITADA", "1") == "1"

    TICKETS_POR_PAGINA = 15
    ZONA_HORARIA = os.getenv("ZONA_HORARIA", "America/Caracas")


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    CSRF_HABILITADO = False
    ANTHROPIC_API_KEY = ""  # las pruebas siempre usan el clasificador local


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "1") == "1"
    SESSION_COOKIE_HTTPONLY = True


config_por_nombre = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
