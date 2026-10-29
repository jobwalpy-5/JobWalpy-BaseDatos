"""
problema que resuelve: una cookie normal con el id del admin se puede
inventar o copiar. Aquí la cookie lleva una FIRMA (HMAC) hecha con un secreto
que solo conoce el servidor, y una fecha de vencimiento. Si alguien cambia
una sola letra de la cookie, la firma deja de coincidir y se rechaza

Formato de la cookie:  <id_admin>.<vence_en_segundos>.<firma>
"""
import hashlib
import hmac
import os
import time

DURACION_SEGUNDOS = 8 * 60 * 60  # la sesión de admin dura 8 horas


def _secreto() -> bytes:
    base = os.environ.get("SECRET_KEY")
    if not base:
        raise RuntimeError("Falta la variable de entorno SECRET_KEY para firmar la sesión de admin.")
    return ("jobwalpy-admin:" + base).encode()


def _firma(texto: str) -> str:
    return hmac.new(_secreto(), texto.encode(), hashlib.sha256).hexdigest()


def firmar(admin_id: str) -> str:
    vence = int(time.time()) + DURACION_SEGUNDOS
    cuerpo = f"{admin_id}.{vence}"
    return f"{cuerpo}.{_firma(cuerpo)}"


def verificar(valor: str | None) -> str | None:
    """Devuelve el id del admin si la cookie es auténtica y no ha vencido; si no, None."""
    if not valor:
        return None
    try:
        admin_id, vence, firma = valor.rsplit(".", 2)
        if not hmac.compare_digest(firma, _firma(f"{admin_id}.{vence}")):
            return None
        if int(vence) < time.time():
            return None
        return admin_id
    except (ValueError, TypeError):
        return None
