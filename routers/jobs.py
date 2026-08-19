from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import date
import database as db
from routers.context_helper import chat_context
 
router = APIRouter()
templates = Jinja2Templates(directory="templates")
 
# ── VER TODOS LOS EMPLEOS ─────────────────────────────────────────────────────
@router.get("/jobs", response_class=HTMLResponse)
async def jobs_page(
    request: Request, 
    search: str = "", 
    category: str = "",
    type: str = "", 
    salary: str = ""
): # 👈 CORREGIDO: Eliminado user_id de los parámetros
    user_id = request.cookies.get("user_id") # 👈 SOLUCIÓN: Lectura segura desde el request
    
    jobs = db.get_jobs()
    if search:
        jobs = [j for j in jobs if search.lower() in j["title"].lower() or search.lower() in j["company"].lower()]
    if category:
        jobs = [j for j in jobs if j["category"] == category]
    if type:
        jobs = [j for j in jobs if j["type"] == type]
    if salary:
        jobs = [j for j in jobs if j["salary_min"] >= int(salary)]
        
    categories = list(set(j["category"] for j in db.get_jobs()))
    ctx = chat_context(user_id)
    
    return templates.TemplateResponse(request=request, name="jobs.html", context={
        **ctx,
        "jobs": jobs, "categories": categories,
        "search": search, "selected_category": category,
        "selected_type": type, "selected_salary": salary,
        "total": len(jobs)
    })
 
# ── DETALLE DE UN EMPLEO ──────────────────────────────────────────────────────
@router.get("/jobs/{job_id}", response_class=HTMLResponse)
async def job_detail(request: Request, job_id: str): # 👈 CORREGIDO
    user_id = request.cookies.get("user_id") # 👈 SOLUCIÓN
    
    job = db.get_job(job_id)
    if not job:
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
    title: str = Form(...), company: str = Form(...),
    location: str = Form(...), salary_min: int = Form(...),
    salary_max: int = Form(...), type: str = Form(...),
    category: str = Form(...), description: str = Form(...),
    requirements: str = Form(...), benefits: str = Form(...)
): # 👈 CORREGIDO
    user_id = request.cookies.get("user_id") # 👈 SOLUCIÓN
    
    ctx = chat_context(user_id)
    if not ctx["user"] or ctx["user"].get("role") != "empleador":
        return RedirectResponse("/login", status_code=302)
        
    job = {
        "title": title, "company": company, "location": location,
        "salary_min": salary_min, "salary_max": salary_max,
        "type": type, "category": category, "description": description,
        "requirements": [r.strip() for r in requirements.split(",")],
        "benefits": [b.strip() for b in benefits.split(",")],
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
    availability: str = Form(...),
    salary_expectation: str = Form(...)
): # 👈 CORREGIDO
    user_id = request.cookies.get("user_id") # 👈 SOLUCIÓN
    
    if not user_id:
        return RedirectResponse("/login", status_code=302)
        
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
        "salary_expectation": salary_expectation,
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