"""Límite de intentos persistente en PostgreSQL (válido también en despliegues serverless)."""
import hashlib

from nucleo.conexion import get_conn


def permitir_intento(request, accion: str, max_intentos: int, ventana_segundos: int) -> bool:
    """Devuelve False al superar el límite. No guarda la IP en claro."""
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = (forwarded.split(",")[0].strip() if forwarded else
          (request.client.host if request.client else "desconocido"))
    clave = hashlib.sha256(f"jobwalpy:{accion}:{ip}".encode("utf-8")).hexdigest()
    with get_conn() as conn:
        fila = conn.execute(
            """
            INSERT INTO rate_limit_attempts (bucket_key, window_start, attempts)
            VALUES (%s, now(), 1)
            ON CONFLICT (bucket_key) DO UPDATE SET
              window_start = CASE
                WHEN rate_limit_attempts.window_start <= now() - (%s * interval '1 second')
                THEN now() ELSE rate_limit_attempts.window_start END,
              attempts = CASE
                WHEN rate_limit_attempts.window_start <= now() - (%s * interval '1 second')
                THEN 1 ELSE rate_limit_attempts.attempts + 1 END
            RETURNING attempts
            """,
            (clave, ventana_segundos, ventana_segundos),
        ).fetchone()
        # Limpieza ocasional para evitar una consulta de borrado completa en cada petición.
        if int(fila["attempts"]) == 1 and int(clave[-2:], 16) == 0:
            conn.execute("DELETE FROM rate_limit_attempts WHERE window_start < now() - interval '2 days'")
    return int(fila["attempts"]) <= max_intentos
