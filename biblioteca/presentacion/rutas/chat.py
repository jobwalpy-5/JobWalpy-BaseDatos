import asyncio
from urllib.parse import urlparse

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from dominio import servicios as db
from presentacion.plantillas import templates

router = APIRouter()


def _enrich_conversations(user_id: str) -> list:
    """Une cada conversación con los datos de la otra persona (nombre, avatar, etc.)."""
    enriched = []
    for conv in db.get_conversations_by_user(user_id):
        other_id = next(p for p in conv["participants"] if str(p) != str(user_id))
        other_user = db.get_user(other_id)
        if other_user:
            enriched.append({**conv, "other_user": other_user})
    return enriched


# Pagina principal del chat: muestra la lista de conversaciones sin ninguna abierta.
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


# Abre la conversación con otra persona. Si no existe, la crea.
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
        # Chatear con uno mismo no tiene sentido, así que se evita crear esa conversación.
        return RedirectResponse("/chat")

    conv = db.get_or_create_conversation(user_id, other_id, aplicacion_id=aplicacion_id)
    # Al abrir la conversación se marcan como leídos los mensajes que la otra
    # persona envió, igual que el "visto" de cualquier aplicación de chat.
    db.mark_messages_as_read(conv["id"], user_id)
    # Se vuelve a leer la conversación para reflejar el estado "leído" ya actualizado.
    conv = db.get_conversation(conv["id"])

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


# API HTTP para enviar un mensaje. La página la usa como respaldo cuando el
# WebSocket no está conectado.
@router.post("/api/chat/{conv_id}/send")
async def send_message(request: Request, conv_id: str):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return JSONResponse({"error": "No autenticado"}, status_code=401)

    sender = db.get_active_user(user_id)
    if not sender:
        return JSONResponse({"error": "Usuario no encontrado"}, status_code=404)

    # Se exige que la persona sea participante real de la conversación. Sin esta
    # verificación, cualquiera podría escribir en una conversación ajena con solo
    # conocer su id.
    if not db.is_participant(conv_id, user_id):
        return JSONResponse({"error": "No tienes acceso a esta conversación"}, status_code=403)

    body = await request.json()
    text = (body.get("text") or "").strip()
    if not text:
        return JSONResponse({"error": "Mensaje vacío"}, status_code=400)
    if len(text) > 2000:
        return JSONResponse({"error": "El mensaje es demasiado largo (máximo 2000 caracteres)"}, status_code=400)

    message = db.add_message_to_conversation(conv_id, user_id, text)
    # Se avisa por WebSocket a las personas conectadas a esta conversación, para
    # que vean el mensaje en vivo aunque haya sido enviado por HTTP.
    await gestor.enviar_a_sala(conv_id, {"type": "message", "message": message})
    return JSONResponse({"ok": True, "message": message})


# API HTTP para obtener los mensajes nuevos de una conversación (consulta periódica).
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


# Chat en tiempo real con WebSocket.

class GestorConexiones:
    """Lleva la cuenta, en memoria, de quién está conectado en cada conversación."""

    def __init__(self):
        self.salas: dict[str, list[tuple[str, WebSocket]]] = {}

    def conectar(self, conv_id: str, user_id: str, ws: WebSocket) -> None:
        self.salas.setdefault(conv_id, []).append((user_id, ws))

    def desconectar(self, conv_id: str, ws: WebSocket) -> None:
        sala = [(u, w) for (u, w) in self.salas.get(conv_id, []) if w is not ws]
        if sala:
            self.salas[conv_id] = sala
        else:
            self.salas.pop(conv_id, None)

    def otros_conectados(self, conv_id: str, user_id: str) -> set[str]:
        return {u for (u, _) in self.salas.get(conv_id, []) if u != user_id}

    async def enviar_a_sala(self, conv_id: str, payload: dict) -> None:
        # Se recorre una copia de la lista porque desconectar modifica la sala original.
        for _, ws in list(self.salas.get(conv_id, [])):
            try:
                await ws.send_json(payload)
            except Exception:
                self.desconectar(conv_id, ws)


gestor = GestorConexiones()


def _origen_valido(ws: WebSocket) -> bool:
    """Rechaza las conexiones que provienen de otra página (protección tipo CSRF)."""
    origin = ws.headers.get("origin")
    if not origin:
        return True
    return urlparse(origin).netloc == ws.headers.get("host")


@router.websocket("/ws/chat/{conv_id}")
async def chat_ws(websocket: WebSocket, conv_id: str):
    user_id = websocket.cookies.get("user_id")
    if not user_id or not _origen_valido(websocket):
        await websocket.close(code=1008)
        return

    # Las funciones de db son síncronas (psycopg). Se ejecutan en un hilo aparte
    # para que no congelen el servidor mientras esperan la respuesta de la base de datos.
    user = await asyncio.to_thread(db.get_active_user, user_id)
    if not user or not await asyncio.to_thread(db.is_participant, conv_id, user_id):
        await websocket.close(code=1008)
        return

    await websocket.accept()
    gestor.conectar(conv_id, user_id, websocket)

    try:
        # Al conectarse, los mensajes que la otra persona envió pasan a estado leído.
        await asyncio.to_thread(db.mark_messages_as_read, conv_id, user_id)
        await gestor.enviar_a_sala(conv_id, {"type": "read", "reader_id": user_id})

        while True:
            try:
                data = await websocket.receive_json()
                tipo = data.get("type")

                # El ping solo mantiene viva la conexión y no requiere respuesta.
                if tipo == "ping":
                    continue

                if tipo == "message":
                    text = (data.get("text") or "").strip()
                    if not text:
                        await websocket.send_json({"type": "error", "error": "Mensaje vacío"})
                        continue
                    if len(text) > 2000:
                        await websocket.send_json({
                            "type": "error",
                            "error": "El mensaje es demasiado largo (máximo 2000 caracteres)",
                        })
                        continue

                    message = await asyncio.to_thread(
                        db.add_message_to_conversation, conv_id, user_id, text
                    )
                    await gestor.enviar_a_sala(conv_id, {"type": "message", "message": message})

                    # Si la otra persona tiene el chat abierto, se asume que ya vio
                    # el mensaje y se marca como leído.
                    for otro in gestor.otros_conectados(conv_id, user_id):
                        await asyncio.to_thread(db.mark_messages_as_read, conv_id, otro)
                        await gestor.enviar_a_sala(conv_id, {"type": "read", "reader_id": otro})
            except WebSocketDisconnect:
                raise
            except Exception:
                # Un mensaje con problemas no debe cerrar la conexión completa.
                await websocket.send_json({"type": "error", "error": "No se pudo procesar el mensaje"})
    except WebSocketDisconnect:
        pass
    finally:
        gestor.desconectar(conv_id, websocket)