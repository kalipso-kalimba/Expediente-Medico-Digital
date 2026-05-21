from __future__ import annotations

import json
import hashlib
import hmac
import logging
import mimetypes
import os
import re
import secrets
import shutil
import sqlite3
import time
import urllib.parse
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import passlib.hash as passlib_hash

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.platypus import Image as RLImage
from reportlab.lib import colors

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "database"
EXPEDIENTES_DIR = BASE_DIR / "Expediente de pacientes"
TRASH_DIR = BASE_DIR / "papelera"
STORAGE_DIR = BASE_DIR / "storage"
DB_PATH = DATA_DIR / "app.db"
LOCATIONS_PATH = DATA_DIR / "costa_rica_locations.json"
APP_ENV = os.getenv("APP_ENV", "local").lower()
SECRET_KEY = os.getenv("APP_SECRET_KEY", "")
DOCTOR_USERNAME = os.getenv("DOCTOR_USERNAME", "doctor")
DOCTOR_PASSWORD = os.getenv("DOCTOR_PASSWORD", "")
COOKIE_SECURE = os.getenv("APP_COOKIE_SECURE", "false").lower() in {"1", "true", "yes", "on"}
TSE_LOOKUP_ENABLED = os.getenv("TSE_LOOKUP_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
BASE_URL = os.getenv("BASE_URL", "").rstrip("/")
DEFAULT_PASSWORD = "usuariodoctor"
SESSION_COOKIE = "doctor_session"
CSRF_COOKIE = "csrf_token"
TSE_RATE_LIMIT: dict[str, list[float]] = {}
LOCATIONS_CACHE: dict[str, Any] | None = None

app = FastAPI(title="Expediente Médico Digital")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def ensure_dirs() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    EXPEDIENTES_DIR.mkdir(parents=True, exist_ok=True)
    TRASH_DIR.mkdir(parents=True, exist_ok=True)
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def migrate_admin() -> None:
    with db() as conn:
        existing = conn.execute("SELECT id, role, is_active, must_change_password FROM users WHERE username = ?", (DOCTOR_USERNAME,)).fetchone()
        if not existing and DOCTOR_PASSWORD:
            hashed = passlib_hash.bcrypt.hash(DOCTOR_PASSWORD)
            conn.execute(
                "INSERT INTO users (username, password_hash, full_name, email, role, is_active, token_version, must_change_password, created_at, updated_at) VALUES (?, ?, ?, ?, 'admin', 1, 1, 0, ?, ?)",
                (DOCTOR_USERNAME, hashed, DOCTOR_USERNAME, "", datetime.now().isoformat(), datetime.now().isoformat()),
            )
            logger.info("Admin user created from env vars.")
            admin_id = conn.execute("SELECT id FROM users WHERE username = ?", (DOCTOR_USERNAME,)).fetchone()["id"]
        elif existing:
            admin_id = existing["id"]
            updates = []
            if existing["role"] != "admin" or not existing["is_active"]:
                updates.append("role = 'admin', is_active = 1")
            if existing["must_change_password"]:
                updates.append("must_change_password = 0")
            if updates:
                updates.append("updated_at = ?")
                params = (datetime.now().isoformat(), admin_id)
                conn.execute(
                    "UPDATE users SET {} WHERE id = ?".format(", ".join(updates)),
                    params,
                )
                logger.info("Admin user '%s' updated.", DOCTOR_USERNAME)
        else:
            return

        has_doctor_id = "doctor_id" in {row["name"] for row in conn.execute("PRAGMA table_info(links)").fetchall()}
        if has_doctor_id:
            conn.execute("UPDATE links SET doctor_id = ? WHERE doctor_id IS NULL", (admin_id,))
            conn.execute("UPDATE encounters SET doctor_id = ? WHERE doctor_id IS NULL", (admin_id,))


def verify_user_password(username: str, password: str) -> dict | None:
    with db() as conn:
        row = conn.execute(
            "SELECT id, username, password_hash, role, is_active, full_name, must_change_password FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    if not row:
        return None
    if not row["is_active"]:
        return None
    try:
        if passlib_hash.bcrypt.verify(password, row["password_hash"]):
            return dict(row)
    except Exception:
        return None
    return None


def get_user_by_id(user_id: int) -> dict | None:
    with db() as conn:
        row = conn.execute(
            "SELECT id, username, full_name, email, role, is_active, must_change_password FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def hash_password(password: str) -> str:
    return passlib_hash.bcrypt.hash(password)


def set_user_password(user_id: int, new_password: str, must_change: int = 0) -> None:
    hashed = hash_password(new_password)
    with db() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ?, token_version = token_version + 1, must_change_password = ?, updated_at = ? WHERE id = ?",
            (hashed, must_change, datetime.now().isoformat(), user_id),
        )


def get_token_version(user_id: int) -> int:
    with db() as conn:
        row = conn.execute("SELECT token_version FROM users WHERE id = ?", (user_id,)).fetchone()
    return row["token_version"] if row else 0


def session_value(user_id: int, token_version: int | None = None) -> str:
    tv = token_version if token_version is not None else get_token_version(user_id)
    data = f"{user_id}:{tv}"
    return hmac.new(SECRET_KEY.encode(), data.encode(), "sha256").hexdigest()


def doctor_folder_name(username: str) -> str:
    return safe_name(f"M\u00e9dico - {username}")


def doctor_expedientes_dir(username: str) -> Path:
    return EXPEDIENTES_DIR / doctor_folder_name(username)


def get_doctor_username(doctor_id: int) -> str:
    with db() as conn:
        row = conn.execute("SELECT username FROM users WHERE id = ?", (doctor_id,)).fetchone()
    return row["username"] if row else "admin"


def can_access_encounter(user: dict, encounter_id: int) -> dict | None:
    with db() as conn:
        encounter = conn.execute(
            """
            SELECT e.*, p.full_name, p.identification, p.folder_name
            FROM encounters e JOIN patients p ON p.id = e.patient_id
            WHERE e.id = ?
            """,
            (encounter_id,),
        ).fetchone()
    if not encounter:
        return None
    if user["role"] == "admin":
        return dict(encounter)
    if encounter["doctor_id"] == user["id"] or encounter["doctor_id"] is None:
        return dict(encounter)
    return None


@contextmanager
def db() -> Any:
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used_at TEXT
            );

            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                identification TEXT UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                folder_name TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS encounters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                token TEXT NOT NULL,
                payload TEXT NOT NULL,
                pdf_path TEXT NOT NULL,
                front_image_path TEXT NOT NULL,
                back_image_path TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(patient_id) REFERENCES patients(id)
            );
            """
        )
        link_columns = {row["name"] for row in conn.execute("PRAGMA table_info(links)").fetchall()}
        if "opened_at" not in link_columns:
            conn.execute("ALTER TABLE links ADD COLUMN opened_at TEXT")
        if "canceled_at" not in link_columns:
            conn.execute("ALTER TABLE links ADD COLUMN canceled_at TEXT")
        if "canceled_by" not in link_columns:
            conn.execute("ALTER TABLE links ADD COLUMN canceled_by TEXT")
        if "patient_id" not in link_columns:
            conn.execute("ALTER TABLE links ADD COLUMN patient_id INTEGER REFERENCES patients(id)")
        if "source" not in link_columns:
            conn.execute("ALTER TABLE links ADD COLUMN source TEXT NOT NULL DEFAULT 'remote'")

        encounter_columns = {row["name"] for row in conn.execute("PRAGMA table_info(encounters)").fetchall()}
        if "encounter_folder_path" not in encounter_columns:
            conn.execute("ALTER TABLE encounters ADD COLUMN encounter_folder_path TEXT")
        if "source" not in encounter_columns:
            conn.execute("ALTER TABLE encounters ADD COLUMN source TEXT NOT NULL DEFAULT 'remote'")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL DEFAULT '',
                full_name TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                role TEXT NOT NULL DEFAULT 'doctor' CHECK(role IN ('admin', 'doctor')),
                is_active INTEGER NOT NULL DEFAULT 1,
                token_version INTEGER NOT NULL DEFAULT 0,
                must_change_password INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT ''
            )
            """
        )
        user_columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "must_change_password" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 1")
        if "deleted_at" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN deleted_at TEXT")
        doctor_id_links = {row["name"] for row in conn.execute("PRAGMA table_info(links)").fetchall()}
        if "doctor_id" not in doctor_id_links:
            conn.execute("ALTER TABLE links ADD COLUMN doctor_id INTEGER REFERENCES users(id)")
        doctor_id_encounters = {row["name"] for row in conn.execute("PRAGMA table_info(encounters)").fetchall()}
        if "doctor_id" not in doctor_id_encounters:
            conn.execute("ALTER TABLE encounters ADD COLUMN doctor_id INTEGER REFERENCES users(id)")
        patient_columns = {row["name"] for row in conn.execute("PRAGMA table_info(patients)").fetchall()}
        if "doctor_id" not in patient_columns:
            conn.execute("PRAGMA foreign_keys=OFF")
            conn.executescript("""
                CREATE TABLE patients_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    identification TEXT NOT NULL,
                    full_name TEXT NOT NULL,
                    folder_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    doctor_id INTEGER REFERENCES users(id)
                );
                INSERT INTO patients_new (id, identification, full_name, folder_name, created_at)
                    SELECT id, identification, full_name, folder_name, created_at FROM patients;
                DROP TABLE patients;
                ALTER TABLE patients_new RENAME TO patients;
            """)
            conn.execute("PRAGMA foreign_keys=ON")
        migrate_admin()
    sync_existing_expedientes()


