"""Debug script - tests form submission to find the 400 error"""
import requests, re, time, sys

s = requests.Session()
BASE = "http://127.0.0.1:8765"

# Create link and get form
r = s.get(f"{BASE}/")
csrf = re.search(r'name="csrf_token"\s+value="([^"]+)"', r.text).group(1)
s.post(f"{BASE}/login",
    data={"username": "doctor", "password": "test123", "csrf_token": csrf},
    allow_redirects=False)

r = s.get(f"{BASE}/doctor")
csrf = re.search(r'name="csrf_token"\s+value="([^"]+)"', r.text).group(1)
s.post(f"{BASE}/doctor/links", data={"csrf_token": csrf}, allow_redirects=False)

r = s.get(f"{BASE}/doctor")
tok = re.findall(r"/patient/([A-Za-z0-9_-]+)", r.text)[0]

r = s.get(f"{BASE}/patient/" + tok)
csrf = re.search(r'name="csrf_token"\s+value="([^"]+)"', r.text).group(1)

ts = str(int(time.time()))
files = {
    "cedula_front": ("f.jpg", b"FAKEIMAGE", "image/jpeg"),
    "cedula_back": ("b.jpg", b"FAKEIMAGE", "image/jpeg"),
}
data = {
    "csrf_token": csrf,
    "nationality": "Costarricense",
    "id_type": "cedula",
    "identification": "1-2345-6789",
    "full_name": "Test " + ts,
    "whatsapp": "88888888",
    "email": ts + "@t.com",
    "age": "30",
    "birth_date": "1994-01-01",
    "civil_status": "Soltero(a)",
    "profession": "Ing.",
    "province": "San Jos\u00e9",
    "province_code": "1",
    "canton": "Central",
    "canton_code": "1",
    "district_or_locality": "Carmen",
    "district_or_locality_code": "1",
    "exact_address": "100 m sur",
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
}
r = s.post(f"{BASE}/patient/{tok}/submit", data=data, files=files)
print(f"Status: {r.status_code}")
print(f"Response (first 500 chars): {r.text[:500]}")
