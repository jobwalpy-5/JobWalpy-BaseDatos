import os
from pathlib import Path
from dotenv import load_dotenv

# Obtener la raíz del proyecto.
BASE_DIR = Path(__file__).resolve().parents[2]

# Cargar las variables del archivo .env sin sobrescribir
# las variables de entorno configuradas en el sistema o en Vercel.
ENV_FILE = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_FILE, override=False)

# Obtener la URL de conexión a PostgreSQL.
DATABASE_URL = os.getenv("DATABASE_URL")

# Comprobar que la variable esté configurada.
if not DATABASE_URL:
    raise RuntimeError(
        "Falta la variable DATABASE_URL. "
        f"Se buscó el archivo .env en: {ENV_FILE}"
    )