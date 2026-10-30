"""


Los lanza el repositorio (cuando la base de datos rechaza un duplicado) o el
servicio (cuando una regla no se cumple), y los atrapan las rutas para
mostrarle un mensaje claro a la persona.
"""


class EmailYaRegistradoError(Exception):
    """Se lanza cuando alguien intenta registrarse con un email que ya existe."""


class TaxIdYaRegistradoError(Exception):
    """Se lanza cuando el NIT/RUT/RFC de la empresa ya está registrado por otra cuenta."""


class YaAplicasteError(Exception):
    """Se lanza si la misma persona intenta aplicar dos veces al mismo empleo."""


class DocumentoYaRegistradoError(Exception):
    """Se lanza cuando el documento de identidad ya pertenece a una cuenta."""
