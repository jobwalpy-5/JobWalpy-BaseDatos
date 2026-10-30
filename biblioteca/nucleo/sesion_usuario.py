"""
Antes, la cookie `user_id` guardaba el id en texto simple. Como los ids de las
personas se ven en la página de chat (/chat/<id>), cualquiera podía escribir
esa cookie a mano en su navegador y "ser" esa persona SIN contraseña.

Al iniciar sesión, la cookie guarda  <id>.<vence>.<firma>. La firma es un HMAC
hecho con un secreto que solo conoce el servidor, así que nadie puede fabricar
una cookie válida de otra persona.

Para no tener que cambiar las ~30 rutas que leen `request.cookies["user_id"]`,
el middleware `SesionFirmadaMiddleware` revisa la firma ANTES de que llegue la
petición a las rutas: si es válida, deja el id limpio en la cookie (las rutas
siguen funcionando igual); si es falsa o vencida, quita la cookie (la persona
queda como visitante).
"""
import hashlib
import hmac
import os
import time

NOMBRE_COOKIE = "user_id"
DURACION_SEGUNDOS = 30 * 24 * 60 * 60  # 30 días, igual que antes


def _secreto() -> bytes:
    # Prefijo distinto al del admin: una cookie de usuario NUNCA sirve como cookie de admin.
    base = os.environ.get("SECRET_KEY")
    if not base:
        raise RuntimeError("Falta la variable de entorno SECRET_KEY para firmar la sesión.")
    return ("jobwalpy-usuario:" + base).encode()


def _firma(texto: str) -> str:
    return hmac.new(_secreto(), texto.encode(), hashlib.sha256).hexdigest()


def firmar(user_id: str) -> str:
    vence = int(time.time()) + DURACION_SEGUNDOS
    cuerpo = f"{user_id}.{vence}"
    return f"{cuerpo}.{_firma(cuerpo)}"


def verificar(valor: str | None) -> str | None:
    """Devuelve el id si la cookie es auténtica y no ha vencido; si no, None."""
    if not valor:
        return None
    try:
        user_id, vence, firma = valor.rsplit(".", 2)
        if not hmac.compare_digest(firma, _firma(f"{user_id}.{vence}")):
            return None
        if int(vence) < time.time():
            return None
        return user_id
    except (ValueError, TypeError):
        return None


def iniciar_sesion(response, user_id: str) -> None:
    """Deja la cookie firmada en la respuesta (la usan login y registros)."""
    response.set_cookie(
        key=NOMBRE_COOKIE, value=firmar(str(user_id)), max_age=DURACION_SEGUNDOS,
       httponly=True, samesite="lax", path="/",
        secure=os.environ.get("COOKIE_SECURE", "0" if os.environ.get("ENVIRONMENT") == "development" else "1") == "1",
    )


def _limpiar_cookie(cabecera: str) -> str:
    """Recibe 'a=1; user_id=XYZ; b=2' y devuelve el texto con user_id verificado (o sin él)."""
    salida = []
    for par in cabecera.split(";"):
        nombre, _, valor = par.strip().partition("=")
        if nombre == NOMBRE_COOKIE:
            user_id = verificar(valor)
            if user_id is None:
                continue                      # firma falsa/vencida → se descarta
            par = f"{NOMBRE_COOKIE}={user_id}"  # válida → id limpio para las rutas
        if par.strip():
            salida.append(par.strip())
    return "; ".join(salida)


class SesionFirmadaMiddleware:
    """Middleware ASGI puro: verifica la firma de la cookie user_id en cada petición."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            cabeceras = []
            for clave, valor in scope["headers"]:
                if clave == b"cookie":
                    valor = _limpiar_cookie(valor.decode("latin-1")).encode("latin-1")
                    if not valor:
                        continue
                cabeceras.append((clave, valor))
            scope = {**scope, "headers": cabeceras}
        await self.app(scope, receive, send)
