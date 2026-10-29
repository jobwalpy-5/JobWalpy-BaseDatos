from fastapi import APIRouter, Request, Form, UploadFile, File, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from typing import Optional
from pathlib import Path
import os
import re

from dominio import servicios as db
from presentacion.plantillas import templates, DIR_STATIC
# ← CAMBIO: ya no hacen falta BLOCKED_DOMAINS ni validar_password_fuerte aquí
from dominio.esquemas import BuscadorCreate, EmpleadorCreate, validar_password_fuerte
from presentacion.rutas.context_helper import chat_context
from presentacion.rutas.admin import iniciar_sesion_admin
from nucleo.sesion_usuario import iniciar_sesion
from nucleo.correo import enviar_correo   # ← NUEVO

router = APIRouter()

# ← CAMBIO: se eliminó PASSWORD_RE (ahora valida EmpleadorCreate)

# ← NUEVO: formato mínimo de correo (mismo criterio que el formulario HTML)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


# ── LOGIN ─────────────────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: str = "/", reset: str = ""):   # ← NUEVO: parámetro "reset"
    user_id = request.cookies.get("user_id")
    # Si ya tiene una sesión válida (el usuario existe y sigue activo), directo a la raíz
    if user_id and db.get_active_user(user_id):
        return RedirectResponse("/")
    # ← NUEVO: mensaje verde cuando vienen de restablecer la contraseña
    success = "Contraseña actualizada. Ya puedes iniciar sesión." if reset == "ok" else ""
    return templates.TemplateResponse(request=request, name="login.html",
                                      context={"next": next, "success": success})


# ← CAMBIO: "def" en vez de "async def" (el hash de la contraseña es pesado y así no congela el servidor)
@router.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...), next: str = Form(default="/")):

    # ← NUEVO: el servidor también exige que sea un correo (no solo el navegador)
    email = email.strip()
    if len(email) > 254 or not EMAIL_RE.match(email):
        return templates.TemplateResponse(request=request, name="login.html",
            context={"error": "Escribe un correo válido (nombre@dominio.com).", "next": next})

    # 1) ¿Es un administrador? (tabla aparte; se revisa primero)
    admin = db.verify_admin_login(email, password)
    if admin:
        response = RedirectResponse("/admin/dashboard", status_code=302)
        iniciar_sesion_admin(response, admin["id"])
        return response

    # 2) Si no, es un usuario normal.
    # db.verify_login hashea internamente y compara de forma segura; nunca compara texto plano.
    user = db.verify_login(email, password)
    if not user:
        return templates.TemplateResponse(request=request, name="login.html",
            context={"error": "Correo o contraseña incorrectos", "next": next})

    # ← CAMBIO: evita redirecciones a otros sitios ("//sitio-malo.com" o "/\")
    destino = next if (next.startswith("/") and not next.startswith("//") and "\\" not in next) else "/"
    response = RedirectResponse(destino, status_code=302)
    # ← CAMBIO: cookie FIRMADA (en vez de guardar el id en texto plano)
    iniciar_sesion(response, user["id"])
    return response


# ── REGISTER BUSCADOR ─────────────────────────────────────────────────────────

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(request=request, name="register.html", context={})


