"""
CAPA 3 · DISEÑO — rutas de carpetas y motor de plantillas.

Un solo lugar que sabe DÓNDE están las plantillas HTML y los archivos
estáticos. Todas las rutas importan `templates` desde aquí en vez de crear
cada una su propio Jinja2Templates(directory="templates").

La ruta se calcula desde la ubicación de ESTE archivo, así funciona igual
en tu PC, desde cualquier carpeta, y en Vercel.
"""
from pathlib import Path

from fastapi.templating import Jinja2Templates

DIR_PRESENTACION = Path(__file__).resolve().parent
DIR_TEMPLATES = DIR_PRESENTACION / "templates"
DIR_STATIC = DIR_PRESENTACION / "static"

templates = Jinja2Templates(directory=str(DIR_TEMPLATES))
