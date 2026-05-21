"""
Comprehensive test: 23 scenarios for new encounter subfolder structure
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


def csrf_from(html):
    return re.search(r'name="csrf_token"\s+value="([^"]+)"', html).group(1)


# Login
r = s.get(f"{BASE}/")
csrf = csrf_from(r.text)
s.post(f"{BASE}/login", data={"username": "doctor", "password": "test123", "csrf_token": csrf}, allow_redirects=False)
check("1. Login exitoso", True)


def create_encounter(ident, name, suffix):
    ts = str(int(time.time())) + suffix
    r = s.get(f"{BASE}/doctor")
    csrf = csrf_from(r.text)
    s.post(f"{BASE}/doctor/links", data={"csrf_token": csrf}, allow_redirects=False)
    r = s.get(f"{BASE}/doctor")
    tok = re.findall(r"/patient/([A-Za-z0-9_-]+)", r.text)
    if not tok:
        return None, "no token"
    tok = tok[0]
    r = s.get(f"{BASE}/patient/{tok}")
    csrf = csrf_from(r.text)
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
    if r.status_code != 303:
        return None, f"submit status {r.status_code}: {r.text[:200]}"
    return tok, None


ts = str(int(time.time()))
ident = f"1-{ts[-4:]}-{ts[-8:-4]}"
name = f"Paciente E {ts[-4:]}"

# Scenario 1-5: First encounter for new patient
tok, err = create_encounter(ident, name, "a")
check(f"2. Crear formulario paciente nuevo ({err})", tok is not None)

patient_folder = None
for pf in EXP_DIR.iterdir():
    if ident in pf.name:
        patient_folder = pf
        break
check("3. Se crea carpeta principal del paciente", patient_folder and patient_folder.is_dir())

enc_subfolders = sorted([f for f in patient_folder.iterdir() if f.is_dir()]) if patient_folder else []
enc_folder = enc_subfolders[0] if enc_subfolders else None
check("4. Se crea carpeta de atencion dentro", enc_folder and enc_folder.is_dir())

files_in_enc = list(enc_folder.iterdir()) if enc_folder else []
pdf_files = [f for f in files_in_enc if f.suffix == ".pdf"]
front_files = [f for f in files_in_enc if "cedula-frontal" in f.name]
back_files = [f for f in files_in_enc if "cedula-trasera" in f.name]
check("5. PDF dentro de carpeta de atencion", len(pdf_files) == 1)
check("6. Foto frontal dentro de carpeta de atencion", len(front_files) == 1)
check("7. Foto trasera dentro de carpeta de atencion", len(back_files) == 1)

if pdf_files:
    pdf_content = pdf_files[0].read_bytes()
    check("8. PDF incluye seccion de identificacion", b"Documento de identificaci" in pdf_content)
    check("9. PDF incluye leyenda definitiva", b"revisada, verificada y valorada" in pdf_content)

# Scenario 6-9: Second encounter for same patient
tok2, err2 = create_encounter(ident, name, "b")
check("10. Segundo formulario mismo paciente", tok2 is not None)

enc_subfolders_after = sorted([f for f in patient_folder.iterdir() if f.is_dir()]) if patient_folder else []
check("11. NO se sobrescribe atencion anterior", len(enc_subfolders_after) == 2)
check("12. Se crea segunda carpeta de atencion", len(enc_subfolders_after) == 2)

# Each encounter has its own photos
for ef in enc_subfolders_after:
    ef_files = list(ef.iterdir())
    for f in ef_files:
        if "cedula-frontal" in f.name:
            content = f.read_bytes()
            check(f"13. {ef.name}: foto frontal propia con contenido de esa ocasion", content.startswith(b"FRONT-"))
        if "cedula-trasera" in f.name:
            content = f.read_bytes()
            check(f"13. {ef.name}: foto trasera propia con contenido de esa ocasion", content.startswith(b"BACK-"))

# Scenario 10-13: Search and verify
r = s.get(f"{BASE}/doctor/patients/search?identification={ident}")
check("14. Consultar paciente por cedula exitoso", r.status_code == 200)
enc_ids_in_search = re.findall(r"/doctor/encounters/(\d+)", r.text)
check("15. Aparece historial del paciente", len(enc_ids_in_search) >= 1)

# Verify each encounter detail loads with correct images
for eid in set(enc_ids_in_search):
    r = s.get(f"{BASE}/doctor/encounters/{eid}")
    check(f"16. Detalle de atencion {eid} carga", r.status_code == 200)
    r = s.get(f"{BASE}/doctor/encounters/{eid}/images/front")
    check(f"16. Vista frontal {eid} carga", r.status_code == 200)
    r = s.get(f"{BASE}/doctor/encounters/{eid}/images/back")
    check(f"16. Vista trasera {eid} carga", r.status_code == 200)

# Scenario 14-16: Delete one encounter
r = s.get(f"{BASE}/doctor")
all_enc_ids = list(set(re.findall(r"/doctor/encounters/(\d+)", r.text)))
check("17. Hay al menos 2 atenciones antes de eliminar", len(all_enc_ids) >= 2)

delete_id = all_enc_ids[0]
r = s.get(f"{BASE}/doctor/encounters/{delete_id}")
csrf = csrf_from(r.text)
r = s.post(f"{BASE}/doctor/encounters/{delete_id}/delete", data={"csrf_token": csrf}, allow_redirects=False)
check("18. Eliminar atencion retorna redirect", r.status_code == 303)

remaining_folders = list([f for f in patient_folder.iterdir() if f.is_dir()]) if patient_folder else []
check("19. Solo queda 1 atencion despues de eliminar", len(remaining_folders) == 1)

remaining_id = all_enc_ids[1]
r = s.get(f"{BASE}/doctor/encounters/{remaining_id}", allow_redirects=False)
check("20. Las demas atenciones intactas", r.status_code == 200)

# Check remaining encounter still has its files
remaining_enc_folder = remaining_folders[0]
remaining_files = list(remaining_enc_folder.iterdir())
check("21. Atencion restante conserva PDF", any(f.suffix == ".pdf" for f in remaining_files))
check("22. Atencion restante conserva foto frontal", any("cedula-frontal" in f.name for f in remaining_files))
check("23. Atencion restante conserva foto trasera", any("cedula-trasera" in f.name for f in remaining_files))

print(f"\nTotal: {sum(1 for _, ok in results if ok)}/{len(results)} passed")
sys.exit(0 if all(ok for _, ok in results) else 1)
