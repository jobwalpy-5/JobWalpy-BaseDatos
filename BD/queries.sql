-- ============================================================
--  JobWalpy - Consultas típicas .
-- ============================================================

-- ------------------------------------------------------------
-- REGISTRO Y AUTENTICACIÓN
-- ------------------------------------------------------------

-- Registrar una nueva cuenta de buscador (paso 1: solo datos de auth)
-- NOTA: el $2$ es un ejemplo de hash — en el código real lo genera
-- auth.hash_password(), nunca se escribe la contraseña en texto plano.
INSERT INTO usuarios (id, email, password_hash, rol, verificado, activo, fecha_registro)
VALUES ('uuid-generado-por-python', 'juan@example.com', 'salt$hash_real', 'buscador', FALSE, TRUE, '2026-09-02');

-- Crear el perfil asociado a esa cuenta (paso 2, justo después del registro)
INSERT INTO perfiles_buscador (usuario_id, nombre, avatar, avatar_color)
VALUES ('uuid-generado-por-python', 'Juan Pérez', 'JP', '#6366f1');

-- Login: buscar usuario por email para validar contraseña
SELECT id, email, password_hash, rol, activo
FROM usuarios
WHERE email = 'juan@example.com';

-- Desactivar una cuenta sin borrar sus datos (borrado suave — así funciona SIEMPRE en este proyecto)
UPDATE usuarios
SET activo = FALSE
WHERE id = 'uuid-del-usuario';

-- ------------------------------------------------------------
-- PERFIL
-- ------------------------------------------------------------

-- Editar datos generales del perfil de un buscador
UPDATE perfiles_buscador
SET bio = 'Desarrollador backend con 3 años de experiencia',
    ubicacion = 'Bogotá',
    telefono = '3001234567'
WHERE usuario_id = 'uuid-del-usuario';

-- Actualizar habilidades, experiencia y educación
-- (skills se guarda como texto JSON, ej: '["Python", "SQL", "FastAPI"]')
UPDATE perfiles_buscador
SET skills = '["Python", "SQL", "FastAPI"]',
    experiencia = '3 años como desarrollador backend',
    educacion = 'Ingeniería de Sistemas'
WHERE usuario_id = 'uuid-del-usuario';

-- Actualizar foto de perfil (la URL viene de MinIO, el archivo NO se guarda en la base de datos)
UPDATE perfiles_buscador
SET profile_photo_url = 'https://tu-endpoint-minio/jobwalpy-media/profile-photos/uuid-del-usuario.jpg'
WHERE usuario_id = 'uuid-del-usuario';

-- Buscar perfiles de buscadores por nombre o habilidad (para que empleadores encuentren candidatos)
SELECT u.id, p.nombre, p.skills
FROM usuarios u
JOIN perfiles_buscador p ON p.usuario_id = u.id
WHERE u.rol = 'buscador'
  AND u.activo = TRUE
  AND (p.nombre ILIKE '%juan%' OR p.skills ILIKE '%Python%');

-- ------------------------------------------------------------
-- EMPRESAS (perfiles_empleador — no es tabla aparte, es el perfil del rol empleador)
-- ------------------------------------------------------------

-- Registrar una empresa: primero el usuario base
INSERT INTO usuarios (id, email, password_hash, rol, verificado, activo, fecha_registro)
VALUES ('uuid-generado-por-python', 'contacto@techcorp.com', 'salt$hash_real', 'empleador', FALSE, TRUE, '2026-09-02');

-- Después su perfil de empresa, con el NIT obligatorio y único
INSERT INTO perfiles_empleador (usuario_id, contact_name, company_name, legal_name, tax_id, address, industry, ubicacion, avatar, avatar_color, verificado_legal)
VALUES ('uuid-generado-por-python', 'Ana Gómez', 'TechCorp', 'TechCorp S.A.S.', '900123456-1', 'Calle 1', 'Tecnología', 'Medellín', 'TC', '#0ea5e9', FALSE);

-- Ver los datos de la empresa de un usuario
SELECT * FROM perfiles_empleador WHERE usuario_id = 'uuid-del-usuario';

-- ------------------------------------------------------------
-- EMPLEOS
-- ------------------------------------------------------------

-- Publicar una nueva oferta de empleo
INSERT INTO empleos (
    id, titulo, empresa, ubicacion, salario_min, salario_max,
    tipo, categoria, descripcion, requisitos, beneficios, publicado_por, publicado_at, activo
)
VALUES (
    'uuid-generado-por-python', 'Desarrollador Backend', 'TechCorp', 'Medellín',
    3000000, 5000000, 'Tiempo completo', 'Tecnología',
    'Buscamos desarrollador con experiencia en FastAPI y Postgres',
    '["Python", "SQL"]', '["Trabajo remoto", "Seguro médico"]',
    'uuid-del-empleador', '2026-09-02', TRUE
);

-- Listar todos los empleos, más recientes primero (la base de la página /jobs)
SELECT * FROM empleos ORDER BY publicado_at DESC, id DESC;

-- Buscar empleos por palabra clave (el filtrado real por texto pasa en Python, no aquí —
-- esto es solo la consulta base que trae TODOS los empleos antes de ese filtro)
SELECT * FROM empleos;

-- Ver el detalle de un empleo específico
SELECT * FROM empleos WHERE id = 'uuid-del-empleo';

-- Ver todos los empleos publicados por un empleador (su dashboard)
SELECT * FROM empleos WHERE publicado_por = 'uuid-del-empleador';

-- Cerrar un empleo (ya no acepta más postulaciones)
UPDATE empleos SET activo = FALSE WHERE id = 'uuid-del-empleo';

