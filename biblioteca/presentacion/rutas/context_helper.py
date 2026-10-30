# presentacion/rutas/context_helper.py
from dominio import servicios as db


def chat_context(user_id: str) -> dict:
    """Inyecta solo contactos con conversación previa, no el directorio completo."""
    user = db.get_active_user(user_id) if user_id else None
    chattable_users = []
    if user:
        conversations = db.get_conversations_by_user(user_id)
        contact_ids = {
            str(participant)
            for conv in conversations
            for participant in conv.get("participants", [])
            if str(participant) != str(user_id)
        }
        chattable_users = [
            u for u in db.get_users()
            if str(u["id"]) in contact_ids and str(u["id"]) != str(user_id)
        ]
    return {"user": user, "chattable_users": chattable_users}
