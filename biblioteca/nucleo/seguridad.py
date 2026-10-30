"""


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

# Los hashes nuevos usan 600.000 iteraciones. Se conserva la verificación de hashes
# antiguos (260.000) para no bloquear a usuarios existentes tras el despliegue.
PBKDF2_ITERATIONS = 600_000
LEGACY_PBKDF2_ITERATIONS = 260_000


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

    password_bytes = password.encode("utf-8")
    salt_bytes = salt.encode("utf-8")
    new_hash = hashlib.pbkdf2_hmac(
        "sha256", password_bytes, salt_bytes, PBKDF2_ITERATIONS
    ).hex()
    if hmac.compare_digest(new_hash, pwd_hash):
        return True
    legacy_hash = hashlib.pbkdf2_hmac(
        "sha256", password_bytes, salt_bytes, LEGACY_PBKDF2_ITERATIONS
    ).hex()
    return hmac.compare_digest(legacy_hash, pwd_hash)


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
