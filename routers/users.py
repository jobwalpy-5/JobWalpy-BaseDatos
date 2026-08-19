from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from typing import Optional
from pathlib import Path
import re

import database as db
from models import BuscadorCreate, EmpleadorCreate, BLOCKED_DOMAINS, validar_password_fuerte
from routers.context_helper import chat_context

router = APIRouter()
templates = Jinja2Templates(directory="templates")

BASE_DIR = Path(__file__).resolve().parent.parent

PASSWORD_RE = re.compile(r'^(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()\-_.,?":{}|<>]).{8,}$')


# ── LOGIN ─────────────────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: str = "/"):
    user_id = request.cookies.get("user_id")
    # Si ya tiene una sesión válida (el usuario existe y sigue activo), directo a la raíz
    if user_id and db.get_active_user(user_id):
        return RedirectResponse("/")
    return templates.TemplateResponse(request=request, name="login.html", context={"next": next})


@router.post("/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...), next: str = Form(default="/")):
    # db.verify_login hashea internamente y compara de forma segura; nunca compara texto plano.
    user = db.verify_login(email, password)
    if not user:
        return templates.TemplateResponse(request=request, name="login.html",
            context={"error": "Correo o contraseña incorrectos", "next": next})

    destino = next if next and next.startswith("/") else "/"
    response = RedirectResponse(destino, status_code=302)
    response.set_cookie(
        key="user_id",
        value=str(user["id"]),
        max_age=2592000,
        httponly=True,
        samesite="lax",
        path="/"
    )
    return response


# ── REGISTER BUSCADOR ─────────────────────────────────────────────────────────

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(request=request, name="register.html", context={})


@router.post("/register")
async def register(
    request: Request,
    name: str = Form(...), email: str = Form(...),
    password: str = Form(...), role: str = Form(...),
    location: str = Form(default=""), bio: str = Form(default="")
):
    if role == "empleador":
        return RedirectResponse("/register/employer", status_code=302)

    # Validar con el mismo modelo que usa el resto de la app (pydantic),
    # así el mensaje de error es siempre el mismo sin importar por dónde entre el dato.
    try:
        BuscadorCreate(name=name, email=email, password=password, location=location, bio=bio)
    except ValidationError as e:
        return templates.TemplateResponse(request=request, name="register.html",
            context={"error": e.errors()[0]["msg"]})

    try:
        user = db.create_buscador({
            "name": name, "email": email, "password": password,
            "location": location, "bio": bio,
        })
    except db.EmailYaRegistradoError:
        return templates.TemplateResponse(request=request, name="register.html",
            context={"error": "Este correo ya está registrado"})

    # Genera el token de verificación de correo. El envío real del email
    # (con un proveedor externo) es el siguiente paso pendiente de conectar;
    # por ahora la cuenta queda creada con verified=False hasta confirmarse.
    db.generar_token_verificacion(user["id"])

    response = RedirectResponse("/profile", status_code=302)
    response.set_cookie(
        key="user_id",
        value=str(user["id"]),
        max_age=2592000,
        httponly=True,
        samesite="lax",
        path="/"
    )
    return response


# ── REGISTER EMPLEADOR ────────────────────────────────────────────────────────

@router.get("/register/employer", response_class=HTMLResponse)
async def register_employer_page(request: Request):
    return templates.TemplateResponse(request=request, name="register_employer.html", context={})


@router.post("/register/employer")
async def register_employer(
    request: Request,
    contact_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    phone: str = Form(...),
    company_name: str = Form(...),
    legal_name: str = Form(...),
    tax_id: str = Form(...),
    address: str = Form(...),
    location: str = Form(...),
    industry: str = Form(...),
    size: str = Form(default=""),
    website: str = Form(default=""),
    document: Optional[UploadFile] = File(default=None)
):
    form_data = {
        "contact_name": contact_name, "email": email, "phone": phone,
        "company_name": company_name, "legal_name": legal_name,
        "tax_id": tax_id, "address": address, "location": location,
        "industry": industry, "size": size, "website": website
    }

    errors = []
    domain = email.split("@")[-1].lower()
    if domain in BLOCKED_DOMAINS:
        errors.append(f"Usa un correo corporativo, no @{domain}.")
    if not PASSWORD_RE.match(password):
        errors.append("La contraseña debe tener mínimo 8 caracteres, una mayúscula, un número y un carácter especial.")
    if not tax_id.strip():
        errors.append("El NIT / RUT / RFC es obligatorio.")

    if errors:
        return templates.TemplateResponse(request=request, name="register_employer.html",
            context={"errors": errors, "form": form_data})

    # Guardar el documento de verificación (Cámara de Comercio) si lo subieron.
    doc_relpath = ""
    if document and document.filename:
        safe_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", document.filename)
        upload_dir = BASE_DIR / "static" / "uploads" / "docs"
        upload_dir.mkdir(parents=True, exist_ok=True)
        clean_tax_id = re.sub(r"[^a-zA-Z0-9]", "", tax_id)
        stored_name = f"{clean_tax_id}_{safe_name}"
        content = await document.read()
        with open(upload_dir / stored_name, "wb") as f:
            f.write(content)
        doc_relpath = f"docs/{stored_name}"

    try:
        user = db.create_empleador({
            "contact_name": contact_name, "email": email, "password": password, "phone": phone,
            "company_name": company_name, "legal_name": legal_name, "tax_id": tax_id.strip(),
            "address": address, "location": location, "industry": industry, "size": size,
            "website": website, "document": doc_relpath,
        })
    except db.EmailYaRegistradoError:
        errors.append("Este correo ya está registrado.")
    except db.TaxIdYaRegistradoError:
        errors.append("Ese NIT/RUT/RFC ya está asociado a otra cuenta empresarial.")

    if errors:
        return templates.TemplateResponse(request=request, name="register_employer.html",
            context={"errors": errors, "form": form_data})

    db.generar_token_verificacion(user["id"])

    response = RedirectResponse("/profile", status_code=302)
    response.set_cookie(
        key="user_id",
        value=str(user["id"]),
        max_age=2592000,
        httponly=True,
        samesite="lax",
        path="/"
    )
    return response


# ── LOGOUT ────────────────────────────────────────────────────────────────────

@router.get("/logout")
async def logout():
    response = RedirectResponse("/", status_code=302)
    response.delete_cookie("user_id", path="/")
    return response


# ── VERIFICAR EMAIL ────────────────────────────────────────────────────────────

@router.get("/verificar")
async def verify_email(request: Request, token: str = ""):
    ok = db.confirmar_email(token) if token else False
    destino = "/profile?success=correo_verificado" if ok else "/profile?error=token_invalido"
    return RedirectResponse(destino, status_code=302)


# ── PROFILE ───────────────────────────────────────────────────────────────────

@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse("/login")

    ctx = chat_context(user_id)
    if not ctx["user"]:
        return RedirectResponse("/login")

    user = ctx["user"]
    applications = db.get_applications_by_user(user_id) if user.get("role") == "buscador" else []
    apps_with_jobs = []
    for app in applications:
        job = db.get_job(app["job_id"])
        if job:
            apps_with_jobs.append({**app, "job": job})

    posted_jobs = [j for j in db.get_jobs() if str(j.get("posted_by")) == str(user_id)]
    return templates.TemplateResponse(request=request, name="profile.html", context={
        **ctx, "applications": apps_with_jobs, "posted_jobs": posted_jobs
    })


@router.post("/profile/update")
async def update_profile(
    request: Request,
    name: str = Form(...), bio: str = Form(default=""),
    location: str = Form(default=""), skills: str = Form(default=""),
    experience: str = Form(default=""), education: str = Form(default="")
):
    user_id = request.cookies.get("user_id")
    if not user_id or not db.get_active_user(user_id):
        return RedirectResponse("/login")

    db.update_user(user_id, {
        "name": name, "bio": bio, "location": location,
        "skills": [s.strip() for s in skills.split(",") if s.strip()],
        "experience": experience, "education": education
    })
    return RedirectResponse("/profile?updated=1", status_code=302)


@router.post("/profile/delete")
async def delete_account(request: Request):
    user_id = request.cookies.get("user_id")
    if user_id:
        db.delete_user(user_id)
    response = RedirectResponse("/", status_code=302)
    response.delete_cookie("user_id", path="/")
    return response
