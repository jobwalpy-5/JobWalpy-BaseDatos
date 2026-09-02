-- ============================================================
--  JobWalpy - Módulo: Usuarios y Perfiles - Consultas típicas
-- ============================================================
 
-- ------------------------------------------------------------
-- REGISTRO Y AUTENTICACIÓN
-- ------------------------------------------------------------
 
-- Registrar una nueva cuenta (paso 1: solo datos de auth)
INSERT INTO Usuario (email, password, rol)
VALUES ('juan@example.com', 'hashed_password', 'buscador')
RETURNING id_usuario;
 
-- Crear el perfil asociado a esa cuenta (paso 2, justo después del registro)
INSERT INTO Perfil (id_usuario, nombre_completo)
VALUES ('11111111-1111-1111-1111-111111111111', 'Juan Pérez');
 
-- Login: buscar usuario por email para validar contraseña
SELECT id_usuario, email, password, rol, activo
FROM Usuario
WHERE email = 'juan@example.com';
 
-- Registrar el último acceso al iniciar sesión
UPDATE Usuario
SET ultimo_acceso = now()
WHERE id_usuario = '11111111-1111-1111-1111-111111111111';
 
-- Cambiar contraseña
UPDATE Usuario
SET password = 'nuevo_hash'
WHERE id_usuario = '11111111-1111-1111-1111-111111111111';
 
-- Desactivar una cuenta sin borrar sus datos (soft delete)
UPDATE Usuario
SET activo = FALSE
WHERE id_usuario = '11111111-1111-1111-1111-111111111111';
 
-- Eliminar una cuenta por completo (borra en cascada su perfil y redes sociales)
DELETE FROM Usuario WHERE id_usuario = '11111111-1111-1111-1111-111111111111';
 
 
-- ------------------------------------------------------------
-- PERFIL
-- ------------------------------------------------------------
 
-- Ver el perfil público de un usuario (para que otros lo vean)
SELECT * FROM vista_perfil_publico
WHERE id_usuario = '11111111-1111-1111-1111-111111111111';
 
-- Editar datos generales del perfil
UPDATE Perfil
SET biografia = 'Desarrollador backend con 3 años de experiencia',
    ubicacion = 'Bogotá',
    telefono = '3001234567',
    fecha_actualizacion = now()
WHERE id_usuario = '11111111-1111-1111-1111-111111111111';
 
-- Actualizar habilidades, experiencia y educación (perfil de un buscador de empleo)
UPDATE Perfil
SET skills = ARRAY['Python', 'SQL', 'FastAPI'],
    experiencia = '3 años como desarrollador backend',
    educacion = 'Ingeniería de Sistemas',
    fecha_actualizacion = now()
WHERE id_usuario = '11111111-1111-1111-1111-111111111111';
 
-- Actualizar avatar
UPDATE Perfil
SET avatar_url = 'https://cdn.jobwalpy.com/avatars/juan.png'
WHERE id_usuario = '11111111-1111-1111-1111-111111111111';
 
-- Buscar perfiles por nombre o habilidad (para que empleadores encuentren candidatos)
SELECT * FROM vista_perfil_publico
WHERE rol = 'buscador'
  AND (nombre_completo ILIKE '%juan%' OR 'Python' = ANY(skills));
 
 
-- ------------------------------------------------------------
-- REDES SOCIALES
-- ------------------------------------------------------------
 
-- Agregar un enlace de red social al perfil
INSERT INTO RedSocial (id_perfil, plataforma, url)
VALUES ('22222222-2222-2222-2222-222222222222', 'linkedin', 'https://linkedin.com/in/juanperez');
 
-- Ver todos los enlaces de un perfil
SELECT plataforma, url
FROM RedSocial
WHERE id_perfil = '22222222-2222-2222-2222-222222222222';
 
-- Eliminar un enlace específico
DELETE FROM RedSocial WHERE id_red = '33333333-3333-3333-3333-333333333333';

-- ------------------------------------------------------------
-- USUARIOS
-- ------------------------------------------------------------

-- Registrar un nuevo usuario (buscador de empleo o empleador)
INSERT INTO Usuario (nombre, email, password, rol, ubicacion)
VALUES ('Juan Pérez', 'juan@example.com', 'hashed_password', 'buscador', 'Medellín');

-- Buscar usuario por email, para el login
SELECT * FROM Usuario WHERE email = 'juan@example.com';

-- Actualizar el perfil de un usuario (bio, ubicación, habilidades)
UPDATE Usuario
SET bio = 'Desarrollador backend con 3 años de experiencia',
    ubicacion = 'Bogotá',
    skills = ARRAY['Python', 'SQL', 'FastAPI']
WHERE id_usuario = '11111111-1111-1111-1111-111111111111';

-- Eliminar una cuenta de usuario (borra en cascada sus ofertas y postulaciones)
DELETE FROM Usuario WHERE id_usuario = '11111111-1111-1111-1111-111111111111';


-- ------------------------------------------------------------
-- EMPRESAS
-- ------------------------------------------------------------

