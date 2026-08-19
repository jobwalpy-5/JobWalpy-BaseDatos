
import json
import os
from contextlib import contextmanager
from datetime import date, datetime, timedelta

import psycopg
from psycopg.rows import dict_row

from auth import hash_password, verify_password, new_id, new_token

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "Falta la variable de entorno DATABASE_URL. Copia el 'Pooled connection "
        "string' desde el dashboard de Neon (Connection Details) y configúrala "
        "como variable de entorno (localmente en tu .env, y en Vercel en "
        "Project Settings -> Environment Variables)."
    )

AVATAR_COLORS = ["#6366f1", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"]


# ── CONEXIÓN ──────────────────────────────────────────────────────────────────

class _PGConn:
    """
    Envoltorio delgado sobre una conexión psycopg para poder seguir escribiendo
    conn.execute(sql, params).fetchone() / .fetchall(), igual que con sqlite3,
    y así no tener que reescribir cada función de este archivo.
    """
    __slots__ = ("_conn",)

    def __init__(self, raw_conn):
        self._conn = raw_conn

    def execute(self, sql: str, params=()):
        cur = self._conn.cursor()
        cur.execute(sql, params)
        return cur

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


@contextmanager
def get_conn():
    raw = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    conn = _PGConn(raw)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Crea las tablas si no existen. Idempotente — seguro de correr en cada arranque."""
    ddl_statements = [
        """
        CREATE TABLE IF NOT EXISTS usuarios (
            id              TEXT PRIMARY KEY,
            email           TEXT NOT NULL UNIQUE,
            password_hash   TEXT NOT NULL,
            rol             TEXT NOT NULL CHECK (rol IN ('buscador', 'empleador')),
            verificado      BOOLEAN NOT NULL DEFAULT FALSE,
            activo          BOOLEAN NOT NULL DEFAULT TRUE,
            fecha_registro  TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS perfiles_buscador (
            usuario_id      TEXT PRIMARY KEY REFERENCES usuarios(id) ON DELETE CASCADE,
            nombre          TEXT NOT NULL,
            telefono        TEXT DEFAULT '',
            ubicacion       TEXT DEFAULT '',
            bio             TEXT DEFAULT '',
            skills          TEXT DEFAULT '[]',
            experiencia     TEXT DEFAULT '',
            educacion       TEXT DEFAULT '',
            cv_url          TEXT DEFAULT '',
            avatar          TEXT NOT NULL,
            avatar_color    TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS perfiles_empleador (
            usuario_id       TEXT PRIMARY KEY REFERENCES usuarios(id) ON DELETE CASCADE,
            contact_name     TEXT NOT NULL,
            telefono         TEXT DEFAULT '',
            company_name     TEXT NOT NULL,
            legal_name       TEXT DEFAULT '',
            tax_id           TEXT UNIQUE,
            website          TEXT DEFAULT '',
            address          TEXT DEFAULT '',
            industry         TEXT DEFAULT '',
            size             TEXT DEFAULT '',
            ubicacion        TEXT DEFAULT '',
            bio              TEXT DEFAULT '',
            documento_path   TEXT DEFAULT '',
            verificado_legal BOOLEAN NOT NULL DEFAULT FALSE,
            avatar           TEXT NOT NULL,
            avatar_color     TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS tokens_verificacion (
            token       TEXT PRIMARY KEY,
            usuario_id  TEXT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            creado_at   TEXT NOT NULL,
            expira_at   TEXT NOT NULL
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_usuarios_rol ON usuarios (rol)",
        "CREATE INDEX IF NOT EXISTS idx_perfiles_empleador_taxid ON perfiles_empleador (tax_id)",
        """
        CREATE TABLE IF NOT EXISTS empleos (
            id              TEXT PRIMARY KEY,
            titulo          TEXT NOT NULL,
            empresa         TEXT NOT NULL,
            ubicacion       TEXT NOT NULL,
            salario_min     INTEGER NOT NULL,
            salario_max     INTEGER NOT NULL,
            tipo            TEXT NOT NULL,
            categoria       TEXT NOT NULL,
            descripcion     TEXT NOT NULL,
            requisitos      TEXT DEFAULT '[]',
            beneficios      TEXT DEFAULT '[]',
            publicado_por   TEXT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            publicado_at    TEXT NOT NULL,
            activo          BOOLEAN NOT NULL DEFAULT TRUE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS aplicaciones (
            id                   BIGSERIAL PRIMARY KEY,
            empleo_id            TEXT NOT NULL REFERENCES empleos(id) ON DELETE CASCADE,
            usuario_id           TEXT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            carta_presentacion   TEXT DEFAULT '',
            telefono             TEXT DEFAULT '',
            anios_experiencia    TEXT DEFAULT '',
            nivel_educativo      TEXT DEFAULT '',
            disponibilidad       TEXT DEFAULT '',
            pretension_salarial  TEXT DEFAULT '',
            estado               TEXT NOT NULL DEFAULT 'pendiente',
            aplicado_at          TEXT NOT NULL,
            UNIQUE (empleo_id, usuario_id)
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_empleos_publicado_por ON empleos (publicado_por)",
        "CREATE INDEX IF NOT EXISTS idx_empleos_categoria ON empleos (categoria)",
        "CREATE INDEX IF NOT EXISTS idx_aplicaciones_empleo ON aplicaciones (empleo_id)",
        "CREATE INDEX IF NOT EXISTS idx_aplicaciones_usuario ON aplicaciones (usuario_id)",
        """
        CREATE TABLE IF NOT EXISTS conversaciones (
            id              TEXT PRIMARY KEY,
            participante_a  TEXT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            participante_b  TEXT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            aplicacion_id   BIGINT REFERENCES aplicaciones(id) ON DELETE SET NULL,
            last_message    TEXT DEFAULT '',
            last_at         TEXT DEFAULT '',
            created_at      TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS mensajes (
            id               BIGSERIAL PRIMARY KEY,
            conversacion_id  TEXT NOT NULL REFERENCES conversaciones(id) ON DELETE CASCADE,
            sender_id        TEXT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            texto            TEXT NOT NULL,
            leido            BOOLEAN NOT NULL DEFAULT FALSE,
            hora_display     TEXT NOT NULL,
            creado_at        TEXT NOT NULL
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_conversaciones_a ON conversaciones (participante_a)",
        "CREATE INDEX IF NOT EXISTS idx_conversaciones_b ON conversaciones (participante_b)",
        "CREATE INDEX IF NOT EXISTS idx_conversaciones_aplicacion ON conversaciones (aplicacion_id)",
        "CREATE INDEX IF NOT EXISTS idx_mensajes_conversacion ON mensajes (conversacion_id, id)",

        # ── MIGRACIONES para bases que ya tenían estas tablas creadas SIN
        # estas dos columnas (aplicacion_id, leido). CREATE TABLE IF NOT
        # EXISTS no las agrega a una tabla que ya existe — por eso hace
        # falta este ALTER TABLE aparte. Es idempotente: si la columna ya
        # existe, no hace nada.
        "ALTER TABLE conversaciones ADD COLUMN IF NOT EXISTS aplicacion_id BIGINT REFERENCES aplicaciones(id) ON DELETE SET NULL",
        "ALTER TABLE mensajes ADD COLUMN IF NOT EXISTS leido BOOLEAN NOT NULL DEFAULT FALSE",

        # ── VISTA opcional, inspirada en la propuesta de tu compañero/a
        # (su "ofertas_activas"), adaptada a los nombres de columnas de
        # este proyecto. No la usa ningún router todavía — está disponible
        # para consultarla directo en el SQL Editor de Neon si la necesitas.
        """
        CREATE OR REPLACE VIEW empleos_activos AS
        SELECT
            e.id, e.titulo, e.ubicacion, e.salario_min, e.salario_max,
            e.empresa, e.publicado_at
        FROM empleos e
        WHERE e.activo = TRUE
        """,
    ]
    with get_conn() as conn:
        for stmt in ddl_statements:
            conn.execute(stmt)


def _avatar_for(name: str, index: int) -> tuple[str, str]:
    iniciales = "".join(p[0] for p in name.split()[:2]).upper() or "??"
    color = AVATAR_COLORS[index % len(AVATAR_COLORS)]
    return iniciales, color


def _next_avatar_index(conn) -> int:
    return conn.execute("SELECT COUNT(*) AS n FROM usuarios").fetchone()["n"]


# ── HELPERS INTERNOS DE CREACIÓN ──────────────────────────────────────────────

def _create_buscador_row(data: dict, verificado: bool, avatar_index: int) -> str:
    uid = new_id()
    avatar, color = _avatar_for(data["name"], avatar_index)
    with get_conn() as conn:
        try:
            conn.execute(
                "INSERT INTO usuarios (id, email, password_hash, rol, verificado, activo, fecha_registro) "
                "VALUES (%s, %s, %s, 'buscador', %s, TRUE, %s)",
                (uid, data["email"].lower().strip(), hash_password(data["password"]),
                 verificado, str(date.today())),
            )
        except psycopg.errors.UniqueViolation:
            # Última línea de defensa contra una condición de carrera: el
            # SELECT previo en create_buscador() ya revisó que el email no
            # existiera, pero si dos registros llegan casi al mismo tiempo,
            # solo el UNIQUE de la tabla puede detectarlo con certeza.
            raise EmailYaRegistradoError(f"El correo {data['email']} ya está registrado.")
        conn.execute(
            "INSERT INTO perfiles_buscador "
            "(usuario_id, nombre, telefono, ubicacion, bio, skills, experiencia, educacion, cv_url, avatar, avatar_color) "
            "VALUES (%s, %s, %s, %s, %s, '[]', '', '', '', %s, %s)",
            (uid, data["name"], data.get("phone", ""), data.get("location", ""),
             data.get("bio", ""), avatar, color),
        )
    return uid


def _create_empleador_row(data: dict, verificado: bool, verificado_legal: bool, avatar_index: int) -> str:
    uid = new_id()
    avatar, color = _avatar_for(data["company_name"], avatar_index)
    with get_conn() as conn:
        try:
            conn.execute(
                "INSERT INTO usuarios (id, email, password_hash, rol, verificado, activo, fecha_registro) "
                "VALUES (%s, %s, %s, 'empleador', %s, TRUE, %s)",
                (uid, data["email"].lower().strip(), hash_password(data["password"]),
                 verificado, str(date.today())),
            )
        except psycopg.errors.UniqueViolation:
            # Mismo caso que en _create_buscador_row: última defensa contra
            # una condición de carrera en el email.
            raise EmailYaRegistradoError(f"El correo {data['email']} ya está registrado.")
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
            # Misma condición de carrera pero sobre tax_id (NIT/RUT). El
            # rollback del context manager revierte también el INSERT en
            # `usuarios` de arriba, así que no queda una cuenta huérfana.
            raise TaxIdYaRegistradoError(
                f"El NIT/RUT {data['tax_id']} ya está asociado a otra cuenta empresarial."
            )
    return uid


# ── LECTURA: combinar usuarios + perfil en un solo dict "plano" ─────────────

def _row_to_dict(conn, row: dict) -> dict:
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


def get_users() -> list:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM usuarios WHERE activo = TRUE").fetchall()
        return [_row_to_dict(conn, r) for r in rows]


def get_user(user_id: str) -> dict | None:
    """
    Devuelve un usuario por id SIN filtrar por estado activo. Úsala para
    mostrar información de OTRA persona (quién publicó un empleo, con quién
    chateas, quién aplicó) donde una cuenta desactivada igual debe poder
    mostrarse en el historial.

    Para saber si la cookie de sesión de QUIEN NAVEGA sigue siendo válida,
    usa get_active_user() en su lugar.
    """
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM usuarios WHERE id = %s", (str(user_id),)).fetchone()
        return _row_to_dict(conn, row) if row else None


def get_active_user(user_id: str) -> dict | None:
    """Como get_user(), pero devuelve None si la cuenta fue desactivada/borrada."""
    user = get_user(user_id)
    if not user or not user.get("active", False):
        return None
    return user


def get_user_by_email(email: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM usuarios WHERE email = %s", (email.lower().strip(),)
        ).fetchone()
        return _row_to_dict(conn, row) if row else None


# ── REGISTRO ──────────────────────────────────────────────────────────────────

class EmailYaRegistradoError(Exception):
    """Se lanza cuando alguien intenta registrarse con un email que ya existe."""


class TaxIdYaRegistradoError(Exception):
    """Se lanza cuando el NIT/RUT/RFC de la empresa ya está registrado por otra cuenta."""


def create_buscador(data: dict) -> dict:
    if get_user_by_email(data["email"]):
        raise EmailYaRegistradoError(f"El correo {data['email']} ya está registrado.")
    with get_conn() as conn:
        avatar_index = _next_avatar_index(conn)
    uid = _create_buscador_row(data, verificado=False, avatar_index=avatar_index)
    return get_user(uid)


def create_empleador(data: dict) -> dict:
    if get_user_by_email(data["email"]):
        raise EmailYaRegistradoError(f"El correo {data['email']} ya está registrado.")
    with get_conn() as conn:
        existing_tax = conn.execute(
            "SELECT usuario_id FROM perfiles_empleador WHERE tax_id = %s", (data["tax_id"],)
        ).fetchone()
        avatar_index = _next_avatar_index(conn)
    if existing_tax:
        raise TaxIdYaRegistradoError(
            f"El NIT/RUT {data['tax_id']} ya está asociado a otra cuenta empresarial."
        )
    uid = _create_empleador_row(data, verificado=False, verificado_legal=False, avatar_index=avatar_index)
    return get_user(uid)


# ── LOGIN ─────────────────────────────────────────────────────────────────────

def verify_login(email: str, password: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM usuarios WHERE email = %s", (email.lower().strip(),)
        ).fetchone()
        stored_hash = row["password_hash"] if row else "x$x"
        ok = verify_password(password, stored_hash)
        if not row or not ok or not row["activo"]:
            return None
        return _row_to_dict(conn, row)


# ── VERIFICACIÓN DE EMAIL ─────────────────────────────────────────────────────

def generar_token_verificacion(user_id: str, horas_validez: int = 48) -> str:
    token = new_token()
    now = datetime.utcnow()
    expira = now + timedelta(hours=horas_validez)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO tokens_verificacion (token, usuario_id, creado_at, expira_at) VALUES (%s, %s, %s, %s)",
            (token, user_id, now.isoformat(), expira.isoformat()),
        )
    return token


def confirmar_email(token: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT usuario_id, expira_at FROM tokens_verificacion WHERE token = %s", (token,)
        ).fetchone()
        if not row:
            return False
        if datetime.fromisoformat(row["expira_at"]) < datetime.utcnow():
            return False
        conn.execute("UPDATE usuarios SET verificado = TRUE WHERE id = %s", (row["usuario_id"],))
        conn.execute("DELETE FROM tokens_verificacion WHERE token = %s", (token,))
    return True


def admin_verificar_empresa(user_id: str) -> bool:
    """
    Marca una empresa como legalmente verificada (revisión manual del NIT/RUT
    contra el registro mercantil). Pensado para un futuro panel de admin.
    """
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE perfiles_empleador SET verificado_legal = TRUE WHERE usuario_id = %s", (user_id,)
        )
        return cur.rowcount > 0


# ── ACTUALIZAR / ELIMINAR ─────────────────────────────────────────────────────

def update_user(user_id: str, data: dict) -> dict | None:
    user = get_user(user_id)
    if not user:
        return None
    with get_conn() as conn:
        if user["role"] == "buscador":
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
    return get_user(user_id)


def delete_user(user_id: str) -> bool:
    """Borrado suave: se marca la cuenta como inactiva en vez de borrar la fila."""
    with get_conn() as conn:
        cur = conn.execute("UPDATE usuarios SET activo = FALSE WHERE id = %s", (str(user_id),))
        return cur.rowcount > 0


# ── INICIALIZACIÓN AL IMPORTAR EL MÓDULO ──────────────────────────────────────
init_db()


# ══════════════════════════════════════════════════════════════════════════════
# Empleos / Aplicaciones — YA VIVEN EN NEON (antes eran listas en memoria).
# Conversaciones / Mensajes — YA VIVEN EN NEON (ver funciones más abajo en
# esta sección) — se movieron para que el chat sobreviva a los reinicios de
# Vercel y para que nadie pueda leer una conversación ajena adivinando su id.
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


def get_jobs() -> list:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM empleos ORDER BY publicado_at DESC, id DESC").fetchall()
    return [_job_row_to_dict(r) for r in rows]


def get_job(job_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM empleos WHERE id = %s", (str(job_id),)).fetchone()
    return _job_row_to_dict(row) if row else None


def create_job(job: dict) -> dict:
    """
    job: dict con title, company, location, salary_min, salary_max, type,
    category, description, requirements (list), benefits (list), posted_by,
    posted_at, active. El id ya no es un contador (str(len()+1), que se
    duplicaba si se borraba un empleo) — ahora es un UUID real, igual que
    con los usuarios.
    """
    job_id = new_id()
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
    return get_job(job_id)


def delete_job(job_id: str) -> bool:
    """
    Borra el empleo de verdad (no es borrado suave como en usuarios — un
    empleo no tiene el mismo valor histórico que la cuenta de una persona).
    Por el ON DELETE CASCADE del esquema, esto también borra las
    aplicaciones asociadas a ese empleo — que de todas formas ya quedaban
    invisibles en la app (routers/applications.py las salta si el empleo
    no existe), así que esto solo limpia filas muertas en vez de dejarlas
    huérfanas para siempre.
    """
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM empleos WHERE id = %s", (str(job_id),))
        return cur.rowcount > 0


def _app_row_to_dict(row: dict) -> dict:
    return {
        "id": str(row["id"]), "job_id": row["empleo_id"], "user_id": row["usuario_id"],
        "cover_letter": row["carta_presentacion"], "phone": row["telefono"],
        "experience_years": row["anios_experiencia"], "education_level": row["nivel_educativo"],
        "availability": row["disponibilidad"], "salary_expectation": row["pretension_salarial"],
        "status": row["estado"], "applied_at": row["aplicado_at"],
    }


def get_applications() -> list:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM aplicaciones ORDER BY id DESC").fetchall()
    return [_app_row_to_dict(r) for r in rows]


def get_application(app_id: str) -> dict | None:
    try:
        aid = int(app_id)
    except (TypeError, ValueError):
        return None
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM aplicaciones WHERE id = %s", (aid,)).fetchone()
    return _app_row_to_dict(row) if row else None


def get_applications_by_user(user_id: str) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM aplicaciones WHERE usuario_id = %s ORDER BY id DESC", (str(user_id),)
        ).fetchall()
    return [_app_row_to_dict(r) for r in rows]


def get_applications_by_job(job_id: str) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM aplicaciones WHERE empleo_id = %s ORDER BY id DESC", (str(job_id),)
        ).fetchall()
    return [_app_row_to_dict(r) for r in rows]


class YaAplicasteError(Exception):
    """Se lanza si la misma persona intenta aplicar dos veces al mismo empleo."""


def create_application(app: dict) -> dict:
    """
    app: dict con job_id, user_id, cover_letter, phone, experience_years,
    education_level, availability, salary_expectation, status, applied_at.

    La tabla tiene UNIQUE (empleo_id, usuario_id): aunque el router ya
    revisa duplicados antes de llegar aquí, esta es la última línea de
    defensa real contra una condición de carrera (por ejemplo, dos clics
    casi simultáneos en "Aplicar" antes de que el botón se deshabilite).
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


def update_application_status(app_id: str, status: str) -> dict | None:
    try:
        aid = int(app_id)
    except (TypeError, ValueError):
        return None
    with get_conn() as conn:
        row = conn.execute(
            "UPDATE aplicaciones SET estado = %s WHERE id = %s RETURNING *", (status, aid)
        ).fetchone()
    return _app_row_to_dict(row) if row else None


def get_conversations_by_user(user_id: str) -> list:
    """
    Lista de conversaciones donde participa este usuario, ordenadas por el
    mensaje más reciente primero. NO trae los mensajes completos (por
    performance) — para eso está get_conversation(conv_id).
    """
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


def get_conversation(conv_id: str) -> dict | None:
    """Trae una conversación completa, con todos sus mensajes en orden."""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM conversaciones WHERE id = %s", (conv_id,)).fetchone()
        if not row:
            return None
        msg_rows = conn.execute(
            "SELECT * FROM mensajes WHERE conversacion_id = %s ORDER BY id ASC", (conv_id,)
        ).fetchall()
    return {
        "id": row["id"],
        "participants": [row["participante_a"], row["participante_b"]],
        "aplicacion_id": row["aplicacion_id"],
        "messages": [_message_to_dict(m) for m in msg_rows],
        "last_message": row["last_message"],
        "last_at": row["last_at"],
    }


def get_or_create_conversation(user1_id: str, user2_id: str, aplicacion_id: int | None = None) -> dict:
    """
    Devuelve la conversación entre estos dos usuarios, creándola si es la
    primera vez que se hablan. El id es determinístico (los dos ids de
    usuario ordenados y unidos con "__"), así que dos personas siempre
    caen en la MISMA conversación sin importar quién la abrió primero.

    aplicacion_id (opcional): si el chat nace desde "Contactar" en una
    aplicación específica (ver applications.html), se guarda esa referencia.
    Si la conversación ya existía sin ese dato, se completa ahora
    (COALESCE) en vez de perderlo — pero nunca se pisa un aplicacion_id
    que ya estaba guardado.
    """
    a, b = sorted([str(user1_id), str(user2_id)])
    conv_id = f"{a}__{b}"
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO conversaciones (id, participante_a, participante_b, aplicacion_id, last_message, last_at, created_at) "
            "VALUES (%s, %s, %s, %s, '', '', %s) "
            "ON CONFLICT (id) DO UPDATE SET aplicacion_id = COALESCE(conversaciones.aplicacion_id, EXCLUDED.aplicacion_id)",
            (conv_id, a, b, aplicacion_id, datetime.utcnow().isoformat()),
        )
    return get_conversation(conv_id)


def _message_to_dict(m: dict) -> dict:
    # El nombre/avatar del remitente se busca en vivo (no se duplica en cada
    # mensaje), así que si alguien cambia su nombre después, los mensajes
    # viejos se siguen mostrando con su nombre actualizado — como en
    # cualquier chat real.
    sender = get_user(m["sender_id"]) or {"name": "Usuario", "avatar": "?", "avatar_color": "#6366f1"}
    return {
        "id": str(m["id"]),  # BIGSERIAL: entero autoincremental real, no un timestamp aproximado
        "sender_id": m["sender_id"],
        "sender_name": sender.get("name", "Usuario"),
        "sender_avatar": sender.get("avatar", "?"),
        "sender_color": sender.get("avatar_color", "#6366f1"),
        "text": m["texto"],
        "read": bool(m["leido"]),
        "at": m["hora_display"],
    }


def add_message_to_conversation(conv_id: str, sender_id: str, text: str) -> dict | None:
    """Inserta un mensaje nuevo y actualiza el 'último mensaje' de la conversación."""
    now = datetime.utcnow()
    hora_display = now.strftime("%H:%M")
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO mensajes (conversacion_id, sender_id, texto, hora_display, creado_at) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING *",
            (conv_id, sender_id, text, hora_display, now.isoformat()),
        ).fetchone()
        conn.execute(
            "UPDATE conversaciones SET last_message = %s, last_at = %s WHERE id = %s",
            (text, hora_display, conv_id),
        )
    return _message_to_dict(row)


def get_new_messages(conv_id: str, since_id: int) -> list:
    """Mensajes con id mayor a since_id — usado por el polling del chat."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM mensajes WHERE conversacion_id = %s AND id > %s ORDER BY id ASC",
            (conv_id, since_id),
        ).fetchall()
    return [_message_to_dict(r) for r in rows]


def mark_messages_as_read(conv_id: str, reader_id: str) -> None:
    """
    Marca como leídos los mensajes de esta conversación que NO mandó
    reader_id (es decir, los que le mandó la otra persona). Se llama al
    abrir la conversación — igual que "visto" en cualquier chat real.
    """
    with get_conn() as conn:
        conn.execute(
            "UPDATE mensajes SET leido = TRUE WHERE conversacion_id = %s AND sender_id != %s AND leido = FALSE",
            (conv_id, str(reader_id)),
        )


def is_participant(conv_id: str, user_id: str) -> bool:
    """
    ¿Este usuario realmente pertenece a esta conversación? Se usa para que
    nadie pueda leer o escribir en un chat ajeno adivinando su id (que es
    solo los dos ids de usuario pegados — bastante adivinable).
    """
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM conversaciones WHERE id = %s AND (participante_a = %s OR participante_b = %s)",
            (conv_id, str(user_id), str(user_id)),
        ).fetchone()
    return row is not None