@router.post("/register")
def register(   # ← CAMBIO: "def" (por el mismo motivo del hash)
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
    # ← CAMBIO: cookie firmada
    iniciar_sesion(response, user["id"])
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

    # ← CAMBIO: se valida con EmpleadorCreate (correo corporativo, contraseña fuerte, NIT obligatorio)
    errors = []
    try:
        EmpleadorCreate(**form_data, password=password)
    except ValidationError as e:
        errors = [err["msg"].replace("Value error, ", "") for err in e.errors()]

    if errors:
        return templates.TemplateResponse(request=request, name="register_employer.html",
            context={"errors": errors, "form": form_data})

    # Guardar el documento de verificación (Cámara de Comercio) si lo subieron.
    doc_relpath = ""
    if document and document.filename:
        content = await document.read()
        # ← CAMBIO: solo PDF/JPG/PNG y máximo 5 MB
        ext = Path(document.filename).suffix.lower()
        if ext not in {".pdf", ".jpg", ".jpeg", ".png"} or len(content) > 5 * 1024 * 1024:
            return templates.TemplateResponse(request=request, name="register_employer.html",
                context={"errors": ["El documento debe ser PDF, JPG o PNG de máximo 5 MB."],
                         "form": form_data})

        safe_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", document.filename)
        upload_dir = DIR_STATIC / "uploads" / "docs"
        upload_dir.mkdir(parents=True, exist_ok=True)
        clean_tax_id = re.sub(r"[^a-zA-Z0-9]", "", tax_id)
        stored_name = f"{clean_tax_id}_{safe_name}"
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
    # ← CAMBIO: cookie firmada
    iniciar_sesion(response, user["id"])
    return response


# ── OLVIDÉ MI CONTRASEÑA (HTMX) ───────────────────────────────────────────────

def _recuperar(request: Request, **contexto):
    """HTMX pide solo el fragmento (el panel); una visita normal recibe la página completa."""
    nombre = "_recuperar_panel.html" if request.headers.get("HX-Request") else "recuperar.html"
    resp = templates.TemplateResponse(request=request, name=nombre, context=contexto)
    resp.headers["Vary"] = "HX-Request"   # la misma URL puede devolver dos cosas: que no se mezclen en caché
    return resp


@router.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page(request: Request):
    return _recuperar(request, modo="solicitar")


@router.post("/forgot-password", response_class=HTMLResponse)
def forgot_password(request: Request, email: str = Form(...)):
    email = email.strip()
    if len(email) > 254 or not EMAIL_RE.match(email):
        return _recuperar(request, modo="solicitar", error="Escribe un correo válido.")

    token = db.solicitar_restablecer_password(email)
    if token:
        # APP_URL (ej. https://tu-sitio.com) evita que un atacante falsifique el enlace del correo.
        base = os.environ.get("APP_URL", "").rstrip("/") or str(request.base_url).rstrip("/")
        enlace = f"{base}/reset-password?token={token}"
        try:
            enviar_correo(
                email,
                "Restablece tu contraseña — JobWalpy",
                "Hola,\n\nRecibimos una solicitud para restablecer tu contraseña en JobWalpy.\n"
                f"Abre este enlace (vale 1 hora y solo se puede usar una vez):\n\n{enlace}\n\n"
                "Si no fuiste tú, ignora este mensaje: tu contraseña no cambia.",
            )
        except Exception as e:
            print(f"[CORREO] No se pudo enviar el correo de restablecimiento: {e}")

    # Misma respuesta exista o no el correo (así no se puede averiguar quién está registrado).
    return _recuperar(request, modo="enviado")


@router.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(request: Request, token: str = ""):
    if not token or not db.token_restablecer_valido(token):
        return _recuperar(request, modo="invalido")
    return _recuperar(request, modo="nueva", token=token)


@router.post("/reset-password", response_class=HTMLResponse)
def reset_password(request: Request, token: str = Form(...),
                   password: str = Form(...), password2: str = Form(...)):
    if password != password2:
        return _recuperar(request, modo="nueva", token=token, error="Las contraseñas no coinciden.")
    try:
        validar_password_fuerte(password)
    except ValueError as e:
        return _recuperar(request, modo="nueva", token=token, error=str(e))

    if not db.restablecer_password(token, password):
        return _recuperar(request, modo="invalido")

    # Con HTMX una redirección 302 metería la página de login DENTRO del panel;
    # HX-Redirect le dice a HTMX que navegue de verdad a /login.
    if request.headers.get("HX-Request"):
        return Response(status_code=200, headers={"HX-Redirect": "/login?reset=ok"})
    return RedirectResponse("/login?reset=ok", status_code=302)


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
        **ctx, "applications": apps_with_jobs, "posted_jobs": posted_jobs,
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
