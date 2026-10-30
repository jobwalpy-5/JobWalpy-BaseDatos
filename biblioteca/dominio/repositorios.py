"""
Reglas de este archivo:
  — Solo habla con la base de datos: SELECT / INSERT / UPDATE / DELETE.
  ...
    no tienen que cambiar.
"""
import json

import psycopg

from dominio.errores import (
    EmailYaRegistradoError,
    TaxIdYaRegistradoError,
    YaAplicasteError,
    DocumentoYaRegistradoError,
)
from nucleo.conexion import get_conn


#══════════════════════════════════════════════════════════════════════════════
# USUARIOS
#══════════════════════════════════════════════════════════════════════════════

def _fila_a_usuario(conn, row: dict) -> dict:
    base = {
        "id": row["id"],
        "email": row["email"],
        "role": row["rol"],
        "verified": bool(row["verificado"]),
        "active": bool(row["activo"]),
        "created_at": row["fecha_registro"],
    }

    if row["rol"] == "admin":
        base.update({"name": "Administrador", "phone": "", "location": "", "bio": "",
                     "avatar": "AD", "avatar_color": "#4f46e5", "verified_company": False})
        return base

    if row["rol"] == "buscador":
        p = conn.execute(
            "SELECT * FROM perfiles_buscador WHERE usuario_id = %s", (row["id"],)
        ).fetchone()
        base.update({
            "name": p["nombre"], "phone": p["telefono"], "location": p["ubicacion"],
            "bio": p["bio"], "skills": json.loads(p["skills"] or "[]"),
            "experience": p["experiencia"], "education": p["educacion"],
            "cv_url": p["cv_url"], "avatar": p["avatar"], "avatar_color": p["avatar_color"], "profile_photo_url": p["profile_photo_url"],
            "presentation_video_url": p["presentation_video_url"],
            "verified_company": False,
        })
    else:
        p = conn.execute(
            "SELECT * FROM perfiles_empleador WHERE usuario_id = %s", (row["id"],)
        ).fetchone()
        base.update({
            "name": p["company_name"], "contact_name": p["contact_name"], "phone": p["telefono"],
            "company_name": p["company_name"], "legal_name": p["legal_name"], "tax_id": p["tax_id"],
            "website": p["website"], "address": p["address"], "industry": p["industry"],
            "size": p["size"], "location": p["ubicacion"], "bio": p["bio"],
            "document": p["documento_path"],
            "avatar": p["avatar"], "avatar_color": p["avatar_color"],
            "verified_company": bool(p["verificado_legal"]),
        })
    return base


def contar_buscadores_activos() -> int:
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM usuarios WHERE activo = TRUE AND rol = 'buscador'").fetchone()["n"]


def contar_usuarios_activos() -> int:
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM usuarios WHERE activo = TRUE").fetchone()["n"]


def existe_email(email: str) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT 1 FROM usuarios WHERE email = %s", (email,)).fetchone()
    return row is not None


def existe_documento(document_type: str, document_number: str) -> bool:
    """Compara documentos normalizados; el índice UNIQUE es la defensa final."""
    with get_conn() as conn:
        row = conn.execute(
            """SELECT 1 FROM perfiles_buscador
               WHERE upper(tipo_documento) = upper(%s)
                 AND upper(regexp_replace(documento_numero, '[ .-]', '', 'g')) = upper(regexp_replace(%s, '[ .-]', '', 'g'))
               LIMIT 1""",
            (document_type.strip().upper(), document_number.strip().upper()),
        ).fetchone()
    return row is not None


def contar_usuarios() -> int:
    """Alias de compatibilidad para llamadas antiguas."""
    return contar_usuarios_activos()


def existe_tax_id(tax_id) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM perfiles_empleador WHERE tax_id = %s", (tax_id,)
        ).fetchone()
    return row is not None


def listar_usuarios_activos() -> list:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM usuarios WHERE activo = TRUE").fetchall()
        return [_fila_a_usuario(conn, r) for r in rows]


