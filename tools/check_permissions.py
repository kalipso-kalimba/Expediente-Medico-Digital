"""
check_permissions.py — Revisa el aislamiento de datos entre médicos.

Detecta:
  - Links/encounters sin doctor_id
  - Formularios presenciales incompletos sin doctor_id
  - Posibles fugas de datos entre médicos
  - Usuarios suspendidos/borrados con datos asociados

Uso:
    python tools/check_permissions.py
"""

import os
import sqlite3
import sys
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


def check_permissions() -> int:
    errors = 0

    if not DB_PATH.exists():
        fail(f"No existe la base de datos: {DB_PATH}")
        return 1

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    tables = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

    # --- Links sin doctor_id ---
    if "links" in tables:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(links)").fetchall()}
        if "doctor_id" in cols:
            null_links = conn.execute("SELECT COUNT(*) AS c FROM links WHERE doctor_id IS NULL").fetchone()["c"]
            if null_links:
                warn(f"{null_links} link(s) sin doctor_id (asignados implícitamente al admin al iniciar la app)")
                errors += 1
            else:
                ok("Todos los links tienen doctor_id asignado")

    # --- Encounters sin doctor_id ---
    if "encounters" in tables:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(encounters)").fetchall()}
        if "doctor_id" in cols:
            null_enc = conn.execute("SELECT COUNT(*) AS c FROM encounters WHERE doctor_id IS NULL").fetchone()["c"]
            if null_enc:
                warn(f"{null_enc} encounter(s) sin doctor_id")
                errors += 1
            else:
                ok("Todos los encounters tienen doctor_id asignado")

    # --- Formularios presenciales incompletos sin doctor_id ---
    if "links" in tables:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(links)").fetchall()}
        if "doctor_id" in cols and "source" in cols and "status" in cols:
            orphan_drafts = conn.execute("SELECT COUNT(*) AS c FROM links WHERE source='in_person' AND status='in_progress' AND doctor_id IS NULL").fetchone()["c"]
            if orphan_drafts:
                warn(f"{orphan_drafts} formulario(s) presencial(es) incompleto(s) sin doctor_id (huérfanos)")
                errors += 1
            else:
                ok("No hay formularios presenciales incompletos huérfanos")

    # --- Distribución por médico ---
    if "users" in tables and "links" in tables:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(links)").fetchall()}
        doc_col = "doctor_id" in cols

        print()
        print("--- Distribución de datos por médico ---")
        users = conn.execute("SELECT id, username, role, is_active, deleted_at FROM users ORDER BY id").fetchall()

        for u in users:
            status_parts = []
            if u["role"] == "admin":
                status_parts.append("admin")
            if not u["is_active"]:
                status_parts.append("suspendido")
            if u["deleted_at"]:
                status_parts.append("borrado")
            if not u["is_active"] and u["deleted_at"]:
                status_parts = ["borrado"]

            label = "activo" if not status_parts else ", ".join(status_parts)
            protected = " [PROTEGIDA]" if u["username"] == DOCTOR_USERNAME else ""

            if doc_col:
                link_count = conn.execute("SELECT COUNT(*) AS c FROM links WHERE doctor_id = ?", (u["id"],)).fetchone()["c"]
                enc_count = conn.execute("SELECT COUNT(*) AS c FROM encounters WHERE doctor_id = ?", (u["id"],)).fetchone()["c"]
                draft_count = conn.execute(
                    "SELECT COUNT(*) AS c FROM links WHERE doctor_id = ? AND source='in_person' AND status='in_progress'",
                    (u["id"],),
                ).fetchone()["c"]
            else:
                link_count = enc_count = draft_count = -1

            print(f"  {u['username']:20s} ({label:12s}){protected}  links={link_count:<4d}  encounters={enc_count:<4d}  borradores={draft_count:<4d}")

    # --- Usuarios sin datos ---
    if "users" in tables and doc_col:
        print()
        print("--- Usuarios sin actividad ---")
        inactive_count = 0
        for u in users:
            if doc_col:
                total = conn.execute("SELECT COUNT(*) AS c FROM links WHERE doctor_id = ?", (u["id"],)).fetchone()["c"]
                if total == 0:
                    print(f"  {u['username']:20s} — sin links ni encounters")
                    inactive_count += 1
        if inactive_count == 0:
            ok("Todos los usuarios tienen datos asociados")

    # --- Verificación de médicos suspendidos/borrados con datos ---
    if "users" in tables and doc_col:
        print()
        print("--- Médicos suspendidos/borrados con datos ---")
        suspended_with_data = False
        for u in users:
            if not u["is_active"] or u["deleted_at"]:
                total = conn.execute("SELECT COUNT(*) AS c FROM links WHERE doctor_id = ?", (u["id"],)).fetchone()["c"]
                if total > 0:
                    print(f"  {u['username']:20s} — {total} registro(s) de datos retenidos (borrado lógico)")
                    suspended_with_data = True
        if not suspended_with_data:
            ok("No hay médicos suspendidos/borrados con datos (o hay pero es esperado por borrado lógico)")

    conn.close()

    if errors:
        print(f"\n{errors} problema(s) de permisos encontrado(s). Revise las advertencias.")
    else:
        print("\nNo se detectaron problemas de permisos ni aislamiento.")

    return errors


def main():
    print("=== check_permissions: Revisión de aislamiento de datos ===")
    print(f"DB: {DB_PATH}")
    print()

    errors = check_permissions()
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
