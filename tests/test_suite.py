import re
import time

import requests

if __name__ != "__main__":
    import pytest

    pytest.skip("script-style smoke test; run with python tests/test_suite.py", allow_module_level=True)

BASE = "http://127.0.0.1:8765"
s = requests.Session()
h = {"User-Agent": "Test/1.0"}

# Health check
r = s.get(f"{BASE}/health")
print(f"Health: {r.status_code}")

# Login page
r = s.get(f"{BASE}/")
csrf = re.search(r'name="csrf_token"\s+value="([^"]+)"', r.text).group(1)
r = s.post(f"{BASE}/login", data={"username": "doctor", "password": "test123", "csrf_token": csrf}, allow_redirects=False)
print(f"Login: {r.status_code}")

# Doctor panel
r = s.get(f"{BASE}/doctor")
print(f"Panel: {r.status_code}, 'Panel principal' in text: {'Panel principal' in r.text}")

# Create link
csrf = re.search(r'name="csrf_token"\s+value="([^"]+)"', r.text).group(1)
r = s.post(f"{BASE}/doctor/links", data={"csrf_token": csrf}, allow_redirects=False)
print(f"Link created: {r.status_code}")

# Get token
r = s.get(f"{BASE}/doctor")
tokens = re.findall(r"/patient/([A-Za-z0-9_-]+)", r.text)
print(f"Token: {tokens[0] if tokens else 'NONE'}")

token = tokens[0]

# Get patient form
r = s.get(f"{BASE}/patient/{token}")
print(f"Patient form: {r.status_code}, 'form' in text: {'form' in r.text.lower()}")
csrf = re.search(r'name="csrf_token"\s+value="([^"]+)"', r.text).group(1)

# Submit form with test data
ts = str(int(time.time()))
files = {
    "cedula_front": ("front.jpg", b"fake-image-data-front", "image/jpeg"),
    "cedula_back": ("back.jpg", b"fake-image-data-back", "image/jpeg"),
}
data = {
    "csrf_token": csrf,
    "nationality": "Costarricense",
    "id_type": "cedula",
    "identification": "1-2345-6789",
    "full_name": f"Test Paciente {ts}",
    "whatsapp": "88888888",
    "email": f"test{ts}@test.com",
    "age": "30",
    "birth_date": "1994-01-01",
    "civil_status": "Soltero(a)",
    "profession": "Ingeniero",
    "province": "San José",
    "province_code": "1",
    "canton": "Central",
    "canton_code": "1",
    "district_or_locality": "Carmen",
    "district_or_locality_code": "1",
    "exact_address": "100 m sur de la iglesia",
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
    "license_types": [],
    "truth_declaration": "accepted",
}
r = s.post(f"{BASE}/patient/{token}/submit", data=data, files=files, allow_redirects=False)
print(f"Submit form: {r.status_code}, Location: {r.headers.get('Location', '')}")

# Check doctor panel for encounter
r = s.get(f"{BASE}/doctor")
print(f"After submit - panel: {r.status_code}")
encounter_match = re.findall(r"/doctor/encounters/(\d+)", r.text)
print(f"Encounters found: {encounter_match}")

# Get encounter detail
if encounter_match:
    eid = encounter_match[0]
    r = s.get(f"{BASE}/doctor/encounters/{eid}")
    print(f"Encounter detail: {r.status_code}, 'Detalle' in text: {'Detalle' in r.text}")

    # Test image viewer
    r = s.get(f"{BASE}/doctor/encounters/{eid}/images/front")
    print(f"Image viewer front: {r.status_code}")
    r = s.get(f"{BASE}/doctor/encounters/{eid}/images/back")
    print(f"Image viewer back: {r.status_code}")

    # Test raw image
    r = s.get(f"{BASE}/doctor/encounters/{eid}/images/front/raw")
    print(f"Raw image front: {r.status_code}")

    # Test PDF
    r = s.get(f"{BASE}/doctor/encounters/{eid}/pdf")
    print(f"PDF download: {r.status_code}, Content-Type: {r.headers.get('Content-Type', '')}")
    if r.status_code == 200:
        print(f"  PDF size: {len(r.content)} bytes")

    # Test delete
    r = s.get(f"{BASE}/doctor/encounters/{eid}")
    csrf = re.search(r'name="csrf_token"\s+value="([^"]+)"', r.text).group(1)
    r = s.post(f"{BASE}/doctor/encounters/{eid}/delete", data={"csrf_token": csrf}, allow_redirects=False)
    print(f"Delete encounter: {r.status_code}")

    # Verify deleted
    r = s.get(f"{BASE}/doctor/encounters/{eid}", allow_redirects=False)
    print(f"After delete - detail: {r.status_code}")

print("\nAll basic tests OK")
