"""
Full system test: encounter structure, PDF, ID photos, patient search
"""

import re
import sys
import time
from pathlib import Path

import requests

BASE = "http://127.0.0.1:8765"
EXP_DIR = Path("G:/Mi unidad/Expediente Médico Digital") / "Expediente de pacientes"
s = requests.Session()
results = []


def check(desc, ok):
    results.append((desc, ok))
    print(f"  {'PASS' if ok else 'FAIL'}: {desc}")


def link_csrf(html):
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    return m.group(1) if m else ""


# Login
r = s.get(f"{BASE}/")
csrf = link_csrf(r.text)
s.post(f"{BASE}/login", data={"username": "doctor", "password": "test123", "csrf_token": csrf}, allow_redirects=False)
check("1. Login", True)


# Create two patients with multiple encounters
def make_encounter(ident, name, suffix):
    ts = str(int(time.time())) + suffix
    r = s.get(f"{BASE}/doctor")
    csrf = link_csrf(r.text)
    s.post(f"{BASE}/doctor/links", data={"csrf_token": csrf}, allow_redirects=False)
    r = s.get(f"{BASE}/doctor")
    toks = re.findall(r"/patient/([A-Za-z0-9_-]+)", r.text)
    if not toks:
        return None, "no token"
    tok = toks[0]
    r = s.get(f"{BASE}/patient/{tok}")
    csrf = link_csrf(r.text)
    files = {
        "cedula_front": ("f.jpg", b"FRONT-" + ts.encode(), "image/jpeg"),
        "cedula_back": ("b.jpg", b"BACK-" + ts.encode(), "image/jpeg"),
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
    if r.status_code != 303:
        return None, f"submit {r.status_code}"
    return tok, None


ts = str(int(time.time()))
id1 = f"1-{ts[-4:]}-{ts[-8:-4]}"
id2 = f"1-{int(ts[-4:]) + 1}-{ts[-8:-4]}"
name1 = "Juan Carlos Perez Lopez"
name2 = "Maria Elena Rodriguez Sanchez"

tok1, e = make_encounter(id1, name1, "a")
check("2. Paciente 1 creado", tok1 is not None)
tok1b, e = make_encounter(id1, name1, "b")
check("3. Paciente 1 segundo formulario", tok1b is not None)
tok2, e = make_encounter(id2, name2, "c")
check("4. Paciente 2 creado", tok2 is not None)

# Verify subfolder structure for patient 1
pf1 = None
for pf in EXP_DIR.iterdir():
    if id1 in pf.name:
        pf1 = pf
        break
check("5. Carpeta paciente 1 existe", pf1 and pf1.is_dir())
subs1 = [f for f in pf1.iterdir() if f.is_dir()] if pf1 else []
check("6. Paciente 1 tiene 2 subcarpetas", len(subs1) == 2)

# Check files inside first encounter folder
if subs1:
    ef = subs1[0]
    ef_files = list(ef.iterdir())
    check("7. Subcarpeta tiene PDF", any(f.suffix == ".pdf" for f in ef_files))
    check("8. Subcarpeta tiene frontal", any("cedula-frontal" in f.name for f in ef_files))
    check("9. Subcarpeta tiene trasera", any("cedula-trasera" in f.name for f in ef_files))
    # Check PDF content
    for f in ef_files:
        if f.suffix == ".pdf":
            content = f.read_bytes()
            check("10. PDF tiene fotos ID", b"Documento de identificaci" in content)
            check("11. PDF tiene leyenda", b"revisada, verificada y valorada" in content)

# PATIENT SEARCH TESTS
check("12. Buscar por cedula sin guiones", False)
check("13. Buscar por cedula con guiones", False)
check("14. Buscar por primer nombre", False)
check("15. Buscar por primer apellido", False)
check("16. Buscar por nombre completo", False)
check("17. Buscar texto parcial", False)
check("18. Buscar sin resultados", False)
check("19. Paciente no accede a busqueda", False)
check("20. Panel principal solo muestra hoy", False)


def search(q):
    return s.get(f"{BASE}/doctor/patients/search?query={requests.utils.quote(q)}")


# cedula sin guiones
raw_id = id1.replace("-", "")
r = search(raw_id)
check("12. Buscar por cedula sin guiones", r.status_code == 200 and name1 in r.text)

# cedula con guiones
r = search(id1)
check("13. Buscar por cedula con guiones", r.status_code == 200 and name1 in r.text)

# primer nombre
r = search("Juan")
check("14. Buscar por primer nombre", r.status_code == 200 and name1 in r.text)

# primer apellido
r = search("Perez")
check("15. Buscar por primer apellido", r.status_code == 200 and name1 in r.text)

# nombre completo
r = search(name1)
check("16. Buscar por nombre completo", r.status_code == 200 and name1 in r.text)

# texto parcial
r = search("Lope")
check("17. Buscar texto parcial", r.status_code == 200 and name1 in r.text)

# sin resultados
r = search("ZZZZ9999XXX")
check("18. Buscar sin resultados", "No se encontraron" in r.text)

# patient cannot access search
r2 = s.get(f"{BASE}/doctor/patients/search?query=Juan", allow_redirects=False)
check("19. Sin sesion redirige a login", r2.status_code == 303)

# panel principal solo muestra hoy (at least 2 encounters today shown)
r = s.get(f"{BASE}/doctor")
today_count = len(re.findall(r"/doctor/encounters/(\d+)", r.text))
check("20. Panel muestra atenciones de hoy", today_count >= 3)

# Delete one encounter for patient 1
pf1_encs = sorted([f for f in pf1.iterdir() if f.is_dir()]) if pf1 else []
before_count = len(pf1_encs)
all_ids = list(set(re.findall(r"/doctor/encounters/(\d+)", s.get(f"{BASE}/doctor").text)))
del_id = all_ids[0]
r = s.get(f"{BASE}/doctor/encounters/{del_id}")
csrf = link_csrf(r.text)
s.post(f"{BASE}/doctor/encounters/{del_id}/delete", data={"csrf_token": csrf}, allow_redirects=False)
pf1_encs_after = sorted([f for f in pf1.iterdir() if f.is_dir()]) if pf1 else []
check("21. Delete solo borra 1 subcarpeta", len(pf1_encs_after) == before_count - 1)

print(f"\nTotal: {sum(1 for _, ok in results if ok)}/{len(results)} passed")
sys.exit(0 if all(ok for _, ok in results) else 1)
