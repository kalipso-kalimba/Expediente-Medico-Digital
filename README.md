# Expediente Médico Digital

Sistema web para formularios médicos. Generación de enlaces únicos para pacientes, carga de fotografías de cédula/DIMEX, generación de PDF, panel privado para el médico.

El sistema funciona en **dos entornos** sincronizados desde un mismo repositorio:

| Entorno | URL | Propósito |
|---|---|---|
| **Local** | `http://127.0.0.1:8000` | Pruebas, respaldo, trabajo interno |
| **Render (en línea)** | `https://expediente-medico-digital.onrender.com` | Acceso desde internet |

## Requisitos

- Python 3.12+
- pip

## Ejecutar en entorno local

```bash
# 1. Clonar el repositorio
git clone https://github.com/kalipso-kalimba/Expediente-Medico-Digital.git
cd Expediente-Medico-Digital

# 2. Crear entorno virtual
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno (opcional)
# Copiar y editar .env.example como .env
cp .env.example .env

# 5. Iniciar servidor
uvicorn app.main:app --reload
```

Abrir `http://127.0.0.1:8000`.

## Variables de entorno

| Variable | Local | Render | Descripción |
|---|---|---|---|
| `APP_ENV` | `local` | `production` | Entorno de ejecución |
| `APP_SECRET_KEY` | cualquier valor | generar aleatoria | Clave secreta para sesiones |
| `DOCTOR_USERNAME` | `doctor` | `doctor` | Usuario del médico |
| `DOCTOR_PASSWORD` | `Cambiar123!` | elegir una segura | Contraseña del médico |
| `APP_COOKIE_SECURE` | `false` | `true` | Cookies seguras (requiere HTTPS) |
| `BASE_URL` | `http://127.0.0.1:8000` | `https://expediente-medico-digital.onrender.com` | URL para enlaces de pacientes |
| `TSE_LOOKUP_ENABLED` | `false` | `false` | Consulta automática al TSE |

## Ejemplo .env para local

```env
APP_ENV=local
APP_SECRET_KEY=mi_clave_local
DOCTOR_USERNAME=doctor
DOCTOR_PASSWORD=Cambiar123!
APP_COOKIE_SECURE=false
BASE_URL=http://127.0.0.1:8000
TSE_LOOKUP_ENABLED=false
```

## Despliegue en Render

### Build Command

```bash
pip install -r requirements.txt
```

### Start Command

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips '*'
```

### Opción 1 — Blueprint (automático)

1. Ir a https://dashboard.render.com
2. New + → Blueprint → Conectar con `kalipso-kalimba/Expediente-Medico-Digital`
3. Render leerá `render.yaml` y configurará todo
4. Hacer clic en **Apply**
5. En Environment, verificar las variables

### Opción 2 — Web Service (manual)

1. New + → Web Service → Conectar repositorio
2. Build: `pip install -r requirements.txt`
3. Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips '*'`
4. Agregar en Environment:

| Variable | Valor |
|---|---|
| `APP_SECRET_KEY` | Click "Generate" |
| `DOCTOR_USERNAME` | `doctor` |
| `DOCTOR_PASSWORD` | Una contraseña segura |
| `APP_COOKIE_SECURE` | `true` |
| `BASE_URL` | `https://expediente-medico-digital.onrender.com` |
| `TSE_LOOKUP_ENABLED` | `false` |

### Auto-deploy

Si el auto-deploy está habilitado, cada push a `master` en GitHub despliega automáticamente en Render. Para forzar un despliegue manual: Dashboard → servicio → Manual Deploy → Deploy latest commit.

## Mantener ambas versiones sincronizadas

Cada cambio debe seguir este flujo:

1. **Probar localmente**: `uvicorn app.main:app --reload`
2. **Subir a GitHub**: `git push origin master`
3. **Render se despliega solo** (si auto-deploy está activo) o **Manual Deploy**
4. **Verificar en línea**: `https://expediente-medico-digital.onrender.com`

