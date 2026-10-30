"""
 DISEÑO — rutas de carpetas y motor de plantillas.

La ruta se calcula desde la ubicación de ESTE archivo, así funciona igual
en tu PC, desde cualquier carpeta, y en Vercel.
"""
from pathlib import Path

from fastapi.templating import Jinja2Templates

DIR_PRESENTACION = Path(__file__).resolve().parent
DIR_TEMPLATES = DIR_PRESENTACION / "templates"
DIR_STATIC = DIR_PRESENTACION / "static"

templates = Jinja2Templates(directory=str(DIR_TEMPLATES))
