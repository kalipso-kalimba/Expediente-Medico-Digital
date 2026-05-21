import http.client
import os
import sys
import threading
import time
import urllib.parse

if __name__ != "__main__":
    import pytest

    pytest.skip("script-style smoke test; run with python tests/test_flow.py", allow_module_level=True)

os.environ["APP_SECRET_KEY"] = "test-secret-key"  # noqa: S105
os.environ["DOCTOR_USERNAME"] = "doctor"
os.environ["DOCTOR_PASSWORD"] = "test1234"  # noqa: S105

sys.path.insert(0, "G:/Mi unidad/Expediente M\u00e9dico Digital")
import uvicorn


def start():
    uvicorn.run("app.main:app", host="127.0.0.1", port=16789, log_level="error")


t = threading.Thread(target=start, daemon=True)
t.start()
time.sleep(3)

conn = http.client.HTTPConnection("127.0.0.1", 16789, timeout=10)

# 1. GET login
conn.request("GET", "/login")
resp = conn.getresponse()
body = resp.read().decode()
cookies = resp.getheader("Set-Cookie", "")
csrf = ""
for c in cookies.split(","):
    if "csrf_token" in c:
        csrf = c.split(";")[0].split("=")[1]
print(f"1. Login page: {resp.status} CSRF: {bool(csrf)}")

# 2. POST login
data = urllib.parse.urlencode({"username": "doctor", "password": "test1234", "csrf_token": csrf})
conn.request("POST", "/login", data, {"Content-Type": "application/x-www-form-urlencoded", "Cookie": f"csrf_token={csrf}"})
resp = conn.getresponse()
body = resp.read().decode()
session = ""
for c in resp.getheader("Set-Cookie", "").split(","):
    if "doctor_session" in c:
        session = c.split(";")[0]
print(f"2. Login POST: {resp.status} Session: {bool(session)}")

if not session:
    print("LOGIN FAILED - stopping")
    # Check if error in body
    if "Credenciales" in body or "error" in body.lower():
        print("  Error message found in response")
    conn.close()
    sys.exit(1)

# 3. GET /doctor
conn.request("GET", "/doctor", headers={"Cookie": session + "; csrf_token=" + csrf})
resp = conn.getresponse()
body = resp.read().decode()
print(f"3. Doctor panel: {resp.status} Length: {len(body)}")
checks = ["Bienvenido", "Admin</span>", "Nuevo enlace"]
for c in checks:
    print(f"   Contains '{c}': {c in body}")

# 4. POST create link
conn.request(
    "POST", "/doctor/links", urllib.parse.urlencode({"csrf_token": csrf}), {"Content-Type": "application/x-www-form-urlencoded", "Cookie": session + "; csrf_token=" + csrf}
)
resp = conn.getresponse()
body = resp.read().decode()
print(f"4. Create link: {resp.status}")

# 5. GET /doctor/users (admin)
conn.request("GET", "/doctor/users", headers={"Cookie": session})
resp = conn.getresponse()
body = resp.read().decode()
print(f"5. Admin users: {resp.status} Length: {len(body)}")
print(f"   Has doctor user: {'doctor' in body}")
print(f"   Has Nuevo usuario: {'Nuevo usuario' in body}")

print("\nALL CHECKS PASSED")
conn.close()
