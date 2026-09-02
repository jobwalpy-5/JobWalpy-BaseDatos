-- =============================================================================
-- ESQUEMA DE BASE DE DATOS: JobWalpy
-- Descripción: Creación de tablas, tipos ENUM, restricciones e índices.
-- =============================================================================

-- Habilitar extensión para UUIDs y funciones geoespaciales de PostGIS
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "postgis";

-- -----------------------------------------------------------------------------
-- TIPOS ENUMERADOS (ENUMS)
-- -----------------------------------------------------------------------------

-- Roles de usuario autorizados
CREATE TYPE user_role AS ENUM ('candidate', 'employer', 'admin');

-- Modalidad de trabajo para las ofertas laborales
CREATE TYPE work_type_enum AS ENUM ('remote', 'hybrid', 'on_site');

-- Estado de publicación de la vacante
CREATE TYPE job_status_enum AS ENUM ('active', 'closed', 'draft');

-- Estado del ciclo de vida de una postulación
CREATE TYPE application_status_enum AS ENUM ('pending', 'reviewing', 'interviewed', 'accepted', 'rejected');

-- -----------------------------------------------------------------------------
-- TABLAS PRINCIPALES
-- -----------------------------------------------------------------------------

-- ============================================================
--  JobWalpy - Módulo: Usuarios y Perfiles
-- ============================================================

-- Extensión para generar UUIDs
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ------------------------------------------------------------
-- USUARIO
-- Datos de autenticación y cuenta. Es el núcleo que referencian
-- las demás bases (Empresa, OfertaTrabajo, Postulacion, etc.)
-- ------------------------------------------------------------
CREATE TABLE Usuario (
    id_usuario      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(150) NOT NULL UNIQUE,
    password        VARCHAR(255) NOT NULL,          -- hash de la contraseña (bcrypt)
    rol             VARCHAR(20) NOT NULL CHECK (rol IN ('buscador', 'empleador')),
    activo          BOOLEAN NOT NULL DEFAULT TRUE,   -- permite desactivar sin borrar la cuenta
    fecha_creacion  TIMESTAMPTZ NOT NULL DEFAULT now(),
    ultimo_acceso   TIMESTAMPTZ
);

