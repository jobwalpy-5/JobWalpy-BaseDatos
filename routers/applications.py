from fastapi import APIRouter, Request, Form, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import database as db

router = APIRouter()
templates = Jinja2Templates(directory="templates")


# ── VER APLICACIONES RECIBIDAS (empleador) ────────────────────────────────────
# NOTA: esta ruta no existía en la versión anterior — sin ella, applications.html
# era inalcanzable (nada apuntaba a /applications). La agrego para que el botón
# "Ver candidatos" / flujo del empleador funcione de verdad.
@router.get("/applications", response_class=HTMLResponse)
async def applications_page(request: Request):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse("/login?next=/applications", status_code=302)

    user = db.get_active_user(user_id)
    if not user or user.get("role") != "empleador":
        return RedirectResponse("/", status_code=302)

    my_job_ids = {j["id"] for j in db.get_jobs() if str(j.get("posted_by")) == str(user_id)}
    enriched = []
    for app in db.get_applications():
        if app["job_id"] not in my_job_ids:
            continue
        job = db.get_job(app["job_id"])
        applicant = db.get_user(app["user_id"])
        if not job or not applicant:
            continue
        enriched.append({**app, "job": job, "applicant": applicant})

    enriched.sort(key=lambda a: a.get("applied_at", ""), reverse=True)

    return templates.TemplateResponse(request=request, name="applications.html", context={
        "user": user, "applications": enriched, "total": len(enriched)
    })


# ── CAMBIAR ESTADO DE UNA APLICACIÓN (empleador) ──────────────────────────────
@router.post("/applications/{application_id}/status")
async def update_status(
    application_id: str,
    status: str = Form(...),
    user_id: str = Cookie(default=None)
):
    """Permite al empleador cambiar el estado de una aplicación."""
    if not user_id:
        return RedirectResponse("/login", status_code=302)

    user = db.get_active_user(user_id)
    if not user or user.get("role") != "empleador":
        return RedirectResponse("/", status_code=302)

    application = db.get_application(application_id)
    if not application:
        return RedirectResponse("/applications", status_code=302)

    # Verificar que el empleo pertenece al empleador
    job = db.get_job(application["job_id"])
    if not job or str(job.get("posted_by")) != str(user_id):
        return RedirectResponse("/applications", status_code=302)

    db.update_application_status(application_id, status)
    return RedirectResponse("/applications?updated=1", status_code=302)