def split_patient_folder_name(folder_name: str) -> tuple[str, str] | None:
    if " - " not in folder_name:
        return None
    full_name, identification = folder_name.rsplit(" - ", 1)
    if not full_name.strip() or not identification.strip():
        return None
    return full_name.strip(), identification.strip()


def sync_existing_expedientes() -> None:
    ensure_dirs()
    with db() as conn:
        for folder in EXPEDIENTES_DIR.iterdir():
            if not folder.is_dir():
                continue
            parsed = split_patient_folder_name(folder.name)
            if not parsed:
                continue
            full_name, identification = parsed
            patient = conn.execute("SELECT * FROM patients WHERE identification = ?", (identification,)).fetchone()
            if patient:
                patient_id = patient["id"]
            else:
                cur = conn.execute(
                    "INSERT INTO patients (identification, full_name, folder_name, created_at, doctor_id) VALUES (?, ?, ?, ?, ?)",
                    (identification, full_name, folder.name, datetime.now().isoformat(), 1),
                )
                patient_id = cur.lastrowid

            def import_pdf(p: Path, enc_subfolder: Path | None = None) -> None:
                existing = conn.execute("SELECT id FROM encounters WHERE pdf_path = ?", (str(p),)).fetchone()
                if existing:
                    return
                date_prefix = p.name[:10]
                parent_dir = enc_subfolder or folder
                front_image = next(parent_dir.glob(f"{date_prefix} - cedula-frontal -*"), None)
                back_image = next(parent_dir.glob(f"{date_prefix} - cedula-trasera -*"), None)
                if not front_image or not back_image:
                    return
                digest = hashlib.sha256(str(p).encode()).hexdigest()[:24]
                token = f"imported-{digest}"
                payload = {
                    "full_name": full_name,
                    "identification": identification,
                    "imported_from_files": "Si",
                    "source": "Expediente existente sincronizado",
                }
                created_at = f"{date_prefix}T00:00:00" if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_prefix) else datetime.now().isoformat()
                enc_folder_path = str(enc_subfolder) if enc_subfolder else None
                admin_id = 1
                conn.execute(
                    """
                    INSERT INTO encounters (patient_id, token, payload, pdf_path, front_image_path, back_image_path, encounter_folder_path, created_at, doctor_id, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'remote')
                    """,
                    (patient_id, token, json.dumps(payload, ensure_ascii=True), str(p), str(front_image), str(back_image), enc_folder_path, created_at, admin_id),
                )

            for pdf_path in folder.glob("*.pdf"):
                import_pdf(pdf_path)

            for subfolder in sorted(folder.iterdir()):
                if not subfolder.is_dir():
                    continue
                if not re.search(r"\d{4}-\d{2}-\d{2} - \d{2}-\d{2} - Atenci", subfolder.name):
                    continue
                for pdf_path in subfolder.glob("*.pdf"):
                    import_pdf(pdf_path, subfolder)


def set_private_cookie(response: RedirectResponse | HTMLResponse, name: str, value: str) -> None:
    response.set_cookie(name, value, httponly=True, samesite="strict", secure=COOKIE_SECURE)


def csrf_token_for(request: Request) -> str:
    token = request.cookies.get(CSRF_COOKIE, "")
    if re.fullmatch(r"[A-Za-z0-9_-]{32,128}", token):
        return token
    return secrets.token_urlsafe(32)


def validate_csrf(request: Request, csrf_token: str) -> None:
    cookie_token = request.cookies.get(CSRF_COOKIE, "")
    if not cookie_token or not hmac.compare_digest(cookie_token, csrf_token):
        raise HTTPException(403, "Solicitud no valida. Recargue la pagina e intente de nuevo.")


def template_with_csrf(request: Request, template_name: str, context: dict[str, Any]) -> HTMLResponse:
    token = csrf_token_for(request)
    response = templates.TemplateResponse(template_name, {**context, "csrf_token": token})
    set_private_cookie(response, CSRF_COOKIE, token)
    return response


@app.on_event("startup")
def startup() -> None:
    if not SECRET_KEY:
        logger.warning("APP_SECRET_KEY no configurada. Usando clave insegura para desarrollo local.")
    if not BASE_URL:
        logger.warning("BASE_URL no configurada. Las URLs generadas se basaran en la solicitud entrante.")
    init_db()


def current_user(request: Request) -> dict | None:
    session = request.cookies.get(SESSION_COOKIE)
    if not session:
        return None
    with db() as conn:
        rows = conn.execute("SELECT id, username, full_name, role, is_active, token_version, must_change_password FROM users").fetchall()
    for row in rows:
        if not row["is_active"]:
            continue
        tv = row["token_version"]
        for version in (tv, tv - 1):
            if hmac.compare_digest(session, session_value(row["id"], version)):
                return dict(row)
    return None


def require_doctor_skip_force(request: Request) -> dict:
    """Checks auth only, does not check must_change_password."""
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user


def require_doctor(request: Request) -> dict:
    user = require_doctor_skip_force(request)
    if user.get("must_change_password"):
        raise HTTPException(status_code=303, headers={"Location": "/doctor/force-change-password"})
    return user


def require_admin(request: Request) -> dict:
    user = require_doctor(request)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado. Se requieren permisos de administrador.")
    return user


