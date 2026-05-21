"""
seed_demo_data.py — Genera 20 expedientes ficticios de prueba (6 médicos).

Uso:
    python tools/seed_demo_data.py

Entorno:
    Respeta STORAGE_BACKEND, STORAGE_ROOT y PATIENT_FILES_ROOT.
    Bloquea en APP_ENV=production salvo --force.

Opciones:
    --force       Ejecutar aunque APP_ENV=production
    --recreate    Borrar y regenerar demos existentes
"""

import argparse
import io
import json
import os
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# ── Asegurar que podemos importar desde el proyecto ──
_HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_HERE))
os.environ.setdefault("APP_ENV", "local")
os.environ.setdefault("APP_SECRET_KEY", "seed-demo-secret")
os.environ.setdefault("DOCTOR_USERNAME", "doctor")

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from app.pdf_generator import build_pdf  # noqa: E402
from app.storage import PATIENT_FILES_ROOT, storage  # noqa: E402

DB_PATH = _HERE / "database" / "app.db"
APP_ENV = os.getenv("APP_ENV", "local")

DEMO_PATIENTS = [
    {"name": "Paciente Demo Uno", "id": "DEMO-0001"},
    {"name": "Paciente Demo Dos", "id": "DEMO-0002"},
    {"name": "Paciente Demo Tres", "id": "DEMO-0003"},
    {"name": "Paciente Demo Cuatro", "id": "DEMO-0004"},
    {"name": "Paciente Demo Cinco", "id": "DEMO-0005"},
    {"name": "Paciente Demo Seis", "id": "DEMO-0006"},
    {"name": "Paciente Demo Siete", "id": "DEMO-0007"},
    {"name": "Paciente Demo Ocho", "id": "DEMO-0008"},
    {"name": "Paciente Demo Nueve", "id": "DEMO-0009"},
    {"name": "Paciente Demo Diez", "id": "DEMO-0010"},
    {"name": "Paciente Demo Once", "id": "DEMO-0011"},
    {"name": "Paciente Demo Doce", "id": "DEMO-0012"},
    {"name": "Paciente Demo Trece", "id": "DEMO-0013"},
    {"name": "Paciente Demo Catorce", "id": "DEMO-0014"},
    {"name": "Paciente Demo Quince", "id": "DEMO-0015"},
    {"name": "Paciente Demo Dieciseis", "id": "DEMO-0016"},
    {"name": "Paciente Demo Diecisiete", "id": "DEMO-0017"},
    {"name": "Paciente Demo Dieciocho", "id": "DEMO-0018"},
    {"name": "Paciente Demo Diecinueve", "id": "DEMO-0019"},
    {"name": "Paciente Demo Veinte", "id": "DEMO-0020"},
]

ALL_DEMO_IDS = {p["id"] for p in DEMO_PATIENTS}
ALL_DEMO_USERS = {"medico_demo_1", "medico_demo_2", "medico_demo_3", "medico_demo_4", "medico_demo_5", "medico_demo_6"}

DOCTOR_USERNAME = os.getenv("DOCTOR_USERNAME", "doctor")
DEMO_DOCS = [
    {"username": "medico_demo_1", "full_name": "Dr. Demo Uno", "password": "usuariodoctor"},
    {"username": "medico_demo_2", "full_name": "Dra. Demo Dos", "password": "usuariodoctor"},
    {"username": "medico_demo_3", "full_name": "Dr. Demo Tres", "password": "usuariodoctor"},
    {"username": "medico_demo_4", "full_name": "Dra. Demo Cuatro", "password": "usuariodoctor"},
    {"username": "medico_demo_5", "full_name": "Dr. Demo Cinco", "password": "usuariodoctor"},
    {"username": "medico_demo_6", "full_name": "Dra. Demo Seis", "password": "usuariodoctor"},
]