-- ------------------------------------------------------------
-- PERFIL
-- Datos públicos/editables del usuario, en tabla separada
-- (relación 1 a 1 con Usuario) para no mezclar auth con perfil.
-- ------------------------------------------------------------
CREATE TABLE Perfil (
    id_perfil           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    id_usuario          UUID NOT NULL UNIQUE REFERENCES Usuario(id_usuario) ON DELETE CASCADE,
    nombre_completo      VARCHAR(150) NOT NULL,
    avatar_url            VARCHAR(255),
    avatar_color           VARCHAR(20),
    biografia              TEXT,
    ubicacion               VARCHAR(150),
    telefono                 VARCHAR(30),
    sitio_web                 VARCHAR(255),

    -- campos relevantes principalmente para usuarios con rol 'buscador'
    skills                    TEXT[],
    experiencia                TEXT,
    educacion                    TEXT,
    cv_url                        VARCHAR(255),

    fecha_actualizacion          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------
-- RED_SOCIAL
-- Enlaces opcionales de un perfil (LinkedIn, GitHub, portafolio...)
-- Relación 1 a muchos: un perfil puede tener varios enlaces.
-- ------------------------------------------------------------
CREATE TABLE RedSocial (
    id_red          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    id_perfil       UUID NOT NULL REFERENCES Perfil(id_perfil) ON DELETE CASCADE,
    plataforma      VARCHAR(50) NOT NULL,   -- 'linkedin', 'github', 'portafolio', etc.
    url             VARCHAR(255) NOT NULL
);

-- ------------------------------------------------------------
-- Índices útiles
-- ------------------------------------------------------------

-- Acelera el login por email
CREATE INDEX idx_usuario_email ON Usuario(email);

-- Acelera cargar el perfil de un usuario (caso más frecuente)
CREATE INDEX idx_perfil_usuario ON Perfil(id_usuario);

-- Acelera cargar los enlaces de un perfil
CREATE INDEX idx_redsocial_perfil ON RedSocial(id_perfil);

-- ------------------------------------------------------------
-- Vista: perfil público completo (usuario + perfil, sin password)
-- Pensada para las páginas de perfil visibles a otros usuarios
-- ------------------------------------------------------------
CREATE VIEW vista_perfil_publico AS
SELECT
    u.id_usuario,
    u.rol,
    u.fecha_creacion,
    p.nombre_completo,
    p.avatar_url,
    p.avatar_color,
    p.biografia,
    p.ubicacion,
    p.sitio_web,
    p.skills,
    p.experiencia,
    p.educacion
FROM Usuario u
JOIN Perfil p ON p.id_usuario = u.id_usuario
WHERE u.activo = TRUE;

-- ------------------------------------------------------------
-- EMPRESA (opcional)
-- ------------------------------------------------------------
CREATE TABLE Empresa (
    id_empresa      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    id_creador      UUID NOT NULL REFERENCES Usuario(id_usuario) ON DELETE CASCADE,
    nombre          VARCHAR(150) NOT NULL,
    descripcion     TEXT,
    sitio_web       VARCHAR(255)
);

-- ------------------------------------------------------------
-- OFERTATRABAJO
-- ------------------------------------------------------------
CREATE TABLE OfertaTrabajo (
    id_oferta          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    id_publicador       UUID NOT NULL REFERENCES Usuario(id_usuario) ON DELETE CASCADE,
    id_empresa          UUID REFERENCES Empresa(id_empresa) ON DELETE SET NULL,
    titulo               VARCHAR(200) NOT NULL,
    descripcion          TEXT NOT NULL,
    salario_min          INTEGER,
    salario_max          INTEGER,
    empresa_nombre       VARCHAR(150),      -- texto libre si no hay fila en Empresa
    ubicacion            VARCHAR(150),
    estado               VARCHAR(20) NOT NULL DEFAULT 'activa'
                          CHECK (estado IN ('activa', 'cerrada')),
    fecha_publicacion    TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- campos extra que tu models.py (JobBase) ya usa; quítalos si no los necesitas
    tipo_empleo          VARCHAR(50),        -- "Tiempo completo", "Medio tiempo", etc.
    categoria             VARCHAR(100),
    requisitos            TEXT[],
    beneficios             TEXT[]
);

-- ------------------------------------------------------------
-- POSTULACION (tabla intermedia Usuario <-> OfertaTrabajo)
-- ------------------------------------------------------------
CREATE TABLE Postulacion (
    id_postulacion      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    id_oferta           UUID NOT NULL REFERENCES OfertaTrabajo(id_oferta) ON DELETE CASCADE,
    id_candidato         UUID NOT NULL REFERENCES Usuario(id_usuario) ON DELETE CASCADE,
    estado                VARCHAR(20) NOT NULL DEFAULT 'pendiente'
                          CHECK (estado IN ('pendiente', 'aceptado', 'rechazado')),
    fecha_postulacion    TIMESTAMPTZ NOT NULL DEFAULT now(),
    carta_presentacion   TEXT,
    telefono              VARCHAR(30),
    anos_experiencia      VARCHAR(50),
    nivel_educativo       VARCHAR(100),
    disponibilidad        VARCHAR(100),
    expectativa_salarial  VARCHAR(100),

    -- Evita que un usuario se postule dos veces a la misma oferta
    UNIQUE (id_oferta, id_candidato)
);

-- ------------------------------------------------------------
-- Índices útiles
-- ------------------------------------------------------------

-- Acelera "ver mis ofertas publicadas" (dashboard del empleador)
CREATE INDEX idx_oferta_publicador ON OfertaTrabajo(id_publicador);

-- Acelera listar ofertas de una empresa
CREATE INDEX idx_oferta_empresa ON OfertaTrabajo(id_empresa);

-- Acelera "ver postulantes de esta oferta" (lado empleador)
CREATE INDEX idx_postulacion_oferta ON Postulacion(id_oferta);

-- Acelera "ver mis postulaciones" (lado candidato)
CREATE INDEX idx_postulacion_candidato ON Postulacion(id_candidato);

-- ------------------------------------------------------------
-- Vista: ofertas activas con datos de la empresa/publicador ya unidos
-- Simplifica el listado principal de empleos (routers/jobs.py)
-- ------------------------------------------------------------
CREATE VIEW vista_ofertas_activas AS
SELECT
    o.id_oferta,
    o.titulo,
    o.descripcion,
    o.salario_min,
    o.salario_max,
    COALESCE(e.nombre, o.empresa_nombre) AS empresa,   -- usa Empresa si existe, si no el texto libre
    o.ubicacion,
    o.tipo_empleo,
    o.categoria,
    o.fecha_publicacion,
    u.nombre AS publicado_por
FROM OfertaTrabajo o
JOIN Usuario u ON u.id_usuario = o.id_publicador
LEFT JOIN Empresa e ON e.id_empresa = o.id_empresa
WHERE o.estado = 'activa';

-- TABLAS PRINCIPALES
-- 1. Tabla de Usuarios (base de autenticación para candidatos y empresas)
CREATE TABLE "usuarios" (
    "id_usuario" SERIAL,
    "nombre" TEXT NOT NULL,
    "apellido" TEXT NOT NULL,
    "email" TEXT NOT NULL UNIQUE,
    "password_hash" TEXT NOT NULL,
    "rol" TEXT NOT NULL CHECK("rol" IN ('candidato', 'empresa')),
    "fecha_registro" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY("id_usuario")
);

-- 2. Tabla de Candidatos (perfil profesional, 1 a 1 con usuarios)
CREATE TABLE "candidatos" (
    "id_candidato" SERIAL,
    "id_usuario" INTEGER NOT NULL UNIQUE,
    "telefono" TEXT,
    "cv_url" TEXT,
    "titulo_profesional" TEXT,
    PRIMARY KEY("id_candidato"),
    FOREIGN KEY("id_usuario") REFERENCES "usuarios"("id_usuario") ON DELETE CASCADE
);

-- 3. Tabla de Empresas (perfil de empleador, 1 a 1 con usuarios)
CREATE TABLE "empresas" (
    "id_empresa" SERIAL,
    "id_usuario" INTEGER NOT NULL UNIQUE,
    "nombre_empresa" TEXT NOT NULL,
    "descripcion" TEXT,
    "sitio_web" TEXT,
    PRIMARY KEY("id_empresa"),
    FOREIGN KEY("id_usuario") REFERENCES "usuarios"("id_usuario") ON DELETE CASCADE
);

-- 4. Tabla de Ofertas de Empleo (vacantes publicadas por una empresa)
CREATE TABLE "ofertas_empleo" (
    "id_oferta" SERIAL,
    "id_empresa" INTEGER NOT NULL,
    "titulo" TEXT NOT NULL,
    "descripcion" TEXT NOT NULL,
    "ubicacion" TEXT,
    "salario" NUMERIC,
    "fecha_publicacion" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "activa" BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY("id_oferta"),
    FOREIGN KEY("id_empresa") REFERENCES "empresas"("id_empresa") ON DELETE CASCADE
);

-- 5. Tabla de Postulaciones (candidato que aplica a una oferta)
CREATE TABLE "postulaciones" (
    "id_postulacion" SERIAL,
    "id_candidato" INTEGER NOT NULL,
    "id_oferta" INTEGER NOT NULL,
    "estado" TEXT NOT NULL DEFAULT 'pendiente'
        CHECK("estado" IN ('pendiente', 'aceptado', 'rechazado')),
    "fecha_postulacion" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY("id_postulacion"),
    FOREIGN KEY("id_candidato") REFERENCES "candidatos"("id_candidato") ON DELETE CASCADE,
    FOREIGN KEY("id_oferta") REFERENCES "ofertas_empleo"("id_oferta") ON DELETE CASCADE,
    UNIQUE("id_candidato", "id_oferta")
);

-- 6. Tabla de Conversaciones (sala de chat, opcionalmente ligada a una postulación)
CREATE TABLE "conversaciones" (
    "id_conversacion" SERIAL,
    "id_postulacion" INTEGER,
    "fecha_creacion" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY("id_conversacion"),
    FOREIGN KEY("id_postulacion") REFERENCES "postulaciones"("id_postulacion") ON DELETE SET NULL
);

-- 7. Tabla intermedia: Participantes del chat (relación muchos a muchos)
CREATE TABLE "participantes" (
    "id_conversacion" INTEGER NOT NULL,
    "id_usuario" INTEGER NOT NULL,
    PRIMARY KEY("id_conversacion", "id_usuario"),
    FOREIGN KEY("id_conversacion") REFERENCES "conversaciones"("id_conversacion") ON DELETE CASCADE,
    FOREIGN KEY("id_usuario") REFERENCES "usuarios"("id_usuario") ON DELETE CASCADE
);

-- 8. Tabla de Mensajes (cada mensaje individual dentro de una conversación)
CREATE TABLE "mensajes" (
    "id_mensaje" SERIAL,
    "id_conversacion" INTEGER NOT NULL,
    "id_emisor" INTEGER NOT NULL,
    "contenido" TEXT NOT NULL,
    "leido" BOOLEAN NOT NULL DEFAULT FALSE,
    "fecha_envio" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY("id_mensaje"),
    FOREIGN KEY("id_conversacion") REFERENCES "conversaciones"("id_conversacion") ON DELETE CASCADE,
    FOREIGN KEY("id_emisor") REFERENCES "usuarios"("id_usuario") ON DELETE CASCADE
);


-- ÍNDICES DE OPTIMIZACIÓN
-- Acelera el login y la búsqueda de usuarios por email
CREATE INDEX "idx_usuarios_email" ON "usuarios" ("email");

-- Acelera listar las ofertas publicadas por una empresa específica
CREATE INDEX "idx_ofertas_empresa" ON "ofertas_empleo" ("id_empresa");

-- Aceleran la búsqueda de postulaciones por candidato u oferta
CREATE INDEX "idx_postulaciones_candidato" ON "postulaciones" ("id_candidato");
CREATE INDEX "idx_postulaciones_oferta" ON "postulaciones" ("id_oferta");

-- Acelera cargar todos los mensajes de una conversación
CREATE INDEX "idx_mensajes_conversacion" ON "mensajes" ("id_conversacion");


-- VISTAS (VIEWS)
-- Vista para obtener rápidamente las ofertas activas con el nombre de la empresa
CREATE VIEW "ofertas_activas" AS
SELECT
    o."id_oferta",
    o."titulo",
    o."ubicacion",
    o."salario",
    e."nombre_empresa",
    o."fecha_publicacion"
FROM "ofertas_empleo" o
JOIN "empresas" e ON o."id_empresa" = e."id_empresa"
WHERE o."activa" = TRUE;