def link_unavailable(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("link_unavailable.html", {"request": request})


def load_locations() -> dict[str, Any]:
    global LOCATIONS_CACHE
    if LOCATIONS_CACHE is None:
        with LOCATIONS_PATH.open("r", encoding="utf-8-sig") as locations_file:
            LOCATIONS_CACHE = json.load(locations_file)
    return LOCATIONS_CACHE


def find_location(province_code: str, canton_code: str = "", district_code: str = "") -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
    province = next((item for item in load_locations()["provinces"] if item["code"] == province_code), None)
    canton = None
    district = None
    if province and canton_code:
        canton = next((item for item in province["cantons"] if item["code"] == canton_code), None)
    if canton and district_code:
        district = next((item for item in canton["districts"] if item["district_code"] == district_code), None)
    return province, canton, district


def validate_location_selection(province_code: str, province_name: str, canton_code: str, canton_name: str, locality_code: str, locality_name: str) -> bool:
    province, canton, district = find_location(province_code, canton_code, locality_code)
    if not province or not canton or province["name"] != province_name or canton["name"] != canton_name:
        return False
    if locality_code:
        return bool(district and district["name"] == locality_name)
    return bool(
        locality_name.strip()
        and not any(char in locality_name for char in "<>\x00")
    )


def link_status(link: sqlite3.Row | dict[str, Any], now: datetime | None = None) -> str:
    now = now or datetime.now()
    if link["canceled_at"]:
        return "Cancelado"
    if link["used_at"]:
        return "Completado"
    if datetime.fromisoformat(link["expires_at"]) < now:
        return "Vencido"
    if link["opened_at"]:
        return "Abierto"
    return "Disponible"


def protected_storage_path(path_value: str) -> Path:
    path = Path(path_value)
    if not path.exists() or EXPEDIENTES_DIR not in path.resolve().parents:
        raise HTTPException(404, "Archivo no disponible")
    return path


def deletable_storage_path(path_value: str) -> Path | None:
    path = Path(path_value)
    try:
        resolved = path.resolve()
    except OSError:
        return None
    if EXPEDIENTES_DIR not in resolved.parents:
        return None
    return resolved


def delete_encounter_file(path_value: str, destination_dir: Path | None = None) -> Path | None:
    path = deletable_storage_path(path_value)
    if path and path.exists() and path.is_file():
        move_to_trash(path, destination_dir or trash_scope_dir("archivo eliminado sin contexto"))
        return path.parent
    return path.parent if path else None


def trash_scope_dir(reason: str) -> Path:
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    destination = available_path(TRASH_DIR / f"{stamp} - {safe_name(reason)}")
    destination.mkdir(parents=True, exist_ok=True)
    return destination


def move_to_trash(path: Path, destination_dir: Path) -> Path | None:
    if not path.exists():
        return None
    target = available_path(destination_dir / path.name)
    shutil.move(str(path), str(target))
    return target


def safe_name(value: str) -> str:
    value = re.sub(r"[<>:\"/\\|?*\x00-\x1F]", "", value).strip()
    value = re.sub(r"\s+", " ", value)
    return value[:120] or "sin-nombre"


def validate_identification(kind: str, value: str) -> bool:
    normalized = value.strip()
    if kind == "cedula":
        return bool(re.fullmatch(r"\d-?\d{4}-?\d{4}", normalized))
    if kind == "dimex":
        return bool(re.fullmatch(r"[A-Za-z0-9-]{8,20}", normalized))
    return False


def normalize_cedula(value: str) -> str:
    return re.sub(r"\D", "", value)


def normalize_identification_lookup(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", value).upper()


def validate_cedula_number(value: str) -> bool:
    return bool(re.fullmatch(r"\d{9}", normalize_cedula(value)))


def rate_limited(key: str, max_requests: int = 5, seconds: int = 300) -> bool:
    now = time.time()
    recent = [item for item in TSE_RATE_LIMIT.get(key, []) if now - item < seconds]
    TSE_RATE_LIMIT[key] = recent
    if len(recent) >= max_requests:
        return True
    recent.append(now)
    return False


def lookup_tse_public_data(cedula: str) -> dict[str, str] | None:
    if not TSE_LOOKUP_ENABLED:
        return None
    query = urllib.parse.urlencode({"cedula": cedula})
    url = f"https://servicioselectorales.tse.go.cr/chc/consulta_cedula.aspx?{query}"
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "ExpedienteMedicoDigital/1.0"})
        with urllib.request.urlopen(request, timeout=5) as response:
            html = response.read(200_000).decode("utf-8", errors="ignore")
    except Exception:
        logger.exception("No fue posible consultar datos publicos del TSE para una cedula normalizada")
        return None

    # El sitio no documenta una API publica estable. Solo se extrae el nombre si
    # aparece en texto simple conocido; si no, el formulario continua manual.
    match = re.search(r"Nombre(?:\s+Completo)?\s*</[^>]+>\s*<[^>]+>\s*([^<]+)", html, re.IGNORECASE)
    if not match:
        return None
    full_name = re.sub(r"\s+", " ", match.group(1)).strip()
    if not full_name:
        return None
    return {"full_name": full_name}


def save_upload(upload: UploadFile, destination: Path) -> None:
    allowed = {"image/jpeg", "image/png", "image/webp"}
    if upload.content_type not in allowed:
        raise HTTPException(400, "Solo se permiten imagenes JPG, PNG o WEBP")
    with destination.open("wb") as out:
        shutil.copyfileobj(upload.file, out)
    if destination.stat().st_size > 8 * 1024 * 1024:
        destination.unlink(missing_ok=True)
        raise HTTPException(400, "Cada imagen debe pesar maximo 8 MB")


def image_extension(upload: UploadFile) -> str:
    return {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}.get(upload.content_type or "", ".jpg")


def available_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 1000):
        candidate = path.with_name(f"{path.stem} ({index}){path.suffix}")
        if not candidate.exists():
            return candidate
    raise HTTPException(500, "No se pudo crear un nombre de archivo disponible")


