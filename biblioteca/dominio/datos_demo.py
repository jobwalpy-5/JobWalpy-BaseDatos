"""
CAPA 2 · LÓGICA — datos de las cuentas de demostración.

Solo contiene DATOS (nada de código). Para cambiar un nombre, un teléfono o
agregar una cuenta, se edita aquí. La función que los usa es
servicios.sembrar_cuentas_demo(), y se ejecuta con:  python sembrar_demo.py

⚠ La clave es pública (está en este archivo). Sirve para demos y desarrollo;
  antes de lanzar con usuarios reales, borra estas cuentas:
      DELETE FROM usuarios WHERE id LIKE 'demo\\_%';
"""

CLAVE_DEMO = "demo1234"
FECHA_DEMO = "2026-09-01"

EMPLEADORES = [
    {"id": "demo_emp_1", "email": "carlos@tech.co", "contact_name": "Carlos Gómez",
     "phone": "+573001112233", "company_name": "Tech Solutions", "legal_name": "Tech Legal",
     "tax_id": "900123456-1", "website": "https://tech.co", "address": "Calle 100",
     "industry": "Tech", "size": "Mediano", "location": "Medellín", "bio": "Software",
     "avatar": "TC", "avatar_color": "#6366f1"},
    {"id": "demo_emp_2", "email": "mariana@innova.com", "contact_name": "Mariana Ríos",
     "phone": "+573002223344", "company_name": "Innova Col", "legal_name": "Innova Legal",
     "tax_id": "900234567-2", "website": "https://innova.com", "address": "Carrera 43",
     "industry": "Consultoría", "size": "Grande", "location": "Medellín", "bio": "RRHH",
     "avatar": "IN", "avatar_color": "#0ea5e9"},
    {"id": "demo_emp_3", "email": "alejandro@trans.net", "contact_name": "Alejandro Ruiz",
     "phone": "+573003334455", "company_name": "Transandina", "legal_name": "Trans Legal",
     "tax_id": "900345678-3", "website": "https://trans.net", "address": "Calle 30",
     "industry": "Logística", "size": "Grande", "location": "Bogotá", "bio": "Logística",
     "avatar": "TR", "avatar_color": "#10b981"},
]

BUSCADORES = [
    {"id": "demo_bus_1", "email": "ana.gomez@email.com", "name": "Ana Gómez",
     "phone": "+573111112233", "location": "Medellín", "bio": "Python Developer",
     "skills": ["Python", "FastAPI"], "experience": "1 año", "education": "Sistemas",
     "avatar": "AG", "avatar_color": "#6366f1"},
    {"id": "demo_bus_2", "email": "mateo.perez@email.com", "name": "Mateo Pérez",
     "phone": "+573112223344", "location": "Bogotá", "bio": "Soporte TI",
     "skills": ["Linux", "Redes"], "experience": "2 años", "education": "Técnico",
     "avatar": "MP", "avatar_color": "#0ea5e9"},
    {"id": "demo_bus_3", "email": "lucia.rodriguez@email.com", "name": "Lucía Rodríguez",
     "phone": "+573113334455", "location": "Cali", "bio": "UX/UI Designer",
     "skills": ["Figma", "UI"], "experience": "Prácticas", "education": "Diseño",
     "avatar": "LR", "avatar_color": "#10b981"},
]
