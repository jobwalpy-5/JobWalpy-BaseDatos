from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from datetime import date, datetime
from zoneinfo import ZoneInfo
from dominio import servicios as db
from presentacion.plantillas import templates
from presentacion.rutas.context_helper import chat_context

router = APIRouter()

# ── VER TODOS LOS EMPLEOS ───────────────────────────────────────────────────
@router.get("/jobs", response_class=HTMLResponse)
async def jobs_page(
    request: Request,
    search: str = "",
    category: str = "",
    type: str = "",
    view: str = "",
    location: str = "",
    skills: str = "",
    experience: str = ""
):
    user_id = request.cookies.get("user_id")

    ctx = chat_context(user_id)
    user = ctx.get("user")
    candidates_view = view == "candidatos" or (user and user.get("role") == "empleador")
    if candidates_view:
        if not user or user.get("role") != "empleador":
            return RedirectResponse("/login?next=/jobs?view=candidatos", status_code=302)
        if not user.get("verified_company"):
            return RedirectResponse("/profile?error=empresa_pendiente", status_code=302)
        seekers = [u for u in db.get_users() if u.get("role") == "buscador" and u.get("active", True)]
        if search:
            q = search.casefold()
            seekers = [u for u in seekers if q in u.get("name", "").casefold()
                       or q in u.get("bio", "").casefold()
                       or any(q in str(skill).casefold() for skill in u.get("skills", []))]
        if location:
            q = location.casefold().strip()
            # Si el filtro viene como "Ciudad, Departamento", también encuentra
            # perfiles antiguos que guardaron solamente el nombre de la ciudad.
            ciudad_q = q.split(",", 1)[0].strip()
            seekers = [
                u for u in seekers
                if q in str(u.get("location", "")).casefold()
                or (ciudad_q and ciudad_q in str(u.get("location", "")).casefold())
            ]
        if skills:
            q = skills.casefold()
            seekers = [u for u in seekers if any(q in str(skill).casefold() for skill in u.get("skills", []))]
        if experience:
            seekers = [u for u in seekers if u.get("experience")]
        return templates.TemplateResponse(request=request, name="jobs.html", context={
            **ctx, "view": "candidatos", "seekers": seekers, "jobs": [],
            "categories": [], "search": search, "selected_category": category,
            "selected_type": type, "filter_location": location, "filter_skills": skills,
            "filter_experience": experience, "total": len(seekers)
        })

    activos = [j for j in db.get_jobs() if j.get("active", True)]
    jobs = activos
    if search:
        q = search.casefold()
        jobs = [j for j in jobs if q in j["title"].casefold() or q in j["company"].casefold()]
    if category:
        jobs = [j for j in jobs if j["category"] == category]
    if type:
        jobs = [j for j in jobs if j["type"] == type]
    categories = sorted({j["category"] for j in activos})
    return templates.TemplateResponse(request=request, name="jobs.html", context={
        **ctx, "view": "empleos", "jobs": jobs, "seekers": [],
        "categories": categories, "search": search, "selected_category": category,
        "selected_type": type, "filter_location": "", "filter_skills": "",
        "filter_experience": "", "total": len(jobs)
    })

# ── DETALLE DE UN EMPLEO ────────────────────────────────────────────────────
@router.get("/jobs/{job_id}", response_class=HTMLResponse)
async def job_detail(request: Request, job_id: str):
    user_id = request.cookies.get("user_id")

    job = db.get_job(job_id)
    # ← CAMBIO 3: un empleo desactivado solo lo ve su dueño
    if not job or (not job["active"] and str(job.get("posted_by")) != str(user_id)):
        return RedirectResponse("/jobs")

    ctx = chat_context(user_id)
    applications = db.get_applications_by_job(job_id)
    already_applied = any(a["user_id"] == user_id for a in applications) if user_id else False

    return templates.TemplateResponse(request=request, name="job_detail.html", context={
        **ctx,
        "job": job, "already_applied": already_applied,
        "applicant_count": len(applications)
    })

# ── FORMULARIO: PUBLICAR TRABAJO ─────────────────────────────────────────────
@router.get("/post-job", response_class=HTMLResponse)
async def post_job_page(request: Request):
    user_id = request.cookies.get("user_id")

    ctx = chat_context(user_id)
    if not ctx["user"] or ctx["user"].get("role") != "empleador":
        return RedirectResponse("/login?next=/post-job")
    if not ctx["user"].get("verified_company"):
        return RedirectResponse("/profile?error=empresa_pendiente", status_code=302)
    return templates.TemplateResponse(request=request, name="post_job.html", context=ctx)