def build_pdf(pdf_path: Path, data: dict[str, Any], front_path: Path, back_path: Path, source: str = "remote") -> None:
    styles = getSampleStyleSheet()
    section_style = ParagraphStyle("SectionTitle", parent=styles["Heading2"], fontSize=10, textColor=colors.HexColor("#1f3a5f"), spaceBefore=12, spaceAfter=4)
    small_style = ParagraphStyle("SmallText", parent=styles["Normal"], fontSize=7.5, leading=9, textColor=colors.HexColor("#555555"))
    cell_style = ParagraphStyle("CellText", parent=styles["Normal"], fontSize=7.5, leading=9)
    label_style = ParagraphStyle("LabelText", parent=cell_style, textColor=colors.HexColor("#333333"))
    value_style = ParagraphStyle("ValueText", parent=cell_style, textColor=colors.HexColor("#111111"))
    obs_hint = ParagraphStyle("ObsHint", parent=styles["Normal"], fontSize=7, textColor=colors.HexColor("#999999"))
    story = []

    story.append(Spacer(1, 4))

    # Header bar
    header_data = [[
        Paragraph("Expediente M\u00e9dico Digital", ParagraphStyle("H", fontSize=13, textColor=colors.white, fontName="Helvetica-Bold", spaceAfter=0, leading=16)),
        Paragraph(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ParagraphStyle("HD", fontSize=7.5, textColor=colors.white, alignment=2, spaceAfter=0, leading=10)),
    ]]
    ht = Table(header_data, colWidths=[300, 210])
    ht.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1f3a5f")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (0, 0), 12),
        ("RIGHTPADDING", (-1, -1), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(ht)
    story.append(Spacer(1, 6))

    # Disclaimer
    disclaimer = (
        "La informaci\u00f3n contenida en este documento corresponde exclusivamente a los datos "
        "proporcionados por el paciente mediante formulario. El paciente declara que los datos "
        "suministrados son reales, correctos y completos. Adem\u00e1s, dicha informaci\u00f3n ser\u00e1 "
        "revisada, verificada y valorada por el m\u00e9dico antes de emitir cualquier criterio cl\u00ednico, "
        "diagn\u00f3stico o decisi\u00f3n m\u00e9dica."
    )
    story.append(Paragraph(disclaimer, small_style))
    origin_text = "Origen del formulario: Atenci\u00f3n presencial." if source == "in_person" else "Origen del formulario: Enlace enviado al paciente."
    story.append(Paragraph(origin_text, small_style))
    story.append(Spacer(1, 10))

    # Field definitions
    labels = {
        "nationality": "Nacionalidad",
        "id_type": "Tipo de identificaci\u00f3n",
        "identification": "Identificaci\u00f3n",
        "full_name": "Nombre completo",
        "whatsapp": "WhatsApp",
        "email": "Email",
        "age": "Edad",
        "birth_date": "Fecha de nacimiento",
        "civil_status": "Estado civil",
        "profession": "Profesi\u00f3n u oficio",
        "province": "Provincia",
        "canton": "Cant\u00f3n",
        "district_or_locality": "Distrito, barrio o localidad",
        "exact_address": "Otras se\u00f1as",
        "organ_donor": "Donador de \u00f3rganos",
        "has_illness": "Padece enfermedades",
        "illnesses": "Enfermedades",
        "treatments": "Medicamentos o tratamientos",
        "smokes": "Fuma",
        "smoke_frequency": "Frecuencia fumado",
        "smoke_product": "Producto fumado",
        "drinks": "Toma licor",
        "drink_frequency": "Consumo de licor",
        "uses_drugs": "Consume drogas",
        "drug_type": "Tipo de droga",
        "drug_frequency": "Frecuencia droga",
        "weight": "Peso",
        "height": "Estatura",
        "uses_glasses": "Usa lentes",
        "glasses_use": "Uso de lentes",
        "laterality": "Lateralidad",
        "license_types": "Tipos de licencia",
        "truth_declaration": "Declaraci\u00f3n de veracidad",
    }
    general_keys = [
        "full_name", "identification", "id_type", "nationality", "age", "birth_date",
        "civil_status", "profession", "whatsapp", "email",
        "province", "canton", "district_or_locality", "exact_address",
    ]
    medical_keys = [
        "organ_donor", "has_illness", "illnesses", "treatments",
        "smokes", "smoke_frequency", "smoke_product",
        "drinks", "drink_frequency",
        "uses_drugs", "drug_type", "drug_frequency",
        "weight", "height", "uses_glasses", "glasses_use", "laterality",
        "license_types", "truth_declaration",
    ]

    def make_table(keys: list[str]) -> Table:
        rows = [
            [
                Paragraph("Campo", ParagraphStyle("Th", parent=cell_style, textColor=colors.white, fontName="Helvetica-Bold")),
                Paragraph("Respuesta", ParagraphStyle("Th", parent=cell_style, textColor=colors.white, fontName="Helvetica-Bold")),
            ]
        ]
        for k in keys:
            v = data.get(k, "")
            if isinstance(v, list):
                v = ", ".join(v)
            rows.append([
                Paragraph(labels.get(k, k), label_style),
                Paragraph(str(v or "No indicado"), value_style),
            ])
        t = Table(rows, colWidths=[145, 365])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a5f")),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d0d7de")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f8fa")]),
        ]))
        return t

    # Section: Datos generales
    story.append(Paragraph("Datos generales del paciente", section_style))
    story.append(make_table(general_keys))
    story.append(Spacer(1, 10))

    # Section: Informacion medica
    story.append(Paragraph("Informaci\u00f3n m\u00e9dica", section_style))
    story.append(make_table(medical_keys))
    story.append(Spacer(1, 14))

    # Section: ID photos
    story.append(Paragraph("Documento de identificaci\u00f3n aportado por el paciente", section_style))
    story.append(Spacer(1, 6))
    try:
        img_w = 200
        img_h = 140
        if front_path.exists() and back_path.exists():
            fi = RLImage(str(front_path), width=img_w, height=img_h, kind="proportional")
            bi = RLImage(str(back_path), width=img_w, height=img_h, kind="proportional")
            pt = Table(
                [
                    [Paragraph("Frontal", ParagraphStyle("FL", parent=styles["Normal"], fontSize=8, alignment=1)),
                     Paragraph("Trasera", ParagraphStyle("FL", parent=styles["Normal"], fontSize=8, alignment=1))],
                    [fi, bi],
                ],
                colWidths=[img_w + 30, img_w + 30],
            )
            pt.setStyle(TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]))
            story.append(pt)
        else:
            if front_path.exists():
                story.append(Paragraph("Frontal", ParagraphStyle("FL", fontSize=8)))
                story.append(RLImage(str(front_path), width=img_w, height=img_h, kind="proportional"))
            if back_path.exists():
                story.append(Paragraph("Trasera", ParagraphStyle("FL", fontSize=8)))
                story.append(RLImage(str(back_path), width=img_w, height=img_h, kind="proportional"))
    except Exception:
        logger.exception("Error al incluir im\u00e1genes de identificaci\u00f3n en el PDF")

    story.append(Spacer(1, 14))
    story.append(Paragraph("Observaciones del m\u00e9dico", section_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph("_" * 65, small_style))
    story.append(Spacer(1, 2))
    story.append(Paragraph("Espacio reservado para anotaciones, diagn\u00f3stico y recomendaciones del m\u00e9dico.", obs_hint))

    SimpleDocTemplate(str(pdf_path), pagesize=letter, rightMargin=36, leftMargin=36, topMargin=28, bottomMargin=28).build(story)


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    if current_user(request):
        return RedirectResponse("/doctor", status_code=303)
    return template_with_csrf(request, "login.html", {"request": request, "error": None, "msg": ""})


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, msg: str = "") -> HTMLResponse:
    return template_with_csrf(request, "login.html", {"request": request, "error": None, "msg": msg})


@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...), csrf_token: str = Form(...)):
    validate_csrf(request, csrf_token)
    user = verify_user_password(username, password)
    if not user:
        return template_with_csrf(request, "login.html", {"request": request, "error": "Credenciales invalidas"})
    response = RedirectResponse("/doctor", status_code=303)
    set_private_cookie(response, SESSION_COOKIE, session_value(user["id"]))
    return response


@app.post("/logout")
def logout(request: Request, csrf_token: str = Form(...)) -> RedirectResponse:
    validate_csrf(request, csrf_token)
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/doctor/force-change-password", response_class=HTMLResponse)
def force_change_password_form(request: Request, user: dict = Depends(require_doctor_skip_force)) -> HTMLResponse:
    if not user.get("must_change_password"):
        return RedirectResponse("/doctor", status_code=303)
    return template_with_csrf(request, "change_password.html", {"request": request, "error": None, "success": None, "force": True})


@app.post("/doctor/force-change-password")
def force_change_password(
    request: Request,
    user: dict = Depends(require_doctor_skip_force),
    csrf_token: str = Form(...),
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
) -> Response:
    validate_csrf(request, csrf_token)
    if not user.get("must_change_password"):
        return RedirectResponse("/doctor", status_code=303)
    error = None
    if not verify_user_password(user["username"], current_password):
        error = "La contrasena actual no es correcta."
    elif new_password != confirm_password:
        error = "La nueva contrasena y la confirmacion no coinciden."
    elif not new_password or len(new_password) < 8:
        error = "La nueva contrasena debe tener al menos 8 caracteres."
    elif new_password == DEFAULT_PASSWORD:
        error = "La nueva contrasena no puede ser la contrasena provisional."
    if error:
        return template_with_csrf(request, "change_password.html", {"request": request, "error": error, "success": None, "force": True})
    set_user_password(user["id"], new_password, must_change=0)
    response = RedirectResponse("/doctor?msg=password_updated", status_code=303)
    set_private_cookie(response, SESSION_COOKIE, session_value(user["id"]))
    return response


