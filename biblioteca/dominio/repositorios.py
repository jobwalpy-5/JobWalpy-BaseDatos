"""
CAPA 2 · LÓGICA — repositorio.

Este es el ÚNICO archivo del proyecto que contiene SQL.

OJO: este archivo NO crea tablas. Las tablas ya existen en Neon; cómo deben
verse está documentado en BD/esquema.sql.

Reglas de este archivo:
  • Solo habla con la base de datos: SELECT / INSERT / UPDATE / DELETE.
  • No decide nada del negocio (no hashea contraseñas, no revisa si un token
    expiró, no inventa ids). Eso vive en servicios.py, que le pasa todo ya
    resuelto.
  • Devuelve diccionarios con las mismas llaves que la app ya usaba
    ("name", "role", "job_id"...), así que los routers y las plantillas
    no tienen que cambiar.
"""
import json

import psycopg

from dominio.errores import (
    EmailYaRegistradoError,
    TaxIdYaRegistradoError,
    YaAplicasteError,
)
from nucleo.conexion import get_conn


# ══════════════════════════════════════════════════════════════════════════════
# USUARIOS
# ══════════════════════════════════════════════════════════════════════════════

def _fila_a_usuario(conn, row: dict) -> dict:
    base = {
        "id": row["id"],
        "email": row["email"],
        "role": row["rol"],
        "verified": bool(row["verificado"]),
        "active": bool(row["activo"]),
        "created_at": row["fecha_registro"],
    }
    if row["rol"] == "buscador":
        p = conn.execute(
            "SELECT * FROM perfiles_buscador WHERE usuario_id = %s", (row["id"],)
        ).fetchone()
        base.update({
            "name": p["nombre"], "phone": p["telefono"], "location": p["ubicacion"],
            "bio": p["bio"], "skills": json.loads(p["skills"] or "[]"),
            "experience": p["experiencia"], "education": p["educacion"],
            "cv_url": p["cv_url"], "avatar": p["avatar"], "avatar_color": p["avatar_color"],
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


def contar_usuarios() -> int:
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM usuarios").fetchone()["n"]


def existe_email(email: str) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT 1 FROM usuarios WHERE email = %s", (email,)).fetchone()
    return row is not None


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
        conn.execute(
            "INSERT INTO perfiles_buscador "
            "(usuario_id, nombre, telefono, ubicacion, bio, skills, experiencia, educacion, cv_url, avatar, avatar_color) "
            "VALUES (%s, %s, %s, %s, %s, '[]', '', '', '', %s, %s)",
            (uid, data["name"], data.get("phone", ""), data.get("location", ""),
             data.get("bio", ""), avatar, color),
        )


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
                      "education": "educacion", "cv_url": "cv_url"}
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
    with get_conn() as conn:
        cur = conn.execute("UPDATE usuarios SET activo = FALSE WHERE id = %s", (str(user_id),))
        return cur.rowcount > 0


# ══════════════════════════════════════════════════════════════════════════════
# EMPLEOS
# ══════════════════════════════════════════════════════════════════════════════

def _job_row_to_dict(row: dict) -> dict:
    return {
        "id": row["id"], "title": row["titulo"], "company": row["empresa"],
        "location": row["ubicacion"], "salary_min": row["salario_min"], "salary_max": row["salario_max"],
        "type": row["tipo"], "category": row["categoria"], "description": row["descripcion"],
        "requirements": json.loads(row["requisitos"] or "[]"),
        "benefits": json.loads(row["beneficios"] or "[]"),
        "posted_by": row["publicado_por"], "posted_at": row["publicado_at"],
        "active": bool(row["activo"]),
    }


def listar_empleos() -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM empleos ORDER BY publicado_at DESC, id DESC"
        ).fetchall()

        if rows:
            print("TIPO DE REGISTRO:", type(rows[0]))
            print("COLUMNAS DISPONIBLES:", rows[0].keys() if hasattr(rows[0], "keys") else "El registro no tiene keys()")
            print("PRIMER REGISTRO:", rows[0])

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
            (job_id, job["title"], job["company"], job["location"], job["salary_min"], job["salary_max"],
             job["type"], job["category"], job["description"], json.dumps(job.get("requirements", [])),
             json.dumps(job.get("benefits", [])), job["posted_by"], job["posted_at"],
             job.get("active", True)),
        )


def borrar_empleo(job_id: str) -> bool:
    """Borra de verdad. Por el ON DELETE CASCADE también borra sus aplicaciones."""
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM empleos WHERE id = %s", (str(job_id),))
        return cur.rowcount > 0


# ══════════════════════════════════════════════════════════════════════════════
# APLICACIONES
# ══════════════════════════════════════════════════════════════════════════════

def _app_row_to_dict(row: dict) -> dict:
    return {
        "id": str(row["id"]), "job_id": row["empleo_id"], "user_id": row["usuario_id"],
        "cover_letter": row["carta_presentacion"], "phone": row["telefono"],
        "experience_years": row["anios_experiencia"], "education_level": row["nivel_educativo"],
        "availability": row["disponibilidad"], "salary_expectation": row["pretension_salarial"],
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
                "anios_experiencia, nivel_educativo, disponibilidad, pretension_salarial, estado, aplicado_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *",
                (app["job_id"], app["user_id"], app.get("cover_letter", ""), app.get("phone", ""),
                 app.get("experience_years", ""), app.get("education_level", ""),
                 app.get("availability", ""), app.get("salary_expectation", ""),
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


# ══════════════════════════════════════════════════════════════════════════════
# CONVERSACIONES Y MENSAJES
# ══════════════════════════════════════════════════════════════════════════════

def listar_conversaciones_de_usuario(user_id: str) -> list:
    """Sin los mensajes (por performance). Para eso está obtener_conversacion + listar_mensajes."""
    uid = str(user_id)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM conversaciones WHERE participante_a = %s OR participante_b = %s "
            "ORDER BY last_at DESC NULLS LAST, created_at DESC",
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

# ── RECUPERACIÓN DE CONTRASEÑA: OPERACIONES DE BASE DE DATOS ─────

def guardar_token_restablecer(
    token_hash: str,
    user_id: str,
    creado_at: str,
    expira_at: str
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO tokens_restablecer
                (token_hash, usuario_id, creado_at, expira_at)
            VALUES (%s, %s, %s, %s)
            """,
            (token_hash, str(user_id), creado_at, expira_at),
        )


def obtener_token_restablecer(token_hash: str) -> dict | None:
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT usuario_id, expira_at
            FROM tokens_restablecer
            WHERE token_hash = %s
            """,
            (token_hash,),
        ).fetchone()


def aplicar_restablecer_password(user_id: str, password_hash: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE usuarios SET password_hash = %s WHERE id = %s",
            (password_hash, str(user_id)),
        )
        conn.execute(
            "DELETE FROM tokens_restablecer WHERE usuario_id = %s",
            (str(user_id),),
        )