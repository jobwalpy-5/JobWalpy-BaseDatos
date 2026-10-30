import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, Request, Cookie
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()
if not os.environ.get("SECRET_KEY"):
    raise RuntimeError("Falta SECRET_KEY. Configúrala antes de iniciar JobWalpy.")

from presentacion.rutas.jobs import router as jobs_router
from presentacion.rutas.users import router as users_router
from presentacion.rutas.applications import router as applications_router
from presentacion.rutas.chat import router as chat_router
from presentacion.rutas.media import router as media_router

from dominio import servicios as db
from presentacion.plantillas import templates, DIR_STATIC
from presentacion.rutas.admin import router as admin_router
from nucleo.sesion_usuario import SesionFirmadaMiddleware


app = FastAPI(title="JobWalpy", description="Plataforma de empleo")


class PublicStaticFiles(StaticFiles):
    """No expone documentos legales que pudieran quedar de versiones anteriores."""
    async def get_response(self, path: str, scope):
        normalized = path.replace("\\", "/").lstrip("/")
        if normalized.startswith("uploads/docs/") or normalized == "uploads/docs":
            return Response(status_code=404)
        return await super().get_response(path, scope)


app.mount("/static", PublicStaticFiles(directory=str(DIR_STATIC)), name="static")


class SameOriginGuard:
    """Rechaza formularios mutadores con origen cruzado como defensa CSRF adicional."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http" and scope.get("method") in {"POST", "PUT", "PATCH", "DELETE"}:
            headers = {k.lower(): v for k, v in scope.get("headers", [])}
            origin = headers.get(b"origin", b"").decode("latin-1")
            host = headers.get(b"host", b"").decode("latin-1")
            fetch_site = headers.get(b"sec-fetch-site", b"").decode("latin-1").lower()
            cross_origin = bool(origin and urlparse(origin).netloc.lower() != host.lower())
            if cross_origin or fetch_site == "cross-site":
                response = Response("Solicitud rechazada por política de origen.", status_code=403)
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)



app.add_middleware(SameOriginGuard)
app.add_middleware(SesionFirmadaMiddleware)

app.include_router(jobs_router)
app.include_router(users_router)
app.include_router(applications_router)
app.include_router(chat_router)
app.include_router(media_router)
app.include_router(admin_router)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, user_id: str = Cookie(default=None)):
    all_jobs = db.get_jobs()
    recent_jobs = [j for j in all_jobs if j.get("active", True)][:4]
    categories = list(set(str(j.get("category", "")) for j in all_jobs if j.get("category")))

    stats = {
        "total_jobs":   len([j for j in all_jobs if j.get("active", True)]),
        "total_users":  db.contar_buscadores_activos(),
        "categories":   len(categories),
        "applications": len(db.get_applications()),
    }

    user = db.get_active_user(user_id) if user_id else None
    recent_seekers     = []
    chattable_users    = []
    posted_jobs        = []
    recent_applications = []

    if user:
        all_users = db.get_users()
        contact_ids = {
            str(participant)
            for conv in db.get_conversations_by_user(user_id)
            for participant in conv.get("participants", [])
            if str(participant) != str(user_id)
        }
        chattable_users = [u for u in all_users if str(u["id"]) in contact_ids]

        if user.get("role") == "empleador" and user.get("verified_company"):
            recent_seekers = [u for u in all_users if u.get("role") == "buscador"][:6]
            posted_jobs    = [j for j in all_jobs if str(j.get("posted_by")) == str(user_id)]
        else:
            # Buscador: mostrar sus últimas 3 aplicaciones
            apps = db.get_applications_by_user(user_id)
            for app in apps[:3]:
                job = db.get_job(app["job_id"])
                if job:
                    recent_applications.append({**app, "job": job})

    return templates.TemplateResponse(request=request, name="index.html", context={
        "user":                user,
        "recent_jobs":         recent_jobs,
        "recent_seekers":      recent_seekers,
        "posted_jobs":         posted_jobs,
        "recent_applications": recent_applications,
        "chattable_users":     chattable_users,
        "categories":          categories,
        "stats":               stats,
    })

