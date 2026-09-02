"""
storage.py — Almacenamiento de objetos (MinIO) para JobWalpy
================================================================

Integra la propuesta de tu compañero/a de foto de perfil, video de
presentación y portafolio. La base de datos NUNCA guarda el archivo en sí
— solo la URL que MinIO devuelve, tal como proponía el documento original.

VARIABLES DE ENTORNO NECESARIAS (agrégalas a tu .env, igual que DATABASE_URL):
    MINIO_ENDPOINT      ej. "localhost:9000" o "play.min.io" o tu servidor real
    MINIO_ACCESS_KEY    usuario/access key de tu MinIO
    MINIO_SECRET_KEY    contraseña/secret key de tu MinIO
    MINIO_BUCKET        nombre del bucket (por defecto "jobwalpy-media")
    MINIO_SECURE        "true" si tu MinIO usa https, "false" si es http (por defecto "true")

Si estas variables no están configuradas, cualquier intento de subir un
archivo falla con un error CLARO (RuntimeError) en vez de fallar en
silencio o guardar datos corruptos — mismo criterio que usamos con
DATABASE_URL en database.py.
"""

import io
import os
import uuid

from minio import Minio

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY")
MINIO_BUCKET = os.environ.get("MINIO_BUCKET", "jobwalpy-media")
MINIO_SECURE = os.environ.get("MINIO_SECURE", "true").lower() == "true"

_client: Minio | None = None


def _get_client() -> Minio:
    """Conecta (una sola vez) y crea el bucket si no existe."""
    global _client
    if _client is not None:
        return _client
    if not (MINIO_ENDPOINT and MINIO_ACCESS_KEY and MINIO_SECRET_KEY):
        raise RuntimeError(
            "Faltan variables de entorno de MinIO (MINIO_ENDPOINT, MINIO_ACCESS_KEY, "
            "MINIO_SECRET_KEY). Configúralas en tu .env, igual que hiciste con DATABASE_URL."
        )
    _client = Minio(
        MINIO_ENDPOINT, access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY, secure=MINIO_SECURE,
    )
    if not _client.bucket_exists(MINIO_BUCKET):
        _client.make_bucket(MINIO_BUCKET)
    return _client


# ── REGLAS DE VALIDACIÓN (tal como las pidió la propuesta original) ─────────

ALLOWED_IMAGE_EXT = {"jpg", "jpeg", "png", "webp"}
ALLOWED_VIDEO_EXT = {"mp4", "mov", "webm"}
ALLOWED_PORTFOLIO_EXT = {"pdf", "jpg", "jpeg", "png"}

MAX_IMAGE_SIZE = 10 * 1024 * 1024        # 10 MB — razonable para una foto de perfil
MAX_VIDEO_SIZE = 100 * 1024 * 1024       # 100 MB — el límite que pedía la propuesta
MAX_PORTFOLIO_FILE_SIZE = 20 * 1024 * 1024  # 20 MB por archivo de portafolio


class ArchivoInvalidoError(Exception):
    """Se lanza cuando un archivo no cumple el formato o tamaño permitido."""


def _extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def _validar(filename: str, size_bytes: int, extensiones_permitidas: set, max_bytes: int) -> str:
    ext = _extension(filename)
    if ext not in extensiones_permitidas:
        raise ArchivoInvalidoError(
            f"Formato .{ext or '(sin extensión)'} no permitido. "
            f"Formatos válidos: {', '.join(sorted(extensiones_permitidas))}."
        )
    if size_bytes > max_bytes:
        raise ArchivoInvalidoError(
            f"El archivo pesa {size_bytes / (1024 * 1024):.1f} MB; "
            f"el máximo permitido es {max_bytes / (1024 * 1024):.0f} MB."
        )
    return ext


def _content_type(ext: str) -> str:
    return {
        "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp",
        "mp4": "video/mp4", "mov": "video/quicktime", "webm": "video/webm",
        "pdf": "application/pdf",
    }.get(ext, "application/octet-stream")


def _upload(object_name: str, content: bytes, content_type: str) -> str:
    client = _get_client()
    client.put_object(
        MINIO_BUCKET, object_name, io.BytesIO(content),
        length=len(content), content_type=content_type,
    )
    protocolo = "https" if MINIO_SECURE else "http"
    return f"{protocolo}://{MINIO_ENDPOINT}/{MINIO_BUCKET}/{object_name}"


# ── FUNCIONES PÚBLICAS (una por tipo de archivo, como pedía la propuesta) ───

def upload_profile_photo(user_id: str, filename: str, content: bytes) -> str:
    ext = _validar(filename, len(content), ALLOWED_IMAGE_EXT, MAX_IMAGE_SIZE)
    object_name = f"profile-photos/{user_id}.{ext}"
    return _upload(object_name, content, _content_type(ext))


def upload_presentation_video(user_id: str, filename: str, content: bytes) -> str:
    ext = _validar(filename, len(content), ALLOWED_VIDEO_EXT, MAX_VIDEO_SIZE)
    # NOTA HONESTA: la propuesta original también pedía limitar la duración
    # a 2 minutos. Validar la duración real de un video requiere leer sus
    # metadatos (con ffprobe/moviepy), algo que no puedo instalar ni probar
    # en este entorno sin acceso a internet. El límite de TAMAÑO (100 MB)
    # sí se aplica; la duración queda como TODO explícito para cuando
    # alguien del equipo lo pruebe con un MinIO real.
    object_name = f"presentation-videos/{user_id}.{ext}"
    return _upload(object_name, content, _content_type(ext))


def upload_portfolio_file(user_id: str, filename: str, content: bytes) -> str:
    ext = _validar(filename, len(content), ALLOWED_PORTFOLIO_EXT, MAX_PORTFOLIO_FILE_SIZE)
    nombre_unico = f"{uuid.uuid4()}.{ext}"
    object_name = f"portfolios/{user_id}/{nombre_unico}"
    return _upload(object_name, content, _content_type(ext))
