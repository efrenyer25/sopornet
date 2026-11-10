"""Servicio de Inteligencia Artificial para clasificar tickets.

Dado el título y la descripción de un ticket devuelve:
    - categoria  : clave de la categoría más probable
    - prioridad  : baja | media | alta | critica
    - sugerencia : pasos recomendados para el técnico / respuesta al cliente
    - confianza  : valor entre 0 y 1
    - fuente     : "claude" (modelo de lenguaje) o "local" (reglas NLP)

Estrategia:
    1. Si existe ANTHROPIC_API_KEY se consulta un modelo de lenguaje (Claude)
       pidiéndole una respuesta en JSON.
    2. Si no hay clave, falla la red o la respuesta no es válida, se usa un
       clasificador local basado en palabras clave (no requiere internet).
       Así la aplicación siempre funciona, también durante la presentación.
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import asdict, dataclass

from flask import current_app

log = logging.getLogger(__name__)

CATEGORIAS = {
    "conexion": "Sin servicio / caída de conexión",
    "velocidad": "Lentitud o intermitencia",
    "equipos": "Equipos (router, ONT, decodificador)",
    "instalacion": "Instalación, mudanza o cambio de plan",
    "facturacion": "Facturación y pagos",
    "otro": "Otro",
}

PRIORIDADES_VALIDAS = ("baja", "media", "alta", "critica")


@dataclass
class ResultadoIA:
    categoria: str
    prioridad: str
    sugerencia: str
    confianza: float
    fuente: str

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Utilidades de procesamiento de texto (NLP básico)
# --------------------------------------------------------------------------- #
def normalizar(texto: str) -> str:
    """Minúsculas, sin acentos y sin signos de puntuación."""
    texto = unicodedata.normalize("NFKD", texto.lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9ñ ]+", " ", texto)


# Palabras clave con peso por categoría
PALABRAS_CLAVE: dict[str, dict[str, int]] = {
    "conexion": {
        "sin servicio": 4, "sin internet": 4, "no hay internet": 4, "no tengo internet": 4,
        "caida": 3, "caido": 3, "no conecta": 3, "sin conexion": 4, "no navega": 3,
        "luz roja": 3, "luz los": 3, "corte": 2, "fibra cortada": 4, "sin senal": 3, "no funciona": 1,
    },
    "velocidad": {
        "lento": 4, "lenta": 4, "lentitud": 4, "intermitente": 4, "intermitencia": 4,
        "se cae": 2, "velocidad": 3, "mbps": 2, "ping": 3, "latencia": 3, "se corta": 2,
        "buffering": 3, "carga": 1, "speedtest": 3, "baja velocidad": 4,
    },
    "equipos": {
        "router": 3, "modem": 3, "ont": 3, "onu": 3, "decodificador": 3, "equipo": 2,
        "wifi": 2, "contrasena": 2, "clave wifi": 3, "reinicia": 2, "quemado": 3,
        "danado": 2, "enciende": 2, "antena": 2, "cable": 1,
    },
    "instalacion": {
        "instalacion": 4, "instalar": 3, "mudanza": 4, "mudar": 3, "cambio de plan": 4,
        "nuevo servicio": 4, "visita": 2, "cita": 2, "contratar": 3, "upgrade": 3,
        "traslado": 3, "aumentar plan": 4,
    },
    "facturacion": {
        "factura": 4, "cobro": 4, "pago": 3, "pague": 3, "monto": 3, "deuda": 3,
        "recibo": 3, "cobraron": 4, "doble cobro": 5, "suspendido por pago": 5,
        "transferencia": 2, "reembolso": 4, "precio": 2, "tarifa": 3,
    },
}

PALABRAS_URGENCIA = {
    "critica": ["empresa", "corporativo", "hospital", "clinica", "banco", "toda la zona",
                "todo el sector", "varios clientes", "masiva", "fibra cortada", "emergencia",
                "punto de venta", "pos"],
    "alta": ["urgente", "desde ayer", "dias sin", "varios dias", "trabajo", "teletrabajo",
             "clases", "no funciona nada", "sin servicio", "sin internet", "reclamo"],
    "baja": ["consulta", "informacion", "duda", "me gustaria", "quisiera saber"],
}

PRIORIDAD_BASE = {
    "conexion": "alta",
    "velocidad": "media",
    "equipos": "media",
    "instalacion": "baja",
    "facturacion": "media",
    "otro": "baja",
}

SUGERENCIAS = {
    "conexion": (
        "1. Verificar en el NMS si la ONT del cliente está en línea y revisar alarmas de la OLT/puerto PON.\n"
        "2. Confirmar si hay avería masiva en el sector (otros tickets del mismo nodo).\n"
        "3. Pedir al cliente revisar luces del equipo (PON/LOS) y reiniciar la ONT 30 segundos.\n"
        "4. Si LOS en rojo: agendar visita técnica para medir potencia óptica y revisar la acometida.\n"
        "Respuesta sugerida: «Estimado cliente, ya estamos revisando su conexión. Le pedimos verificar "
        "si la luz LOS de su equipo está en rojo; le mantendremos informado.»"
    ),
    "velocidad": (
        "1. Solicitar una prueba de velocidad por cable (no WiFi) y comparar con el plan contratado.\n"
        "2. Revisar potencia óptica y errores en la interfaz del cliente.\n"
        "3. Verificar saturación del canal WiFi y cantidad de dispositivos conectados.\n"
        "4. Si la potencia es baja (< -27 dBm), escalar a visita técnica.\n"
        "Respuesta sugerida: «Para ayudarle mejor, ¿podría realizar una prueba en speedtest.net con un "
        "equipo conectado por cable y enviarnos el resultado?»"
    ),
    "equipos": (
        "1. Identificar modelo y serial del equipo.\n"
        "2. Guiar un reinicio y, si persiste, restablecimiento de fábrica con reaprovisionamiento remoto.\n"
        "3. Si el equipo no enciende o está dañado, generar orden de reemplazo.\n"
        "Respuesta sugerida: «Vamos a revisar su equipo de forma remota. Si es necesario, coordinaremos "
        "el reemplazo sin costo adicional dentro de la garantía.»"
    ),
    "instalacion": (
        "1. Verificar factibilidad técnica (cobertura y puertos disponibles en la caja NAP).\n"
        "2. Confirmar datos y dirección del cliente.\n"
        "3. Agendar cita con cuadrilla y notificar al cliente fecha y franja horaria.\n"
        "Respuesta sugerida: «Hemos recibido su solicitud. En breve le confirmaremos la fecha disponible "
        "para la visita técnica.»"
    ),
    "facturacion": (
        "1. Revisar estado de cuenta y pagos registrados del cliente.\n"
        "2. Validar comprobante de pago y conciliar con el área de cobranzas.\n"
        "3. Si hay cobro indebido, generar nota de crédito y reactivar servicio si aplica.\n"
        "Respuesta sugerida: «Estamos verificando su estado de cuenta. Por favor envíenos el comprobante "
        "de pago para agilizar la revisión.»"
    ),
    "otro": (
        "1. Contactar al cliente para ampliar la información del caso.\n"
        "2. Reclasificar el ticket a la categoría correcta.\n"
        "Respuesta sugerida: «Gracias por contactarnos. ¿Podría darnos más detalles de su solicitud?»"
    ),
}


# --------------------------------------------------------------------------- #
# Clasificador local
# --------------------------------------------------------------------------- #
def _puntuar_categorias(texto: str) -> dict[str, int]:
    return {
        cat: sum(peso for palabra, peso in palabras.items() if re.search(rf"\b{palabra}\b", texto))
        for cat, palabras in PALABRAS_CLAVE.items()
    }


def _detectar_prioridad(texto: str, categoria: str) -> str:
    for nivel in ("critica", "alta", "baja"):
        if any(re.search(rf"\b{p}\b", texto) for p in PALABRAS_URGENCIA[nivel]):
            # una consulta "baja" no rebaja una categoría que de por sí es alta
            if nivel == "baja" and PRIORIDAD_BASE[categoria] == "alta":
                continue
            return nivel
    return PRIORIDAD_BASE[categoria]


def clasificar_local(titulo: str, descripcion: str) -> ResultadoIA:
    texto = normalizar(f"{titulo} {titulo} {descripcion}")  # el título pesa el doble
    puntajes = _puntuar_categorias(texto)
    total = sum(puntajes.values())
    categoria, mejor = max(puntajes.items(), key=lambda kv: kv[1])

    if mejor == 0:
        categoria, confianza = "otro", 0.3
    else:
        confianza = round(min(0.95, 0.5 + 0.5 * mejor / total), 2)

    prioridad = _detectar_prioridad(texto, categoria)
    return ResultadoIA(categoria, prioridad, SUGERENCIAS[categoria], confianza, "local")


# --------------------------------------------------------------------------- #
# Clasificador con modelo de lenguaje (Claude)
# --------------------------------------------------------------------------- #
PROMPT_SISTEMA = f"""Eres un analista de soporte técnico de un proveedor de internet por fibra óptica en Venezuela.
Clasifica el ticket del cliente y responde SOLO con un objeto JSON con estas claves:
- "categoria": una de {list(CATEGORIAS)}
- "prioridad": una de {list(PRIORIDADES_VALIDAS)} (critica = clientes empresariales o averías masivas)
- "sugerencia": pasos concretos numerados para el técnico y una respuesta breve y amable para el cliente
- "confianza": número entre 0 y 1
Categorías: {json.dumps(CATEGORIAS, ensure_ascii=False)}"""


def _extraer_json(texto: str) -> dict:
    coincidencia = re.search(r"\{.*\}", texto, re.DOTALL)
    if not coincidencia:
        raise ValueError("La respuesta del modelo no contiene JSON")
    return json.loads(coincidencia.group(0))


def clasificar_con_llm(titulo: str, descripcion: str, api_key: str, modelo: str) -> ResultadoIA:
    import anthropic  # importación diferida: solo se necesita si hay API key

    cliente = anthropic.Anthropic(api_key=api_key, timeout=20)
    respuesta = cliente.messages.create(
        model=modelo,
        max_tokens=600,
        system=PROMPT_SISTEMA,
        messages=[{"role": "user", "content": f"Título: {titulo}\nDescripción: {descripcion}"}],
    )
    datos = _extraer_json(respuesta.content[0].text)

    categoria = datos.get("categoria", "otro")
    prioridad = datos.get("prioridad", "media")
    if categoria not in CATEGORIAS or prioridad not in PRIORIDADES_VALIDAS:
        raise ValueError(f"Valores fuera de catálogo: {categoria}, {prioridad}")

    return ResultadoIA(
        categoria=categoria,
        prioridad=prioridad,
        sugerencia=str(datos.get("sugerencia", "")).strip() or SUGERENCIAS[categoria],
        confianza=float(datos.get("confianza", 0.8)),
        fuente="claude",
    )


# --------------------------------------------------------------------------- #
# Punto de entrada público
# --------------------------------------------------------------------------- #
def clasificar_ticket(titulo: str, descripcion: str) -> ResultadoIA:
    """Clasifica un ticket usando el LLM si está disponible, o el modelo local."""
    titulo, descripcion = (titulo or "").strip(), (descripcion or "").strip()
    config = current_app.config if current_app else {}
    api_key = config.get("ANTHROPIC_API_KEY")

    if config.get("IA_HABILITADA", True) and api_key:
        try:
            return clasificar_con_llm(titulo, descripcion, api_key, config.get("IA_MODELO"))
        except Exception as error:  # noqa: BLE001 - cualquier fallo cae al modelo local
            log.warning("Fallo la IA externa, se usa el clasificador local: %s", error)

    return clasificar_local(titulo, descripcion)
