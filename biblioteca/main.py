import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, Request, Cookie
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

from presentacion.rutas.jobs import router as jobs_router
from presentacion.rutas.users import router as users_router
from presentacion.rutas.applications import router as applications_router
from presentacion.rutas.chat import router as chat_router
from presentacion.rutas.media import router as media_router

from dominio import servicios as db
from presentacion.plantillas import templates, DIR_STATIC

from presentacion.rutas import admin


app = FastAPI(title="JobWalpy", description="Plataforma de empleo")
app.mount("/static", StaticFiles(directory=str(DIR_STATIC)), name="static")

app.include_router(jobs_router)
app.include_router(users_router)
app.include_router(applications_router)
app.include_router(chat_router)
app.include_router(media_router)
app.include_router(admin.router)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, user_id: str = Cookie(default=None)):
    all_jobs = db.get_jobs()
    recent_jobs = [j for j in all_jobs if j.get("active", True)][:4]
    categories = list(set(str(j.get("category", "")) for j in all_jobs if j.get("category")))

    stats = {
        "total_jobs":   len([j for j in all_jobs if j.get("active", True)]),
        "total_users":  len(db.get_users()),
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
        chattable_users = [u for u in all_users if str(u["id"]) != str(user_id)]

        if user.get("role") == "empleador":
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

