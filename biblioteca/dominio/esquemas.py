from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime
from zoneinfo import ZoneInfo
import re


# ── REGLAS COMPARTIDAS ────────────────────────────────────────────────────
# Dominios de correo "personales" que NO aceptamos para cuentas de EMPRESA.
# Un buscador de empleo sí puede usar gmail/hotmail sin problema; una empresa
# debe registrarse con un correo de su propio dominio (contacto@tuempresa.com)
# para que haya algo verificable detrás del registro.
BLOCKED_DOMAINS = {"gmail.com", "hotmail.com", "outlook.com", "yahoo.com",
                    "icloud.com", "live.com", "aol.com", "protonmail.com"}


def validar_password_fuerte(v: str) -> str:
    """Regla única de contraseña fuerte, reutilizada por buscadores y empleadores."""
    if len(v) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres.")
    if not re.search(r"[A-Z]", v):
        raise ValueError("La contraseña debe tener al menos una mayúscula.")
    if not re.search(r"\d", v):
        raise ValueError("La contraseña debe tener al menos un número.")
    if len(v) > 128:
        raise ValueError("La contraseña no puede superar 128 caracteres.")
    if not re.search(r"[^A-Za-z0-9\s]", v):
        raise ValueError("La contraseña debe tener al menos un carácter especial.")
    return v


# ── REGISTRO: BUSCADOR DE EMPLEO ───────────────────────────────────────────

class BuscadorCreate(BaseModel):
    """Registro de una persona que busca empleo."""
    first_name: str = Field(min_length=1, max_length=60)
    last_name: str = Field(min_length=1, max_length=60)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    document_type: str
    document_number: str = Field(min_length=5, max_length=20)
    phone: Optional[str] = Field(default="", max_length=30)
    location: Optional[str] = Field(default="", max_length=100)
    bio: Optional[str] = Field(default="", max_length=1000)

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_person_name(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v or not re.fullmatch(r"[A-Za-zÀ-ÿ'’ -]+", v, flags=re.UNICODE):
            raise ValueError("Usa solo letras, espacios, apóstrofes o guiones en nombres y apellidos.")
        return v

    @field_validator("document_type")
    @classmethod
    def validate_document_type(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in {"CC", "CE", "PPT", "PASAPORTE"}:
            raise ValueError("Selecciona un tipo de documento válido.")
        return v

    @field_validator("document_number")
    @classmethod
    def normalize_document_number(cls, v: str) -> str:
        v = re.sub(r"[ .-]", "", v.strip()).upper()
        if not re.fullmatch(r"[A-Z0-9]{5,20}", v):
            raise ValueError("El documento debe tener entre 5 y 20 caracteres alfanuméricos.")
        return v

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        return validar_password_fuerte(v)


# ── REGISTRO: EMPLEADOR (EMPRESA) ──────────────────────────────────────────

class EmpleadorCreate(BaseModel):
    """Registro completo de empleador — datos de contacto + datos legales de la empresa."""
    # Datos del contacto humano que administra la cuenta
    contact_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str
    phone: str = Field(min_length=7, max_length=30)

    # Datos legales de la empresa (esto es lo que la hace "verificable" como real)
    company_name: str = Field(min_length=2, max_length=120)  # Nombre comercial legal_name: str = Field(min_length=2, max_length=160)    # Razón social
    tax_id: str = Field(min_length=5, max_length=30)         # NIT / RFC / RUT — único
    website: Optional[str] = Field(default="", max_length=300)
    address: str = Field(min_length=3, max_length=200)
    industry: str = Field(min_length=2, max_length=80)
    size: Optional[str] = Field(default="", max_length=40)
    location: str = Field(min_length=2, max_length=100)

    @field_validator("email")
    @classmethod
    def corporate_email_required(cls, v: str) -> str:
        domain = v.split("@")[-1].lower()
        if domain in BLOCKED_DOMAINS:
            raise ValueError(
                f"Por seguridad no aceptamos correos de {domain}. "
                "Usa el correo corporativo de tu empresa."
            )
        return v

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        return validar_password_fuerte(v)

    @field_validator("tax_id")
    @classmethod
    def tax_id_required(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("El NIT/RUT/RFC es obligatorio.")
        return v.strip()


# ── LOGIN ──────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ── ACTUALIZAR PERFIL ──────────────────────────────────────────────────────

class BuscadorUpdate(BaseModel):
    name: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    phone: Optional[str] = None
    skills: Optional[list[str]] = None
    experience: Optional[str] = None
    education: Optional[str] = None
    cv_url: Optional[str] = None


class EmpleadorUpdate(BaseModel):
    company_name: Optional[str] = None
    legal_name: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    industry: Optional[str] = None
    size: Optional[str] = None
    location: Optional[str] = None
    bio: Optional[str] = None


# ── SALIDA (lo que se muestra / envía al frontend, NUNCA incluye password) ──

class UserOut(BaseModel):
    id: str
    name: str
    email: str
    role: str  # "buscador" | "empleador"
    location: Optional[str] = ""
    bio: Optional[str] = ""
    avatar: str
    avatar_color: str
    verified: bool = False           # correo verificado (todos los roles)
    verified_company: bool = False   # solo aplica a empleadores (revisión legal)
    # Campos de buscador (vacíos si el usuario es empleador)
    skills: list[str] = Field(default_factory=list)
    experience: Optional[str] = ""
    education: Optional[str] = ""
    # Campos de empleador (vacíos si el usuario es buscador)
    company_name: Optional[str] = ""
    industry: Optional[str] = ""
    size: Optional[str] = ""


# ── JOB MODELS ──────────────────────────────────────────────────────────────

class JobBase(BaseModel):
    title: str
    company: str
    location: str
    type: str
    category: str
    description: str
    requirements: list[str] = []
    benefits: list[str] = []


class JobCreate(JobBase):
    posted_by: str


class JobOut(JobBase):
    id: str
    posted_by: str
    posted_at: str
    active: bool = True


# ── APPLICATION MODELS ──────────────────────────────────────────────────────

class ApplicationCreate(BaseModel):
    job_id: str
    user_id: str
    cover_letter: Optional[str] = ""
    status: str = "pendiente"
    applied_at: str = Field(default_factory=lambda: datetime.now(ZoneInfo("America/Bogota")).date().isoformat())


class ApplicationOut(ApplicationCreate):
    id: str


class ApplicationStatusUpdate(BaseModel):
    status: str = Field(pattern=r"^(pendiente|aceptado|rechazado)$")
