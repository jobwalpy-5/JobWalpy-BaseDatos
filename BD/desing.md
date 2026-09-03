# Documento de Diseño de Base de Datos: JobWalpy (DESIGN.md)

## 1. Propósito (*Purpose*)

El propósito fundamental de la base de datos de **JobWalpy** es soportar el ciclo de vida completo del reclutamiento de personal y la interacción directa en tiempo real entre candidatos y empleadores. A diferencia de las plataformas tradicionales de empleo estáticas, JobWalpy integra un subsistema de mensajería bidireccional acoplado al proceso de postulación, lo que exige una arquitectura de datos optimizada tanto para consultas complejas de búsqueda de empleo (*Read-Heavy*) como para un flujo concurrente de alta frecuencia de mensajes e interacciones (*Write-Heavy*).

Esta base de datos ha sido diseñada para garantizar la integridad referencial, mitigar la redundancia de datos mediante la Normalización de Boyce-Codd (BCNF) en su capa relacional principal, y permitir la expansión hacia capacidades avanzadas como búsquedas geoespaciales por proximidad y analíticas históricas sobre ofertas laborales.

---

## 2. Alcance (*Scope*)

El alcance del sistema abarca cuatro grandes dominios funcionales dentro del ecosistema de la plataforma:

1. **Gestión de Identidad y Perfiles:** Manejo unificado de usuarios (autenticación, roles y estado de verificación) junto con la segregación de perfiles profesionales para candidatos (CVs, habilidades en formato JSON semiestructurado) y entidades de empresas para empleadores.
2. **Publicación y Catálogo de Empleos:** Creación, categorización, filtrado multi-criterio (salario, modalidad, tipo de contrato) y geolocalización de ofertas de trabajo activas e históricas.
3. **Flujo de Postulaciones y Selección:** Registro del ciclo de vida de una candidatura desde la aplicación inicial hasta las fases de entrevista, aceptación o rechazo.
4. **Mensajería síncrona/asíncrona y Notificaciones:** Sala de conversaciones dinámicas ligadas al contexto de una postulación activa, control de confirmación de lectura de mensajes e historial de alertas del sistema.

### Fuera del Alcance (*Out of Scope*)

Se excluyen del esquema relacional primario el procesamiento directo de transacciones bancarias o pasarelas de pago (suscripciones de empresas), el almacenamiento físico binario de documentos o videos (el cual se delega a un almacenamiento de objetos tipo S3, guardando solo punteros URI) y los registros masivos de *logs* de auditoría de infraestructura.

---

## 3. Entidades y Atributos (*Entities & Attributes*)

El dominio se modela utilizando un enfoque híbrido relacional con soporte para tipos de datos avanzados (JSONB y Geometría espacial de PostGIS):

![Diagrama Entidad Relación de JobWalpy](actualizacionmed.png)

### 3.1 `users` (Usuarios)

Entidad central de autenticación y control de acceso.

* **`id`** (`UUID`, PK): Identificador único global generado mediante `gen_random_uuid()` para evitar enumeración maliciosa.
* **`email`** (`VARCHAR(255)`, UNIQUE, NOT NULL): Correo electrónico del usuario, sanitizado a minúsculas.
* **`password_hash`** (`VARCHAR(255)`, NOT NULL): Hash criptográfico de la contraseña (Bcrypt / Argon2).
* **`role`** (`ENUM`, NOT NULL): Rol dentro del sistema (`candidate`, `employer`, `admin`).
* **`is_verified`** (`BOOLEAN`, DEFAULT `FALSE`): Estado de verificación de correo o identidad.
* **`created_at`** (`TIMESTAMPTZ`, DEFAULT `CURRENT_TIMESTAMP`).

### 3.2 `profiles` (Perfiles Profesionales)

Contiene la información detallada del currículum vitae del candidato.

* **`id`** (`UUID`, PK).
* **`user_id`** (`UUID`, FK, UNIQUE, NOT NULL): Relación 1:1 estricta con la tabla `users`.
* **`full_name`**, **`headline`**, **`phone`** (`VARCHAR`).
* **`bio`** (`TEXT`).
* **`cv_url`** (`VARCHAR(512)`): Enlace al almacenamiento de objetos (p. ej. AWS S3).
* **`skills`** (`JSONB`): Matriz de habilidades técnicas (ej: `["Python", "FastAPI", "PostgreSQL"]`). Se optó por `JSONB` sobre una tabla `skills` normalizada para reducir el costo de *JOINs* en consultas de perfilado rápido.

