"""
Niveles (de menos a más poder):
  soporte      → solo mirar
  moderador    → mirar + aprobar / rechazar / suspender / desactivar
  super_admin  → todo lo anterior + borrar de forma permanente
"""
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from dominio import servicios as db
from nucleo import sesion_admin
from presentacion.plantillas import templates

router = APIRouter(prefix="/admin")

NOMBRE_COOKIE = "admin_sesion"
PODER = {"soporte": 1, "moderador": 2, "super_admin": 3}


def iniciar_sesion_admin(response, admin_id: str) -> None:
    """La usa el login (users.py) para dejar la cookie firmada en la respuesta."""
    response.set_cookie(
        key=NOMBRE_COOKIE, value=sesion_admin.firmar(admin_id),
        max_age=sesion_admin.DURACION_SEGUNDOS,
        httponly=True, samesite="lax", path="/",
    )


def _acceso(request: Request, minimo: int = 1):
    """Devuelve (admin, None) si puede entrar, o (None, respuesta_de_rechazo)."""
    admin_id = sesion_admin.verificar(request.cookies.get(NOMBRE_COOKIE))
    admin = db.get_admin(admin_id) if admin_id else None
    if not admin:
        return None, RedirectResponse("/login?next=/admin/dashboard", status_code=302)
    if PODER.get(admin["nivel"], 0) < minimo:
        return None, RedirectResponse("/admin/dashboard?msg=no_tienes_permiso", status_code=303)
    return admin, None


def _volver(destino: str, mensaje: str) -> RedirectResponse:
    return RedirectResponse(f"{destino}?msg={mensaje}", status_code=303)


# ── PÁGINAS ───────────────────────────────────────────────────────────────────

@router.get("")
async def raiz():
    return RedirectResponse("/admin/dashboard", status_code=302)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    admin, rechazo = _acceso(request)
    if rechazo:
        return rechazo
    return templates.TemplateResponse(request=request, name="admin_dashboard.html", context={
        "admin": admin,
        "stats": db.admin_estadisticas(),
        "empresas_pendientes": db.admin_empleadores_pendientes(),
        "usuarios_recientes": db.admin_usuarios_recientes(5),
        "empleos_recientes": db.admin_empleos_recientes(5),
    })


@router.get("/usuarios", response_class=HTMLResponse)
async def usuarios(request: Request, search: str = "", rol: str = "", verificado: str = ""):
    admin, rechazo = _acceso(request)
    if rechazo:
        return rechazo
    return templates.TemplateResponse(request=request, name="admin_usuarios.html", context={
        "admin": admin, "usuarios": db.admin_listar_usuarios(search, rol, verificado),
        "search": search, "rol": rol, "verificado": verificado,
    })


@router.get("/empresas", response_class=HTMLResponse)
async def empresas(request: Request, estado: str = ""):
    admin, rechazo = _acceso(request)
    if rechazo:
        return rechazo
    return templates.TemplateResponse(request=request, name="admin_empresas.html", context={
        "admin": admin, "empresas": db.admin_listar_empleadores(estado), "estado": estado,
    })


@router.get("/empleos", response_class=HTMLResponse)
async def empleos(request: Request, search: str = ""):
    admin, rechazo = _acceso(request)
    if rechazo:
        return rechazo
    return templates.TemplateResponse(request=request, name="admin_empleos.html", context={
        "admin": admin, "empleos": db.admin_listar_empleos(search), "search": search,
    })


# ── ACCIONES SOBRE USUARIOS ───────────────────────────────────────────────────

@router.post("/usuarios/{user_id}/verificar")
async def usuario_verificar(request: Request, user_id: str):
    admin, rechazo = _acceso(request, PODER["moderador"])
    if rechazo:
        return rechazo
    db.admin_marcar_correo_verificado(user_id)
    return _volver("/admin/usuarios", "correo_marcado_como_verificado")


@router.post("/usuarios/{user_id}/suspender")
async def usuario_suspender(request: Request, user_id: str):
    admin, rechazo = _acceso(request, PODER["moderador"])
    if rechazo:
        return rechazo
    db.admin_alternar_suspension_usuario(user_id)
    return _volver("/admin/usuarios", "estado_del_usuario_actualizado")


@router.post("/usuarios/{user_id}/eliminar")
async def usuario_eliminar(request: Request, user_id: str):
    admin, rechazo = _acceso(request, PODER["super_admin"])
    if rechazo:
        return rechazo
    db.admin_borrar_usuario(user_id)
    return _volver("/admin/usuarios", "usuario_eliminado")


# ── ACCIONES SOBRE EMPRESAS ───────────────────────────────────────────────────

@router.post("/empresas/{user_id}/aprobar")
async def empresa_aprobar(request: Request, user_id: str):
    admin, rechazo = _acceso(request, PODER["moderador"])
    if rechazo:
        return rechazo
    db.admin_aprobar_empresa(user_id)
    return _volver("/admin/empresas", "empresa_aprobada")


@router.post("/empresas/{user_id}/rechazar")
async def empresa_rechazar(request: Request, user_id: str):
    admin, rechazo = _acceso(request, PODER["moderador"])
    if rechazo:
        return rechazo
    db.admin_rechazar_empresa(user_id)
    return _volver("/admin/empresas", "empresa_rechazada")


@router.post("/empresas/{user_id}/eliminar")
async def empresa_eliminar(request: Request, user_id: str):
    admin, rechazo = _acceso(request, PODER["super_admin"])
    if rechazo:
        return rechazo
    db.admin_borrar_usuario(user_id)
    return _volver("/admin/empresas", "empresa_eliminada")


# ── ACCIONES SOBRE EMPLEOS ────────────────────────────────────────────────────

@router.post("/empleos/{job_id}/desactivar")
async def empleo_alternar(request: Request, job_id: str):
    admin, rechazo = _acceso(request, PODER["moderador"])
    if rechazo:
        return rechazo
    db.admin_alternar_empleo(job_id)
    return _volver("/admin/empleos", "estado_del_empleo_actualizado")


@router.post("/empleos/{job_id}/eliminar")
async def empleo_eliminar(request: Request, job_id: str):
    admin, rechazo = _acceso(request, PODER["super_admin"])
    if rechazo:
        return rechazo
    db.admin_borrar_empleo(job_id)
    return _volver("/admin/empleos", "empleo_eliminado")


# ── SALIR ─────────────────────────────────────────────────────────────────────

@router.get("/logout")
async def logout():
    response = RedirectResponse("/", status_code=302)
    response.delete_cookie(NOMBRE_COOKIE, path="/")
    return response
