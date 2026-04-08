# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — Mapa de Viabilidad de Negocios.

Build with:
    pyinstaller app.spec

Produces a single executable: dist/ViabilidadNegocios.exe
The user must place a .env file (with GROQ_API_KEY) next to the .exe.
"""

import sys
from pathlib import Path

block_cipher = None

# Paths relative to this spec file
ROOT = Path(SPECPATH)

a = Analysis(
    [str(ROOT / 'launcher.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / 'static'), 'static'),
        (str(ROOT / 'templates'), 'templates'),
        (str(ROOT / 'ageb_data.csv'), '.'),
    ],
    hiddenimports=[
        # --- uvicorn internals ---
        'uvicorn',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        # --- FastAPI / Starlette ---
        'fastapi',
        'starlette',
        'starlette.responses',
        'starlette.routing',
        'starlette.middleware',
        'starlette.middleware.cors',
        # --- Pydantic ---
        'pydantic',
        # --- httpx (async HTTP client) ---
        'httpx',
        'httpcore',
        # --- Data processing ---
        'pandas',
        'openpyxl',
        # --- PDF generation ---
        'fpdf',
        # --- dotenv ---
        'dotenv',
        # --- fuzzy matching ---
        'fuzzywuzzy',
        'Levenshtein',
        # --- app modules ---
        'app',
        'app.main',
        'app.models',
        'app.models.schemas',
        'app.services',
        'app.services.ageb_reader',
        'app.services.analysis_engine',
        'app.services.data_service',
        'app.services.export_service',
        'app.services.llm_service',
        'app.services.scian_catalog',
        'app.services.zone_service',
        'app.clients',
        'app.clients.google_places_client',
        'app.clients.denue_client',
        'app.clients.overture_client',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ViabilidadNegocios',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,          # Keep console visible for loading messages
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
