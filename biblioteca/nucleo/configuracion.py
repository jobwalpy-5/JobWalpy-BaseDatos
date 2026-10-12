"""
CAPA 1 · CONEXIÓN — configuración.

Aquí se leen las variables de entorno. Si mañana necesitas una nueva
(una clave secreta, un bucket de archivos...), se agrega en este archivo
y el resto del proyecto la importa desde aquí.
"""
import os

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "Falta la variable de entorno DATABASE_URL. Copia el 'Pooled connection "
        "string' desde el dashboard de Neon (Connection Details) y configúrala "
        "como variable de entorno (localmente en tu .env, y en Vercel en "
        "Project Settings -> Environment Variables)."
    )