# Distribución: admin no tiene pacientes propios
ASSIGNMENT = [
    (0, "medico_demo_1"),
    (1, "medico_demo_1"),
    (2, "medico_demo_1"),
    (3, "medico_demo_1"),
    (4, "medico_demo_2"),
    (5, "medico_demo_2"),
    (6, "medico_demo_2"),
    (7, "medico_demo_3"),
    (8, "medico_demo_3"),
    (9, "medico_demo_3"),
    (10, "medico_demo_4"),
    (11, "medico_demo_4"),
    (12, "medico_demo_4"),
    (13, "medico_demo_5"),
    (14, "medico_demo_5"),
    (15, "medico_demo_5"),
    (16, "medico_demo_6"),
    (17, "medico_demo_6"),
    (18, "medico_demo_6"),
    (19, "medico_demo_6"),
]


# ── DB helpers ──────────────────────────────────────────────────────────


def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def ensure_is_demo_column(conn, table):
    cols = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if "is_demo" not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN is_demo INTEGER NOT NULL DEFAULT 0")
        print(f"  [INFO] Columna is_demo agregada a {table}")


def existing_demo_patients(conn):
    rows = conn.execute(
        "SELECT identification FROM patients WHERE identification IN ({})".format(",".join("?" for _ in ALL_DEMO_IDS)),  # noqa: S608
        list(ALL_DEMO_IDS),
    ).fetchall()
    return {r["identification"] for r in rows}


def existing_demo_doctors(conn):
    rows = conn.execute(
        "SELECT username FROM users WHERE username IN ({})".format(",".join("?" for _ in ALL_DEMO_USERS)),  # noqa: S608
        list(ALL_DEMO_USERS),
    ).fetchall()
    return {r["username"] for r in rows}


def get_user_id(conn, username):
    row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    return row["id"] if row else None


def create_demo_doctor(conn, doc):
    existing = get_user_id(conn, doc["username"])
    if existing:
        conn.execute("UPDATE users SET is_demo = 1 WHERE id = ?", (existing,))
        return existing, False
    import passlib.hash as passlib_hash

    hashed = passlib_hash.bcrypt.hash(doc["password"])
    now = datetime.now().isoformat()
    cur = conn.execute(
        """INSERT INTO users (username, password_hash, full_name, email, role, is_active,
           token_version, must_change_password, created_at, updated_at, is_demo)
           VALUES (?, ?, ?, ?, 'doctor', 1, 1, 1, ?, ?, 1)""",
        (doc["username"], hashed, doc["full_name"], "", now, now),
    )
    return cur.lastrowid, True


def doctor_folder_name(username):
    safe = re.sub(r"[<>:\"/\\|?*\x00-\x1F]", "", username).strip()
    return f"M\u00e9dico - {safe}"


def doctor_storage_key(username):
    return f"{PATIENT_FILES_ROOT}/{doctor_folder_name(username)}"


# ── Image generation ────────────────────────────────────────────────────


def make_placeholder_image(text_lines, width=400, height=250):
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 14)
        small = ImageFont.truetype("arial.ttf", 11)
    except OSError:
        font = ImageFont.load_default()
        small = ImageFont.load_default()
    y = 20
    for line in text_lines:
        draw.text((20, y), line, fill="red", font=font)
        y += 22
    draw.text((20, y + 10), "SIN VALIDEZ LEGAL", fill="red", font=small)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=60)
    return buf.getvalue()


# ── Demo data payload ───────────────────────────────────────────────────


def demo_payload(patient, doc_username, idx):
    return {
        "nationality": "Costarricense",
        "id_type": "Cédula de identidad",
        "identification": patient["id"],
        "full_name": patient["name"],
        "whatsapp": f"8888-{idx + 1:04d}",
        "email": f"demo{idx + 1}@example.com",
        "age": str(25 + idx),
        "birth_date": f"{1990 + idx}-01-15",
        "civil_status": "Soltero/a",
        "profession": "Profesional demo",
        "province": "San José",
        "province_code": "1",
        "canton": "San José",
        "canton_code": "101",
        "district_or_locality": "Hospital",
        "district_or_locality_code": "10101",
        "exact_address": "Dirección demo de prueba",
        "organ_donor": "Si",
        "has_illness": "Si",
        "illnesses": "Ninguna (demo)",
        "treatments": "Ninguno (demo)",
        "smokes": "No",
        "smoke_frequency": "",
        "smoke_product": "",
        "drinks": "No",
        "drink_frequency": "",
        "uses_drugs": "No",
        "drug_type": "",
        "drug_frequency": "",
        "weight": "70",
        "height": "170",
        "uses_glasses": "No",
        "glasses_use": "",
        "laterality": "Diestro",
        "license_types": "B1",
        "truth_declaration": "Si",
    }