def obtener_usuario(user_id: str) -> dict | None:
    """Por id, SIN filtrar por estado activo."""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM usuarios WHERE id = %s", (str(user_id),)).fetchone()
        return _fila_a_usuario(conn, row) if row else None


def obtener_usuario_por_email(email: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM usuarios WHERE email = %s", (email,)).fetchone()
        return _fila_a_usuario(conn, row) if row else None


def obtener_credenciales(email: str) -> dict | None:
    """Solo lo necesario para el login: id, hash de la contraseña y si está activo."""
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, password_hash, activo FROM usuarios WHERE email = %s", (email,)
        ).fetchone()


def insertar_buscador(*, uid, email, password_hash, verificado, fecha_registro,
                      data, avatar, color) -> None:
    with get_conn() as conn:
        try:
            conn.execute(
                "INSERT INTO usuarios (id, email, password_hash, rol, verificado, activo, fecha_registro) "
                "VALUES (%s, %s, %s, 'buscador', %s, TRUE, %s)",
                (uid, email, password_hash, verificado, fecha_registro),
            )
        except psycopg.errors.UniqueViolation:
            # Última línea de defensa contra una condición de carrera: el
            # servicio ya revisó que el email no existiera, pero si dos
            # registros llegan casi al mismo tiempo, solo el UNIQUE de la
            # tabla puede detectarlo con certeza.
            raise EmailYaRegistradoError(f"El correo {email} ya está registrado.")
        try:
            conn.execute(
                "INSERT INTO perfiles_buscador "
                "(usuario_id, nombre, telefono, ubicacion, bio, skills, experiencia, educacion, cv_url, avatar, avatar_color, tipo_documento, documento_numero) "
                "VALUES (%s, %s, %s, %s, %s, '[]', '', '', '', %s, %s, %s, %s)",
                (uid, data["name"], data.get("phone", ""), data.get("location", ""),
                 data.get("bio", ""), avatar, color, data.get("document_type"), data.get("document_number")),
            )
        except psycopg.errors.UniqueViolation as exc:
            if getattr(exc.diag, "constraint_name", "") == "uq_perfiles_buscador_documento":
                raise DocumentoYaRegistradoError("Este documento ya está asociado a una cuenta.") from exc
            raise


def insertar_empleador(*, uid, email, password_hash, verificado, verificado_legal,
                       fecha_registro, data, avatar, color) -> None:
    with get_conn() as conn:
        try:
            conn.execute(
                "INSERT INTO usuarios (id, email, password_hash, rol, verificado, activo, fecha_registro) "
                "VALUES (%s, %s, %s, 'empleador', %s, TRUE, %s)",
                (uid, email, password_hash, verificado, fecha_registro),
            )
        except psycopg.errors.UniqueViolation:
            raise EmailYaRegistradoError(f"El correo {email} ya está registrado.")
        try:
            conn.execute(
                "INSERT INTO perfiles_empleador "
                "(usuario_id, contact_name, telefono, company_name, legal_name, tax_id, website, address, "
                " industry, size, ubicacion, bio, documento_path, verificado_legal, avatar, avatar_color) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, '', %s, %s, %s, %s)",
                (uid, data["contact_name"], data.get("phone", ""), data["company_name"],
                 data.get("legal_name", ""), data.get("tax_id"), data.get("website", ""),
                 data.get("address", ""), data.get("industry", ""), data.get("size", ""),
                 data.get("location", ""), data.get("document", ""), verificado_legal, avatar, color),
            )
        except psycopg.errors.UniqueViolation:
            # Condición de carrera sobre tax_id (NIT/RUT). El rollback del
            # context manager revierte también el INSERT en `usuarios` de
            # arriba, así que no queda una cuenta huérfana.
            raise TaxIdYaRegistradoError(
                f"El NIT/RUT {data['tax_id']} ya está asociado a otra cuenta empresarial."
            )


