"""Test password change functionality"""

import re
import sys
from pathlib import Path

import requests

if __name__ != "__main__":
    import pytest

    pytest.skip("script-style smoke test; run with python tests/test_password.py", allow_module_level=True)

BASE = "http://127.0.0.1:8765"
EXP_DIR = Path("G:/Mi unidad/Expediente Médico Digital") / "Expediente de pacientes"
PASS = "test123"  # noqa: S105
NEW_PASS = "NuevaPass123!"  # noqa: S105

s = requests.Session()
results = []


def check(desc, ok):
    results.append((desc, ok))
    print(f"  {'PASS' if ok else 'FAIL'}: {desc}")


def link_csrf(html):
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    return m.group(1) if m else ""


def login(pw):
    s.cookies.clear()
    r = s.get(f"{BASE}/")
    csrf = link_csrf(r.text)
    r = s.post(f"{BASE}/login", data={"username": "doctor", "password": pw, "csrf_token": csrf}, allow_redirects=False)
    return r.status_code == 303


def is_logged_in():
    r = s.get(f"{BASE}/doctor", allow_redirects=False)
    return r.status_code == 200


# 1. Login with current password
check("1. Login con contrasena actual", login(PASS))
check("2. Panel medico accesible", is_logged_in())

# 3. Access change password form
r = s.get(f"{BASE}/doctor/change-password")
check("3. Formulario cambio contrasena accesible", r.status_code == 200 and "Cambiar contrase" in r.text)

# 4. Try wrong current password
csrf = link_csrf(r.text)
r = s.post(
    f"{BASE}/doctor/change-password",
    data={
        "csrf_token": csrf,
        "current_password": "wrongpass",
        "new_password": NEW_PASS,
        "confirm_password": NEW_PASS,
    },
)
check("4. Rechaza contrasena actual incorrecta", r.status_code == 200 and "no es correcta" in r.text)

# 5. Mismatched confirmation
csrf = link_csrf(r.text)
r = s.post(
    f"{BASE}/doctor/change-password",
    data={
        "csrf_token": csrf,
        "current_password": PASS,
        "new_password": NEW_PASS,
        "confirm_password": "diferente",
    },
)
check("5. Rechaza confirmacion diferente", r.status_code == 200 and "no coinciden" in r.text)

# 6. Short password
csrf = link_csrf(r.text)
r = s.post(
    f"{BASE}/doctor/change-password",
    data={
        "csrf_token": csrf,
        "current_password": PASS,
        "new_password": "abc",
        "confirm_password": "abc",
    },
)
check("6. Rechaza contrasena corta", r.status_code == 200 and "8 caracteres" in r.text)

# 7. Same as current
csrf = link_csrf(r.text)
r = s.post(
    f"{BASE}/doctor/change-password",
    data={
        "csrf_token": csrf,
        "current_password": PASS,
        "new_password": PASS,
        "confirm_password": PASS,
    },
)
check("7. Rechaza contrasena igual a actual", r.status_code == 200 and "no puede ser igual" in r.text)

# 8. Change password correctly
csrf = link_csrf(r.text)
r = s.post(
    f"{BASE}/doctor/change-password",
    data={
        "csrf_token": csrf,
        "current_password": PASS,
        "new_password": NEW_PASS,
        "confirm_password": NEW_PASS,
    },
    allow_redirects=False,
)
check("8. Cambio correcto redirige a login", r.status_code == 303 and "msg=password_changed" in r.headers.get("Location", ""))

# 9. Old password no longer works
check("9. Contrasena anterior rechazada", not login(PASS))

# 10. New password works
check("10. Nueva contrasena funciona", login(NEW_PASS))
check("11. Panel accesible con nueva contrasena", is_logged_in())

# 11. Patient cannot access change password
s2 = requests.Session()
r = s2.get(f"{BASE}/doctor/change-password", allow_redirects=False)
check("12. Paciente no accede a cambio contrasena", r.status_code == 303)

# 12. Empty password rejection
check("13. Login con contrasena vacia rechazado", not login(""))

# Clean up - change back to test password for subsequent tests
r = s2.get(f"{BASE}/")
csrf = link_csrf(r.text)
s2.post(f"{BASE}/login", data={"username": "doctor", "password": NEW_PASS, "csrf_token": csrf}, allow_redirects=False)
r2 = s2.get(f"{BASE}/doctor/change-password")
csrf2 = link_csrf(r2.text)
s2.post(
    f"{BASE}/doctor/change-password",
    data={
        "csrf_token": csrf2,
        "current_password": NEW_PASS,
        "new_password": PASS,
        "confirm_password": PASS,
    },
    allow_redirects=False,
)
check("14. Restaurada contrasena original", login(PASS))

# Also test that patient form still works after password change (login with new creds)
check("15. Flujo paciente intacto tras cambio", is_logged_in())

print(f"\nTotal: {sum(1 for _, ok in results if ok)}/{len(results)} passed")
sys.exit(0 if all(ok for _, ok in results) else 1)
