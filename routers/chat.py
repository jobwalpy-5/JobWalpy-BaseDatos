from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import database as db

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def _enrich_conversations(user_id: str) -> list:
    """Une cada conversación con los datos de la OTRA persona (nombre, avatar...)."""
    enriched = []
    for conv in db.get_conversations_by_user(user_id):
        other_id = next(p for p in conv["participants"] if str(p) != str(user_id))
        other_user = db.get_user(other_id)
        if other_user:
            enriched.append({**conv, "other_user": other_user})
    return enriched


# ── PÁGINA PRINCIPAL CHAT ─────────────────────────────────────────────────────
@router.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse("/login")

    user = db.get_active_user(user_id)
    if not user:
        return RedirectResponse("/login")

    all_users = db.get_users()
    chattable = [u for u in all_users if str(u["id"]) != str(user_id)]

    return templates.TemplateResponse(
        request=request, name="chat.html",
        context={
            "user": user,
            "conversations": _enrich_conversations(user_id),
            "chattable_users": chattable,
            "active_conv": None,
            "other_user": None
        }
    )


# ── ABRIR CONVERSACIÓN ────────────────────────────────────────────────────────
@router.get("/chat/{other_id}", response_class=HTMLResponse)
async def chat_with(request: Request, other_id: str, aplicacion_id: int | None = None):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse("/login")

    user = db.get_active_user(user_id)
    other_user = db.get_user(other_id)
    if not user or not other_user:
        return RedirectResponse("/chat")

    if str(other_id) == str(user_id):
        # No tiene sentido chatear contigo mismo — evita crear una conversación rara.
        return RedirectResponse("/chat")

    conv = db.get_or_create_conversation(user_id, other_id, aplicacion_id=aplicacion_id)
    # Al abrir la conversación, se marcan como leídos los mensajes que la
    # OTRA persona te mandó — igual que el "visto" de cualquier chat real.
    db.mark_messages_as_read(conv["id"], user_id)
    conv = db.get_conversation(conv["id"])  # releer para reflejar el estado "leído" ya actualizado

    all_users = db.get_users()
    chattable = [u for u in all_users if str(u["id"]) != str(user_id)]

    return templates.TemplateResponse(
        request=request, name="chat.html",
        context={
            "user": user,
            "conversations": _enrich_conversations(user_id),
            "chattable_users": chattable,
            "active_conv": conv,
            "other_user": other_user
        }
    )


# ── API: ENVIAR MENSAJE ───────────────────────────────────────────────────────
@router.post("/api/chat/{conv_id}/send")
async def send_message(request: Request, conv_id: str):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return JSONResponse({"error": "No autenticado"}, status_code=401)

    sender = db.get_active_user(user_id)
    if not sender:
        return JSONResponse({"error": "Usuario no encontrado"}, status_code=404)

    # Antes no existía esta verificación: cualquiera podía mandar mensajes a
    # CUALQUIER conversación con solo adivinar su id. Ahora se exige ser
    # participante real de esa conversación.
    if not db.is_participant(conv_id, user_id):
        return JSONResponse({"error": "No tienes acceso a esta conversación"}, status_code=403)

    body = await request.json()
    text = (body.get("text") or "").strip()
    if not text:
        return JSONResponse({"error": "Mensaje vacío"}, status_code=400)
    if len(text) > 2000:
        return JSONResponse({"error": "El mensaje es demasiado largo (máximo 2000 caracteres)"}, status_code=400)

    message = db.add_message_to_conversation(conv_id, user_id, text)
    return JSONResponse({"ok": True, "message": message})


# ── API: POLLING — obtener mensajes nuevos ────────────────────────────────────
@router.get("/api/chat/{conv_id}/messages")
async def get_messages(request: Request, conv_id: str, since: str = "0"):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return JSONResponse({"error": "No autenticado"}, status_code=401)

    if not db.is_participant(conv_id, user_id):
        return JSONResponse({"messages": []})

    try:
        since_id = int(since)
    except ValueError:
        since_id = 0

    new_msgs = db.get_new_messages(conv_id, since_id)
    return JSONResponse({"messages": new_msgs})
