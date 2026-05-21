"""
smoke_test.py — Prueba rápida del flujo principal del sistema.

Ejecuta las validaciones usando TestClient de FastAPI.
Requiere httpx (incluido en requirements-dev.txt).

Uso:
    pip install -r requirements-dev.txt
    python tools/smoke_test.py
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("APP_ENV", "local")
os.environ.setdefault("APP_SECRET_KEY", "smoke-test-secret-key")
os.environ.setdefault("DOCTOR_USERNAME", "doctor")
os.environ.setdefault("DOCTOR_PASSWORD", "SmokeTest123!")
os.environ.setdefault("BASE_URL", "http://localhost:8765")
os.environ.setdefault("APP_COOKIE_SECURE", "false")
os.environ.setdefault("TSE_LOOKUP_ENABLED", "false")

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.main import DB_PATH, DEFAULT_PASSWORD, DOCTOR_USERNAME, app  # noqa: E402

try:
    from fastapi.testclient import TestClient
except ImportError:
    print("ERROR: Se requiere httpx. Instale con: pip install -r requirements-dev.txt")
    sys.exit(1)

client = TestClient(app)

PASS = 0
FAIL = 0
TOTAL = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL, TOTAL
    TOTAL += 1
    if condition:
        print(f"  [PASS] {label}")
        PASS += 1
    else:
        msg = f" | {detail}" if detail else ""
        print(f"  [FAIL] {label}{msg}")
        FAIL += 1


def get_csrf(html: str) -> str:
    import re

    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    return m.group(1) if m else ""


def main() -> int:
    global PASS, FAIL, TOTAL

    print("=== smoke_test: Prueba rápida del sistema ===")
    print(f"DB: {DB_PATH}")
    print()

    # 1. Login admin
    r = client.get("/login")
    check("GET /login", r.status_code == 200)

    csrf = get_csrf(r.text)
    r = client.post("/login", data={"username": DOCTOR_USERNAME, "password": os.environ["DOCTOR_PASSWORD"], "csrf_token": csrf}, follow_redirects=False)
    check("Login admin", r.status_code == 303, f"status={r.status_code}")

    # 2. Panel admin
    r = client.get("/doctor")
    check("GET /doctor (panel)", r.status_code == 200, f"status={r.status_code}")

    # 3. Admin users list
    r = client.get("/doctor/users")
    check("GET /doctor/users (admin only)", r.status_code == 200)

    # 4. DOCTOR_USERNAME tiene role=admin, is_active=1
    r2 = client.get("/doctor/users")
    check("Lista de usuarios accesible", r2.status_code == 200)

    # 5. Crear médico de prueba
    r = client.get("/doctor/users/new")
    csrf_new = get_csrf(r.text)
    test_doctor = f"smoke_test_dr_{abs(hash('smoke')) % 10000}"
    r = client.post(
        "/doctor/users/new",
        data={
            "csrf_token": csrf_new,
            "username": test_doctor,
            "full_name": "Smoke Test Doctor",
            "role": "doctor",
        },
        follow_redirects=False,
    )
    check(f"Crear médico '{test_doctor}'", r.status_code == 303, f"status={r.status_code}")

    # 6. Médico normal no accede a /doctor/users
    r = client.get("/login")
    csrf_dr = get_csrf(r.text)
    r = client.post("/login", data={"username": test_doctor, "password": DEFAULT_PASSWORD, "csrf_token": csrf_dr}, follow_redirects=False)
    check(f"Login médico '{test_doctor}' con contraseña provisional", r.status_code == 303)

    r = client.get("/doctor/force-change-password")
    csrf_fc = get_csrf(r.text)
    r = client.post("/doctor/force-change-password", data={"csrf_token": csrf_fc, "new_password": "NewPass123!", "confirm_password": "NewPass123!"}, follow_redirects=False)
    check("Cambio obligatorio de contraseña", r.status_code == 303)

    r = client.get("/doctor/users", follow_redirects=False)
    check("Médico normal NO accede a /doctor/users", r.status_code == 303, f"status={r.status_code} (redirige a /doctor)")

    # 7. Crear enlace paciente (remote)
    r = client.get("/doctor")
    csrf_link = get_csrf(r.text)
    r = client.post("/doctor/links", data={"csrf_token": csrf_link}, follow_redirects=False)
    check("Crear enlace paciente", r.status_code == 303, f"status={r.status_code}")
    location = r.headers.get("Location", "")
    token = location.split("/patient/")[-1] if "/patient/" in location else ""
    check("Enlace contiene token válido", len(token) > 20, f"token={token[:30]}...")

    # 8. Formulario presencial
    r = client.get("/doctor")
    csrf_ip = get_csrf(r.text)
    r = client.post("/doctor/forms/in-person", data={"csrf_token": csrf_ip}, follow_redirects=False)
    check("Crear formulario presencial", r.status_code == 303, f"status={r.status_code}")
    ip_location = r.headers.get("Location", "")
    ip_token = ip_location.split("/patient/")[1].split("?")[0] if "/patient/" in ip_location else ""
    check("Token presencial válido", bool(ip_token) and "mode=in_person" in ip_location)

    # 9. Guardar borrador presencial
    r = client.get(f"/patient/{ip_token}?mode=in_person")
    check("Formulario presencial accesible", r.status_code == 200)
    csrf_save = get_csrf(r.text)
    r = client.post(
        f"/patient/{ip_token}/save-draft",
        data={
            "csrf_token": csrf_save,
            "full_name": "Paciente Smoke",
            "identification": "1-1234-5678",
            "whatsapp": "88888888",
            "email": "smoke@test.com",
        },
    )
    check("Guardar borrador", r.status_code == 303, f"status={r.status_code}")

    # 10. Ver borrador en panel
    r = client.get("/doctor")
    check("Panel médico accesible tras borrador", r.status_code == 200)
    check("Borrador visible en panel", "incompleto" in r.text.lower() or "Paciente Smoke" in r.text)

    # 11. Completar formulario presencial
    r = client.get(f"/patient/{ip_token}?mode=in_person")
    csrf_submit = get_csrf(r.text)
    pid = f"9-{abs(hash('smoke_final')) % 10000:04d}-{abs(hash('smoke_final2')) % 10000:04d}"
    from io import BytesIO

    fake_jpeg = BytesIO(
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \"#\x1c\x1c(7),\x01\a\a\a\n\x08\n\x13\r\n\r\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04\x04\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x11\x04\x12\x05!1A\x06\x13Qa\x07\"q\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1\xf0$3br\x82\t\n\x16\x17\x18\x19\x1a%&'()*456789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff\xc0\x00\x0b\x08\x01\x01\x01\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\a\b\t\n\x0b\xff\xc4\x00\xb1\x10\x00\x02\x01\x03\x04\x01\x03\x04\x02\x04\x03\x05\x05\x04\x04\x00\x00\x00\x00\x00\x00\x01\x02\x03\x11\x04\x12!1\x06\x13Qa\x07\"q\x142\x81\x91\xa1\x08\x14B\xb1\xc1\x15R\xd1\xf0$3br\x82\t\n\x16\x17\x18\x19\x1a%&'()*456789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff\xda\x00\x08\x01\x01\x00\x00?\x00\x08\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\xff\xd9"
    )
    r = client.post(
        f"/patient/{ip_token}/submit",
        data={
            "csrf_token": csrf_submit,
            "nationality": "Costarricense",
            "id_type": "cedula",
            "identification": pid,
            "full_name": "Paciente Smoke Final",
            "whatsapp": "88888888",
            "email": "final@smoke.com",
            "age": "30",
            "birth_date": "1994-01-01",
            "civil_status": "S",
            "profession": "Ingeniero",
            "province": "San José",
            "province_code": "1",
            "canton": "Central",
            "canton_code": "1",
            "district_or_locality": "Carmen",
            "district_or_locality_code": "1",
            "exact_address": "200 m este",
            "organ_donor": "No",
            "has_illness": "No",
            "illnesses": "",
            "treatments": "",
            "smokes": "No",
            "smoke_frequency": "",
            "smoke_product": "",
            "drinks": "No",
            "drink_frequency": "",
            "uses_drugs": "No",
            "drug_type": "",
            "drug_frequency": "",
            "weight": "70",
            "height": "175",
            "uses_glasses": "No",
            "glasses_use": "",
            "laterality": "Diestro(a)",
            "license_types": "",
            "truth_declaration": "accepted",
        },
        files={"cedula_front": ("f.jpg", fake_jpeg, "image/jpeg"), "cedula_back": ("b.jpg", fake_jpeg, "image/jpeg")},
        follow_redirects=False,
    )
    check("Completar formulario presencial", r.status_code == 303, f"status={r.status_code}")

    # 12. Logout y login como admin para verificar
    r = client.get("/login")
    csrf_admin = get_csrf(r.text)
    r = client.post("/login", data={"username": DOCTOR_USERNAME, "password": os.environ["DOCTOR_PASSWORD"], "csrf_token": csrf_admin}, follow_redirects=False)
    check("Re-login como admin", r.status_code == 303)

    r = client.get("/doctor")
    check("Panel admin: formulario completado", "Paciente Smoke Final" in r.text or "Completado" in r.text)

    # 13. Verificar /health
    r = client.get("/health")
    check("Health check", r.status_code == 200)

    print()
    print(f"=== Resultados: {PASS}/{TOTAL} pruebas pasaron ===")
    if FAIL:
        print(f"\n{FAIL} prueba(s) fallaron. Revise los detalles arriba.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
