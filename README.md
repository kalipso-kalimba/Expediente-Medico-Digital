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
| `BASE_URL` | URL pública del sitio | `https://expediente-medico-digital.onrender.com` |
| `TSE_LOOKUP_ENABLED` | Consulta automática al TSE | `false` |

## Despliegue en Render

### Build Command

```bash
pip install -r requirements.txt
```

### Start Command

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips '*'
```

### Cómo desplegar en Render

Opción 1 — Blueprint (automático):
1. Ir a https://dashboard.render.com
2. New + → Blueprint → Conectar con `kalipso-kalimba/Expediente-Medico-Digital`
3. Render leerá `render.yaml` y configurará todo
4. Hacer clic en **Apply**
5. En Environment, verificar que `DOCTOR_USERNAME` y `DOCTOR_PASSWORD` tengan valores

Opción 2 — Web Service (manual):
1. New + → Web Service → Conectar repositorio
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips '*'`
4. Agregar estas variables en Environment:

| Variable | Valor |
|---|---|
| `APP_SECRET_KEY` | Click "Generate" |
| `DOCTOR_USERNAME` | `doctor` |
| `DOCTOR_PASSWORD` | Una contraseña segura |
| `APP_COOKIE_SECURE` | `true` |
| `BASE_URL` | `https://expediente-medico-digital.onrender.com` |
| `TSE_LOOKUP_ENABLED` | `false` |

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
