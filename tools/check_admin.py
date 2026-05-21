"""
check_admin.py — Verifica y corrige la cuenta principal del sistema (DOCTOR_USERNAME).

Uso:
    python tools/check_admin.py              (solo verificar)
    python tools/check_admin.py --fix        (corregir automáticamente)
"""

import argparse
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "database" / "app.db"

DOCTOR_USERNAME = os.getenv("DOCTOR_USERNAME", "doctor")


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def ok(msg: str):
    print(f"  [OK] {msg}")


def warn(msg: str):
    print(f"  [ADVERTENCIA] {msg}")


def fail(msg: str):
    print(f"  [FALLO] {msg}")


def fix(msg: str):
    print(f"  [CORREGIDO] {msg}")


def check_admin(fix: bool = False) -> int:
    errors = 0

    if not DB_PATH.exists():
        fail(f"No existe la base de datos: {DB_PATH}")
        return 1

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    user = conn.execute(
        "SELECT id, username, full_name, role, is_active, deleted_at, must_change_password, email FROM users WHERE username = ?",
        (DOCTOR_USERNAME,),
    ).fetchone()

    if not user:
        fail(f"Usuario principal '{DOCTOR_USERNAME}' NO existe en la base de datos.")
        print("\nPara crearlo, inicie la aplicación con DOCTOR_PASSWORD configurado en el entorno.")
        conn.close()
        return 1

    ok(f"Usuario '{DOCTOR_USERNAME}' encontrado (id={user['id']}, nombre='{user['full_name']}')")

    needs_update = False
    updates = []

    if user["role"] != "admin":
        fail(f"Role actual: '{user['role']}' — debe ser 'admin'")
        errors += 1
        if fix:
            updates.append("role = 'admin'")
            needs_update = True

    if not user["is_active"]:
        fail(f"Estado: is_active = {user['is_active']} — debe ser 1")
        errors += 1
        if fix:
            updates.append("is_active = 1")
            needs_update = True

    if user["deleted_at"] is not None:
        fail(f"Estado: deleted_at = {user['deleted_at']} — debe ser NULL")
        errors += 1
        if fix:
            updates.append("deleted_at = NULL")
            needs_update = True

    if not needs_update and user["role"] == "admin" and user["is_active"] and user["deleted_at"] is None:
        ok("Cuenta protegida: role=admin, is_active=1, deleted_at=NULL")

    if needs_update and fix:
        updates.append("updated_at = ?")
        params = [datetime.now().isoformat()]
        sql = "UPDATE users SET {} WHERE id = ?".format(", ".join(updates))  # noqa: S608
        params.append(user["id"])
        conn.execute(sql, params)
        conn.commit()
        fix(f"Cuenta '{DOCTOR_USERNAME}' actualizada: {', '.join(u.split('=')[0].strip() for u in updates if '=' in u)}")
        errors = 0

    elif needs_update and not fix:
        warn("Use --fix para corregir automáticamente los problemas detectados.")

    total_users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    admin_count = conn.execute("SELECT COUNT(*) AS c FROM users WHERE role='admin' AND is_active=1 AND deleted_at IS NULL").fetchone()["c"]

    print()
    print("--- Resumen de usuarios ---")
    print(f"  Total usuarios:          {total_users}")
    print(f"  Admins activos:          {admin_count}")
    print(f"  Cuenta protegida:        '{DOCTOR_USERNAME}'")

    if admin_count == 0:
        fail("No hay ningún administrador activo. El sistema quedaría inaccesible.")
        errors += 1

    conn.close()
    return errors


def main():
    parser = argparse.ArgumentParser(description="Verifica y corrige la cuenta principal del sistema.")
    parser.add_argument("--fix", action="store_true", help="Corregir automáticamente role, is_active, deleted_at")
    args = parser.parse_args()

    print("=== check_admin: Verificación de cuenta principal ===")
    print(f"DB: {DB_PATH}")
    print(f"Usuario principal: {DOCTOR_USERNAME}")
    print()

    errors = check_admin(fix=args.fix)
    print(f"\n{'Todos los chequeos pasaron.' if not errors else f'{errors} problema(s) pendiente(s).'}")

    if fix and not errors:
        print("La cuenta principal está correctamente protegida.")

    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