## Limitaciones de Render Free

- Almacenamiento efímero: los datos se pierden al reiniciar o redeploy.
- El servicio se duerme tras 15 minutos sin actividad.
- Límite de 750 horas/mes.
- Para producción real: migrar a PostgreSQL + almacenamiento externo.

## Estructura de carpetas

```text
app/                  → Código backend (FastAPI)
templates/            → Plantillas HTML
static/               → CSS y JavaScript
database/             → Base de datos SQLite y ubicaciones CR
storage/              → Almacenamiento temporal (runtime)
Expediente de pacientes/ → PDFs e imágenes de pacientes
```

## Herramientas de desarrollo

```bash
# Instalar dependencias de desarrollo
pip install -r requirements-dev.txt

# Linter y formateador
ruff check .
ruff format .

# Pruebas
pytest -v
pytest tests/test_minimal.py -v
python tests/test_comprehensive.py

# Seguridad
bandit -r app
pip-audit -r requirements.txt

# Pre-commit hooks (una vez)
pre-commit install
pre-commit run --all-files

# Herramientas internas de revisión
python tools/check_db.py
python tools/check_db.py --fix
python tools/check_admin.py
python tools/check_admin.py --fix
python tools/check_permissions.py
python tools/smoke_test.py

# Limpieza de archivos temporales
python tools/clean_temp.py --dry-run
python tools/clean_temp.py --execute
```

## Dependencias

### Producción (requirements.txt)

- FastAPI
- Uvicorn
- Jinja2
- python-multipart
- ReportLab
- passlib[bcrypt]
- bcrypt

### Desarrollo (requirements-dev.txt)

- ruff (linter/formateador)
- pytest + httpx (pruebas)
- pre-commit (hooks)
- bandit (seguridad)
- pip-audit (vulnerabilidades)

## Almacenamiento privado en NAS

El sistema puede usar un **NAS Synology** como almacenamiento privado de archivos generados.

### ¿Qué se almacena en el NAS?

- PDFs generados
- Fotos de cédula/DIMEX (frontales y traseras)
- Carpetas de expedientes por atención
- Formularios presenciales incompletos
- Respaldos y archivos temporales

### ¿Qué NO se almacena en el NAS?

- Código fuente (sigue en GitHub)
- Git ni repositorios
- requirements.txt ni configuraciones de Render
- Credenciales ni .env
- Claves secretas

### Configuración

| Variable | Descripción | Ejemplo |
|---|---|---|
| `STORAGE_BACKEND` | Backend de almacenamiento usar `local_path` | `local_path` |
| `STORAGE_ROOT` | Ruta a la carpeta "Expediente Medico Digital" del usuario OpenCode en el NAS (ajustar a su entorno; no usar esta ruta literalmente) | `/mnt/nas/Expediente Medico Digital` |
| `PATIENT_FILES_ROOT` | Nombre de la carpeta raíz de expedientes | `Expediente de pacientes` |

### Funcionamiento

1. El médico usa la aplicación normalmente (sesión, permisos, formularios)
2. Los archivos se guardan automáticamente en la carpeta del NAS configurada en `STORAGE_ROOT`
3. La base de datos guarda rutas **relativas**, no absolutas
4. El médico ve/descarga archivos desde las rutas de la aplicación (`/doctor/encounters/{id}/pdf`)
5. **No hay enlaces directos al NAS** visibles para el usuario
6. El administrador ve todos los archivos; cada médico solo ve los suyos
7. GitHub solo contiene el código — los archivos generados no se suben al repositorio

### Estructura de carpetas en el NAS

```
Expediente Medico Digital/
├── Expediente de pacientes/
│   └── Médico - {usuario}/
│       └── {Paciente} - {identificación}/
│           └── {YYYY-MM-DD} - {HH-MM} - Atención/
│               ├── formulario.pdf
│               ├── cedula-frontal.jpg
│               └── cedula-trasera.jpg
├── formularios_incompletos/
├── backups/
├── logs/
└── tmp/
```
