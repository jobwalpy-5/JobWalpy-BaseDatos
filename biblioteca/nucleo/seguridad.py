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

Por qué esto importa:
    Antes, en database.py, las contraseñas se guardaban tal cual:
        {"password": "1234"}
    Eso significa que cualquiera con acceso a la base de datos (o a un
    backup, o a un error de log) ve la contraseña real de cada usuario.
    Como casi nadie reutiliza contraseñas... es broma, todo el mundo las
    reutiliza. Por eso SIEMPRE se debe guardar un hash, nunca la contraseña.
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
    """
    Convierte una contraseña en texto plano en un string seguro para guardar
    en la base de datos, con el formato:  "salt$hash"

    El "salt" es aleatorio y distinto para cada usuario. Esto evita que dos
    usuarios con la misma contraseña ("123456") tengan el mismo hash guardado,
    lo cual protege contra ataques de "rainbow tables".
    """
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    ).hex()
    return f"{salt}${pwd_hash}"


def verify_password(password: str, stored_hash: str) -> bool:
    """
    Verifica si `password` (lo que el usuario escribió al hacer login)
    corresponde al `stored_hash` guardado en la base de datos.

    Usamos hmac.compare_digest en vez de "==" para comparar los hashes,
    porque "==" puede filtrar información por temporización (timing attack).
    """
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
