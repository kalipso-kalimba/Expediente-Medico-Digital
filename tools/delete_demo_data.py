"""
delete_demo_data.py — Elimina todos los datos demo del sistema.

Uso:
    python tools/delete_demo_data.py

Opciones:
    --force       Ejecutar sin confirmacion
    --yes         Responder "si" automaticamente
"""

import argparse
import os
import sqlite3
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_HERE))
os.environ.setdefault("APP_SECRET_KEY", "delete-demo-secret")

from app.storage import storage  # noqa: E402

DB_PATH = _HERE / "database" / "app.db"
APP_ENV = os.getenv("APP_ENV", "local")


def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def has_real_data(conn):
    """Check if there are non-demo encounters."""
    row = conn.execute("SELECT COUNT(*) AS c FROM encounters WHERE is_demo != 1").fetchone()
    return row["c"] > 0


def main():
    parser = argparse.ArgumentParser(description="Eliminar datos demo del sistema")
    parser.add_argument("--force", action="store_true", help="Ejecutar aunque APP_ENV=production")
    parser.add_argument("--yes", action="store_true", help="Responder si automaticamente")
    args = parser.parse_args()

    if APP_ENV == "production" and not args.force:
        print("ERROR: APP_ENV=production. Use --force para ejecutar en produccion.")
        sys.exit(1)

    if not DB_PATH.exists():
        print("No se encontro la base de datos.")
        sys.exit(1)

    conn = get_conn()

    # Check if is_demo column exists
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(encounters)").fetchall()}
    if "is_demo" not in cols:
        print("No hay columna is_demo. No hay datos demo que eliminar.")
        conn.close()
        return

    # Count demo data
    demo_encounters = conn.execute("SELECT COUNT(*) AS c FROM encounters WHERE is_demo = 1").fetchone()["c"]
    demo_links = conn.execute("SELECT COUNT(*) AS c FROM links WHERE is_demo = 1").fetchone()["c"]
    demo_patients = conn.execute("SELECT COUNT(*) AS c FROM patients WHERE identification LIKE 'DEMO-%'").fetchone()["c"]

    if demo_encounters == 0 and demo_links == 0 and demo_patients == 0:
        print("No se encontraron datos demo.")
        conn.close()
        return

    print("Datos demo encontrados:")
    print(f"  Encounters demo: {demo_encounters}")
    print(f"  Links demo:      {demo_links}")
    print(f"  Pacientes demo:  {demo_patients}")

    if not args.yes:
        resp = input("\nBorrar todos los datos demo? (s/N): ").strip().lower()
        if resp not in ("s", "si", "yes", "y"):
            print("Cancelado.")
            conn.close()
            return

    # ── 1. Eliminar archivos f�sicos ──
    demo_files = conn.execute("SELECT pdf_path, front_image_path, back_image_path, encounter_folder_path FROM encounters WHERE is_demo = 1").fetchall()

    files_deleted = 0
    folders_deleted = 0

    for enc in demo_files:
        for col in ("pdf_path", "front_image_path", "back_image_path"):
            key = enc[col]
            if key:
                try:
                    if storage.exists(key):
                        storage.delete(key)
                        files_deleted += 1
                except Exception:  # noqa: S110
                    pass

        enc_folder = enc["encounter_folder_path"]
        if enc_folder:
            try:
                if storage.is_dir(enc_folder):
                    storage.rmdir(enc_folder)
                    folders_deleted += 1
            except Exception:  # noqa: S110
                pass

    # ── 2. Eliminar de BD ──
    conn.execute("DELETE FROM encounters WHERE is_demo = 1")
    conn.execute("DELETE FROM links WHERE is_demo = 1")
    conn.execute("DELETE FROM patients WHERE identification LIKE 'DEMO-%'")

    # ── 3. Eliminar m�dicos demo si no tienen datos reales ──
    for username in ("medico_demo_1", "medico_demo_2", "medico_demo_3", "medico_demo_4"):
        user = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if not user:
            continue
        uid = user["id"]
        has_encounters = conn.execute("SELECT COUNT(*) AS c FROM encounters WHERE doctor_id = ?", (uid,)).fetchone()["c"]
        has_links = conn.execute("SELECT COUNT(*) AS c FROM links WHERE doctor_id = ?", (uid,)).fetchone()["c"]
        if has_encounters == 0 and has_links == 0:
            conn.execute("DELETE FROM users WHERE id = ?", (uid,))
            print(f"  Medico demo '{username}' eliminado.")
        else:
            print(f"  Medico demo '{username}' conservado (tiene datos reales).")

    conn.commit()
    conn.close()

    print("\nResumen:")
    print(f"  Archivos eliminados: {files_deleted}")
    print(f"  Carpetas eliminadas: {folders_deleted}")
    print(f"  Encounters demo:     {demo_encounters} -> 0")
    print(f"  Links demo:          {demo_links} -> 0")
    print(f"  Pacientes demo:      {demo_patients} -> 0")
    print("\nDatos demo eliminados correctamente.")


if __name__ == "__main__":
    main()
