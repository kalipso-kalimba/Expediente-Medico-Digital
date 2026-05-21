"""Debug the form creation flow"""
import requests, re, time

s = requests.Session()
BASE = "http://127.0.0.1:8765"

# Login
r = s.get(f"{BASE}/")
print(f"GET /: status={r.status_code}, cookies={dict(s.cookies)}")

csrf = re.search(r'name="csrf_token"\s+value="([^"]+)"', r.text).group(1)
r = s.post(f"{BASE}/login",
    data={"username": "doctor", "password": "", "csrf_token": csrf},
    allow_redirects=False)
print(f"POST /login: status={r.status_code}, cookies={dict(s.cookies)}")

# Doctor page
r = s.get(f"{BASE}/doctor")
print(f"GET /doctor: status={r.status_code}, cookies={dict(s.cookies)}")
print(f"  'Panel principal' in text: {'Panel principal' in r.text}")

# Create link
csrf = re.search(r'name="csrf_token"\s+value="([^"]+)"', r.text).group(1)
print(f"  CSRF: {csrf[:20]}...")
r = s.post(f"{BASE}/doctor/links", data={"csrf_token": csrf}, allow_redirects=False)
print(f"POST /doctor/links: status={r.status_code}, Location={r.headers.get('Location','')}")

# Doctor page again
r = s.get(f"{BASE}/doctor")
print(f"GET /doctor: status={r.status_code}")
tokens = re.findall(r"/patient/([A-Za-z0-9_-]+)", r.text)
print(f"  Tokens found: {len(tokens)}")
if tokens:
    print(f"  First token: {tokens[0]}")
    print(f"  Last token: {tokens[-1]}")
    
    # Try the patient form
    tok = tokens[0]
    r = s.get(f"{BASE}/patient/{tok}")
    print(f"GET /patient/{tok}: status={r.status_code}")
    print(f"  Has 'csrf_token': {'csrf_token' in r.text}")
    
    # Submit form
    csrf2 = re.search(r'name="csrf_token"\s+value="([^"]+)"', r.text)
    if csrf2:
        csrf2 = csrf2.group(1)
        ts = str(int(time.time()))
        ident = f"1-{ts[-4:]}-{ts[-8:-4]}"
        name = f"Test {ts[-6:]}"
        files = {
            "cedula_front": ("f.jpg", b"FRONT", "image/jpeg"),
            "cedula_back": ("b.jpg", b"BACK", "image/jpeg"),
        }
        data = {
            "csrf_token": csrf2, "nationality": "Costarricense", "id_type": "cedula",
            "identification": ident, "full_name": name,
            "whatsapp": "88888888", "email": f"{ts}@t.com", "age": "30",
            "birth_date": "1994-01-01", "civil_status": "Soltero(a)",
            "profession": "Ing.", "province": "San Jos\u00e9", "province_code": "1",
            "canton": "Central", "canton_code": "1",
            "district_or_locality": "Carmen", "district_or_locality_code": "1",
            "exact_address": "100 m sur", "organ_donor": "No", "has_illness": "No",
            "illnesses": "", "treatments": "", "smokes": "No", "smoke_frequency": "",
            "smoke_product": "", "drinks": "No", "drink_frequency": "",
            "uses_drugs": "No", "drug_type": "", "drug_frequency": "",
            "weight": "70", "height": "175", "uses_glasses": "No",
            "glasses_use": "", "laterality": "Diestro(a)", "license_types": "",
            "truth_declaration": "accepted",
        }
        r = s.post(f"{BASE}/patient/{tok}/submit", data=data, files=files, allow_redirects=False)
        print(f"POST /submit: status={r.status_code}")
        if r.status_code != 303:
            print(f"  Error: {r.text[:300]}")
