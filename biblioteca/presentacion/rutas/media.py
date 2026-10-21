from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi.responses import RedirectResponse

from dominio import servicios as db
from nucleo import almacenamiento as storage

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


# ── FOTO DE PERFIL ────────────────────────────────────────────────────────────
@router.post("/profile/photo")
async def upload_profile_photo(request: Request, photo: UploadFile = File(...)):
    user = _require_buscador(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    content = await photo.read()
    try:
        url = storage.upload_profile_photo(user["id"], photo.filename, content)
    except storage.ArchivoInvalidoError as e:
        return RedirectResponse(f"/profile?error={e}", status_code=302)
    except RuntimeError as e:
        # MinIO no está configurado — error claro en vez de un 500 genérico.
        return RedirectResponse(f"/profile?error={e}", status_code=302)

    db.update_user(user["id"], {"profile_photo_url": url})
    return RedirectResponse("/profile?success=foto_actualizada", status_code=302)


# ── VIDEO DE PRESENTACIÓN ──────────────────────────────────────────────────────
@router.post("/profile/video")
async def upload_video_presentation(request: Request, video: UploadFile = File(...)):
    user = _require_buscador(request)
    if not user:
        return RedirectResponse("/login", status_code=302)

    content = await video.read()
    try:
        url = storage.upload_presentation_video(user["id"], video.filename, content)
    except (storage.ArchivoInvalidoError, RuntimeError) as e:
        return RedirectResponse(f"/profile?error={e}", status_code=302)

    db.update_user(user["id"], {"presentation_video_url": url})
    return RedirectResponse("/profile?success=video_actualizado", status_code=302)


# aqui se eliminó la parte del portafolio
