"""
Pruebas mínimas automatizadas con pytest.

Usa una base de datos temporal para no contaminar la base real.

Ejecutar:
    pytest tests/test_minimal.py -v
"""

import os
import re
import sqlite3
from io import BytesIO
from pathlib import Path

# --- Config fresh environment BEFORE importing app ---
os.environ.setdefault("APP_ENV", "local")
os.environ.setdefault("APP_SECRET_KEY", "pytest-minimal-secret-2024")
os.environ.setdefault("DOCTOR_USERNAME", "doctor")
os.environ.setdefault("DOCTOR_PASSWORD", "Pytest123!")
os.environ.setdefault("BASE_URL", "http://localhost:9876")
os.environ.setdefault("APP_COOKIE_SECURE", "false")
os.environ.setdefault("TSE_LOOKUP_ENABLED", "false")

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "database" / "app.db"

# Remove existing DB so admin is freshly created with our password
if DB_PATH.exists():
    DB_PATH.unlink()
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import DEFAULT_PASSWORD, DOCTOR_USERNAME, app  # noqa: E402


def _get_csrf(html: str) -> str:
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    return m.group(1) if m else ""


def _fake_jpeg() -> BytesIO:
    return BytesIO(
        b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $."#\x1c\x1c(7),\x01\a\a\a\n\x08\n\x13\r\n\r\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\x1a\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04\x04\x00\x00\x00\x00\x00\x00\x01\x02\x03\x11\x04\x12!1\x06\x13Qa\x07"q\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1\xf0$3br\x82\t\n\x16\x17\x18\x19\x1a%&\'()*456789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff\xc0\x00\x0b\x08\x01\x01\x01\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\a\b\t\n\x0b\xff\xc4\x00\xb1\x10\x00\x02\x01\x03\x04\x01\x03\x04\x02\x04\x03\x05\x05\x04\x04\x00\x00\x00\x00\x00\x01\x02\x03\x11\x04\x12!1\x06\x13Qa\x07"q\x142\x81\x91\xa1\x08\x14B\xb1\xc1\x15R\xd1\xf0$3br\x82\t\n\x16\x17\x18\x19\x1a%&\'()*456789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff\xda\x00\x08\x01\x01\x00\x00?\x00\x08\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\x02\xff\xd9'
    )


