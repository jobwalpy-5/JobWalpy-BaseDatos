"""

Cómo trabaja HTMX aquí:
  • Las páginas completas (GET) se piden normal. Si HTMX pide la misma URL
    (para un filtro), el servidor devuelve solo el FRAGMENTO de la tabla.
  • Cada botón hace un POST; el servidor responde con la FILA ya actualizada
    (o vacío si se borró) y HTMX la cambia en su lugar, sin recargar.
  • Los mensajes emergentes los pide el servidor con el encabezado HX-Trigger.

Seguridad (igual que antes, más una capa):
  • La revisión "¿es admin y qué nivel tiene?" se hace en CADA ruta (_acceso).
  • Los POST exigen el encabezado  HX-Request: true. Un formulario escondido en
    otra página web NO puede añadir encabezados propios, así que esto frena
    ataques CSRF (además de SameSite=Lax en la cookie).

Niveles:  soporte (solo mirar) · moderador (gestionar) · super_admin (borrar).
"""
import json

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, Response

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


# ── Ayudas ────────────────────────────────────────────────────────────────────

def _es_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


def _toast(mensaje: str, tipo: str = "ok") -> dict:
    # ensure_ascii=True: los encabezados HTTP no admiten símbolos como ✓.
    return {"HX-Trigger": json.dumps({"toast": {"mensaje": mensaje, "tipo": tipo}}, ensure_ascii=True)}


def _sin_cambio(mensaje: str) -> Response:
    """Respuesta que NO toca la pantalla, solo muestra un aviso."""
    return Response(status_code=200, headers={**_toast(mensaje, "error"), "HX-Reswap": "none"})


def _acceso(request: Request, minimo: int = 1, accion: bool = False):
    """
    Devuelve (admin, None) si puede pasar, o (None, respuesta_de_rechazo).
    accion=True para los POST: exigen HTMX y el nivel mínimo indicado.
    """
    if accion and not _es_htmx(request):
        return None, Response("Petición no válida.", status_code=400)

    admin_id = sesion_admin.verificar(request.cookies.get(NOMBRE_COOKIE))
    admin = db.get_admin(admin_id) if admin_id else None
    if not admin:
        destino = "/login?next=/admin/dashboard"
        if _es_htmx(request):
            # Una redirección normal se "pintaría" dentro de la tabla; HX-Redirect
            # hace que HTMX cambie de página completa.
            return None, Response(status_code=200, headers={"HX-Redirect": destino})
        return None, RedirectResponse(destino, status_code=302)

    if PODER.get(admin["nivel"], 0) < minimo:
        if accion:
            return None, _sin_cambio("Tu nivel no permite esta acción.")
        return None, RedirectResponse("/admin/dashboard", status_code=303)
    return admin, None


def _pagina(request: Request, completa: str, parcial: str, admin: dict, contexto: dict) -> Response:
    """Si pide HTMX → solo el fragmento; si no → la página completa."""
    nombre = parcial if _es_htmx(request) else completa
    respuesta = templates.TemplateResponse(request=request, name=nombre,
                                           context={"admin": admin, **contexto})
    respuesta.headers["Vary"] = "HX-Request"  # el navegador no mezcla fragmento y página
    return respuesta


def _fila(request: Request, plantilla: str, contexto: dict, admin: dict, mensaje: str) -> Response:
    """Devuelve la fila ya actualizada y un aviso. Si la fila ya no existe, la quita."""
    clave = next(iter(contexto))
    if contexto[clave] is None:
        return HTMLResponse("", headers=_toast("El elemento ya no existe.", "error"))
    respuesta = templates.TemplateResponse(request=request, name=plantilla,
                                           context={"admin": admin, **contexto})
    respuesta.headers.update(_toast(mensaje))
    return respuesta


def _quitar(mensaje: str) -> HTMLResponse:
    """Respuesta vacía: HTMX reemplaza la fila por nada (= la elimina)."""
    return HTMLResponse("", headers=_toast(mensaje))


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
    return _pagina(request, "admin_usuarios.html", "_admin_usuarios_lista.html", admin, {
        "usuarios": db.admin_listar_usuarios(search, rol, verificado),
        "search": search, "rol": rol, "verificado": verificado,
    })


@router.get("/empresas", response_class=HTMLResponse)
async def empresas(request: Request, estado: str = ""):
    admin, rechazo = _acceso(request)
    if rechazo:
        return rechazo
    return _pagina(request, "admin_empresas.html", "_admin_empresas_lista.html", admin, {
        "empresas": db.admin_listar_empleadores(estado), "estado": estado,
    })


