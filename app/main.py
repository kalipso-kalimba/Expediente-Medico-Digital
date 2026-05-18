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

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
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
SECRET_KEY = os.getenv("APP_SECRET_KEY", "dev-secret-change-me")
DOCTOR_USERNAME = os.getenv("DOCTOR_USERNAME", "doctor")
DOCTOR_PASSWORD = os.getenv("DOCTOR_PASSWORD", "Cambiar123!")
COOKIE_SECURE = os.getenv("APP_COOKIE_SECURE", "false").lower() in {"1", "true", "yes", "on"}
TSE_LOOKUP_ENABLED = os.getenv("TSE_LOOKUP_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
BASE_URL = os.getenv("BASE_URL", "").rstrip("/")
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
                    "INSERT INTO patients (identification, full_name, folder_name, created_at) VALUES (?, ?, ?, ?)",
                    (identification, full_name, folder.name, datetime.now().isoformat()),
                )
                patient_id = cur.lastrowid

            for pdf_path in folder.glob("*.pdf"):
                existing = conn.execute("SELECT id FROM encounters WHERE pdf_path = ?", (str(pdf_path),)).fetchone()
                if existing:
                    continue
                date_prefix = pdf_path.name[:10]
                front_image = next(folder.glob(f"{date_prefix} - cedula-frontal -*"), None)
                back_image = next(folder.glob(f"{date_prefix} - cedula-trasera -*"), None)
                if not front_image or not back_image:
                    continue
                digest = hashlib.sha256(str(pdf_path).encode()).hexdigest()[:24]
                token = f"imported-{digest}"
                payload = {
                    "full_name": full_name,
                    "identification": identification,
                    "imported_from_files": "Si",
                    "source": "Expediente existente sincronizado",
                }
                created_at = f"{date_prefix}T00:00:00" if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_prefix) else datetime.now().isoformat()
                conn.execute(
                    """
                    INSERT INTO encounters (patient_id, token, payload, pdf_path, front_image_path, back_image_path, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (patient_id, token, json.dumps(payload, ensure_ascii=True), str(pdf_path), str(front_image), str(back_image), created_at),
                )


def session_value() -> str:
    return hmac.new(SECRET_KEY.encode(), DOCTOR_USERNAME.encode(), "sha256").hexdigest()


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
    init_db()


def current_user(request: Request) -> str | None:
    session = request.cookies.get(SESSION_COOKIE)
    if session and hmac.compare_digest(session, session_value()):
        return DOCTOR_USERNAME
    return None


def require_doctor(request: Request) -> str:
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user


def link_unavailable(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("link_unavailable.html", {"request": request}, status_code=404)


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


def build_pdf(pdf_path: Path, data: dict[str, Any], front_name: str, back_name: str) -> None:
    styles = getSampleStyleSheet()
    story = [Paragraph("Informe de formulario medico", styles["Title"]), Spacer(1, 12)]
    story.append(Paragraph(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["Normal"]))
    story.append(Spacer(1, 12))

    rows = [["Campo", "Respuesta"]]
    labels = {
        "nationality": "Nacionalidad",
        "id_type": "Tipo de identificacion",
        "identification": "Identificacion",
        "full_name": "Nombre completo",
        "whatsapp": "WhatsApp",
        "email": "Email",
        "age": "Edad",
        "birth_date": "Fecha de nacimiento",
        "civil_status": "Estado civil",
        "profession": "Profesion u oficio",
        "province": "Provincia",
        "canton": "Canton",
        "district_or_locality": "Distrito, barrio o localidad",
        "exact_address": "Otras senas",
        "organ_donor": "Donador de organos",
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
        "truth_declaration": "Declaracion de veracidad",
    }
    for key, label in labels.items():
        value = data.get(key, "")
        if isinstance(value, list):
            value = ", ".join(value)
        rows.append([label, str(value or "No indicado")])
    rows.append(["Fotografia frontal", front_name])
    rows.append(["Fotografia trasera", back_name])

    table = Table(rows, colWidths=[180, 330])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a5f")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f7fb")]),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 18))
    story.append(Paragraph("Observaciones del medico:", styles["Heading2"]))
    story.append(Paragraph("_______________________________________________", styles["Normal"]))
    SimpleDocTemplate(str(pdf_path), pagesize=letter, rightMargin=36, leftMargin=36).build(story)


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    if current_user(request):
        return RedirectResponse("/doctor", status_code=303)
    return template_with_csrf(request, "login.html", {"request": request, "error": None})


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse:
    return template_with_csrf(request, "login.html", {"request": request, "error": None})


@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...), csrf_token: str = Form(...)):
    validate_csrf(request, csrf_token)
    if username != DOCTOR_USERNAME or password != DOCTOR_PASSWORD:
        return template_with_csrf(request, "login.html", {"request": request, "error": "Credenciales invalidas"})
    response = RedirectResponse("/doctor", status_code=303)
    set_private_cookie(response, SESSION_COOKIE, session_value())
    return response


@app.post("/logout")
def logout(request: Request, csrf_token: str = Form(...)) -> RedirectResponse:
    validate_csrf(request, csrf_token)
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/doctor", response_class=HTMLResponse)
def doctor_panel(request: Request, _: str = Depends(require_doctor)) -> HTMLResponse:
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start = today_start + timedelta(days=1)
    with db() as conn:
        link_rows = conn.execute(
            """
            SELECT l.*, e.id AS encounter_id, e.pdf_path, e.created_at AS completed_at, p.full_name, p.identification
            FROM links l
            LEFT JOIN encounters e ON e.token = l.token
            LEFT JOIN patients p ON p.id = e.patient_id
            ORDER BY l.created_at DESC LIMIT 25
            """
        ).fetchall()
        encounters = conn.execute(
            """
            SELECT e.id, e.created_at, p.full_name, p.identification, e.pdf_path, e.front_image_path, e.back_image_path
            FROM encounters e JOIN patients p ON p.id = e.patient_id
            WHERE e.created_at >= ? AND e.created_at < ?
            ORDER BY e.created_at DESC LIMIT 50
            """,
            (today_start.isoformat(), tomorrow_start.isoformat()),
        ).fetchall()
    links = [{**dict(link), "status": link_status(link, now)} for link in link_rows]
    return template_with_csrf(
        request,
        "doctor.html",
        {"request": request, "links": links, "encounters": encounters, "base_url": BASE_URL or str(request.base_url).rstrip("/")},
    )


@app.get("/doctor/encounters", response_class=HTMLResponse)
def doctor_encounters(request: Request, _: str = Depends(require_doctor)) -> HTMLResponse:
    return doctor_panel(request, _)


@app.post("/doctor/links")
def create_link(request: Request, _: str = Depends(require_doctor), csrf_token: str = Form(...)) -> RedirectResponse:
    validate_csrf(request, csrf_token)
    token = secrets.token_urlsafe(24)
    now = datetime.now()
    with db() as conn:
        conn.execute(
            "INSERT INTO links (token, created_at, expires_at) VALUES (?, ?, ?)",
            (token, now.isoformat(), (now + timedelta(days=14)).isoformat()),
        )
    return RedirectResponse("/doctor", status_code=303)


@app.post("/doctor/links/{link_id}/delete")
def delete_link(link_id: int, request: Request, _: str = Depends(require_doctor), csrf_token: str = Form(...)) -> RedirectResponse:
    validate_csrf(request, csrf_token)
    with db() as conn:
        link = conn.execute("SELECT * FROM links WHERE id = ?", (link_id,)).fetchone()
        if not link:
            return RedirectResponse("/doctor", status_code=303)
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
def patient_search(request: Request, identification: str = "", _: str = Depends(require_doctor)) -> HTMLResponse:
    results = []
    identification = identification.strip()
    normalized_identification = normalize_identification_lookup(identification)
    searched = bool(identification)
    if searched:
        with db() as conn:
            results = conn.execute(
                """
                SELECT e.id, e.created_at, p.full_name, p.identification, e.pdf_path, e.front_image_path, e.back_image_path
                FROM encounters e JOIN patients p ON p.id = e.patient_id
                WHERE p.identification = ?
                   OR UPPER(REPLACE(REPLACE(REPLACE(p.identification, '-', ''), ' ', ''), '.', '')) = ?
                ORDER BY e.created_at DESC
                """,
                (identification, normalized_identification),
            ).fetchall()
    return template_with_csrf(
        request,
        "patient_search.html",
        {"request": request, "identification": identification, "results": results, "searched": searched},
    )


@app.get("/patient/{token}", response_class=HTMLResponse)
def patient_form(token: str, request: Request) -> HTMLResponse:
    with db() as conn:
        link = conn.execute("SELECT * FROM links WHERE token = ?", (token,)).fetchone()
        if link and not link["opened_at"] and not link["used_at"] and not link["canceled_at"] and datetime.fromisoformat(link["expires_at"]) >= datetime.now():
            conn.execute("UPDATE links SET opened_at = ? WHERE token = ?", (datetime.now().isoformat(), token))
    if not link or link["used_at"] or link["canceled_at"] or datetime.fromisoformat(link["expires_at"]) < datetime.now():
        return link_unavailable(request)
    return template_with_csrf(request, "patient.html", {"request": request, "token": token})


@app.post("/patient/{token}/submit")
async def submit_form(
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
    license_types: list[str] = Form(...),
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

    with db() as conn:
        existing_patient = conn.execute("SELECT * FROM patients WHERE identification = ?", (identification,)).fetchone()

    folder_name = existing_patient["folder_name"] if existing_patient else f"{clean_full_name} - {clean_id}"
    patient_folder = EXPEDIENTES_DIR / safe_name(folder_name)
    patient_folder.mkdir(parents=True, exist_ok=True)
    date_prefix = datetime.now().strftime("%Y-%m-%d")
    base_doc_name = f"{date_prefix} - {clean_full_name} - {clean_id}"
    front_path = available_path(patient_folder / f"{date_prefix} - cedula-frontal - {clean_full_name} - {clean_id}{image_extension(cedula_front)}")
    back_path = available_path(patient_folder / f"{date_prefix} - cedula-trasera - {clean_full_name} - {clean_id}{image_extension(cedula_back)}")
    pdf_path = available_path(patient_folder / f"{base_doc_name}.pdf")

    save_upload(cedula_front, front_path)
    save_upload(cedula_back, back_path)
    build_pdf(pdf_path, data, front_path.name, back_path.name)

    try:
        with db() as conn:
            if existing_patient:
                patient_id = existing_patient["id"]
            else:
                cur = conn.execute(
                    "INSERT INTO patients (identification, full_name, folder_name, created_at) VALUES (?, ?, ?, ?)",
                    (identification, full_name, folder_name, datetime.now().isoformat()),
                )
                patient_id = cur.lastrowid
            conn.execute(
                """
                INSERT INTO encounters (patient_id, token, payload, pdf_path, front_image_path, back_image_path, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (patient_id, token, json.dumps(data, ensure_ascii=True), str(pdf_path), str(front_path), str(back_path), datetime.now().isoformat()),
            )
            conn.execute("UPDATE links SET used_at = ? WHERE token = ?", (datetime.now().isoformat(), token))
    except Exception:
        logger.exception("Error registrando la atencion despues de generar el PDF: %s", pdf_path)

    return RedirectResponse("/thank-you", status_code=303)


@app.get("/thank-you", response_class=HTMLResponse)
def thank_you(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("thank_you.html", {"request": request})


@app.get("/patient/{token}/thanks", response_class=HTMLResponse)
def legacy_patient_thanks(token: str, request: Request) -> HTMLResponse:
    return RedirectResponse("/thank-you", status_code=303)


@app.get("/doctor/encounters/{encounter_id}/pdf")
def download_pdf(encounter_id: int, _: str = Depends(require_doctor)) -> FileResponse:
    with db() as conn:
        encounter = conn.execute("SELECT pdf_path FROM encounters WHERE id = ?", (encounter_id,)).fetchone()
    if not encounter:
        raise HTTPException(404, "Documento no encontrado")
    path = protected_storage_path(encounter["pdf_path"])
    return FileResponse(path, media_type="application/pdf", filename=path.name)


@app.get("/doctor/encounters/{encounter_id}", response_class=HTMLResponse)
def encounter_detail(encounter_id: int, request: Request, _: str = Depends(require_doctor)) -> HTMLResponse:
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
        raise HTTPException(404, "Atencion no encontrada")
    payload = json.loads(encounter["payload"])
    return template_with_csrf(
        request,
        "encounter_detail.html",
        {"request": request, "encounter": encounter, "payload": payload, "base_url": BASE_URL or str(request.base_url).rstrip("/")},
    )


@app.post("/doctor/encounters/{encounter_id}/delete")
def delete_encounter(encounter_id: int, request: Request, _: str = Depends(require_doctor), csrf_token: str = Form(...)) -> RedirectResponse:
    validate_csrf(request, csrf_token)
    with db() as conn:
        encounter = conn.execute(
            "SELECT id, token, pdf_path, front_image_path, back_image_path FROM encounters WHERE id = ?",
            (encounter_id,),
        ).fetchone()
        if not encounter:
            return RedirectResponse("/doctor", status_code=303)

        touched_folders = []
        trash_dir = trash_scope_dir(f"atencion {encounter_id}")
        for column in ("pdf_path", "front_image_path", "back_image_path"):
            source_path = deletable_storage_path(encounter[column])
            destination_dir = trash_dir / safe_name(source_path.parent.name) if source_path else trash_dir
            destination_dir.mkdir(parents=True, exist_ok=True)
            folder = delete_encounter_file(encounter[column], destination_dir)
            if folder:
                touched_folders.append(folder)

        conn.execute("DELETE FROM encounters WHERE id = ?", (encounter_id,))
        conn.execute("DELETE FROM links WHERE token = ?", (encounter["token"],))

    for folder in set(touched_folders):
        try:
            if folder != EXPEDIENTES_DIR.resolve() and folder.exists() and not any(folder.iterdir()):
                folder.rmdir()
        except OSError:
            logger.exception("No se pudo eliminar carpeta vacia de expediente: %s", folder)
    return RedirectResponse("/doctor", status_code=303)


@app.get("/doctor/encounters/{encounter_id}/images/{side}")
def view_identification_image(encounter_id: int, side: str, request: Request, _: str = Depends(require_doctor)) -> HTMLResponse:
    if side not in {"front", "back"}:
        raise HTTPException(404, "Imagen no encontrada")
    with db() as conn:
        encounter = conn.execute(
            """
            SELECT e.id, e.created_at, p.full_name, p.identification
            FROM encounters e JOIN patients p ON p.id = e.patient_id
            WHERE e.id = ?
            """,
            (encounter_id,),
        ).fetchone()
    if not encounter:
        raise HTTPException(404, "Imagen no encontrada")
    side_label = "frontal" if side == "front" else "trasera"
    return templates.TemplateResponse(
        "image_viewer.html",
        {"request": request, "encounter": encounter, "side": side, "side_label": side_label},
    )


@app.get("/doctor/encounters/{encounter_id}/images/{side}/raw")
def raw_identification_image(encounter_id: int, side: str, _: str = Depends(require_doctor)) -> FileResponse:
    if side not in {"front", "back"}:
        raise HTTPException(404, "Imagen no encontrada")
    column = "front_image_path" if side == "front" else "back_image_path"
    with db() as conn:
        encounter = conn.execute(f"SELECT {column} FROM encounters WHERE id = ?", (encounter_id,)).fetchone()
    if not encounter:
        raise HTTPException(404, "Imagen no encontrada")
    path = protected_storage_path(encounter[column])
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type, headers={"Content-Disposition": "inline"})


@app.get("/doctor/encounters/{encounter_id}/share", response_class=HTMLResponse)
def share_pdf(encounter_id: int, request: Request, _: str = Depends(require_doctor)) -> HTMLResponse:
    with db() as conn:
        encounter = conn.execute(
            """
            SELECT e.id, e.created_at, p.full_name, p.identification
            FROM encounters e JOIN patients p ON p.id = e.patient_id
            WHERE e.id = ?
            """,
            (encounter_id,),
        ).fetchone()
    if not encounter:
        raise HTTPException(404, "Documento no encontrado")
    return templates.TemplateResponse(
        "share_pdf.html",
        {"request": request, "encounter": encounter, "pdf_url": f"{(BASE_URL or str(request.base_url).rstrip('/'))}/doctor/encounters/{encounter_id}/pdf"},
    )