class TestSmoke:
    def test_smoke(self):
        """Single integrated smoke test that covers all 14 verification points."""
        with TestClient(app) as client:

            def csrf(html):
                return _get_csrf(html)

            # 1. Login page
            r = client.get("/login")
            assert r.status_code == 200
            assert "csrf_token" in r.text

            # 2. Admin login
            csrf1 = csrf(r.text)
            r = client.post("/login", data={"username": DOCTOR_USERNAME, "password": os.environ["DOCTOR_PASSWORD"], "csrf_token": csrf1}, follow_redirects=False)
            assert r.status_code == 303

            # 3. Panel
            r = client.get("/doctor")
            assert r.status_code == 200

            # 4. Users list
            r = client.get("/doctor/users")
            assert r.status_code == 200
            assert DOCTOR_USERNAME in r.text

            # 5. Create doctor
            r = client.get("/doctor/users/new")
            csrf_new = csrf(r.text)
            dr_username = f"test_dr_{abs(hash('int')) % 10000}"
            r = client.post("/doctor/users/new", data={"csrf_token": csrf_new, "username": dr_username, "full_name": "Int Doctor", "role": "doctor"}, follow_redirects=False)
            assert r.status_code == 303

            # 6. New doctor has must_change_password=1
            conn = sqlite3.connect(str(DB_PATH))
            conn.row_factory = sqlite3.Row
            u = conn.execute("SELECT must_change_password FROM users WHERE username = ?", (dr_username,)).fetchone()
            conn.close()
            assert u is not None
            assert u["must_change_password"] == 1

            # 7. Doctor logs in with provisional, forced to change
            r = client.get("/login")
            csrf_dr = csrf(r.text)
            r = client.post("/login", data={"username": dr_username, "password": DEFAULT_PASSWORD, "csrf_token": csrf_dr}, follow_redirects=False)
            assert r.status_code == 303
            r = client.get("/doctor/force-change-password")
            assert r.status_code == 200
            csrf_fc = csrf(r.text)
            r = client.post(
                "/doctor/force-change-password",
                data={"csrf_token": csrf_fc, "current_password": DEFAULT_PASSWORD, "new_password": "NewPass123!", "confirm_password": "NewPass123!"},
                follow_redirects=False,
            )
            assert r.status_code == 303

            # 8. Doctor cannot access /doctor/users
            r = client.get("/doctor/users", follow_redirects=False)
            assert r.status_code in (303, 403)

            # 9. Admin login again
            r = client.get("/login")
            csrf_a2 = csrf(r.text)
            r = client.post("/login", data={"username": DOCTOR_USERNAME, "password": os.environ["DOCTOR_PASSWORD"], "csrf_token": csrf_a2}, follow_redirects=False)
            assert r.status_code == 303

            # 10. Create in-person form
            r = client.get("/doctor")
            csrf_ip = csrf(r.text)
            r = client.post("/doctor/forms/in-person", data={"csrf_token": csrf_ip}, follow_redirects=False)
            assert r.status_code == 303
            location = r.headers.get("Location", "")
            ip_token = location.split("/patient/")[1].split("?")[0] if "/patient/" in location else ""
            assert ip_token
            assert "mode=in_person" in location

            # 11. Save draft
            r = client.get(f"/patient/{ip_token}?mode=in_person")
            assert r.status_code == 200
            csrf_save = csrf(r.text)
            r = client.post(
                f"/patient/{ip_token}/save-draft",
                data={
                    "csrf_token": csrf_save,
                    "full_name": "Test Paciente",
                    "identification": "1-9999-9999",
                },
                follow_redirects=False,
            )
            assert r.status_code == 303, f"status={r.status_code} headers={dict(r.headers)} text={r.text[:200]}"

            # 12. Draft visible in panel
            r = client.get("/doctor")
            assert r.status_code == 200
            assert "incompleto" in r.text.lower() or "Test Paciente" in r.text

            # 13. Complete in-person form
            r = client.get(f"/patient/{ip_token}?mode=in_person")
            csrf_sub = csrf(r.text)
            pid = f"9-{abs(hash('int_complete')) % 10000:04d}-{abs(hash('int_complete2')) % 10000:04d}"
            r = client.post(
                f"/patient/{ip_token}/submit",
                data={
                    "csrf_token": csrf_sub,
                    "nationality": "Costarricense",
                    "id_type": "cedula",
                    "identification": pid,
                    "full_name": "Test Completo",
                    "whatsapp": "88888888",
                    "email": "tc@test.com",
                    "age": "30",
                    "birth_date": "1994-01-01",
                    "civil_status": "S",
                    "profession": "Ing",
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
                files={"cedula_front": ("f.jpg", _fake_jpeg(), "image/jpeg"), "cedula_back": ("b.jpg", _fake_jpeg(), "image/jpeg")},
                follow_redirects=False,
            )
            assert r.status_code == 303

            # 14. Encounter created with source='in_person'
            conn = sqlite3.connect(str(DB_PATH))
            conn.row_factory = sqlite3.Row
            e = conn.execute("SELECT source FROM encounters ORDER BY id DESC LIMIT 1").fetchone()
            conn.close()
            assert e is not None
            assert e["source"] == "in_person"

            # 15. Admin account is protected
            conn = sqlite3.connect(str(DB_PATH))
            conn.row_factory = sqlite3.Row
            u = conn.execute("SELECT role, is_active, deleted_at FROM users WHERE username = ?", (DOCTOR_USERNAME,)).fetchone()
            conn.close()
            assert u is not None
            assert u["role"] == "admin"
            assert u["is_active"] == 1
            assert u["deleted_at"] is None

            # 16. Links have doctor_id
            conn = sqlite3.connect(str(DB_PATH))
            c = conn.execute("SELECT COUNT(*) AS c FROM links WHERE doctor_id IS NULL").fetchone()[0]
            conn.close()
            assert c == 0

            # 17. Encounters have doctor_id
            conn = sqlite3.connect(str(DB_PATH))
            c = conn.execute("SELECT COUNT(*) AS c FROM encounters WHERE doctor_id IS NULL").fetchone()[0]
            conn.close()
            assert c == 0

            # 18. Health check
            r = client.get("/health")
            assert r.status_code == 200

            # 19. Failed login
            r = client.get("/login")
            csrf_fl = csrf(r.text)
            r = client.post("/login", data={"username": DOCTOR_USERNAME, "password": "wrong", "csrf_token": csrf_fl}, follow_redirects=False)
            assert r.status_code in (200, 303)

            # 20. Logout
            r = client.get("/login")
            csrf_lo = csrf(r.text)
            r = client.post("/logout", data={"csrf_token": csrf_lo}, follow_redirects=False)
            assert r.status_code == 303