-- Crear una empresa a nombre de un empleador
INSERT INTO Empresa (id_creador, nombre, descripcion, sitio_web)
VALUES ('22222222-2222-2222-2222-222222222222', 'TechCorp', 'Empresa de software', 'https://techcorp.com');

-- Ver todas las empresas creadas por un usuario
SELECT * FROM Empresa WHERE id_creador = '22222222-2222-2222-2222-222222222222';


-- ------------------------------------------------------------
-- OFERTAS DE TRABAJO
-- ------------------------------------------------------------

-- Publicar una nueva oferta de empleo
INSERT INTO OfertaTrabajo (
    id_publicador, id_empresa, titulo, descripcion,
    salario_min, salario_max, ubicacion, tipo_empleo, categoria,
    requisitos, beneficios
)
VALUES (
    '22222222-2222-2222-2222-222222222222', NULL, 'Desarrollador Backend',
    'Buscamos desarrollador con experiencia en FastAPI y Postgres',
    3000000, 5000000, 'Medellín', 'Tiempo completo', 'Tecnología',
    ARRAY['Python', 'SQL'], ARRAY['Trabajo remoto', 'Seguro médico']
);

-- Listar todas las ofertas activas, más recientes primero (página principal de empleos)
SELECT * FROM vista_ofertas_activas
ORDER BY fecha_publicacion DESC;

-- Buscar ofertas por palabra clave en el título o descripción
SELECT * FROM vista_ofertas_activas
WHERE titulo ILIKE '%desarrollador%' OR descripcion ILIKE '%desarrollador%';

-- Filtrar ofertas por ubicación, categoría y salario mínimo (filtros de búsqueda)
SELECT * FROM vista_ofertas_activas
WHERE ubicacion = 'Medellín'
  AND categoria = 'Tecnología'
  AND salario_min >= 3000000;

-- Ver el detalle de una oferta específica
SELECT * FROM vista_ofertas_activas WHERE id_oferta = '33333333-3333-3333-3333-333333333333';

-- Ver todas las ofertas publicadas por un empleador (su dashboard)
SELECT * FROM OfertaTrabajo WHERE id_publicador = '22222222-2222-2222-2222-222222222222';

-- Cerrar una oferta (ya no acepta más postulaciones)
UPDATE OfertaTrabajo
SET estado = 'cerrada'
WHERE id_oferta = '33333333-3333-3333-3333-333333333333';

-- Eliminar una oferta (borra en cascada sus postulaciones)
DELETE FROM OfertaTrabajo WHERE id_oferta = '33333333-3333-3333-3333-333333333333';


-- ------------------------------------------------------------
-- POSTULACIONES
-- ------------------------------------------------------------

-- Un candidato se postula a una oferta
INSERT INTO Postulacion (
    id_oferta, id_candidato, carta_presentacion,
    telefono, anos_experiencia, nivel_educativo, disponibilidad, expectativa_salarial
)
VALUES (
    '33333333-3333-3333-3333-333333333333', '11111111-1111-1111-1111-111111111111',
    'Estoy muy interesado en esta posición porque...',
    '3001234567', '3 años', 'Universitario', 'Inmediata', '4000000'
);

-- Ver todas las postulaciones que ha hecho un candidato (su historial)
SELECT p.*, o.titulo, o.ubicacion
FROM Postulacion p
JOIN OfertaTrabajo o ON o.id_oferta = p.id_oferta
WHERE p.id_candidato = '11111111-1111-1111-1111-111111111111'
ORDER BY p.fecha_postulacion DESC;

-- Ver todos los postulantes de una oferta (vista del empleador)
SELECT p.*, u.nombre, u.email
FROM Postulacion p
JOIN Usuario u ON u.id_usuario = p.id_candidato
WHERE p.id_oferta = '33333333-3333-3333-3333-333333333333'
ORDER BY p.fecha_postulacion DESC;

-- Cambiar el estado de una postulación (el empleador acepta o rechaza)
UPDATE Postulacion
SET estado = 'aceptado'
WHERE id_postulacion = '44444444-4444-4444-4444-444444444444';

-- Contar cuántas postulaciones tiene cada oferta (métricas del dashboard)
SELECT o.titulo, COUNT(p.id_postulacion) AS total_postulantes
FROM OfertaTrabajo o
LEFT JOIN Postulacion p ON p.id_oferta = o.id_oferta
GROUP BY o.id_oferta, o.titulo
ORDER BY total_postulantes DESC;

-- Evitar postulaciones duplicadas: verificar si un candidato ya se postuló a esta oferta
SELECT 1 FROM Postulacion
WHERE id_oferta = '33333333-3333-3333-3333-333333333333'
  AND id_candidato = '11111111-1111-1111-1111-111111111111';

-- Retirar una postulación
DELETE FROM Postulacion WHERE id_postulacion = '44444444-4444-4444-4444-444444444444';

-- 1. OPERACIONES DE REGISTRO Y AUTENTICACIÓN (INSERT)
-- Registrar un nuevo usuario candidato
INSERT INTO "usuarios" ("nombre", "apellido", "email", "password_hash", "rol")
VALUES ('Juliana', 'Restrepo', 'juliana@example.com', '$2b$12$hash_ejemplo', 'candidato');