def guardar_token_verificacion(token: str, user_id: str, creado_at: str, expira_at: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO tokens_verificacion (token, usuario_id, creado_at, expira_at) VALUES (%s, %s, %s, %s)",
            (token, user_id, creado_at, expira_at),
        )


def obtener_token_verificacion(token: str) -> dict | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT usuario_id, expira_at FROM tokens_verificacion WHERE token = %s", (token,)
        ).fetchone()


def marcar_email_verificado(user_id: str, token: str) -> None:
    """Marca el email como verificado y borra el token, en una sola transacción."""
    with get_conn() as conn:
        conn.execute("UPDATE usuarios SET verificado = TRUE WHERE id = %s", (user_id,))
        conn.execute("DELETE FROM tokens_verificacion WHERE token = %s", (token,))


def marcar_empresa_verificada(user_id: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE perfiles_empleador SET verificado_legal = TRUE WHERE usuario_id = %s", (user_id,)
        )
        return cur.rowcount > 0


def actualizar_perfil(user_id: str, rol: str, data: dict) -> None:
    """Traduce los nombres de campo de la app a columnas y hace el UPDATE del perfil."""
    with get_conn() as conn:
        if rol == "buscador":
            campos = {"name": "nombre", "bio": "bio", "location": "ubicacion",
                      "phone": "telefono", "experience": "experiencia",
                      "education": "educacion", "cv_url": "cv_url", "profile_photo_url": "profile_photo_url"}
            sets, valores = [], []
            for k, columna in campos.items():
                if k in data and data[k] is not None:
                    sets.append(f"{columna} = %s")
                    valores.append(data[k])
            if "skills" in data and data["skills"] is not None:
                sets.append("skills = %s")
                valores.append(json.dumps(data["skills"]))
            if sets:
                valores.append(user_id)
                conn.execute(f"UPDATE perfiles_buscador SET {', '.join(sets)} WHERE usuario_id = %s", valores)
        else:
            campos = {"company_name": "company_name", "legal_name": "legal_name",
                      "website": "website", "address": "address", "industry": "industry",
                      "size": "size", "location": "ubicacion", "bio": "bio"}
            sets, valores = [], []
            # El formulario de perfil usa el mismo campo "name" para ambos roles
            # (para un empleador, "name" = nombre comercial de la empresa).
            if "name" in data and data["name"] is not None:
                sets.append("company_name = %s")
                valores.append(data["name"])
            for k, columna in campos.items():
                if k in data and data[k] is not None:
                    sets.append(f"{columna} = %s")
                    valores.append(data[k])
            if sets:
                valores.append(user_id)
                conn.execute(f"UPDATE perfiles_empleador SET {', '.join(sets)} WHERE usuario_id = %s", valores)


def actualizar_password_hash(user_id: str, password_hash: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE usuarios SET password_hash = %s WHERE id = %s", (password_hash, str(user_id))
        )
        return cur.rowcount > 0


def desactivar_usuario(user_id: str) -> bool:
    # Desactiva la cuenta y oculta sus ofertas sin destruir el historial.
    with get_conn() as conn:
        cur = conn.execute("UPDATE usuarios SET activo = FALSE WHERE id = %s", (str(user_id),))
        conn.execute("UPDATE empleos SET activo = FALSE WHERE publicado_por = %s", (str(user_id),))
        return cur.rowcount > 0


#══════════════════════════════════════════════════════════════════════════════
# EMPLEOS
#══════════════════════════════════════════════════════════════════════════════

def _job_row_to_dict(row: dict) -> dict:
    return {
        "id": row["id"], "title": row["titulo"], "company": row["empresa"],
        "location": row["ubicacion"],
        "type": row["tipo"], "category": row["categoria"], "description": row["descripcion"],
        "requirements": json.loads(row["requisitos"] or "[]"),
        "benefits": json.loads(row["beneficios"] or "[]"),
        "posted_by": row["publicado_por"], "posted_at": row["publicado_at"],
        "active": bool(row["activo"]),
    }


