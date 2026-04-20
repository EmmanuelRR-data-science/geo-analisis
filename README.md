# GeoAnalisis-SDD
Aplicación FastAPI para análisis de viabilidad de negocios con datos geoespaciales, clasificación de negocios y visualización en mapa.

## Requisitos
- Python 3.11+
- `uv` instalado (https://docs.astral.sh/uv/)
- Docker (opcional para despliegue local con contenedores)

## Configuración local con UV
1. Sincronizar entorno de desarrollo:
   - `uv sync --dev`
2. Crear archivo de entorno (si no existe):
   - Copiar `.env.example` a `.env`
   - Configurar llaves/API y credenciales de base de datos

## Comandos de desarrollo
- Ejecutar API en local:
  - `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`
- Ejecutar pruebas:
  - `uv run python -m pytest tests`
- Ejecutar lint:
  - `uv run ruff check app tests`
- Aplicar autofixes de lint:
  - `uv run ruff check --fix app tests`

## Flujo recomendado de calidad
Antes de abrir PR o mergear cambios:
1. `uv run ruff check app tests`
2. `uv run python -m pytest tests`

## Dependencias
- Fuente de verdad de dependencias: `pyproject.toml`
- Lock reproducible: `uv.lock`
- `requirements.txt` se mantiene para compatibilidad de runtime/container legacy.

## CI
El repositorio incluye workflow de GitHub Actions (`.github/workflows/ci.yml`) que valida:
- Ruff
- Pytest

## Control de versiones e higiene del repo
El `.gitignore` excluye artefactos locales, caches, perfiles de navegador y salidas temporales para mantener historial limpio.
