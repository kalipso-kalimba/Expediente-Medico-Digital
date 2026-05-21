"""
clean_temp.py — Limpia archivos temporales de desarrollo de forma segura.

Nunca borra:
  - database/app.db
  - Expediente de pacientes/
  - PDFs, fotos, archivos médicos
  - .env
  - storage/ (archivos en uso)

Uso:
    python tools/clean_temp.py                  (simular, muestra qué borraría)
    python tools/clean_temp.py --dry-run         (lo mismo)
    python tools/clean_temp.py --execute         (borrar realmente, pide confirmación)
    python tools/clean_temp.py --force           (borrar sin confirmación)
"""

import argparse
import shutil
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

PROTECTED_PATTERNS = [
    "*.db",
    "*.db-journal",
    "*.db-wal",
    "*.pdf",
    "*.jpg",
    "*.jpeg",
    "*.png",
    "*.env",
    ".env.*",
]

PROTECTED_DIRS = [
    "Expediente de pacientes",
    "database",
    "papelera",
    "storage",
    ".venv",
]

TEMP_PATTERNS = [
    "__pycache__",
    ".pytest_cache",
    "*.pyc",
    "*.pyo",
    "*.log",
    ".coverage",
    "htmlcov",
    ".mypy_cache",
    ".ruff_cache",
    "debug*.py",
    "debug_*.py",
    "test_debug*.py",
    "tmp*",
    "temp*",
]


def would_delete(path: Path) -> bool:
    """Check if a path should be deleted based on protect rules."""
    resolved = path.resolve()
    for protected_dir in PROTECTED_DIRS:
        if (BASE_DIR / protected_dir).resolve() in resolved.parents or (BASE_DIR / protected_dir).resolve() == resolved:
            return False
    if resolved == BASE_DIR:
        return False
    return True


def collect_temp_files(dry_run: bool) -> list[Path]:
    to_delete = []

    for pattern in TEMP_PATTERNS:
        if pattern.endswith(("__pycache__", ".pytest_cache", "htmlcov", ".mypy_cache", ".ruff_cache")):
            for p in BASE_DIR.rglob(pattern):
                if p.is_dir() and would_delete(p):
                    to_delete.append(p)
        elif "*" in pattern:
            for p in BASE_DIR.rglob(pattern):
                if p.is_file() and would_delete(p):
                    to_delete.append(p)

    if not dry_run:
        # Also find any top-level debug scripts
        for p in BASE_DIR.glob("debug*.py"):
            if p.is_file():
                to_delete.append(p)

    return sorted(set(to_delete))


def confirm(prompt: str) -> bool:
    response = input(f"{prompt} (s/N): ").strip().lower()
    return response in ("s", "si", "sí", "y", "yes")


def clean(dry_run: bool = True, force: bool = False) -> int:
    files = collect_temp_files(dry_run)

    if not files:
        print("No se encontraron archivos temporales para limpiar.")
        return 0

    total_size = 0
    print("Archivos a eliminar:")
    print()
    for f in files:
        if f.is_file():
            size = f.stat().st_size
            total_size += size
            print(f"  {f.relative_to(BASE_DIR)}  ({size:,} bytes)")
        elif f.is_dir():
            dir_size = sum(p.stat().st_size for p in f.rglob("*") if p.is_file())
            total_size += dir_size
            print(f"  {f.relative_to(BASE_DIR)}/  ({dir_size:,} bytes)")
    print()
    print(f"Total: {len(files)} ítems, {total_size:,} bytes liberables")

    if dry_run:
        print("\nModo simulación — no se borró nada. Use --execute para borrar.")
        return 0

    if not force and not confirm("¿Eliminar estos archivos?"):
        print("Operación cancelada.")
        return 1

    deleted = 0
    for f in files:
        try:
            if f.is_dir():
                shutil.rmtree(f)
            else:
                f.unlink()
            deleted += 1
            print(f"  Eliminado: {f.relative_to(BASE_DIR)}")
        except OSError as e:
            print(f"  Error al eliminar {f.relative_to(BASE_DIR)}: {e}", file=sys.stderr)

    print(f"\n{deleted} ítem(s) eliminado(s).")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Limpia archivos temporales de desarrollo de forma segura.")
    parser.add_argument("--dry-run", action="store_true", help="Simular sin borrar (por defecto)")
    parser.add_argument("--execute", action="store_true", help="Borrar realmente (pide confirmación)")
    parser.add_argument("--force", action="store_true", help="Borrar sin confirmación")
    args = parser.parse_args()

    if args.execute:
        dry_run = False
    elif args.force:
        dry_run = False
    else:
        dry_run = True

    print("=== clean_temp: Limpieza de archivos temporales ===")
    print(f"Directorio: {BASE_DIR}")
    print()

    errors = clean(dry_run=dry_run, force=args.force)
    sys.exit(errors)


if __name__ == "__main__":
    main()