def listar_empleos() -> list:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM empleos ORDER BY publicado_at DESC, id DESC").fetchall()
    return [_job_row_to_dict(r) for r in rows]


def obtener_empleo(job_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM empleos WHERE id = %s", (str(job_id),)).fetchone()
    return _job_row_to_dict(row) if row else None


def insertar_empleo(job_id: str, job: dict) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO empleos (id, titulo, empresa, ubicacion, salario_min, salario_max, tipo, "
            "categoria, descripcion, requisitos, beneficios, publicado_por, publicado_at, activo) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (job_id, job["title"], job["company"], job["location"],
             int(job.get("salary_min") or 0), int(job.get("salary_max") or 0),
             job["type"], job["category"], job["description"], json.dumps(job.get("requirements", [])),
             json.dumps(job.get("benefits", [])), job["posted_by"], job["posted_at"],
             job.get("active", True)),
        )


def borrar_empleo(job_id: str) -> bool:
    """Borra de verdad. Por el ON DELETE CASCADE también borra sus aplicaciones."""
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM empleos WHERE id = %s", (str(job_id),))
        return cur.rowcount > 0


#══════════════════════════════════════════════════════════════════════════════
# APLICACIONES
#══════════════════════════════════════════════════════════════════════════════

def _app_row_to_dict(row: dict) -> dict:
    return {
        "id": str(row["id"]), "job_id": row["empleo_id"], "user_id": row["usuario_id"],
        "cover_letter": row["carta_presentacion"], "phone": row["telefono"],
        "experience_years": row["anios_experiencia"], "education_level": row["nivel_educativo"],
        "availability": row["disponibilidad"],
        "status": row["estado"], "applied_at": row["aplicado_at"],
    }


def listar_aplicaciones() -> list:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM aplicaciones ORDER BY id DESC").fetchall()
    return [_app_row_to_dict(r) for r in rows]


def obtener_aplicacion(app_id: str) -> dict | None:
    try:
        aid = int(app_id)
    except (TypeError, ValueError):
        return None
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM aplicaciones WHERE id = %s", (aid,)).fetchone()
    return _app_row_to_dict(row) if row else None


def listar_aplicaciones_de_usuario(user_id: str) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM aplicaciones WHERE usuario_id = %s ORDER BY id DESC", (str(user_id),)
        ).fetchall()
    return [_app_row_to_dict(r) for r in rows]


def listar_aplicaciones_de_empleo(job_id: str) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM aplicaciones WHERE empleo_id = %s ORDER BY id DESC", (str(job_id),)
        ).fetchall()
    return [_app_row_to_dict(r) for r in rows]


def insertar_aplicacion(app: dict) -> dict:
    """
    La tabla tiene UNIQUE (empleo_id, usuario_id): aunque la ruta ya revisa
    duplicados, esta es la última defensa real contra una condición de carrera
    (dos clics casi simultáneos en "Aplicar").
    """
    with get_conn() as conn:
        try:
            row = conn.execute(
                "INSERT INTO aplicaciones (empleo_id, usuario_id, carta_presentacion, telefono, "
                "anios_experiencia, nivel_educativo, disponibilidad, estado, aplicado_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *",
                (app["job_id"], app["user_id"], app.get("cover_letter", ""), app.get("phone", ""),
                 app.get("experience_years", ""), app.get("education_level", ""),
                 app.get("availability", ""),
                 app.get("status", "pendiente"), app.get("applied_at", "")),

            ).fetchone()
        except psycopg.errors.UniqueViolation:
            raise YaAplicasteError("Ya aplicaste a este empleo.")
    return _app_row_to_dict(row)


