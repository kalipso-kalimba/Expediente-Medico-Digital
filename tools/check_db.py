"""
check_db.py — Verifica la estructura y estado de la base de datos.

Uso:
    python tools/check_db.py
    python tools/check_db.py --fix        (corrige problemas simples)
"""

import argparse
import os
import sqlite3
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "database"
DB_PATH = DATA_DIR / "app.db"

DOCTOR_USERNAME = os.getenv("DOCTOR_USERNAME", "doctor")

REQUIRED_TABLES = {"users", "patients", "links", "encounters"}

USERS_COLUMNS = {
    "id",
    "username",
    "password_hash",
    "full_name",
    "email",
    "role",
    "is_active",
    "token_version",
    "must_change_password",
    "deleted_at",
    "created_at",
    "updated_at",
}

LINKS_EXTRA = {"doctor_id", "patient_id", "source", "status", "draft_payload_json", "updated_at"}
ENCOUNTERS_EXTRA = {"doctor_id", "source"}


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def ok(msg: str):
    print(f"  [OK] {msg}")


def warn(msg: str):
    print(f"  [ADVERTENCIA] {msg}")


def fail(msg: str):
    print(f"  [FALLO] {msg}")


def get_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r["name"] for r in rows}


def check_db(fix: bool = False) -> int:
    errors = 0

    if not DB_PATH.exists():
        fail(f"No existe la base de datos: {DB_PATH}")
        return 1
    ok(f"Base de datos encontrada: {DB_PATH} ({DB_PATH.stat().st_size} bytes)")

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    existing = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

    for table in sorted(REQUIRED_TABLES):
        if table in existing:
            ok(f"Tabla '{table}' existe")
        else:
            fail(f"Tabla '{table}' NO existe")
            errors += 1

    if "users" in existing:
        cols = get_columns(conn, "users")
        missing = USERS_COLUMNS - cols
        if missing:
            fail(f"Columna(s) faltante(s) en users: {', '.join(sorted(missing))}")
            errors += 1
        else:
            ok("Tabla users tiene todas las columnas esperadas")

        user = conn.execute(
            "SELECT id, username, role, is_active, deleted_at, must_change_password FROM users WHERE username = ?",
            (DOCTOR_USERNAME,),
        ).fetchone()
        if user:
            ok(f"Usuario principal '{DOCTOR_USERNAME}' existe (id={user['id']})")
            if user["role"] != "admin":
                fail(f"Usuario '{DOCTOR_USERNAME}' tiene role='{user['role']}', debería ser 'admin'")
                errors += 1
            if not user["is_active"]:
                fail(f"Usuario '{DOCTOR_USERNAME}' tiene is_active=0")
                errors += 1
            if user["deleted_at"]:
                fail(f"Usuario '{DOCTOR_USERNAME}' tiene deleted_at={user['deleted_at']}")
                errors += 1
            if user["role"] == "admin" and user["is_active"] and not user["deleted_at"]:
                ok("Usuario principal tiene role=admin, is_active=1, deleted_at=NULL")
        else:
            fail(f"Usuario principal '{DOCTOR_USERNAME}' NO encontrado en la tabla users")
            errors += 1

        count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        ok(f"Total usuarios registrados: {count}")

        admins = conn.execute("SELECT COUNT(*) AS c FROM users WHERE role='admin' AND is_active=1 AND deleted_at IS NULL").fetchone()["c"]
        if admins == 0:
            fail("No hay ningún administrador activo en el sistema")
            errors += 1
        else:
            ok(f"Administradores activos: {admins}")

    if "links" in existing:
        cols = get_columns(conn, "links")
        for col in LINKS_EXTRA:
            if col in cols:
                ok(f"Columna links.{col} existe")
            else:
                warn(f"Columna links.{col} NO existe (puede ser normal en BD antiguas)")

        null_doctor = conn.execute("SELECT COUNT(*) AS c FROM links WHERE doctor_id IS NULL").fetchone()["c"]
        if null_doctor:
            warn(f"{null_doctor} link(s) sin doctor_id")
        else:
            ok("Todos los links tienen doctor_id")

    if "encounters" in existing:
        cols = get_columns(conn, "encounters")
        for col in ENCOUNTERS_EXTRA:
            if col in cols:
                ok(f"Columna encounters.{col} existe")
            else:
                warn(f"Columna encounters.{col} NO existe")

        null_doctor = conn.execute("SELECT COUNT(*) AS c FROM encounters WHERE doctor_id IS NULL").fetchone()["c"]
        if null_doctor:
            warn(f"{null_doctor} encounter(s) sin doctor_id")
        else:
            ok("Todos los encounters tienen doctor_id")

    if "patients" in existing:
        count = conn.execute("SELECT COUNT(*) AS c FROM patients").fetchone()["c"]
        ok(f"Total pacientes registrados: {count}")

    conn.close()

    if errors:
        print(f"\n{errors} problema(s) encontrado(s).")
    else:
        print("\nTodos los chequeos pasaron correctamente.")

    return errors


def main():
    parser = argparse.ArgumentParser(description="Verifica la estructura y estado de la base de datos.")
    parser.add_argument("--fix", action="store_true", help="Corregir problemas simples (solo permite role/admin para DOCTOR_USERNAME)")
    args = parser.parse_args()

    print("=== check_db: Verificación de base de datos ===")
    print(f"DB: {DB_PATH}")
    print(f"Usuario principal: {DOCTOR_USERNAME}")
    print()

    errors = check_db(fix=args.fix)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
