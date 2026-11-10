# Imagen de producción de SoporteNet
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=wsgi.py \
    FLASK_ENV_CONFIG=production

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Usuario sin privilegios
RUN useradd --create-home soporte && chown -R soporte /app
USER soporte

EXPOSE 8000

# Aplica migraciones y arranca Gunicorn
CMD ["sh", "-c", "flask db upgrade && flask seed-si-vacio && gunicorn -w 3 -b 0.0.0.0:${PORT:-8000} wsgi:app"]
