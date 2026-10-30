import os
import smtplib
from email.message import EmailMessage


def enviar_correo(destinatario: str, asunto: str, cuerpo: str) -> bool:
    """
    Envía un correo usando las variables de entorno SMTP.
    Devuelve True si se envía correctamente y False si ocurre un error.
    """
    servidor = os.getenv("SMTP_HOST")
    puerto = int(os.getenv("SMTP_PORT", "587"))
    usuario = os.getenv("SMTP_USER")
    contrasena = os.getenv("SMTP_PASSWORD")
    remitente = os.getenv("SMTP_FROM") or usuario

    if not all([servidor, usuario, contrasena, remitente]):
        print("ERROR: Faltan variables SMTP para enviar el correo.")
        return False

    mensaje = EmailMessage()
    mensaje["From"] = remitente
    mensaje["To"] = destinatario
    mensaje["Subject"] = asunto
    mensaje.set_content(cuerpo)

    try:
        with smtplib.SMTP(servidor, puerto, timeout=20) as smtp:
            smtp.starttls()
            smtp.login(usuario, contrasena)
            smtp.send_message(mensaje)

        return True

    except Exception as error:
        print(f"ERROR al enviar el correo: {error}")
        return False