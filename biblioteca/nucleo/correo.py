import os
import smtplib
from email.message import EmailMessage


def enviar_correo(destino: str, asunto: str, texto: str) -> bool:
    """Devuelve True si se envió por SMTP, False si solo se imprimió en consola."""
    host = os.environ.get("SMTP_HOST")
    if not host:
        print("\n──────── CORREO SIMULADO (SMTP no configurado) ────────")
        print(f"Para:   {destino}\nAsunto: {asunto}\n\n{texto}")
        print("───────────────────────────────────────────────────────\n")
        return False

    puerto = int(os.environ.get("SMTP_PORT", "587"))
    usuario = os.environ.get("SMTP_USER")
    clave = os.environ.get("SMTP_PASSWORD")

    msg = EmailMessage()
    msg["From"] = os.environ.get("SMTP_FROM") or usuario
    msg["To"] = destino
    msg["Subject"] = asunto
    msg.set_content(texto)

    if puerto == 465:
        with smtplib.SMTP_SSL(host, puerto, timeout=15) as s:
            if usuario:
                s.login(usuario, clave)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, puerto, timeout=15) as s:
            s.starttls()
            if usuario:
                s.login(usuario, clave)
            s.send_message(msg)
    return True