# ── ACCIÓN: CREAR TRABAJO ───────────────────────────────────────────────────
@router.post("/post-job")
async def post_job(
    request: Request,
    # ← CAMBIO 4: se quitó el parámetro "company" (ahora sale de la cuenta del empleador)
    title: str = Form(...),
    location: str = Form(...), type: str = Form(...),
    category: str = Form(...), description: str = Form(...),
    requirements: str = Form(...),
    benefits: str = Form(default=""),
    salary_min: int = Form(default=0),
    salary_max: int = Form(default=0)
):
    user_id = request.cookies.get("user_id")

    ctx = chat_context(user_id)
    if not ctx["user"] or ctx["user"].get("role") != "empleador":
        return RedirectResponse("/login", status_code=302)
    if not ctx["user"].get("verified_company"):
        return RedirectResponse("/profile?error=empresa_pendiente", status_code=302)
    if salary_min < 0 or salary_max < 0 or (salary_max and salary_min > salary_max):
        return RedirectResponse("/post-job?error=salario_invalido", status_code=302)

    job = {
        "title": title,
        # ← CAMBIO 6: la empresa es la de la cuenta, no la que venga del formulario
        "company": ctx["user"].get("company_name") or ctx["user"]["name"],
        "location": location,
        "type": type, "category": category, "description": description,
        # ← CAMBIO 7: se ignoran los elementos vacíos ("a, b," ya no crea un "" al final)
        "requirements": [r.strip() for r in requirements.split(",") if r.strip()],
        "benefits": [b.strip() for b in benefits.split(",") if b.strip()],
        "posted_by": user_id, "posted_at": datetime.now(ZoneInfo("America/Bogota")).date().isoformat(), "active": True
    }
    new_job = db.create_job(job)
    return RedirectResponse(f"/jobs/{new_job['id']}", status_code=302)

# ── ACCIÓN: POSTULARSE A UN EMPLEO ───────────────────────────────────────────
@router.post("/jobs/{job_id}/apply")
async def apply_job(
    request: Request,
    job_id: str,
    cover_letter: str = Form(...),
    phone: str = Form(...),
    experience_years: str = Form(...),
    education_level: str = Form(...),
    availability: str = Form(...)
):
    user_id = request.cookies.get("user_id")

    if not user_id:
        return RedirectResponse("/login", status_code=302)

    # Solo un buscador con cuenta activa puede aplicar, y solo a un empleo que exista y esté activo.
    user = db.get_active_user(user_id)
    if not user or user.get("role") != "buscador":
        return RedirectResponse(f"/jobs/{job_id}", status_code=302)
    job = db.get_job(job_id)
    if not job or not job.get("active", True):
        return RedirectResponse("/jobs", status_code=302)

    existing = db.get_applications_by_job(job_id)
    if any(a["user_id"] == user_id for a in existing):
        return RedirectResponse(f"/jobs/{job_id}?error=ya_aplicaste", status_code=302)

    try:
        db.create_application({
        "job_id": job_id,
        "user_id": user_id,
        "cover_letter": cover_letter,
        "phone": phone,
        "experience_years": experience_years,
        "education_level": education_level,
        "availability": availability,
        "status": "pendiente",
        "applied_at": datetime.now(ZoneInfo("America/Bogota")).date().isoformat()
        })
    except db.YaAplicasteError:
        return RedirectResponse(f"/jobs/{job_id}?error=ya_aplicaste", status_code=302)
    return RedirectResponse(f"/jobs/{job_id}?success=aplicacion_enviada", status_code=302)

# ── ACCIÓN: ELIMINAR UN EMPLEO ───────────────────────────────────────────────
@router.post("/jobs/{job_id}/delete")
async def delete_job_route(request: Request, job_id: str):
    user_id = request.cookies.get("user_id")

    job = db.get_job(job_id)
    if not job or str(job.get("posted_by")) != str(user_id):
        return RedirectResponse("/jobs", status_code=302)

    db.delete_job(job_id)
    return RedirectResponse("/profile?success=oferta_cerrada", status_code=302)
