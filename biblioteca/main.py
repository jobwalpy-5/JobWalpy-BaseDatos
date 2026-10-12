import sys
from pathlib import Path

# Permite "from nucleo...", "from dominio..." sin importar desde dónde se arranque.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, Request, Cookie
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()  # En local, lee DATABASE_URL desde .env. En Vercel, no hace nada
                # (la variable ya viene configurada desde su dashboard) y no falla.

from presentacion.rutas.jobs import router as jobs_router
from presentacion.rutas.users import router as users_router
from presentacion.rutas.applications import router as applications_router
from presentacion.rutas.chat import router as chat_router
from presentacion.rutas.media import router as media_router

from dominio import servicios as db
from presentacion.plantillas import templates, DIR_STATIC

app = FastAPI(title="JobWalpy", description="Plataforma de empleo")
app.mount("/static", StaticFiles(directory=str(DIR_STATIC)), name="static")

app.include_router(jobs_router)
app.include_router(users_router)
app.include_router(applications_router)
app.include_router(chat_router)
app.include_router(media_router)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, user_id: str = Cookie(default=None)):
    all_jobs = db.get_jobs()
    recent_jobs = all_jobs[:4]
    categories = list(set(str(j.get("category", "")) for j in all_jobs if j.get("category")))
    stats = {
        "total_jobs": len(all_jobs),
        "total_users": len(db.get_users()),
        "categories": len(categories),
        "applications": len(db.get_applications())
    }
    user = db.get_active_user(user_id) if user_id else None
    recent_seekers = []
    chattable_users = []
    if user:
        all_users = db.get_users()
        chattable_users = [u for u in all_users if str(u["id"]) != str(user_id)]
        if user.get("role") == "empleador":
            recent_seekers = [u for u in all_users if u.get("role") == "buscador"][:6]
    return templates.TemplateResponse(request=request, name="index.html", context={
        "recent_jobs": recent_jobs, "recent_seekers": recent_seekers,
        "chattable_users": chattable_users, "categories": categories,
        "stats": stats, "user": user
    })
