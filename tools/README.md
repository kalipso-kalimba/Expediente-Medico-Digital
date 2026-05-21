# Herramientas de desarrollo

Scripts internos para agilizar pruebas, revisión, mantenimiento y depuración.

## Requisitos

```bash
pip install -r requirements-dev.txt
```

## Uso

### Verificar base de datos

```bash
python tools/check_db.py
python tools/check_db.py --fix    # corrige role/admin del usuario principal
```

### Verificar cuenta principal

```bash
python tools/check_admin.py
python tools/check_admin.py --fix  # corrige role, is_active, deleted_at
```

### Revisar permisos y aislamiento

```bash
python tools/check_permissions.py
```

### Prueba rápida del sistema

```bash
python tools/smoke_test.py
```

### Limpiar archivos temporales

```bash
python tools/clean_temp.py              # simulación (no borra nada)
python tools/clean_temp.py --execute    # borra previa confirmación
python tools/clean_temp.py --force      # borra sin confirmación
```

## Seguridad

- Ningún script imprime contraseñas.
- Ningún script expone datos médicos sensibles.
- Ningún script sube archivos a internet.
- Ningún script borra expedientes reales sin confirmación.
- Ningún script modifica producción.