-- Eliminar un empleo (SÍ es borrado real, no suave — arrastra en cascada sus aplicaciones)
DELETE FROM empleos WHERE id = 'uuid-del-empleo';

-- ------------------------------------------------------------
-- APLICACIONES
-- ------------------------------------------------------------

-- Un candidato se postula a un empleo
INSERT INTO aplicaciones (
    empleo_id, usuario_id, carta_presentacion, telefono,
    anios_experiencia, nivel_educativo, disponibilidad, pretension_salarial, estado, aplicado_at
)
VALUES (
    'uuid-del-empleo', 'uuid-del-candidato',
    'Estoy muy interesado en esta posición porque...',
    '3001234567', '3 años', 'Universitario', 'Inmediata', '4000000', 'pendiente', '2026-09-02'
);

-- Ver todas las aplicaciones que ha hecho un candidato (su historial)
SELECT a.*, e.titulo, e.ubicacion
FROM aplicaciones a
JOIN empleos e ON e.id = a.empleo_id
WHERE a.usuario_id = 'uuid-del-candidato'
ORDER BY a.id DESC;

-- Ver todos los postulantes de un empleo (vista del empleador)
SELECT a.*, u.email
FROM aplicaciones a
JOIN usuarios u ON u.id = a.usuario_id
WHERE a.empleo_id = 'uuid-del-empleo'
ORDER BY a.id DESC;

-- Cambiar el estado de una aplicación (el empleador acepta o rechaza)
UPDATE aplicaciones SET estado = 'aceptado' WHERE id = 1;

-- Contar cuántas aplicaciones tiene cada empleo (métricas del dashboard)
SELECT e.titulo, COUNT(a.id) AS total_postulantes
FROM empleos e
LEFT JOIN aplicaciones a ON a.empleo_id = e.id
GROUP BY e.id, e.titulo
ORDER BY total_postulantes DESC;

-- Evitar postulaciones duplicadas: la tabla ya tiene UNIQUE(empleo_id, usuario_id),
-- pero el código también revisa antes de intentar insertar:
SELECT 1 FROM aplicaciones
WHERE empleo_id = 'uuid-del-empleo' AND usuario_id = 'uuid-del-candidato';

-- ------------------------------------------------------------
-- MENSAJERÍA (CONVERSACIONES Y MENSAJES)
-- ------------------------------------------------------------

-- Abrir/crear una conversación entre dos usuarios (el id se arma en Python:
-- los dos ids de usuario, ordenados alfabéticamente y unidos con "__")
INSERT INTO conversaciones (id, participante_a, participante_b, aplicacion_id, last_message, last_at, created_at)
VALUES ('uuid-a__uuid-b', 'uuid-a', 'uuid-b', NULL, '', '', '2026-09-02T10:00:00')
ON CONFLICT (id) DO NOTHING;

-- Enviar un mensaje dentro de la conversación
INSERT INTO mensajes (conversacion_id, sender_id, texto, leido, eliminado, hora_display, creado_at)
VALUES ('uuid-a__uuid-b', 'uuid-a', 'Hola, vimos tu postulación, ¿tienes disponibilidad esta semana?', FALSE, FALSE, '10:05', '2026-09-02T10:05:00');

-- Obtener el historial completo de mensajes de una conversación, en orden
SELECT m.creado_at, u.email, m.texto
FROM mensajes m
JOIN usuarios u ON m.sender_id = u.id
WHERE m.conversacion_id = 'uuid-a__uuid-b'
ORDER BY m.id ASC;

-- Contar los mensajes no leídos que le quedan pendientes a un usuario en un chat
SELECT COUNT(*) AS mensajes_no_leidos
FROM mensajes
WHERE conversacion_id = 'uuid-a__uuid-b'
  AND sender_id != 'uuid-a'
  AND leido = FALSE;

-- Marcar como leídos los mensajes cuando alguien abre la conversación
UPDATE mensajes
SET leido = TRUE
WHERE conversacion_id = 'uuid-a__uuid-b'
  AND sender_id != 'uuid-a'
  AND leido = FALSE;

-- Eliminar un mensaje (borrado suave — el texto real nunca se vuelve a mostrar)
UPDATE mensajes SET eliminado = TRUE WHERE id = 1;

-- ------------------------------------------------------------
-- PORTAFOLIO
-- ------------------------------------------------------------

-- Agregar un elemento al portafolio de un candidato
INSERT INTO portafolios (id, usuario_id, titulo, descripcion, archivo_url, creado_at)
VALUES ('uuid-generado-por-python', 'uuid-del-candidato', 'Proyecto Backend', 'API en FastAPI', 'https://tu-endpoint-minio/jobwalpy-media/portfolios/uuid/x.pdf', '2026-09-02');

-- Ver el portafolio de un candidato
SELECT * FROM portafolios WHERE usuario_id = 'uuid-del-candidato' ORDER BY creado_at DESC;

-- Eliminar un elemento del portafolio (solo si es realmente del dueño)
DELETE FROM portafolios WHERE id = 'uuid-del-item' AND usuario_id = 'uuid-del-candidato';

-- ------------------------------------------------------------
-- ELIMINACIÓN Y MANTENIMIENTO
-- ------------------------------------------------------------

-- Eliminar un empleo (por cascada elimina también sus aplicaciones)
DELETE FROM empleos WHERE id = 'uuid-del-empleo';

-- "Eliminar" un usuario (en este proyecto NUNCA es un DELETE real —
-- siempre es borrado suave, para no perder el historial de empleos/chats/aplicaciones)
UPDATE usuarios SET activo = FALSE WHERE id = 'uuid-del-usuario';