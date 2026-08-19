# routers/context_helper.py
# Función compartida para inyectar chattable_users en cualquier template
import database as db

def chat_context(user_id: str) -> dict:
    """Retorna user y chattable_users para pasar al template.
    Usa get_active_user: si la cuenta fue borrada, la sesión deja de ser válida."""
    user = db.get_active_user(user_id) if user_id else None
    chattable_users = []
    if user:
        all_users = db.get_users()
        # str() en ambos lados: evita que un usuario no aparezca listado (o se
        # filtre a sí mismo) si algún id llega como tipo distinto.
        chattable_users = [u for u in all_users if str(u["id"]) != str(user_id)]
    return {"user": user, "chattable_users": chattable_users}
