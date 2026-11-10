from functools import wraps

from flask import abort
from flask_login import current_user


def rol_requerido(*roles):
    """Decorador que restringe una vista a ciertos roles."""

    def decorador(vista):
        @wraps(vista)
        def envoltura(*args, **kwargs):
            if not current_user.is_authenticated or current_user.rol not in roles:
                abort(403)
            return vista(*args, **kwargs)

        return envoltura

    return decorador
