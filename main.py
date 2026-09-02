from fastapi import FastAPI, Request, Cookie
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

load_dotenv()  # En local, lee DATABASE_URL desde .env. En Vercel, no hace nada
                # (la variable ya viene configurada desde su dashboard) y no falla.

from routers.jobs import router as jobs_router
from routers.users import router as users_router
from routers.applications import router as applications_router
from routers.chat import router as chat_router
from routers.media import router as media_router

import database as db

app = FastAPI(title="JobWalpy", description="Plataforma de empleo")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

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