def actualizar_estado_aplicacion(app_id: str, status: str) -> dict | None:
    try:
        aid = int(app_id)
    except (TypeError, ValueError):
        return None
    with get_conn() as conn:
        row = conn.execute(
            "UPDATE aplicaciones SET estado = %s WHERE id = %s RETURNING *", (status, aid)
        ).fetchone()
    return _app_row_to_dict(row) if row else None


#══════════════════════════════════════════════════════════════════════════════
# CONVERSACIONES Y MENSAJES
#══════════════════════════════════════════════════════════════════════════════

def listar_conversaciones_de_usuario(user_id: str) -> list:
    """Sin los mensajes (por performance). Para eso está obtener_conversacion + listar_mensajes."""
    uid = str(user_id)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM conversaciones WHERE participante_a = %s OR participante_b = %s "
            "ORDER BY (SELECT MAX(m.id) FROM mensajes m WHERE m.conversacion_id = conversaciones.id) "
            "DESC NULLS LAST, created_at DESC",
            (uid, uid),
        ).fetchall()
    return [{
        "id": r["id"],
        "participants": [r["participante_a"], r["participante_b"]],
        "aplicacion_id": r["aplicacion_id"],
        "last_message": r["last_message"],
        "last_at": r["last_at"],
    } for r in rows]


def obtener_conversacion(conv_id: str) -> dict | None:
    """La conversación SIN sus mensajes."""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM conversaciones WHERE id = %s", (conv_id,)).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "participants": [row["participante_a"], row["participante_b"]],
        "aplicacion_id": row["aplicacion_id"],
        "last_message": row["last_message"],
        "last_at": row["last_at"],
    }


def asegurar_conversacion(conv_id: str, a: str, b: str, aplicacion_id, created_at: str) -> None:
    """
    Crea la conversación si no existe. Si ya existía sin aplicacion_id, se
    completa ahora (COALESCE), pero nunca se pisa uno que ya estaba guardado.
    """
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO conversaciones (id, participante_a, participante_b, aplicacion_id, last_message, last_at, created_at) "
            "VALUES (%s, %s, %s, %s, '', '', %s) "
            "ON CONFLICT (id) DO UPDATE SET aplicacion_id = COALESCE(conversaciones.aplicacion_id, EXCLUDED.aplicacion_id)",
            (conv_id, a, b, aplicacion_id, created_at),
        )


def listar_mensajes(conv_id: str) -> list:
    """Filas crudas de la tabla, en orden. El servicio les agrega los datos del remitente."""
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM mensajes WHERE conversacion_id = %s ORDER BY id ASC", (conv_id,)
        ).fetchall()


def listar_mensajes_nuevos(conv_id: str, since_id: int) -> list:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM mensajes WHERE conversacion_id = %s AND id > %s ORDER BY id ASC",
            (conv_id, since_id),
        ).fetchall()


def insertar_mensaje(conv_id: str, sender_id: str, texto: str, hora_display: str, creado_at: str) -> dict:
    """Inserta el mensaje y actualiza el 'último mensaje' de la conversación (una transacción)."""
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO mensajes (conversacion_id, sender_id, texto, hora_display, creado_at) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING *",
            (conv_id, sender_id, texto, hora_display, creado_at),
        ).fetchone()
        conn.execute(
            "UPDATE conversaciones SET last_message = %s, last_at = %s WHERE id = %s",
            (texto, hora_display, conv_id),
        )
    return row


