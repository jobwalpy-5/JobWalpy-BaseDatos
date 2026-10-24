"""
auth.py — Utilidades de seguridad (JobWalpy)
==============================================

Este archivo NO depende de librerías externas (ni bcrypt, ni passlib).
Todo se hace con el módulo estándar `hashlib` de Python para evitar
problemas de instalación en entornos serverless (Vercel) donde compilar
extensiones en C puede fallar.

Qué hay aquí:
    1. hash_password()   -> convierte una contraseña en texto plano en un
                             hash irreversible + salt.
    2. verify_password() -> compara una contraseña en texto plano contra
                             un hash guardado, sin nunca desencriptarlo.
    3. new_id()           -> genera IDs únicos (UUID4) en vez de "user3".
    4. new_token()        -> genera tokens aleatorios seguros, usados para
                             verificación de email.

"""

import hashlib
import hmac
import secrets
import uuid

# 260,000 iteraciones es la recomendación de OWASP (2023+) para
# PBKDF2-HMAC-SHA256. Más iteraciones = más lento de "romper" por
# fuerza bruta, pero sigue siendo rápido para un solo login real.
PBKDF2_ITERATIONS = 260_000


def hash_password(password: str) -> str:

    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    ).hex()
    return f"{salt}${pwd_hash}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, pwd_hash = stored_hash.split("$")
    except (ValueError, AttributeError):
        return False

    new_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    ).hex()
    return hmac.compare_digest(new_hash, pwd_hash)


def new_id() -> str:
    """
    Genera un ID único garantizado (UUID4), en vez de contar cuántos
    usuarios hay (f"user{len(_users)+1}"), que genera IDs duplicados
    apenas alguien borra un usuario.
    """
    return str(uuid.uuid4())


def new_token(n_bytes: int = 32) -> str:
    """
    Genera un token aleatorio seguro para usar en enlaces de verificación
    de correo o de restablecimiento de contraseña.
    """
    return secrets.token_urlsafe(n_bytes)
