# Expediente Médico Digital

Sistema web para formularios médicos. Generación de enlaces únicos para pacientes, carga de fotografías de cédula/DIMEX, generación de PDF, panel privado para el médico.

## Ejecutar localmente

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Luego abra `http://127.0.0.1:8000`.

## Acceso médico

- Usuario: `doctor`
- Contraseña: `Cambiar123!`

Cambie estos valores en producción usando variables de entorno.

## Variables de entorno

| Variable | Descripción | Ejemplo |
|---|---|---|
| `APP_SECRET_KEY` | Clave secreta para sesiones | `cambiar-por-clave-segura` |
| `DOCTOR_USERNAME` | Usuario del médico | `doctor` |
| `DOCTOR_PASSWORD` | Contraseña del médico | `Cambiar123!` |
| `APP_COOKIE_SECURE` | Cookies seguras (true en HTTPS) | `true` |
| `BASE_URL` | URL pública del sitio | `https://formulariodigital.onrender.com` |
| `TSE_LOOKUP_ENABLED` | Consulta automática al TSE | `false` |

## Despliegue en Render

### Build Command

```bash
pip install -r requirements.txt
```

### Start Command

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Variables requeridas en Render

Debe configurar estas variables en el dashboard de Render:

- `APP_SECRET_KEY` (obligatoria)
- `DOCTOR_USERNAME`
- `DOCTOR_PASSWORD`
- `APP_COOKIE_SECURE=true`
- `BASE_URL=https://formulariodigital.onrender.com`

### Limitaciones de Render Free

- El almacenamiento es efímero: los datos se pierden al reiniciar o redeploy.
- SQLite y archivos locales no persisten entre reinicios.
- Para producción real se recomienda migrar a PostgreSQL y almacenamiento externo.
- El servicio se duerme tras 15 minutos sin actividad.
- Límite de 750 horas/mes.

## Estructura

```text
Expediente de pacientes/
└── Nombre del paciente - número de cédula o DIMEX/
    ├── 2026-05-18 - Nombre del paciente - número.pdf
    ├── 2026-05-18 - cedula-frontal - Nombre.jpg
    └── 2026-05-18 - cedula-trasera - Nombre.jpg
```

## Dependencias

- FastAPI
- Uvicorn
- Jinja2
- python-multipart
- ReportLab
