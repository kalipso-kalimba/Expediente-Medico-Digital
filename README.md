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

## Dependencias

- FastAPI
- Uvicorn
- Jinja2
- python-multipart
- ReportLab
