"""Debug form creation"""
import requests, re, time

s = requests.Session()
BASE = "http://127.0.0.1:8765"

r = s.get(f"{BASE}/")
csrf = re.search(r'name="csrf_token"\s+value="([^"]+)"', r.text).group(1)
s.post(f"{BASE}/login",
    data={"username": "doctor", "password": "test123", "csrf_token": csrf},
    allow_redirects=False)

r = s.get(f"{BASE}/doctor")
csrf = re.search(r'name="csrf_token"\s+value="([^"]+)"', r.text).group(1)
s.post(f"{BASE}/doctor/links", data={"csrf_token": csrf}, allow_redirects=False)

r = s.get(f"{BASE}/doctor")
tokens = re.findall(r"/patient/([A-Za-z0-9_-]+)", r.text)
print(f"Tokens found: {len(tokens)}")
tok = tokens[-1]
print(f"Using token: {tok}")

r = s.get(f"{BASE}/patient/{tok}")
print(f"Patient form status: {r.status_code}")
csrf = re.search(r'name="csrf_token"\s+value="([^"]+)"', r.text).group(1)

ts = str(time.time()).replace(".", "")
ident = f"1-{ts[-5]}-{ts[-4:]}"
name = f"Test D {ts[-6:]}"
print(f"Ident: {ident}, Name: {name}")

front_data = b"FRONT-" + ts.encode()
back_data = b"BACK-" + ts.encode()
files = {
    "cedula_front": ("f.jpg", front_data, "image/jpeg"),
    "cedula_back": ("b.jpg", back_data, "image/jpeg"),
}
data = {
    "csrf_token": csrf,
    "nationality": "Costarricense",
    "id_type": "cedula",
    "identification": ident,
    "full_name": name,
    "whatsapp": "88888888",
    "email": f"{ts}@t.com",
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
r = s.post(f"{BASE}/patient/{tok}/submit", data=data, files=files, allow_redirects=False)
print(f"Submit status: {r.status_code}")
if r.status_code != 303:
    print(f"Response: {r.text[:500]}")
else:
    print(f"Location: {r.headers.get('Location', '')}")
