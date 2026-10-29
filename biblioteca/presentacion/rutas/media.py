from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi.responses import RedirectResponse

from dominio import servicios as db


router = APIRouter()


def _require_buscador(request: Request):
    """
    Devuelve el usuario logueado si es un buscador activo, o None. La
    propuesta original habla de "candidatos", así que estas 3 funciones
    son exclusivas de ese rol — un empleador no sube foto/video/portafolio
    aquí (su perfil de empresa se edita desde /profile/update, como ya
    existía).
    """
    user_id = request.cookies.get("user_id")
    if not user_id:
        return None
    user = db.get_active_user(user_id)
    if not user or user.get("role") != "buscador":
        return None
    return user


# ── FOTO DE PERFIL (por enlace) ──────────────────────────────
@router.post("/profile/photo")
async def set_profile_photo(request: Request, photo_url: str = Form(...)):
    user = _require_buscador(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    photo_url = photo_url.strip()
    if not photo_url.lower().startswith(("http://", "https://")) or len(photo_url) > 500:
        return RedirectResponse("/profile?error=enlace_invalido", status_code=302)

    db.update_user(user["id"], {"profile_photo_url": photo_url})
    return RedirectResponse("/profile?success=foto_actualizada", status_code=302)

