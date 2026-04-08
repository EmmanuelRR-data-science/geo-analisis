# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app

# Instalar dependencias del sistema necesarias para algunas librerías de Python
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    fonts-liberation \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias usando uv
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Etapa final
FROM python:3.11-slim-bookworm

WORKDIR /app

# Copiar el entorno virtual generado por uv
COPY --from=builder /app/.venv /app/.venv

# Asegurar que el PATH incluya el venv
ENV PATH="/app/.venv/bin:$PATH"

# Copiar el código fuente y archivos de configuración
COPY . /app/

# Exponer el puerto de FastAPI
EXPOSE 8000

# Comando para iniciar la aplicación
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
