from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from dominio import servicios as db
from presentacion.plantillas import templates
from presentacion.rutas.context_helper import chat_context

router = APIRouter(prefix="/admin")


def _exigir_admin(request: Request) -> dict:
    """La revisión del rol se hace aquí, en el servidor, en cada ruta."""
    ctx = chat_context(request.cookies.get("user_id"))
    if not db.es_admin(ctx["user"]):
        raise HTTPException(status_code=403, detail="Solo administradores")
    return ctx


@router.get("", response_class=HTMLResponse)
async def panel(request: Request):
    ctx = _exigir_admin(request)
    return templates.TemplateResponse(request=request, name="admin.html", context={
        **ctx,
        "resumen": db.admin_resumen(),
        "empleadores": db.admin_listar_empleadores(),
    })


@router.post("/empleadores/{user_id}/verificar")
async def verificar(request: Request, user_id: str, valor: str = Form(...)):
    _exigir_admin(request)
    db.admin_verificar_empleador(user_id, valor == "1")
    return RedirectResponse("/admin", status_code=303)


@router.post("/usuarios/{user_id}/activo")
async def activo(request: Request, user_id: str, valor: str = Form(...)):
    ctx = _exigir_admin(request)
    if str(ctx["user"]["id"]) != user_id:  # el admin no se puede suspender a sí mismo
        db.admin_cambiar_activo(user_id, valor == "1")
    return RedirectResponse("/admin", status_code=303)