# ── Main ────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Generar 20 expedientes demo de prueba (6 medicos)")
    parser.add_argument("--force", action="store_true", help="Ejecutar aunque APP_ENV=production")
    parser.add_argument("--recreate", action="store_true", help="Borrar y regenerar demos existentes")
    args = parser.parse_args()

    if APP_ENV == "production" and not args.force:
        print("ERROR: APP_ENV=production. Use --force para ejecutar en produccion.")
        sys.exit(1)

    if not DB_PATH.exists():
        print("ERROR: Base de datos no encontrada. Ejecute la app primero para crearla.")
        sys.exit(1)

    conn = get_conn()
    ensure_is_demo_column(conn, "encounters")
    ensure_is_demo_column(conn, "links")
    ensure_is_demo_column(conn, "users")

    if args.recreate:
        print("Eliminando demos existentes...")
        _delete_all_demo(conn)
        conn.commit()

    existing_patients = existing_demo_patients(conn)

    if existing_patients:
        print(f"Ya existen pacientes demo: {', '.join(sorted(existing_patients))}")
        print("Use --recreate para regenerar.")
        conn.close()
        return

    # ── 1. Crear médicos demo si no existen ──
    demo_doc_ids = {}
    for doc in DEMO_DOCS:
        uid, created = create_demo_doctor(conn, doc)
        demo_doc_ids[doc["username"]] = uid
        print(f"  {'Creado' if created else 'Ya existe'} medico demo: {doc['username']} (id={uid})")

    conn.commit()

    # ── Obtener IDs de usuario ──
    admin_id = get_user_id(conn, DOCTOR_USERNAME)
    if not admin_id:
        print("ERROR: Usuario administrador no encontrado.")
        conn.close()
        sys.exit(1)

    user_ids = {}
    user_ids.update(demo_doc_ids)

    print(f"\nGenerando {len(DEMO_PATIENTS)} expedientes demo...")

    created_count = 0
    error_count = 0

    for idx, patient in enumerate(DEMO_PATIENTS):
        doc_username = ASSIGNMENT[idx][1]
        doc_id = user_ids[doc_username]
        doc_key = doctor_storage_key(doc_username)
        safe_name_val = re.sub(r"[<>:\"/\\|?*\x00-\x1F]", "", patient["name"]).strip()
        safe_id = patient["id"]
        folder_name = f"{safe_name_val} - {safe_id}"
        patient_key = f"{doc_key}/{folder_name}"

        now = datetime.now()
        date_prefix = now.strftime("%Y-%m-%d")
        time_prefix = now.strftime("%H-%M-%S")
        enc_folder_name = f"{date_prefix} - {time_prefix} - Atencion Demo"
        enc_key = f"{patient_key}/{enc_folder_name}"

        front_name = f"{date_prefix} - cedula-frontal-demo - {safe_name_val} - {safe_id}.jpg"
        back_name = f"{date_prefix} - cedula-trasera-demo - {safe_name_val} - {safe_id}.jpg"
        pdf_name = f"{date_prefix} - {safe_name_val} - {safe_id}.pdf"

        front_key = f"{enc_key}/{front_name}"
        back_key = f"{enc_key}/{back_name}"
        pdf_key = f"{enc_key}/{pdf_name}"

        payload = demo_payload(patient, doc_username, idx)

        try:
            # Crear imágenes placeholder
            front_img = make_placeholder_image(
                [
                    "DOCUMENTO FICTICIO DE PRUEBA",
                    f"Paciente: {patient['name']}",
                    f"Identificacion: {patient['id']}",
                    "Frontal (demo)",
                ]
            )
            back_img = make_placeholder_image(
                [
                    "DOCUMENTO FICTICIO DE PRUEBA",
                    f"Paciente: {patient['name']}",
                    f"Identificacion: {patient['id']}",
                    "Trasera (demo)",
                ]
            )

            storage.save(front_key, front_img)
            storage.save(back_key, back_img)

            build_pdf(pdf_key, payload, front_key, back_key, source="in_person")

            # Crear paciente primero (necesitamos patient_id para encounters)
            cur = conn.execute(
                "INSERT INTO patients (identification, full_name, folder_name, created_at, doctor_id) VALUES (?, ?, ?, ?, ?)",
                (patient["id"], patient["name"], folder_name, datetime.now().isoformat(), doc_id),
            )
            patient_id = cur.lastrowid

            # Insertar encounter con patient_id
            token = f"demo-{patient['id'].lower()}-{int(datetime.now().timestamp())}"
            conn.execute(
                """INSERT INTO encounters
                   (patient_id, token, payload, pdf_path, front_image_path, back_image_path,
                    encounter_folder_path, created_at, doctor_id, source, is_demo)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                (patient_id, token, json.dumps(payload, ensure_ascii=True), pdf_key, front_key, back_key, enc_key, datetime.now().isoformat(), doc_id, "in_person"),
            )

            # Crear link para trazabilidad
            conn.execute(
                "INSERT INTO links (token, patient_id, doctor_id, source, status, created_at, expires_at, used_at, updated_at, is_demo) VALUES (?, ?, ?, ?, 'completed', ?, ?, ?, ?, 1)",
                (token, patient_id, doc_id, "in_person", datetime.now().isoformat(), datetime.now().isoformat(), datetime.now().isoformat(), datetime.now().isoformat()),
            )

            created_count += 1
            print(f"  [OK] Expediente #{idx + 1}: {patient['name']} ({patient['id']}) -> {doc_username}")

        except Exception as e:
            error_count += 1
            print(f"  [ERROR] Expediente #{idx + 1}: {e}")

        conn.commit()

    conn.close()

    print(f"\n{'=' * 50}")
    print("Resumen:")
    print(f"  Medicos demo creados: {len(DEMO_DOCS)}")
    print(f"  Pacientes demo: {created_count}/{len(DEMO_PATIENTS)}")
    print(f"  PDFs generados: {created_count}")
    print(f"  Imagenes generadas: {created_count * 2}")
    print(f"  Errores: {error_count}")

    demo_counts = {}
    for _, uname in ASSIGNMENT:
        demo_counts[uname] = demo_counts.get(uname, 0) + 1
    for uname in sorted(demo_counts):
        print(f"  {uname}: {demo_counts[uname]} expedientes")

    storage_root = storage.root
    print(f"\n  Almacenamiento: {storage_root}")
    print(f"  Backend: {os.getenv('STORAGE_BACKEND', 'local_path')}")
    if created_count > 0:
        print("\n  Para probar, inicie sesion como:")
        print(f"    admin:       {DOCTOR_USERNAME}")
        for doc in DEMO_DOCS:
            print(f"    {doc['full_name']}: {doc['username']} / {doc['password']}")
    print(f"{'=' * 50}")


def _delete_all_demo(conn):
    """Delete all demo encounters, links, patients, doctors."""
    demo_encounters = conn.execute("SELECT pdf_path, front_image_path, back_image_path, encounter_folder_path FROM encounters WHERE is_demo = 1").fetchall()
    for enc in demo_encounters:
        for col in ("pdf_path", "front_image_path", "back_image_path", "encounter_folder_path"):
            key = enc[col]
            if key:
                try:
                    if col == "encounter_folder_path":
                        if storage.is_dir(key):
                            storage.rmdir(key)
                    else:
                        if storage.exists(key):
                            storage.delete(key)
                except Exception:  # noqa: S110
                    pass

    conn.execute("DELETE FROM encounters WHERE is_demo = 1")
    conn.execute("DELETE FROM links WHERE is_demo = 1")
    conn.execute("DELETE FROM patients WHERE identification LIKE 'DEMO-%'")
    # Remove demo doctors (only if they have no real data left)
    for uname in ALL_DEMO_USERS:
        user = conn.execute("SELECT id FROM users WHERE username = ?", (uname,)).fetchone()
        if user:
            uid = user["id"]
            remaining = conn.execute("SELECT COUNT(*) AS c FROM encounters WHERE doctor_id = ? AND is_demo != 1", (uid,)).fetchone()["c"]
            if remaining == 0:
                conn.execute("DELETE FROM users WHERE id = ?", (uid,))
    conn.commit()


if __name__ == "__main__":
    main()
