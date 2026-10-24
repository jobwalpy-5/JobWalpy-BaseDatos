"""
CAPA 2 · LÓGICA — servicios.

Aquí viven las REGLAS del negocio: qué se valida antes de guardar, cómo se
arma un avatar, cuándo expira un token, cómo se verifica un login...

Las rutas (presentacion/rutas/) llaman SOLO a este archivo.
Este archivo llama SOLO a repositorios.py para tocar la base de datos.
Regla de oro: aquí no debe aparecer ni un SELECT ni un import de psycopg.

Los nombres de las funciones públicas son los mismos que tenía database.py,
así que en las rutas solo cambia la línea del import.
"""
from datetime import date, datetime, timedelta

from dominio import datos_demo
from dominio import repositorios as repo
from dominio.errores import (  # noqa: F401  (se re-exportan para que las rutas los importen desde aquí)
    EmailYaRegistradoError,
    TaxIdYaRegistradoError,
    YaAplicasteError,
)
from nucleo.seguridad import hash_password, new_id, new_token, verify_password

AVATAR_COLORS = ["#6366f1", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"]


# ══════════════════════════════════════════════════════════════════════════════
# USUARIOS
# ══════════════════════════════════════════════════════════════════════════════

def _avatar_para(nombre: str, indice: int) -> tuple[str, str]:
    iniciales = "".join(p[0] for p in nombre.split()[:2]).upper() or "??"
    color = AVATAR_COLORS[indice % len(AVATAR_COLORS)]
    return iniciales, color


def _normalizar_email(email: str) -> str:
    return email.lower().strip()


def get_users() -> list:
    return repo.listar_usuarios_activos()


def get_user(user_id: str) -> dict | None:
    """
    Devuelve un usuario por id SIN filtrar por estado activo. Úsala para
    mostrar información de OTRA persona (quién publicó un empleo, con quién
    chateas, quién aplicó) donde una cuenta desactivada igual debe poder
    mostrarse en el historial.

    Para saber si la cookie de sesión de QUIEN NAVEGA sigue siendo válida,
    usa get_active_user() en su lugar.
    """
    return repo.obtener_usuario(user_id)


def get_active_user(user_id: str) -> dict | None:
    """Como get_user(), pero devuelve None si la cuenta fue desactivada/borrada."""
    user = get_user(user_id)
    if not user or not user.get("active", False):
        return None
    return user


def get_user_by_email(email: str) -> dict | None:
    return repo.obtener_usuario_por_email(_normalizar_email(email))


def create_buscador(data: dict) -> dict:
    email = _normalizar_email(data["email"])
    if repo.existe_email(email):
        raise EmailYaRegistradoError(f"El correo {data['email']} ya está registrado.")

    avatar, color = _avatar_para(data["name"], repo.contar_usuarios())
    uid = new_id()
    repo.insertar_buscador(
        uid=uid, email=email, password_hash=hash_password(data["password"]),
        verificado=False, fecha_registro=str(date.today()),
        data=data, avatar=avatar, color=color,
    )
    return get_user(uid)


def create_empleador(data: dict) -> dict:
    email = _normalizar_email(data["email"])
    if repo.existe_email(email):
        raise EmailYaRegistradoError(f"El correo {data['email']} ya está registrado.")
    if repo.existe_tax_id(data["tax_id"]):
        raise TaxIdYaRegistradoError(
            f"El NIT/RUT {data['tax_id']} ya está asociado a otra cuenta empresarial."
        )

    avatar, color = _avatar_para(data["company_name"], repo.contar_usuarios())
    uid = new_id()
    repo.insertar_empleador(
        uid=uid, email=email, password_hash=hash_password(data["password"]),
        verificado=False, verificado_legal=False, fecha_registro=str(date.today()),
        data=data, avatar=avatar, color=color,
    )
    return get_user(uid)


def verify_login(email: str, password: str) -> dict | None:
    cred = repo.obtener_credenciales(_normalizar_email(email))
    # Si el email no existe se verifica igual contra un hash falso, para que
    # tarde lo mismo y no se pueda averiguar qué correos están registrados.
    stored_hash = cred["password_hash"] if cred else "x$x"
    ok = verify_password(password, stored_hash)
    if not cred or not ok or not cred["activo"]:
        return None
    return repo.obtener_usuario(cred["id"])


def generar_token_verificacion(user_id: str, horas_validez: int = 48) -> str:
    token = new_token()
    ahora = datetime.utcnow()
    expira = ahora + timedelta(hours=horas_validez)
    repo.guardar_token_verificacion(token, user_id, ahora.isoformat(), expira.isoformat())
    return token


def confirmar_email(token: str) -> bool:
    fila = repo.obtener_token_verificacion(token)
    if not fila:
        return False
    if datetime.fromisoformat(fila["expira_at"]) < datetime.utcnow():
        return False
    repo.marcar_email_verificado(fila["usuario_id"], token)
    return True


def admin_verificar_empresa(user_id: str) -> bool:
    """
    Marca una empresa como legalmente verificada (revisión manual del NIT/RUT
    contra el registro mercantil). Pensado para un futuro panel de admin.
    """
    return repo.marcar_empresa_verificada(user_id)


def update_user(user_id: str, data: dict) -> dict | None:
    user = get_user(user_id)
    if not user:
        return None
    repo.actualizar_perfil(user_id, user["role"], data)
    return get_user(user_id)


def delete_user(user_id: str) -> bool:
    """Borrado suave: se marca la cuenta como inactiva en vez de borrar la fila."""
    return repo.desactivar_usuario(user_id)


# ══════════════════════════════════════════════════════════════════════════════
# EMPLEOS
# ══════════════════════════════════════════════════════════════════════════════

def get_jobs() -> list:
    return repo.listar_empleos()


def get_job(job_id: str) -> dict | None:
    return repo.obtener_empleo(job_id)


def create_job(job: dict) -> dict:
    """
    job: dict con title, company, location, salary_min, salary_max, type,
    category, description, requirements (list), benefits (list), posted_by,
    posted_at, active. El id es un UUID real, igual que con los usuarios.
    """
    job_id = new_id()
    repo.insertar_empleo(job_id, job)
    return get_job(job_id)


def delete_job(job_id: str) -> bool:
    """
    Borra el empleo de verdad (no es borrado suave como en usuarios). Por el
    ON DELETE CASCADE del esquema, también se borran las aplicaciones de ese empleo.
    """
    return repo.borrar_empleo(job_id)


# ══════════════════════════════════════════════════════════════════════════════
# APLICACIONES
# ══════════════════════════════════════════════════════════════════════════════

def get_applications() -> list:
    return repo.listar_aplicaciones()


def get_application(app_id: str) -> dict | None:
    return repo.obtener_aplicacion(app_id)


def get_applications_by_user(user_id: str) -> list:
    return repo.listar_aplicaciones_de_usuario(user_id)


def get_applications_by_job(job_id: str) -> list:
    return repo.listar_aplicaciones_de_empleo(job_id)


def create_application(app: dict) -> dict:
    """
    app: dict con job_id, user_id, cover_letter, phone, experience_years,
    education_level, availability, salary_expectation, status, applied_at.
    Lanza YaAplicasteError si la persona ya había aplicado a ese empleo.
    """
    return repo.insertar_aplicacion(app)


def update_application_status(app_id: str, status: str) -> dict | None:
    return repo.actualizar_estado_aplicacion(app_id, status)


# ══════════════════════════════════════════════════════════════════════════════
# CONVERSACIONES Y MENSAJES
# ══════════════════════════════════════════════════════════════════════════════

def _armar_mensaje(m: dict, remitentes: dict) -> dict:
    """
    Convierte una fila de la tabla `mensajes` en el dict que usa la app.
    El nombre/avatar del remitente se busca en vivo (no se duplica en cada
    mensaje), así que si alguien cambia su nombre, los mensajes viejos se
    muestran con el nombre actualizado. `remitentes` es un caché por llamada
    para no consultar al mismo usuario una vez por cada mensaje.
    """
    sid = m["sender_id"]
    if sid not in remitentes:
        remitentes[sid] = get_user(sid) or {"name": "Usuario", "avatar": "?", "avatar_color": "#6366f1"}
    sender = remitentes[sid]
    return {
        "id": str(m["id"]),
        "sender_id": sid,
        "sender_name": sender.get("name", "Usuario"),
        "sender_avatar": sender.get("avatar", "?"),
        "sender_color": sender.get("avatar_color", "#6366f1"),
        "text": m["texto"],
        "read": bool(m["leido"]),
        "at": m["hora_display"],
    }


def get_conversations_by_user(user_id: str) -> list:
    return repo.listar_conversaciones_de_usuario(user_id)


def get_conversation(conv_id: str) -> dict | None:
    """Una conversación completa, con todos sus mensajes en orden."""
    conv = repo.obtener_conversacion(conv_id)
    if not conv:
        return None
    remitentes: dict = {}
    conv["messages"] = [_armar_mensaje(m, remitentes) for m in repo.listar_mensajes(conv_id)]
    return conv


def get_or_create_conversation(user1_id: str, user2_id: str, aplicacion_id: int | None = None) -> dict:
    """
    Devuelve la conversación entre estos dos usuarios, creándola si es la
    primera vez que se hablan. El id es determinístico (los dos ids ordenados
    y unidos con "__"), así dos personas siempre caen en la MISMA conversación
    sin importar quién la abrió primero.
    """
    a, b = sorted([str(user1_id), str(user2_id)])
    conv_id = f"{a}__{b}"
    repo.asegurar_conversacion(conv_id, a, b, aplicacion_id, datetime.utcnow().isoformat())
    return get_conversation(conv_id)


def add_message_to_conversation(conv_id: str, sender_id: str, text: str) -> dict | None:
    ahora = datetime.utcnow()
    fila = repo.insertar_mensaje(conv_id, sender_id, text, ahora.strftime("%H:%M"), ahora.isoformat())
    return _armar_mensaje(fila, {})


def get_new_messages(conv_id: str, since_id: int) -> list:
    """Mensajes con id mayor a since_id — usado por el polling del chat."""
    remitentes: dict = {}
    return [_armar_mensaje(m, remitentes) for m in repo.listar_mensajes_nuevos(conv_id, since_id)]


def mark_messages_as_read(conv_id: str, reader_id: str) -> None:
    repo.marcar_mensajes_leidos(conv_id, reader_id)


def is_participant(conv_id: str, user_id: str) -> bool:
    """
    ¿Este usuario pertenece a esta conversación? Se usa para que nadie pueda
    leer o escribir en un chat ajeno adivinando su id.
    """
    return repo.es_participante(conv_id, user_id)


# ══════════════════════════════════════════════════════════════════════════════
# CUENTAS DEMO
# ══════════════════════════════════════════════════════════════════════════════

def _sembrar_cuenta(c: dict, rol: str, resultado: dict) -> None:
    clave_hash = hash_password(datos_demo.CLAVE_DEMO)   # hash REAL, hecho por la app

    # Caso 1: la cuenta demo ya existe (p. ej. se insertó a mano con SQL y una
    # clave falsa). No se duplica: solo se le pone la clave bien hecha.
    if repo.obtener_usuario(c["id"]):
        repo.actualizar_password_hash(c["id"], clave_hash)
        resultado["actualizadas"].append(c["email"])
        return

    # Caso 2: el correo ya lo usa OTRA cuenta (real). No se toca.
    if repo.existe_email(c["email"]):
        resultado["omitidas"].append(c["email"])
        return

    # Caso 3: no existe: se crea completa.
    try:
        if rol == "empleador":
            repo.insertar_empleador(
                uid=c["id"], email=c["email"], password_hash=clave_hash,
                verificado=True, verificado_legal=True, fecha_registro=datos_demo.FECHA_DEMO,
                data=c, avatar=c["avatar"], color=c["avatar_color"],
            )
            repo.actualizar_perfil(c["id"], "empleador", {"bio": c["bio"]})
        else:
            repo.insertar_buscador(
                uid=c["id"], email=c["email"], password_hash=clave_hash,
                verificado=True, fecha_registro=datos_demo.FECHA_DEMO,
                data=c, avatar=c["avatar"], color=c["avatar_color"],
            )
            repo.actualizar_perfil(c["id"], "buscador", {
                "skills": c["skills"], "experience": c["experience"], "education": c["education"],
            })
    except (EmailYaRegistradoError, TaxIdYaRegistradoError):
        resultado["omitidas"].append(c["email"])
        return
    resultado["creadas"].append(c["email"])


def sembrar_cuentas_demo() -> dict:
    """
    Garantiza que existan las 3 empresas y los 3 buscadores demo (ver
    datos_demo.py), todos con la clave datos_demo.CLAVE_DEMO. Es idempotente:
    se puede correr las veces que quieras.

    Devuelve {"creadas": [...], "actualizadas": [...], "omitidas": [...]}.
    """
    resultado = {"creadas": [], "actualizadas": [], "omitidas": []}
    for c in datos_demo.EMPLEADORES:
        _sembrar_cuenta(c, "empleador", resultado)
    for c in datos_demo.BUSCADORES:
        _sembrar_cuenta(c, "buscador", resultado)
    return resultado

# ── ADMIN ─────────────────────────────────────────────────────────────────────
def es_admin(user) -> bool:
    return bool(user) and user.get("role") == "admin"


def admin_resumen() -> dict:
    return repo.contar_resumen()


def admin_listar_empleadores() -> list:
    return repo.listar_empleadores_admin()


def admin_verificar_empleador(user_id: str, valor: bool) -> None:
    repo.set_verificado_empleador(user_id, valor)


def admin_cambiar_activo(user_id: str, activo: bool) -> None:
    repo.set_activo_usuario(user_id, activo)

    

# ══════════════════════════════════════════════════════════════════════════════
# ADMINISTRADORES — aquí están las DECISIONES; el SQL vive en repositorios.py
# ══════════════════════════════════════════════════════════════════════════════
NIVELES_ADMIN = ("super_admin", "moderador", "soporte")


def verify_admin_login(correo: str, password: str) -> dict | None:
    """
    Devuelve el admin (sin su hash) si el correo y la clave son correctos y la
    cuenta está activa; si no, None. Usa el MISMO hash seguro que los usuarios
    (nucleo.seguridad), no SHA-256 simple.
    """
    admin = repo.buscar_admin_por_correo(correo.lower().strip())
    # Se verifica SIEMPRE contra algún hash (aunque el correo no exista) para
    # que tardar lo mismo no delate qué correos son de administradores.
    guardado = admin["password_hash"] if admin else "x$x"
    clave_ok = verify_password(password, guardado)
    if not admin or not clave_ok or not admin["activo"]:
        return None
    repo.registrar_acceso_admin(admin["id"], datetime.utcnow().isoformat(timespec="seconds"))
    return {k: v for k, v in admin.items() if k != "password_hash"}


def get_admin(admin_id: str) -> dict | None:
    return repo.buscar_admin_por_id(admin_id)


def crear_admin(nombre: str, correo: str, password: str, nivel: str = "moderador") -> str:
    """Crea una cuenta de administrador. Lanza ValueError con un mensaje claro si algo no cumple."""
    correo = correo.lower().strip()
    if nivel not in NIVELES_ADMIN:
        raise ValueError(f"El nivel debe ser uno de: {', '.join(NIVELES_ADMIN)}.")
    if "@" not in correo:
        raise ValueError("El correo no parece válido.")
    if repo.existe_usuario_con_correo(correo):
        raise ValueError("Ese correo ya lo usa una cuenta normal. Usa otro correo para el administrador.")
    if repo.buscar_admin_por_correo(correo):
        raise ValueError("Ya existe un administrador con ese correo.")
    if len(password) < 10:
        raise ValueError("La contraseña del administrador debe tener al menos 10 caracteres.")
    admin_id = new_id()
    repo.insertar_admin(admin_id, nombre.strip(), correo, hash_password(password),
                        nivel, datetime.utcnow().isoformat(timespec="seconds"))
    return admin_id


def admin_estadisticas() -> dict:
    return repo.admin_estadisticas()


def admin_usuarios_recientes(limite: int = 5) -> list:
    return repo.admin_usuarios_recientes(limite)


def admin_empleos_recientes(limite: int = 5) -> list:
    return repo.admin_empleos_recientes(limite)


def admin_empleadores_pendientes() -> list:
    return repo.admin_empleadores_pendientes()


def admin_listar_empleadores(estado: str = "") -> list:
    return repo.admin_listar_empleadores(estado)


def admin_listar_usuarios(busqueda: str = "", rol: str = "", verificado: str = "") -> list:
    return repo.admin_listar_usuarios(busqueda.strip(), rol, verificado)


def admin_listar_empleos(busqueda: str = "") -> list:
    return repo.admin_listar_empleos(busqueda.strip())


def admin_marcar_correo_verificado(user_id: str) -> bool:
    return repo.admin_marcar_correo_verificado(user_id)


def admin_alternar_suspension_usuario(user_id: str) -> bool:
    return repo.admin_alternar_activo_usuario(user_id)


def admin_borrar_usuario(user_id: str) -> bool:
    return repo.admin_borrar_usuario(user_id)


def admin_aprobar_empresa(user_id: str) -> bool:
    """Aprobar = la empresa queda verificada legalmente Y su cuenta activa."""
    ok = repo.admin_poner_verificado_legal(user_id, True)
    if ok:
        repo.admin_poner_activo_usuario(user_id, True)
    return ok


def admin_rechazar_empresa(user_id: str) -> bool:
    """Rechazar = se quita la verificación y se desactiva la cuenta."""
    ok = repo.admin_poner_verificado_legal(user_id, False)
    if ok:
        repo.admin_poner_activo_usuario(user_id, False)
    return ok


def admin_alternar_empleo(job_id: str) -> bool:
    return repo.admin_alternar_activo_empleo(job_id)


def admin_borrar_empleo(job_id: str) -> bool:
    return repo.admin_borrar_empleo(job_id)
