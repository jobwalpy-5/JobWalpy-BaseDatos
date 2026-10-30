"""
Crea (o te deja crear) una cuenta de administrador.

Uso, desde la carpeta que tiene main.py (biblioteca/):
    python crear_admin.py

Te pregunta nombre, correo, nivel y contraseña. La contraseña NO se ve al
escribirla y NO se guarda en ningún archivo: solo se guarda su hash.
"""
import getpass
import re
import sys

from dotenv import load_dotenv

load_dotenv()

from dominio import servicios as db  # noqa: E402  (después de cargar el .env)

REGLA = re.compile(r'^(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{10,}$')


def main() -> None:
    print("— Crear administrador de JobWalpy —")
    nombre = input("Nombre: ").strip()
    correo = input("Correo (distinto al de tu cuenta normal): ").strip()
    nivel = input("Nivel [super_admin / moderador / soporte] (Enter = moderador): ").strip() or "moderador"
    clave = getpass.getpass("Contraseña (mín. 10, con mayúscula, número y símbolo): ")
    clave2 = getpass.getpass("Repite la contraseña: ")

    if clave != clave2:
        sys.exit("✗ Las contraseñas no coinciden. No se creó nada.")
    if not REGLA.match(clave):
        sys.exit("✗ La contraseña debe tener 10+ caracteres, una mayúscula, un número y un símbolo.")
    try:
        db.crear_admin(nombre, correo, clave, nivel)
    except ValueError as e:
        sys.exit(f"✗ {e}")
    print(f"✓ Administrador creado ({nivel}). Entra por /admin/login con ese correo y esa contraseña.")


if __name__ == "__main__":
    main()