### 3.3 `companies` (Empresas)

* **`id`** (`UUID`, PK).
* **`owner_id`** (`UUID`, FK, NOT NULL): Usuario reclutador propietario del perfil de la empresa.
* **`name`** (`VARCHAR(150)`, NOT NULL).
* **`logo_url`**, **`website`** (`VARCHAR(512)`).
* **`is_verified`** (`BOOLEAN`): Insignia de validación corporativa.

### 3.4 `jobs` (Ofertas de Trabajo)

* **`id`** (`UUID`, PK).
* **`publisher_id`** (`UUID`, FK, NOT NULL): Usuario que publica la vacante.
* **`company_id`** (`UUID`, FK, NULLABLE): Referencia opcional si la vacante pertenece a una empresa registrada.
* **`title`** (`VARCHAR(150)`, NOT NULL).
* **`description`** (`TEXT`, NOT NULL).
* **`category`** (`VARCHAR(50)`, NOT NULL).
* **`salary_min`**, **`salary_max`** (`NUMERIC(12, 2)`): Valores numéricos precisos para filtrado por rangos.
* **`work_type`** (`ENUM`: `'remote'`, `'hybrid'`, `'on_site'`).
* **`status`** (`ENUM`: `'active'`, `'closed'`, `'draft'`).
* **`location_point`** (`GEOMETRY(Point, 4326)`): Coordenadas geográficas (Longitud, Latitud) en el sistema WGS 84 para consultas espaciales con PostGIS.

### 3.5 `applications` (Postulaciones)

* **`id`** (`UUID`, PK).
* **`job_id`** (`UUID`, FK, NOT NULL).
* **`candidate_id`** (`UUID`, FK, NOT NULL).
* **`status`** (`ENUM`: `'pending'`, `'reviewing'`, `'interviewed'`, `'accepted'`, `'rejected'`).
* **`cover_letter`** (`TEXT`).
* **`created_at`** (`TIMESTAMPTZ`).

### 3.6 `conversations` & `chat_participants` (Chat)

* **`conversations.id`** (`UUID`, PK).
* **`conversations.application_id`** (`UUID`, FK, UNIQUE, NULLABLE): Vinculación 1:1 opcional con una candidatura. Restringe la creación de chats spam, obligando a que exista un contexto de postulación previo.
* **`chat_participants`** (`conversation_id` FK, `user_id` FK, PK Compuesta): Tabla de uniones N:M. Permite escalar la mensajería desde un chat individual (2 usuarios) hasta salas de entrevistas múltiples con varios miembros del equipo de RRHH.

### 3.7 `messages` (Mensajes de Chat)

* **`id`** (`UUID`, PK).
* **`conversation_id`** (`UUID`, FK, NOT NULL).
* **`sender_id`** (`UUID`, FK, NOT NULL).
* **`content`** (`TEXT`, NOT NULL).
* **`is_read`** (`BOOLEAN`, DEFAULT `FALSE`).
* **`created_at`** (`TIMESTAMPTZ`, DEFAULT `CURRENT_TIMESTAMP`).

---

## 4. Relaciones y Justificación de Decisiones de Diseño (*Relationships & Justification*)

### 4.1 Desacoplamiento de Usuarios y Perfiles (1:1)

Se decidió separar la entidad `users` de `profiles`. La tabla `users` contiene únicamente la información crítica de autenticación y seguridad con un tamaño de fila (*row size*) pequeño. Esto maximiza la densidad de páginas en memoria caché de PostgreSQL al autenticar peticiones HTTP, evitando cargar texto pesado como biografías o rutas de archivos que solo se requieren al consultar el perfil del usuario.

### 4.2 Restricción Contextual del Chat (1:1 entre Postulación y Conversación)

Para solucionar el problema de mensajes no deseados, la tabla `conversations` almacena una clave foránea única hacia `applications`. Esta restricción de unicidad (`UNIQUE CONSTRAINT`) a nivel de base de datos impide a nivel de motor que un reclutador y un candidato abran más de un canal de chat activo para la misma oferta laboral, manteniendo la integridad lógica sin depender únicamente de validaciones en la capa de aplicación.

### 4.3 Abstracción N:M en Chat (`chat_participants`)