def marcar_mensajes_leidos(conv_id: str, reader_id: str) -> None:
    """Marca como leídos los mensajes que NO mandó reader_id."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE mensajes SET leido = TRUE WHERE conversacion_id = %s AND sender_id != %s AND leido = FALSE",
            (conv_id, str(reader_id)),
        )


def es_participante(conv_id: str, user_id: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM conversaciones WHERE id = %s AND (participante_a = %s OR participante_b = %s)",
            (conv_id, str(user_id), str(user_id)),
        ).fetchone()
    return row is not None


# ── ADMIN ───────────────────────────────────────────────────────────────────
def contar_resumen() -> dict:
    with get_conn() as conn:
        return conn.execute(
            "SELECT (SELECT COUNT(*) FROM usuarios WHERE rol='buscador') AS buscadores, "
            "(SELECT COUNT(*) FROM usuarios WHERE rol='empleador') AS empleadores, "
            "(SELECT COUNT(*) FROM empleos) AS empleos"
        ).fetchone()


def listar_empleadores_admin() -> list:
    with get_conn() as conn:
        return conn.execute(
            "SELECT u.id, u.email, u.activo, p.company_name, p.legal_name, p.tax_id, "
            "p.documento_path, p.verificado_legal "
            "FROM usuarios u JOIN perfiles_empleador p ON p.usuario_id = u.id "
            "ORDER BY p.verificado_legal, u.fecha_registro DESC"
        ).fetchall()


def set_verificado_empleador(user_id: str, valor: bool) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE perfiles_empleador SET verificado_legal = %s WHERE usuario_id = %s",
            (valor, user_id),
        )


def set_activo_usuario(user_id: str, activo: bool) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE usuarios SET activo = %s WHERE id = %s", (activo, user_id))



#══════════════════════════════════════════════════════════════════════════════
# ADMINISTRADORES — solo SQL, ninguna decisión (las decisiones están en servicios.py)
#══════════════════════════════════════════════════════════════════════════════

# ── Cuentas de admin ────────────────────────────────────────────────────────

def buscar_admin_por_correo(correo: str) -> dict | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, nombre, correo, password_hash, nivel, activo "
            "FROM administradores WHERE correo = %s", (correo,)
        ).fetchone()


def buscar_admin_por_id(admin_id: str) -> dict | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, nombre, correo, nivel, activo FROM administradores "
            "WHERE id = %s AND activo = TRUE", (str(admin_id),)
        ).fetchone()


def registrar_acceso_admin(admin_id: str, cuando: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE administradores SET ultimo_acceso = %s WHERE id = %s",
                     (cuando, admin_id))


def insertar_admin(admin_id: str, nombre: str, correo: str, password_hash: str,
                   nivel: str, creado_en: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO administradores (id, nombre, correo, password_hash, nivel, creado_en) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (admin_id, nombre, correo, password_hash, nivel, creado_en),
        )


def existe_usuario_con_correo(correo: str) -> bool:
    with get_conn() as conn:
        return conn.execute("SELECT 1 FROM usuarios WHERE email = %s", (correo,)).fetchone() is not None


# ── Lecturas del panel ──────────────────────────────────────────────────────

def admin_estadisticas() -> dict:
    with get_conn() as conn:
        return conn.execute(
            "SELECT "
            " (SELECT COUNT(*) FROM usuarios) AS total_usuarios, "
            " (SELECT COUNT(*) FROM usuarios u JOIN perfiles_empleador p ON p.usuario_id = u.id "
            "   WHERE u.activo AND p.verificado_legal) AS empresas_activas, "
            " (SELECT COUNT(*) FROM usuarios u JOIN perfiles_empleador p ON p.usuario_id = u.id "
            "   WHERE u.activo AND NOT p.verificado_legal) AS empresas_pendientes, "
            " (SELECT COUNT(*) FROM empleos WHERE activo) AS empleos_activos"
        ).fetchone()


def admin_usuarios_recientes(limite: int = 5) -> list:
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, email AS correo, rol, verificado, activo, fecha_registro "
            "FROM usuarios ORDER BY fecha_registro DESC, id LIMIT %s", (limite,)
        ).fetchall()


def admin_empleos_recientes(limite: int = 5) -> list:
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, titulo, empresa, activo, publicado_at "
            "FROM empleos ORDER BY publicado_at DESC, id LIMIT %s", (limite,)
        ).fetchall()


# Lo que el panel llama "empresa aprobada" es perfiles_empleador.verificado_legal.
# (usuarios.verificado significa otra cosa: que la persona confirmó su CORREO.)
_SELECT_EMPLEADORES = (
    "SELECT u.id, u.email AS correo, u.activo, u.fecha_registro, "
    "       p.verificado_legal AS verificado, p.contact_name, p.company_name, p.legal_name, "
    "       p.tax_id, p.industry, p.ubicacion AS location, p.documento_path, p.usuario_id "
    "FROM usuarios u JOIN perfiles_empleador p ON p.usuario_id = u.id "
    "WHERE u.rol = 'empleador'"
)


def admin_empleadores_pendientes() -> list:
    with get_conn() as conn:
        return conn.execute(
            _SELECT_EMPLEADORES + " AND u.activo AND NOT p.verificado_legal "
            "ORDER BY u.fecha_registro DESC"
        ).fetchall()


def admin_listar_empleadores(estado: str = "") -> list:
    sql = _SELECT_EMPLEADORES
    if estado == "pendiente":
        sql += " AND u.activo AND NOT p.verificado_legal"
    elif estado == "aprobado":
        sql += " AND u.activo AND p.verificado_legal"
    elif estado == "rechazado":
        sql += " AND NOT u.activo"
    sql += " ORDER BY u.fecha_registro DESC"
    with get_conn() as conn:
        return conn.execute(sql).fetchall()


def admin_listar_usuarios(busqueda: str = "", rol: str = "", verificado: str = "") -> list:
    sql = ("SELECT id, email AS correo, rol, verificado, activo, fecha_registro "
           "FROM usuarios WHERE 1=1")
    params: list = []
    if busqueda:
        sql += " AND email ILIKE %s"
        params.append(f"%{busqueda}%")
    if rol:
        sql += " AND rol = %s"
        params.append(rol)
    if verificado == "si":
        sql += " AND verificado = TRUE"
    elif verificado == "no":
        sql += " AND verificado = FALSE"
    sql += " ORDER BY fecha_registro DESC, id"
    with get_conn() as conn:
        return conn.execute(sql, params).fetchall()


def admin_listar_empleos(busqueda: str = "") -> list:
    sql = "SELECT id, titulo, empresa, ubicacion, activo, publicado_at FROM empleos WHERE 1=1"
    params: list = []
    if busqueda:
        sql += " AND (titulo ILIKE %s OR empresa ILIKE %s)"
        params += [f"%{busqueda}%", f"%{busqueda}%"]
    sql += " ORDER BY publicado_at DESC, id"
    with get_conn() as conn:
        return conn.execute(sql, params).fetchall()


def admin_obtener_usuario(user_id: str) -> dict | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, email AS correo, rol, verificado, activo, fecha_registro FROM usuarios WHERE id = %s",
            (str(user_id),),
        ).fetchone()


def admin_obtener_empleador(user_id: str) -> dict | None:
    with get_conn() as conn:
        return conn.execute(
            _SELECT_EMPLEADORES + " AND u.id = %s LIMIT 1", (str(user_id),)
        ).fetchone()


def admin_obtener_empleo(job_id: str) -> dict | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, titulo, empresa, ubicacion, activo, publicado_at FROM empleos WHERE id = %s",
            (str(job_id),),
        ).fetchone()


# ── Acciones del panel (cada una devuelve True si cambió alguna fila) ─────────

def admin_marcar_correo_verificado(user_id: str) -> bool:
    with get_conn() as conn:
        return conn.execute("UPDATE usuarios SET verificado = TRUE WHERE id = %s",
                            (user_id,)).rowcount > 0


def admin_alternar_activo_usuario(user_id: str) -> bool:
    with get_conn() as conn:
        return conn.execute("UPDATE usuarios SET activo = NOT activo WHERE id = %s",
                            (user_id,)).rowcount > 0


def admin_poner_activo_usuario(user_id: str, activo: bool) -> bool:
    with get_conn() as conn:
        return conn.execute("UPDATE usuarios SET activo = %s WHERE id = %s",
                            (activo, user_id)).rowcount > 0


def admin_poner_verificado_legal(user_id: str, valor: bool) -> bool:
    with get_conn() as conn:
        return conn.execute("UPDATE perfiles_empleador SET verificado_legal = %s WHERE usuario_id = %s",
                            (valor, user_id)).rowcount > 0


def admin_borrar_usuario(user_id: str) -> bool:
    # Borrado REAL. Por los ON DELETE CASCADE del esquema también se van su
    # perfil, sus empleos, sus aplicaciones y sus conversaciones.
    with get_conn() as conn:
        return conn.execute("DELETE FROM usuarios WHERE id = %s", (user_id,)).rowcount > 0


def admin_alternar_activo_empleo(job_id: str) -> bool:
    with get_conn() as conn:
        return conn.execute("UPDATE empleos SET activo = NOT activo WHERE id = %s",
                            (job_id,)).rowcount > 0


def admin_borrar_empleo(job_id: str) -> bool:
    # Cierra la oferta sin borrar las postulaciones históricas.
    with get_conn() as conn:
        return conn.execute("UPDATE empleos SET activo = FALSE WHERE id = %s", (job_id,)).rowcount > 0



# ── RESTABLECER CONTRASEÑA ──────────────────────────────────────────────────

def guardar_token_restablecer(token_hash: str, user_id: str, creado_at: str, expira_at: str) -> None:
    with get_conn() as conn:
        # Solo el último enlace pedido es válido: se borran los anteriores de esa persona.
        conn.execute("DELETE FROM tokens_restablecer WHERE usuario_id = %s", (str(user_id),))
        conn.execute(
            "INSERT INTO tokens_restablecer (token_hash, usuario_id, creado_at, expira_at) "
            "VALUES (%s, %s, %s, %s)",
            (token_hash, str(user_id), creado_at, expira_at),
        )


def obtener_token_restablecer(token_hash: str) -> dict | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT usuario_id, expira_at FROM tokens_restablecer WHERE token_hash = %s",
            (token_hash,),
        ).fetchone()


def aplicar_restablecer_password(user_id: str, password_hash: str) -> None:
    """Cambia la contraseña y borra los enlaces de esa persona, en una sola transacción."""
    with get_conn() as conn:
        conn.execute("UPDATE usuarios SET password_hash = %s WHERE id = %s", (password_hash, str(user_id)))
        conn.execute("DELETE FROM tokens_restablecer WHERE usuario_id = %s", (str(user_id),))
# ── RESTABLECER CONTRASEÑA ──────────────────────────────────────────────────

def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def solicitar_restablecer_password(email: str, horas_validez: int = 1) -> str | None:
    """
    Si el correo pertenece a una cuenta activa, crea un enlace de un solo uso y devuelve el token.
    Si no existe, devuelve None (la ruta responde igual en ambos casos para no revelar qué correos existen).
    """
    cred = repo.obtener_credenciales(_normalizar_email(email))
    if not cred or not cred["activo"]:
        return None
    token = new_token()
    ahora = datetime.utcnow()
    expira = ahora + timedelta(hours=horas_validez)
    repo.guardar_token_restablecer(_hash_token(token), cred["id"], ahora.isoformat(), expira.isoformat())
    return token


def token_restablecer_valido(token: str) -> bool:
    fila = repo.obtener_token_restablecer(_hash_token(token))
    return bool(fila) and datetime.fromisoformat(fila["expira_at"]) >= datetime.utcnow()


def restablecer_password(token: str, nueva_password: str) -> bool:
    fila = repo.obtener_token_restablecer(_hash_token(token))
    if not fila or datetime.fromisoformat(fila["expira_at"]) < datetime.utcnow():
        return False
    repo.aplicar_restablecer_password(fila["usuario_id"],hash_password(nueva_password))
    return True