@app.get("/doctor/change-password", response_class=HTMLResponse)
def change_password_form(request: Request, _: dict = Depends(require_doctor)) -> HTMLResponse:
    return template_with_csrf(request, "change_password.html", {"request": request, "error": None, "success": None})


@app.post("/doctor/change-password")
def change_password(
    request: Request,
    user: dict = Depends(require_doctor),
    csrf_token: str = Form(...),
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
) -> Response:
    validate_csrf(request, csrf_token)
    error = None
    if not verify_user_password(user["username"], current_password):
        error = "La contrasena actual no es correcta."
    elif new_password != confirm_password:
        error = "La nueva contrasena y la confirmacion no coinciden."
    elif not new_password or len(new_password) < 8:
        error = "La nueva contrasena debe tener al menos 8 caracteres."
    elif new_password == current_password:
        error = "La nueva contrasena no puede ser igual a la actual."
    elif new_password == DEFAULT_PASSWORD:
        error = "La nueva contrasena no puede ser la contrasena provisional."
    if error:
        return template_with_csrf(request, "change_password.html", {"request": request, "error": error, "success": None, "force": False})
    set_user_password(user["id"], new_password, must_change=0)
    response = RedirectResponse("/login?msg=password_changed", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/doctor", response_class=HTMLResponse)
def doctor_panel(request: Request, user: dict = Depends(require_doctor), msg: str = "") -> HTMLResponse:
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start = today_start + timedelta(days=1)
    with db() as conn:
        if user["role"] == "admin":
            links_raw = conn.execute(
                """
                SELECT l.*, p.full_name AS patient_name, p.identification,
                       e.id AS encounter_id, e.created_at AS completed_at,
                       u.username AS doctor_username
                FROM links l
                LEFT JOIN patients p ON l.patient_id = p.id
                LEFT JOIN encounters e ON e.token = l.token
                LEFT JOIN users u ON l.doctor_id = u.id
                WHERE l.created_at >= ? AND l.created_at < ?
                ORDER BY l.created_at DESC
                """,
                (today_start.isoformat(), tomorrow_start.isoformat()),
            ).fetchall()
            encounters_raw = conn.execute(
                """
                SELECT e.id, e.created_at, e.source, p.full_name, p.identification,
                       u.username AS doctor_username
                FROM encounters e
                JOIN patients p ON p.id = e.patient_id
                LEFT JOIN users u ON e.doctor_id = u.id
                WHERE e.created_at >= ? AND e.created_at < ?
                ORDER BY e.created_at DESC
                """,
                (today_start.isoformat(), tomorrow_start.isoformat()),
            ).fetchall()
        else:
            links_raw = conn.execute(
                """
                SELECT l.*, p.full_name AS patient_name, p.identification,
                       e.id AS encounter_id, e.created_at AS completed_at
                FROM links l
                LEFT JOIN patients p ON l.patient_id = p.id
                LEFT JOIN encounters e ON e.token = l.token
                WHERE l.doctor_id = ? AND l.created_at >= ? AND l.created_at < ?
                ORDER BY l.created_at DESC
                """,
                (user["id"], today_start.isoformat(), tomorrow_start.isoformat()),
            ).fetchall()
            encounters_raw = conn.execute(
                """
                SELECT e.id, e.created_at, e.source, p.full_name, p.identification
                FROM encounters e JOIN patients p ON p.id = e.patient_id
                WHERE e.doctor_id = ? AND e.created_at >= ? AND e.created_at < ?
                ORDER BY e.created_at DESC
                """,
                (user["id"], today_start.isoformat(), tomorrow_start.isoformat()),
            ).fetchall()
    links = []
    for link in links_raw:
        d = dict(link)
        d["status_es"] = link_status(link)
        links.append(d)
    success_message = ""
    if msg == "password_updated":
        success_message = "Contrase\u00f1a actualizada correctamente."
    return template_with_csrf(
        request, "doctor.html",
        {"request": request, "links": links, "encounters": encounters_raw, "today": now.date().isoformat(),
         "username": user["username"], "user": user, "base_url": BASE_URL or str(request.base_url).rstrip("/"),
         "APP_ENV": APP_ENV, "success_message": success_message},
    )


@app.get("/doctor/encounters", response_class=HTMLResponse)
def doctor_encounters(request: Request, user: dict = Depends(require_doctor)) -> HTMLResponse:
    return doctor_panel(request, user)


@app.post("/doctor/links")
def create_link(request: Request, user: dict = Depends(require_doctor), csrf_token: str = Form(...)) -> RedirectResponse:
    validate_csrf(request, csrf_token)
    token = secrets.token_urlsafe(24)
    now = datetime.now()
    with db() as conn:
        conn.execute(
            "INSERT INTO links (token, created_at, expires_at, doctor_id) VALUES (?, ?, ?, ?)",
            (token, now.isoformat(), (now + timedelta(days=14)).isoformat(), user["id"]),
        )
    return RedirectResponse("/doctor", status_code=303)


@app.post("/doctor/forms/in-person")
def create_in_person_form(request: Request, user: dict = Depends(require_doctor), csrf_token: str = Form(...)) -> RedirectResponse:
    validate_csrf(request, csrf_token)
    token = secrets.token_urlsafe(24)
    now = datetime.now()
    with db() as conn:
        conn.execute(
            "INSERT INTO links (token, created_at, expires_at, doctor_id, source) VALUES (?, ?, ?, ?, 'in_person')",
            (token, now.isoformat(), (now + timedelta(days=1)).isoformat(), user["id"]),
        )
    return RedirectResponse(f"/patient/{token}?mode=in_person", status_code=303)


@app.post("/doctor/links/{link_id}/delete")
def delete_link(link_id: int, request: Request, user: dict = Depends(require_doctor), csrf_token: str = Form(...)) -> RedirectResponse:
    validate_csrf(request, csrf_token)
    with db() as conn:
        link = conn.execute("SELECT * FROM links WHERE id = ?", (link_id,)).fetchone()
        if not link:
            return RedirectResponse("/doctor", status_code=303)
        if user["role"] != "admin" and link["doctor_id"] != user["id"]:
            raise HTTPException(status_code=403, detail="Acceso denegado.")
        conn.execute("DELETE FROM links WHERE id = ?", (link_id,))
    return RedirectResponse("/doctor", status_code=303)


@app.get("/api/tse/cedula/{cedula}")
def tse_cedula_lookup(cedula: str, request: Request) -> JSONResponse:
    client = request.client.host if request.client else "unknown"
    if rate_limited(client):
        return JSONResponse(
            {
                "success": False,
                "message": "Demasiadas consultas. Complete la informacion manualmente o intente mas tarde.",
            },
            status_code=429,
        )

    normalized = normalize_cedula(cedula)
    if not validate_cedula_number(normalized):
        return JSONResponse(
            {
                "success": False,
                "message": "Digite una cedula nacional valida de 9 digitos.",
            },
            status_code=400,
        )

    result = lookup_tse_public_data(normalized)
    if result:
        return JSONResponse({"success": True, "full_name": result["full_name"], "source": "TSE"})
    return JSONResponse(
        {
            "success": False,
            "message": "No fue posible consultar los datos automaticamente. Complete la informacion manualmente.",
        }
    )


@app.get("/api/locations/provinces")
def locations_provinces() -> JSONResponse:
    provinces = [{"code": item["code"], "name": item["name"]} for item in sorted(load_locations()["provinces"], key=lambda item: int(item["code"]))]
    return JSONResponse({"items": provinces})


@app.get("/api/locations/cantons")
def locations_cantons(province_code: str) -> JSONResponse:
    province, _, _ = find_location(province_code)
    if not province:
        return JSONResponse({"items": []})
    cantons = [{"code": item["code"], "name": item["name"]} for item in sorted(province["cantons"], key=lambda item: int(item["code"]))]
    return JSONResponse({"items": cantons})


@app.get("/api/locations/districts")
def locations_districts(province_code: str, canton_code: str) -> JSONResponse:
    _, canton, _ = find_location(province_code, canton_code)
    if not canton:
        return JSONResponse({"items": []})
    districts = [{"code": item["district_code"], "name": item["name"]} for item in sorted(canton["districts"], key=lambda item: int(item["district_code"]))]
    return JSONResponse({"items": districts})


@app.get("/api/locations/neighborhoods")
def locations_neighborhoods(province_code: str, canton_code: str, district_code: str) -> JSONResponse:
    _, _, district = find_location(province_code, canton_code, district_code)
    if not district:
        return JSONResponse({"items": []})
    neighborhoods = [{"name": item} for item in district.get("neighborhoods", [])]
    return JSONResponse({"items": neighborhoods})


@app.get("/doctor/patients/search", response_class=HTMLResponse)
def patient_search(request: Request, query: str = "", identification: str = "", user: dict = Depends(require_doctor)) -> HTMLResponse:
    results = []
    raw = (query or identification).strip()
    searched = bool(raw)
    if searched:
        like_pattern = f"%{raw}%"
        normalized = normalize_identification_lookup(raw)
        with db() as conn:
            if user["role"] == "admin":
                results = conn.execute(
                    """
                    SELECT e.id, e.created_at, p.full_name, p.identification, e.pdf_path, e.front_image_path, e.back_image_path
                    FROM encounters e JOIN patients p ON p.id = e.patient_id
                    WHERE p.identification = ?
                       OR UPPER(REPLACE(REPLACE(REPLACE(p.identification, '-', ''), ' ', ''), '.', '')) LIKE ?
                       OR LOWER(p.full_name) LIKE ?
                    ORDER BY e.created_at DESC
                    """,
                    (raw, f"%{normalized}%", like_pattern.lower()),
                ).fetchall()
            else:
                results = conn.execute(
                    """
                    SELECT e.id, e.created_at, p.full_name, p.identification, e.pdf_path, e.front_image_path, e.back_image_path
                    FROM encounters e JOIN patients p ON p.id = e.patient_id
                    WHERE e.doctor_id = ? AND (p.identification = ?
                       OR UPPER(REPLACE(REPLACE(REPLACE(p.identification, '-', ''), ' ', ''), '.', '')) LIKE ?
                       OR LOWER(p.full_name) LIKE ?)
                    ORDER BY e.created_at DESC
                    """,
                    (user["id"], raw, f"%{normalized}%", like_pattern.lower()),
                ).fetchall()
    return template_with_csrf(
        request,
        "patient_search.html",
        {"request": request, "query": raw, "results": results, "searched": searched},
    )


@app.get("/patient/{token}", response_class=HTMLResponse)
def patient_form(token: str, request: Request, mode: str = "") -> HTMLResponse:
    with db() as conn:
        link = conn.execute("SELECT * FROM links WHERE token = ?", (token,)).fetchone()
        if link and not link["opened_at"] and not link["used_at"] and not link["canceled_at"] and datetime.fromisoformat(link["expires_at"]) >= datetime.now():
            conn.execute("UPDATE links SET opened_at = ? WHERE token = ?", (datetime.now().isoformat(), token))
            link = conn.execute("SELECT * FROM links WHERE token = ?", (token,)).fetchone()
    if not link or link["used_at"] or link["canceled_at"] or datetime.fromisoformat(link["expires_at"]) < datetime.now():
        return link_unavailable(request)
    is_in_person = mode == "in_person" or link["source"] == "in_person"
    return template_with_csrf(request, "patient.html", {"request": request, "token": token, "is_in_person": is_in_person})


@app.post("/patient/{token}/submit")
def submit_form(
    token: str,
    request: Request,
    nationality: str = Form(...),
    id_type: str = Form(...),
    identification: str = Form(...),
    full_name: str = Form(...),
    whatsapp: str = Form(...),
    email: str = Form(...),
    age: str = Form(...),
    birth_date: str = Form(...),
    civil_status: str = Form(...),
    profession: str = Form(...),
    province: str = Form(...),
    province_code: str = Form(...),
    canton: str = Form(...),
    canton_code: str = Form(...),
    district_or_locality: str = Form(...),
    district_or_locality_code: str = Form(""),
    exact_address: str = Form(...),
    organ_donor: str = Form(...),
    has_illness: str = Form(...),
    illnesses: str = Form(""),
    treatments: str = Form(""),
    smokes: str = Form(...),
    smoke_frequency: str = Form(""),
    smoke_product: str = Form(""),
    drinks: str = Form(...),
    drink_frequency: str = Form(""),
    uses_drugs: str = Form(...),
    drug_type: str = Form(""),
    drug_frequency: str = Form(""),
    weight: str = Form(...),
    height: str = Form(...),
    uses_glasses: str = Form(...),
    glasses_use: str = Form(""),
    laterality: str = Form(...),
    license_types: list[str] = Form(default=[]),
    truth_declaration: str = Form(...),
    csrf_token: str = Form(...),
    cedula_front: UploadFile = File(...),
    cedula_back: UploadFile = File(...),
) -> Response:
    validate_csrf(request, csrf_token)
    if not validate_identification(id_type, identification):
        raise HTTPException(400, "Formato de identificacion invalido")
    if truth_declaration != "accepted":
        raise HTTPException(400, "Debe aceptar la declaracion de veracidad")
    district_or_locality = re.sub(r"\s+", " ", district_or_locality).strip()
    exact_address = re.sub(r"\s+", " ", exact_address).strip()
    if not district_or_locality or not exact_address:
        raise HTTPException(400, "Complete la direccion del paciente")
    if not validate_location_selection(province_code, province, canton_code, canton, district_or_locality_code, district_or_locality):
        raise HTTPException(400, "Seleccione una provincia, canton y distrito/localidad validos")

    with db() as conn:
        link = conn.execute("SELECT * FROM links WHERE token = ?", (token,)).fetchone()
        if not link or link["used_at"] or link["canceled_at"] or datetime.fromisoformat(link["expires_at"]) < datetime.now():
            return link_unavailable(request)
        doctor_id = link["doctor_id"] or 1
        form_source = link["source"] or "remote"

    data = {
        "nationality": nationality,
        "id_type": id_type,
        "identification": identification,
        "full_name": full_name,
        "whatsapp": whatsapp,
        "email": email,
        "age": age,
        "birth_date": birth_date,
        "civil_status": civil_status,
        "profession": profession,
        "province": province,
        "province_code": province_code,
        "canton": canton,
        "canton_code": canton_code,
        "district_or_locality": district_or_locality,
        "district_or_locality_code": district_or_locality_code,
        "exact_address": exact_address,
        "organ_donor": organ_donor,
        "has_illness": has_illness,
        "illnesses": illnesses,
        "treatments": treatments,
        "smokes": smokes,
        "smoke_frequency": smoke_frequency,
        "smoke_product": smoke_product,
        "drinks": drinks,
        "drink_frequency": drink_frequency,
        "uses_drugs": uses_drugs,
        "drug_type": drug_type,
        "drug_frequency": drug_frequency,
        "weight": weight,
        "height": height,
        "uses_glasses": uses_glasses,
        "glasses_use": glasses_use,
        "laterality": laterality,
        "license_types": license_types,
        "truth_declaration": truth_declaration,
    }
    clean_full_name = safe_name(full_name)
    clean_id = safe_name(identification)
    doc_username = get_doctor_username(doctor_id)
    doc_dir = doctor_expedientes_dir(doc_username)

    with db() as conn:
        existing_patient = conn.execute(
            "SELECT * FROM patients WHERE identification = ? AND (doctor_id = ? OR doctor_id IS NULL)",
            (identification, doctor_id),
        ).fetchone()

    folder_name = existing_patient["folder_name"] if existing_patient else f"{clean_full_name} - {clean_id}"
    patient_folder = doc_dir / safe_name(folder_name)
    patient_folder.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    date_prefix = now.strftime("%Y-%m-%d")
    time_prefix = now.strftime("%H-%M")
    encounter_folder_name = f"{date_prefix} - {time_prefix} - Atenci\u00f3n"
    encounter_folder = patient_folder / encounter_folder_name
    encounter_folder.mkdir(parents=True, exist_ok=True)

    base_doc_name = f"{date_prefix} - {clean_full_name} - {clean_id}"
    front_path = available_path(encounter_folder / f"{date_prefix} - cedula-frontal - {clean_full_name} - {clean_id}{image_extension(cedula_front)}")
    back_path = available_path(encounter_folder / f"{date_prefix} - cedula-trasera - {clean_full_name} - {clean_id}{image_extension(cedula_back)}")
    pdf_path = available_path(encounter_folder / f"{base_doc_name}.pdf")

    save_upload(cedula_front, front_path)
    save_upload(cedula_back, back_path)
    build_pdf(pdf_path, data, front_path, back_path, form_source)

    try:
        with db() as conn:
            if existing_patient:
                patient_id = existing_patient["id"]
            else:
                cur = conn.execute(
                    "INSERT INTO patients (identification, full_name, folder_name, created_at, doctor_id) VALUES (?, ?, ?, ?, ?)",
                    (identification, full_name, folder_name, datetime.now().isoformat(), doctor_id),
                )
                patient_id = cur.lastrowid
            conn.execute(
                """
                INSERT INTO encounters (patient_id, token, payload, pdf_path, front_image_path, back_image_path, encounter_folder_path, created_at, doctor_id, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (patient_id, token, json.dumps(data, ensure_ascii=True), str(pdf_path), str(front_path), str(back_path), str(encounter_folder), datetime.now().isoformat(), doctor_id, form_source),
            )
            conn.execute("UPDATE links SET used_at = ?, patient_id = ? WHERE token = ?", (datetime.now().isoformat(), patient_id, token))
    except Exception:
        logger.exception("Error registrando la atencion despues de generar el PDF: %s", pdf_path)

    thank_you_mode = "in_person" if form_source == "in_person" else ""
    return RedirectResponse(f"/thank-you?mode={thank_you_mode}", status_code=303)


@app.get("/thank-you", response_class=HTMLResponse)
def thank_you(request: Request, mode: str = "") -> HTMLResponse:
    is_in_person = mode == "in_person"
    return templates.TemplateResponse("thank_you.html", {"request": request, "is_in_person": is_in_person})


@app.get("/patient/{token}/thanks", response_class=HTMLResponse)
def legacy_patient_thanks(token: str, request: Request) -> HTMLResponse:
    return RedirectResponse("/thank-you", status_code=303)


@app.get("/doctor/encounters/{encounter_id}/pdf")
def download_pdf(encounter_id: int, user: dict = Depends(require_doctor)) -> FileResponse:
    encounter = can_access_encounter(user, encounter_id)
    if not encounter:
        raise HTTPException(404, "Documento no encontrado")
    path = protected_storage_path(encounter["pdf_path"])
    return FileResponse(path, media_type="application/pdf", filename=path.name)


@app.get("/doctor/encounters/{encounter_id}", response_class=HTMLResponse)
def encounter_detail(encounter_id: int, request: Request, user: dict = Depends(require_doctor)) -> HTMLResponse:
    encounter = can_access_encounter(user, encounter_id)
    if not encounter:
        raise HTTPException(404, "Atencion no encontrada")
    payload = json.loads(encounter["payload"])
    return template_with_csrf(
        request,
        "encounter_detail.html",
        {"request": request, "encounter": encounter, "payload": payload, "base_url": BASE_URL or str(request.base_url).rstrip("/")},
    )


@app.post("/doctor/encounters/{encounter_id}/delete")
def delete_encounter(encounter_id: int, request: Request, user: dict = Depends(require_doctor), csrf_token: str = Form(...)) -> RedirectResponse:
    validate_csrf(request, csrf_token)
    encounter = can_access_encounter(user, encounter_id)
    if not encounter:
        return RedirectResponse("/doctor", status_code=303)
    with db() as conn:

        trash_dir = trash_scope_dir(f"atencion {encounter_id}")

        if encounter["encounter_folder_path"]:
            enc_folder = Path(encounter["encounter_folder_path"])
            if enc_folder.exists() and enc_folder.is_dir() and EXPEDIENTES_DIR in enc_folder.resolve().parents:
                shutil.move(str(enc_folder), str(trash_dir / enc_folder.name))
                patient_folder = enc_folder.parent
                try:
                    if patient_folder != EXPEDIENTES_DIR.resolve() and patient_folder.exists() and not any(patient_folder.iterdir()):
                        patient_folder.rmdir()
                except OSError:
                    logger.exception("No se pudo eliminar carpeta vacia de expediente: %s", patient_folder)
        else:
            touched_folders = []
            for column in ("pdf_path", "front_image_path", "back_image_path"):
                source_path = deletable_storage_path(encounter[column])
                destination_dir = trash_dir / safe_name(source_path.parent.name) if source_path else trash_dir
                destination_dir.mkdir(parents=True, exist_ok=True)
                folder = delete_encounter_file(encounter[column], destination_dir)
                if folder:
                    touched_folders.append(folder)
            for folder in set(touched_folders):
                try:
                    if folder != EXPEDIENTES_DIR.resolve() and folder.exists() and not any(folder.iterdir()):
                        folder.rmdir()
                except OSError:
                    logger.exception("No se pudo eliminar carpeta vacia de expediente: %s", folder)

        conn.execute("DELETE FROM encounters WHERE id = ?", (encounter_id,))
        conn.execute("DELETE FROM links WHERE token = ?", (encounter["token"],))

    return RedirectResponse("/doctor", status_code=303)


@app.get("/doctor/encounters/{encounter_id}/images/{side}")
def view_identification_image(encounter_id: int, side: str, request: Request, user: dict = Depends(require_doctor)) -> HTMLResponse:
    if side not in {"front", "back"}:
        raise HTTPException(404, "Imagen no encontrada")
    encounter = can_access_encounter(user, encounter_id)
    if not encounter:
        raise HTTPException(404, "Imagen no encontrada")
    side_label = "frontal" if side == "front" else "trasera"
    return templates.TemplateResponse(
        "image_viewer.html",
        {"request": request, "encounter": encounter, "side": side, "side_label": side_label},
    )


@app.get("/doctor/encounters/{encounter_id}/images/{side}/raw")
def raw_identification_image(encounter_id: int, side: str, user: dict = Depends(require_doctor)) -> FileResponse:
    if side not in {"front", "back"}:
        raise HTTPException(404, "Imagen no encontrada")
    encounter = can_access_encounter(user, encounter_id)
    if not encounter:
        raise HTTPException(404, "Imagen no encontrada")
    column = "front_image_path" if side == "front" else "back_image_path"
    path = protected_storage_path(encounter[column])
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type, headers={"Content-Disposition": "inline"})


@app.get("/doctor/encounters/{encounter_id}/share", response_class=HTMLResponse)
def share_pdf(encounter_id: int, request: Request, user: dict = Depends(require_doctor)) -> HTMLResponse:
    encounter = can_access_encounter(user, encounter_id)
    if not encounter:
        raise HTTPException(404, "Documento no encontrado")
    return templates.TemplateResponse(
        "share_pdf.html",
        {"request": request, "encounter": encounter, "pdf_url": f"{(BASE_URL or str(request.base_url).rstrip('/'))}/doctor/encounters/{encounter_id}/pdf"},
    )


# --- Admin: User management ---

@app.get("/doctor/users", response_class=HTMLResponse)
def users_list(request: Request, _: dict = Depends(require_admin)) -> HTMLResponse:
    with db() as conn:
        users_raw = conn.execute(
                "SELECT id, username, full_name, email, role, is_active, must_change_password, deleted_at, created_at FROM users ORDER BY id"
            ).fetchall()
    return template_with_csrf(
        request, "users_list.html",
        {"request": request, "users": users_raw},
    )


@app.get("/doctor/users/new", response_class=HTMLResponse)
def user_new_form(request: Request, _: dict = Depends(require_admin)) -> HTMLResponse:
    return template_with_csrf(request, "user_form.html", {"request": request, "user": None, "error": None})


@app.post("/doctor/users/new")
def user_new(
    request: Request,
    _: dict = Depends(require_admin),
    csrf_token: str = Form(...),
    username: str = Form(...),
    full_name: str = Form(...),
    role: str = Form("doctor"),
) -> Response:
    validate_csrf(request, csrf_token)
    if not username:
        return template_with_csrf(request, "user_form.html", {"request": request, "user": None, "error": "Nombre de usuario es requerido."})
    if role not in ("admin", "doctor"):
        role = "doctor"
    hashed = hash_password(DEFAULT_PASSWORD)
    try:
        with db() as conn:
            conn.execute(
                "INSERT INTO users (username, password_hash, full_name, role, must_change_password, created_at, updated_at) VALUES (?, ?, ?, ?, 1, ?, ?)",
                (username, hashed, full_name, role, datetime.now().isoformat(), datetime.now().isoformat()),
            )
    except sqlite3.IntegrityError:
        return template_with_csrf(request, "user_form.html", {"request": request, "user": None, "error": f"El usuario '{username}' ya existe."})
    return RedirectResponse("/doctor/users", status_code=303)


@app.get("/doctor/users/{user_id}/edit", response_class=HTMLResponse)
def user_edit_form(user_id: int, request: Request, _: dict = Depends(require_admin)) -> HTMLResponse:
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(404, "Usuario no encontrado")
    return template_with_csrf(request, "user_form.html", {"request": request, "user": user, "error": None})


@app.post("/doctor/users/{user_id}/edit")
def user_edit(
    user_id: int,
    request: Request,
    _: dict = Depends(require_admin),
    csrf_token: str = Form(...),
    full_name: str = Form(...),
    email: str = Form(...),
    role: str = Form("doctor"),
    is_active: str = Form("0"),
) -> Response:
    validate_csrf(request, csrf_token)
    if role not in ("admin", "doctor"):
        role = "doctor"
    active = 1 if is_active == "1" else 0
    with db() as conn:
        conn.execute(
            "UPDATE users SET full_name = ?, email = ?, role = ?, is_active = ?, updated_at = ? WHERE id = ?",
            (full_name, email, role, active, datetime.now().isoformat(), user_id),
        )
    return RedirectResponse("/doctor/users", status_code=303)


@app.post("/doctor/users/{user_id}/reset-password")
def user_reset_password(
    user_id: int,
    request: Request,
    _: dict = Depends(require_admin),
    csrf_token: str = Form(...),
) -> Response:
    validate_csrf(request, csrf_token)
    set_user_password(user_id, DEFAULT_PASSWORD, must_change=1)
    return RedirectResponse("/doctor/users", status_code=303)


@app.post("/doctor/users/{user_id}/suspend")
def user_suspend(
    user_id: int,
    request: Request,
    admin: dict = Depends(require_admin),
    csrf_token: str = Form(...),
) -> Response:
    validate_csrf(request, csrf_token)
    if user_id == admin["id"]:
        return template_with_csrf(request, "users_list.html", {"request": request, "users": _all_users(), "error": "No puede suspenderse a si mismo."})
    with db() as conn:
        target = conn.execute("SELECT id, role, is_active FROM users WHERE id = ?", (user_id,)).fetchone()
        if not target:
            raise HTTPException(404, "Usuario no encontrado")
        if target["role"] == "admin":
            admins = conn.execute("SELECT COUNT(*) AS cnt FROM users WHERE role = 'admin' AND is_active = 1 AND deleted_at IS NULL").fetchone()
            if admins["cnt"] <= 1:
                return template_with_csrf(request, "users_list.html", {"request": request, "users": _all_users(), "error": "No puede suspender al unico administrador activo."})
        conn.execute("UPDATE users SET is_active = 0, updated_at = ? WHERE id = ?", (datetime.now().isoformat(), user_id))
    return RedirectResponse("/doctor/users", status_code=303)


@app.post("/doctor/users/{user_id}/reactivate")
def user_reactivate(
    user_id: int,
    request: Request,
    _: dict = Depends(require_admin),
    csrf_token: str = Form(...),
) -> Response:
    validate_csrf(request, csrf_token)
    with db() as conn:
        target = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if not target:
            raise HTTPException(404, "Usuario no encontrado")
        conn.execute("UPDATE users SET is_active = 1, deleted_at = NULL, updated_at = ? WHERE id = ?", (datetime.now().isoformat(), user_id))
    return RedirectResponse("/doctor/users", status_code=303)


@app.post("/doctor/users/{user_id}/delete")
def user_delete(
    user_id: int,
    request: Request,
    admin: dict = Depends(require_admin),
    csrf_token: str = Form(...),
) -> Response:
    validate_csrf(request, csrf_token)
    if user_id == admin["id"]:
        return template_with_csrf(request, "users_list.html", {"request": request, "users": _all_users(), "error": "No puede borrarse a si mismo."})
    with db() as conn:
        target = conn.execute("SELECT id, role FROM users WHERE id = ?", (user_id,)).fetchone()
        if not target:
            raise HTTPException(404, "Usuario no encontrado")
        if target["role"] == "admin":
            admins = conn.execute("SELECT COUNT(*) AS cnt FROM users WHERE role = 'admin' AND deleted_at IS NULL").fetchone()
            if admins["cnt"] <= 1:
                return template_with_csrf(request, "users_list.html", {"request": request, "users": _all_users(), "error": "No puede borrar al unico administrador."})
        conn.execute("UPDATE users SET is_active = 0, deleted_at = ?, updated_at = ? WHERE id = ?", (datetime.now().isoformat(), datetime.now().isoformat(), user_id))
    return RedirectResponse("/doctor/users", status_code=303)


def _all_users() -> list:
    with db() as conn:
        return conn.execute(
            "SELECT id, username, full_name, email, role, is_active, must_change_password, deleted_at, created_at FROM users ORDER BY id"
        ).fetchall()