@router.get("/empleos", response_class=HTMLResponse)
async def empleos(request: Request, search: str = ""):
    admin, rechazo = _acceso(request)
    if rechazo:
        return rechazo
    return _pagina(request, "admin_empleos.html", "_admin_empleos_lista.html", admin, {
        "empleos": db.admin_listar_empleos(search), "search": search,
    })


# ── ACCIONES SOBRE USUARIOS ───────────────────────────────────────────────────

@router.post("/usuarios/{user_id}/verificar")
async def usuario_verificar(request: Request, user_id: str):
    admin, rechazo = _acceso(request, PODER["moderador"], accion=True)
    if rechazo:
        return rechazo
    db.admin_marcar_correo_verificado(user_id)
    return _fila(request, "_admin_usuario_fila.html", {"u": db.admin_obtener_usuario(user_id)},
                 admin, "Correo marcado como verificado")


@router.post("/usuarios/{user_id}/suspender")
async def usuario_suspender(request: Request, user_id: str):
    admin, rechazo = _acceso(request, PODER["moderador"], accion=True)
    if rechazo:
        return rechazo
    db.admin_alternar_suspension_usuario(user_id)
    return _fila(request, "_admin_usuario_fila.html", {"u": db.admin_obtener_usuario(user_id)},
                 admin, "Estado del usuario actualizado")


@router.post("/usuarios/{user_id}/eliminar")
async def usuario_eliminar(request: Request, user_id: str):
    admin, rechazo = _acceso(request, PODER["super_admin"], accion=True)
    if rechazo:
        return rechazo
    db.admin_borrar_usuario(user_id)
    return _quitar("Usuario eliminado")


# ── ACCIONES SOBRE EMPRESAS ───────────────────────────────────────────────────
# "vista" dice desde dónde se pulsó: en el dashboard la tarjeta desaparece y se
# actualizan los números; en la lista de empresas se repinta la fila.

def _quitar_y_actualizar_numeros(admin: dict, mensaje: str) -> Response:
    numeros = templates.get_template("_admin_stats.html").render(stats=db.admin_estadisticas(), oob=True)
    return HTMLResponse(numeros, headers=_toast(mensaje))


@router.post("/empresas/{user_id}/aprobar")
async def empresa_aprobar(request: Request, user_id: str, vista: str = Form(default="")):
    admin, rechazo = _acceso(request, PODER["moderador"], accion=True)
    if rechazo:
        return rechazo
    db.admin_aprobar_empresa(user_id)
    if vista == "dashboard":
        return _quitar_y_actualizar_numeros(admin, "Empresa aprobada")
    return _fila(request, "_admin_empresa_fila.html", {"e": db.admin_obtener_empleador(user_id)},
                 admin, "Empresa aprobada")


@router.post("/empresas/{user_id}/rechazar")
async def empresa_rechazar(request: Request, user_id: str, vista: str = Form(default="")):
    admin, rechazo = _acceso(request, PODER["moderador"], accion=True)
    if rechazo:
        return rechazo
    db.admin_rechazar_empresa(user_id)
    if vista == "dashboard":
        return _quitar_y_actualizar_numeros(admin, "Empresa rechazada")
    return _fila(request, "_admin_empresa_fila.html", {"e": db.admin_obtener_empleador(user_id)},
                 admin, "Empresa rechazada")


@router.post("/empresas/{user_id}/eliminar")
async def empresa_eliminar(request: Request, user_id: str):
    admin, rechazo = _acceso(request, PODER["super_admin"], accion=True)
    if rechazo:
        return rechazo
    db.admin_borrar_usuario(user_id)
    return _quitar("Empresa eliminada")


# ── ACCIONES SOBRE EMPLEOS ────────────────────────────────────────────────────

@router.post("/empleos/{job_id}/desactivar")
async def empleo_alternar(request: Request, job_id: str):
    admin, rechazo = _acceso(request, PODER["moderador"], accion=True)
    if rechazo:
        return rechazo
    db.admin_alternar_empleo(job_id)
    return _fila(request, "_admin_empleo_fila.html", {"j": db.admin_obtener_empleo(job_id)},
                 admin, "Estado del empleo actualizado")


@router.post("/empleos/{job_id}/eliminar")
async def empleo_eliminar(request: Request, job_id: str):
    admin, rechazo = _acceso(request, PODER["super_admin"], accion=True)
    if rechazo:
        return rechazo
    db.admin_borrar_empleo(job_id)
    return _quitar("Empleo eliminado")


# ── SALIR ─────────────────────────────────────────────────────────────────────

@router.get("/logout")
async def logout():
    response = RedirectResponse("/", status_code=302)
    response.delete_cookie(NOMBRE_COOKIE, path="/")
    return response
