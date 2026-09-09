-- =============================================================================
-- ESQUEMA DE BASE DE DATOS: JobWalpy —
-- Alineada exactamente con database.py:init_db() y schema.sql del proyecto real.
-- =============================================================================

-- ------------------------------------------------------------
-- USUARIOS
-- Datos de autenticación. Es el núcleo que referencian TODAS las
-- demás tablas del proyecto.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS usuarios (
    id              TEXT PRIMARY KEY,
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    rol             TEXT NOT NULL CHECK (rol IN ('buscador', 'empleador')),
    verificado      BOOLEAN NOT NULL DEFAULT FALSE,
    activo          BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_registro  TEXT NOT NULL
);

-- ------------------------------------------------------------
-- PERFILES_BUSCADOR
-- Datos del perfil profesional, SOLO para usuarios con rol 'buscador'.
-- Relación 1 a 1 con usuarios.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS perfiles_buscador (
    usuario_id                TEXT PRIMARY KEY REFERENCES usuarios(id) ON DELETE CASCADE,
    nombre                    TEXT NOT NULL,
    telefono                  TEXT DEFAULT '',
    ubicacion                 TEXT DEFAULT '',
    bio                       TEXT DEFAULT '',
    skills                    TEXT DEFAULT '[]',
    experiencia               TEXT DEFAULT '',
    educacion                 TEXT DEFAULT '',
    cv_url                    TEXT DEFAULT '',
    avatar                    TEXT NOT NULL,
    avatar_color              TEXT NOT NULL,
    profile_photo_url         TEXT DEFAULT '',
    presentation_video_url    TEXT DEFAULT '',
    media_status              TEXT NOT NULL DEFAULT 'pendiente'
);

-- ------------------------------------------------------------
-- PERFILES_EMPLEADOR
-- Datos legales y de la empresa, SOLO para usuarios con rol 'empleador'.
-- Relación 1 a 1 con usuarios.
-- ------------------------------------------------------------
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
);

-- ------------------------------------------------------------
-- TOKENS_VERIFICACION
-- Tokens de un solo uso para confirmar el correo al registrarse.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tokens_verificacion (
    token       TEXT PRIMARY KEY,
    usuario_id  TEXT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    creado_at   TEXT NOT NULL,
    expira_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_usuarios_rol ON usuarios (rol);
CREATE INDEX IF NOT EXISTS idx_perfiles_empleador_taxid ON perfiles_empleador (tax_id);

-- ------------------------------------------------------------
-- EMPLEOS
-- ------------------------------------------------------------
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
);

-- ------------------------------------------------------------
-- APLICACIONES (tabla intermedia usuarios <-> empleos)
-- ------------------------------------------------------------
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
    estado               TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'aceptado', 'rechazado')),
    aplicado_at          TEXT NOT NULL,
    UNIQUE (empleo_id, usuario_id)
);

CREATE INDEX IF NOT EXISTS idx_empleos_publicado_por ON empleos (publicado_por);
CREATE INDEX IF NOT EXISTS idx_empleos_categoria ON empleos (categoria);
CREATE INDEX IF NOT EXISTS idx_aplicaciones_empleo ON aplicaciones (empleo_id);
CREATE INDEX IF NOT EXISTS idx_aplicaciones_usuario ON aplicaciones (usuario_id);

-- ------------------------------------------------------------
-- CONVERSACIONES
-- Un chat siempre es entre exactamente 2 usuarios (participante_a/b),
-- opcionalmente ligado a la postulación que lo originó.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS conversaciones (
    id              TEXT PRIMARY KEY,
    participante_a  TEXT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    participante_b  TEXT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    aplicacion_id   BIGINT REFERENCES aplicaciones(id) ON DELETE SET NULL,
    last_message    TEXT DEFAULT '',
    last_at         TEXT DEFAULT '',
    created_at      TEXT NOT NULL
);

-- ------------------------------------------------------------
-- MENSAJES
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mensajes (
    id               BIGSERIAL PRIMARY KEY,
    conversacion_id  TEXT NOT NULL REFERENCES conversaciones(id) ON DELETE CASCADE,
    sender_id        TEXT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    texto            TEXT NOT NULL,
    leido            BOOLEAN NOT NULL DEFAULT FALSE,
    eliminado        BOOLEAN NOT NULL DEFAULT FALSE,
    hora_display     TEXT NOT NULL,
    creado_at        TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_conversaciones_a ON conversaciones (participante_a);
CREATE INDEX IF NOT EXISTS idx_conversaciones_b ON conversaciones (participante_b);
CREATE INDEX IF NOT EXISTS idx_conversaciones_aplicacion ON conversaciones (aplicacion_id);
CREATE INDEX IF NOT EXISTS idx_mensajes_conversacion ON mensajes (conversacion_id, id);

-- ------------------------------------------------------------
-- PORTAFOLIOS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS portafolios (
    id            TEXT PRIMARY KEY,
    usuario_id    TEXT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    titulo        TEXT NOT NULL,
    descripcion   TEXT DEFAULT '',
    archivo_url   TEXT NOT NULL,
    creado_at     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_portafolios_usuario ON portafolios (usuario_id);

-- ------------------------------------------------------------
-- Vista: empleos activos
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW empleos_activos AS
SELECT
    e.id, e.titulo, e.ubicacion, e.salario_min, e.salario_max,
    e.empresa, e.publicado_at
FROM empleos e
WHERE e.activo = TRUE;