En lugar de añadir los campos `candidate_id` y `employer_id` directamente en la tabla `conversations`, se implementó el patrón de diseño de participantes mediante una tabla intermedia. Esta decisión otorga flexibilidad arquitectónica: si una empresa requiere incorporar a un segundo entrevistador o líder técnico a la conversación, la estructura soporta participantes adicionales sin requerir cambios de esquema o migraciones en la base de datos.

### 4.4 Uso de JSONB para Habilidades (*Skills*)

A pesar de la estricta regla de Primera Formas Normal (1NF) contra atributos multivaluados, se eligió `JSONB` para el campo `skills` en `profiles`. Esta denormalización intencional se justifica porque las habilidades son un conjunto léxico de etiquetas sin atributos propios. Crear una relación N:M con tablas `skills` y `profile_skills` añadiría una sobrecarga de *JOINs* costosos en cada lectura del CV sin aportar beneficios significativos de integridad.

---

## 5. Optimizaciones (*Optimizations*)

### 5.1 Estrategia de Indexación

Para mitigar cuellos de botella en las lecturas, se definieron los siguientes índices específicos:

1. **Índice B-Tree Compuesto en Búsqueda de Vacantes:**
```sql
CREATE INDEX idx_jobs_search ON jobs (status, category, created_at DESC);
```

*Justificación:* Las consultas en el *feed* principal de la app filtran por vacantes activas de una categoría y las ordenan por fecha de publicación. Un índice compuesto cubre el filtrado y el ordenamiento sin necesidad de hacer lecturas completas de la tabla (*Seq Scan*).

2. **Índice GiST para Búsqueda Geoespacial:**
```sql
CREATE INDEX idx_jobs_location ON jobs USING GIST (location_point);
```

*Justificación:* Utiliza árboles de búsqueda espacial (R-Tree / GiST) para resolver consultas de radio de distancia (ej: `ST_DWithin`) en tiempo logarítmico $O(\log N)$.

3. **Índice Parcial en Mensajes No Leídos:**
```sql
CREATE INDEX idx_messages_unread ON messages (conversation_id, recipient_id) 
WHERE is_read = FALSE;
```

*Justificación:* Reduce drásticamente el tamaño del índice al incluir únicamente los mensajes no leídos, optimizando la consulta de badges de notificaciones pendientes en la interfaz.

### 5.2 Particionamiento de Datos (Planes Futuros para `messages`)

Debido a que la tabla `messages` exhibe un comportamiento de crecimiento lineal con pendiente alta, el diseño prevé el particionamiento declarativo por rango basado en el campo `created_at` (particiones mensuales/anuales). Esto permite la desvinculación eficiente de chats antiguos (*table truncation*) sin generar bloqueos globales de tabla (*lock-free archiving*).

---

## 6. Limitaciones del Sistema (*Limitations*)

1. **Escalabilidad Horizontal del Chat Relacional:**
Aunque PostgreSQL maneja eficientemente el almacenamiento de mensajes, bajo escenarios de concurrencia masiva (decenas de miles de mensajes por segundo mediante WebSockets), las operaciones de escritura continua en `messages` pueden generar saturación de buffer de escritura e invalidación frecuente de páginas en disco.
* *Mitigación:* Para volúmenes hiper-escalables, el subsistema de chat deberá desacoplarse del motor SQL principal hacia una base de datos no relacional orientada a documentos (MongoDB/Cassandra) o una capa en memoria (*Redis Pub/Sub*).

2. **Costo de Consultas de Texto Completo (*Full-Text Search*):**
Las búsquedas por coincidencias de texto en títulos y descripciones de trabajo usando `ILIKE '%termino%'` sufren de escasa eficiencia al ignorar índices B-Tree estándar.
* *Mitigación:* Se requiere migrar dichas búsquedas hacia índices GIN con vectores tsvector (`to_tsvector('spanish', description)`) o integrar un motor de búsqueda dedicado como Meilisearch.

3. **Acoplamiento de Esquema en Habilidades:**
El uso de `JSONB` para las habilidades imposibilita la aplicación de restricciones de clave foránea a nivel de base de datos sobre los nombres de las tecnologías, delegando completamente la validación y sanitización de etiquetas a la capa del servidor API.

## Video Pagina

https://youtu.be/aJgSXRMDmOw

https://youtube.com/shorts/NbR4zSGgvXQ?feature=share