-- Crear el perfil profesional del candidato, asociado al usuario recién creado
INSERT INTO "candidatos" ("id_usuario", "telefono", "titulo_profesional")
VALUES (7, '3001234567', 'Desarrolladora Full Stack');

-- Registrar un nuevo usuario de tipo empresa
INSERT INTO "usuarios" ("nombre", "apellido", "email", "password_hash", "rol")
VALUES ('TechCorp', 'Colombia', 'contacto@techcorp.com', '$2b$12$hash_ejemplo', 'empresa');

-- Crear el perfil de la empresa, asociado al usuario recién creado
INSERT INTO "empresas" ("id_usuario", "nombre_empresa", "descripcion", "sitio_web")
VALUES (1, 'TechCorp Colombia', 'Empresa de desarrollo de software', 'https://techcorp.com');

-- 2. PUBLICACIÓN Y BÚSQUEDA DE EMPLEOS (INSERT / SELECT)
-- Una empresa publica una nueva oferta laboral
INSERT INTO "ofertas_empleo" ("id_empresa", "titulo", "descripcion", "ubicacion", "salario")
VALUES (
    1,
    'Desarrollador Full Stack',
    'Tiempo completo. Categoría: Tecnología.',
    'Bogotá, Colombia',
    5500000
);

-- Buscar ofertas activas por categoría/ubicación (usa la vista ofertas_activas)
SELECT * FROM "ofertas_activas"
WHERE "ubicacion" LIKE '%Bogotá%'
ORDER BY "fecha_publicacion" DESC;

-- Buscar una oferta específica por su título
SELECT * FROM "ofertas_empleo"
WHERE "titulo" = 'Desarrollador Full Stack';


-- 3. FLUJO DE POSTULACIÓN Y SELECCIÓN (INSERT / UPDATE / SELECT)
-- Un candidato se postula a una vacante existente
INSERT INTO "postulaciones" ("id_candidato", "id_oferta", "estado")
VALUES (1, 1, 'pendiente');

-- La empresa cambia el estado de una postulación a "aceptado"
UPDATE "postulaciones"
SET "estado" = 'aceptado'
WHERE "id_postulacion" = 1;

-- Ver todas las postulaciones de un candidato, con el nombre de la oferta y la empresa
SELECT p."id_postulacion", o."titulo", e."nombre_empresa", p."estado"
FROM "postulaciones" p
JOIN "ofertas_empleo" o ON p."id_oferta" = o."id_oferta"
JOIN "empresas" e ON o."id_empresa" = e."id_empresa"
WHERE p."id_candidato" = 1;


-- 4. MENSAJERÍA ENTRE CANDIDATO Y EMPRESA (INSERT / SELECT / UPDATE)
-- Abrir una conversación asociada a una postulación
INSERT INTO "conversaciones" ("id_postulacion")
VALUES (1);

-- Añadir a ambas partes como participantes de la conversación
INSERT INTO "participantes" ("id_conversacion", "id_usuario")
VALUES (1, 7), (1, 1);

-- Enviar un mensaje dentro de la conversación
INSERT INTO "mensajes" ("id_conversacion", "id_emisor", "contenido")
VALUES (1, 1, 'Hola Juliana, vimos tu postulación, ¿tienes disponibilidad esta semana para una entrevista?');

-- Obtener el historial completo de mensajes de una conversación, en orden
SELECT m."fecha_envio", u."nombre", m."contenido"
FROM "mensajes" m
JOIN "usuarios" u ON m."id_emisor" = u."id_usuario"
WHERE m."id_conversacion" = 1
ORDER BY m."fecha_envio";

-- Contar los mensajes no leídos que le quedan pendientes a un usuario en un chat
SELECT COUNT(*) AS mensajes_no_leidos
FROM "mensajes"
WHERE "id_conversacion" = 1
  AND "id_emisor" != 7
  AND "leido" = FALSE;

-- Marcar como leídos los mensajes cuando el candidato abre la conversación
UPDATE "mensajes"
SET "leido" = TRUE
WHERE "id_conversacion" = 1
  AND "id_emisor" != 7
  AND "leido" = FALSE;


-- 5. ELIMINACIÓN Y MANTENIMIENTO (DELETE)
-- Eliminar una oferta de empleo (por cascada elimina también sus postulaciones)
DELETE FROM "ofertas_empleo"
WHERE "id_oferta" = 1;

-- Eliminar un usuario (por cascada elimina su perfil, postulaciones y mensajes)
DELETE FROM "usuarios"
WHERE "id_usuario" = 7;

-- -----------------------------------------------------------------------------
-- 5. ELIMINACIÓN Y MANTENIMIENTO (DELETE)
-- -----------------------------------------------------------------------------

-- Eliminar una vacante (por cascada elimina postulaciones y chats asociados)
DELETE FROM jobs
WHERE id = '111e4567-e89b-12d3-a456-426614174000';