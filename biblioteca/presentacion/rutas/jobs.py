git add .
git commit -m "Solución de conflictos y actualización de repositorio"from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from datetime import date
from dominio import servicios as db
from presentacion.plantillas import templates
from presentacion.rutas.context_helper import chat_context
 
router = APIRouter()
 
# ── VER TODOS LOS EMPLEOS (y, para empleadores, la lista de candidatos) ──────
@router.get("/jobs", response_class=HTMLResponse)
async def jobs_page(
    request: Request,
    search: str = "", category: str = "", type: str = "",
    view: str = "", location: str = "", skills: str = "", experience: str = ""
):
    user_id = request.cookies.get("user_id")
    ctx = chat_context(user_id)
    user = ctx["user"]
    q = search.strip().lower()

    # Vista de candidatos: solo para empleadores (el enlace "👥 Candidatos" de la barra).
    if view == "candidatos":
        if not user or user.get("role") != "empleador":
            return RedirectResponse("/login?next=/jobs?view=candidatos", status_code=302)
        wanted = [x.strip().lower() for x in skills.split(",") if x.strip()]
        seekers = []
        for u in db.get_users():
            if u.get("role") != "buscador":
                continue
            if q and q not in f"{u.get('name','')} {u.get('bio','')} {' '.join(u.get('skills') or [])}".lower():
                continue
            if location and location.lower() not in (u.get("location") or "").lower():
                continue
            have = [x.lower() for x in (u.get("skills") or [])]
            if wanted and not all(any(w in h for h in have) for w in wanted):
                continue
            if experience and not (u.get("experience") or "").strip():
                continue
            seekers.append(u)
        return templates.TemplateResponse(request=request, name="jobs.html", context={
            **ctx, "view": "candidatos", "seekers": seekers, "jobs": [], "categories": [],
            "search": search, "selected_category": "", "selected_type": "",
            "filter_location": location, "filter_skills": skills, "filter_experience": experience,
            "total": len(seekers),
        })

    # Lista pública: solo empleos activos (un empleo desactivado por el admin no debe verse).
    all_jobs = [j for j in db.get_jobs() if j.get("active", True)]
    jobs = all_jobs
    if q:
        jobs = [j for j in jobs if q in j["title"].lower() or q in j["company"].lower()]
    if category:
        jobs = [j for j in jobs if j["category"] == category]
    if type:
        jobs = [j for j in jobs if j["type"] == type]
    categories = sorted({j["category"] for j in all_jobs})

    return templates.TemplateResponse(request=request, name="jobs.html", context={
        **ctx, "view": "", "seekers": [], "jobs": jobs, "categories": categories,
        "search": search, "selected_category": category, "selected_type": type,
        "filter_location": "", "filter_skills": "", "filter_experience": "",
        "total": len(jobs),
    })

# ── DETALLE DE UN EMPLEO ──────────────────────────────────────────────────────
@router.get("/jobs/{job_id}", response_class=HTMLResponse)
async def job_detail(request: Request, job_id: str): # 👈 CORREGIDO
    user_id = request.cookies.get("user_id") # 👈 SOLUCIÓN
    
    job = db.get_job(job_id)
    if not job or (not job.get("active", True) and str(job.get("posted_by")) != str(user_id)):
        return RedirectResponse("/jobs")

    ctx = chat_context(user_id)
    applications = db.get_applications_by_job(job_id)
    already_applied = any(a["user_id"] == user_id for a in applications) if user_id else False
    
    return templates.TemplateResponse(request=request, name="job_detail.html", context={
        **ctx,
        "job": job, "already_applied": already_applied,
        "applicant_count": len(applications)
    })
 
# ── FORMULARIO: PUBLICAR TRABAJO ──────────────────────────────────────────────
@router.get("/post-job", response_class=HTMLResponse)
async def post_job_page(request: Request): # 👈 CORREGIDO
    user_id = request.cookies.get("user_id") # 👈 SOLUCIÓN
    
    ctx = chat_context(user_id)
    if not ctx["user"] or ctx["user"].get("role") != "empleador":
        return RedirectResponse("/login?next=/post-job")
    return templates.TemplateResponse(request=request, name="post_job.html", context=ctx)
 
# ── ACCIÓN: CREAR TRABAJO ─────────────────────────────────────────────────────
@router.post("/post-job")
async def post_job(
    request: Request,
    title: str = Form(...),
    location: str = Form(...), type: str = Form(...),
    category: str = Form(...), description: str = Form(...),
    requirements: str = Form(...), benefits: str = Form(default=""),
    salary_min: int = Form(default=0), salary_max: int = Form(default=0)
): # 👈 CORREGIDO
    user_id = request.cookies.get("user_id") # 👈 SOLUCIÓN
    
    ctx = chat_context(user_id)
    if not ctx["user"] or ctx["user"].get("role") != "empleador":
        return RedirectResponse("/login", status_code=302)
        
    if salary_min < 0 or salary_max < 0 or (salary_max and salary_max < salary_min):
        return RedirectResponse("/post-job?error=salario_invalido", status_code=302)

    job = {
        "title": title, "company": ctx["user"].get("company_name") or ctx["user"]["name"], "location": location,
        "salary_min": salary_min, "salary_max": salary_max,
        "type": type, "category": category, "description": description,
        "requirements": [r.strip() for r in requirements.split(",") if r.strip()],
        "benefits": [b.strip() for b in benefits.split(",") if b.strip()],
        "posted_by": user_id, "posted_at": str(date.today()), "active": True
    }
    new_job = db.create_job(job)
    return RedirectResponse(f"/jobs/{new_job['id']}", status_code=302)
 
# ── ACCIÓN: POSTULARSE A UN EMPLEO ────────────────────────────────────────────
@router.post("/jobs/{job_id}/apply")
async def apply_job(
    request: Request, # 👈 AÑADIDO: Necesitamos el request para leer las cookies
    job_id: str,
    cover_letter: str = Form(...),
    phone: str = Form(...),
    experience_years: str = Form(...),
    education_level: str = Form(...),
    availability: str = Form(...)
): # 👈 CORREGIDO
    user_id = request.cookies.get("user_id") # 👈 SOLUCIÓN
    
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
        
    db.create_application({
        "job_id": job_id,
        "user_id": user_id,
        "cover_letter": cover_letter,
        "phone": phone,
        "experience_years": experience_years,
        "education_level": education_level,
        "availability": availability,
        "status": "pendiente",
        "applied_at": str(date.today())
    })
    return RedirectResponse(f"/jobs/{job_id}?success=aplicacion_enviada", status_code=302)
 
# ── ACCIÓN: ELIMINAR UN EMPLEO ────────────────────────────────────────────────
@router.post("/jobs/{job_id}/delete")
async def delete_job_route(request: Request, job_id: str): # 👈 CORREGIDO (Añadido request)
    user_id = request.cookies.get("user_id") # 👈 SOLUCIÓN
    
    job = db.get_job(job_id)
    if not job or job.get("posted_by") != user_id:
        return RedirectResponse("/jobs", status_code=302)
        
    db.delete_job(job_id)
    return RedirectResponse("/jobs", status_code=302)
