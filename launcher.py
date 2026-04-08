"""Punto de entrada del ejecutable — Mapa de Viabilidad de Negocios.

Funciona tanto en desarrollo (python launcher.py) como empaquetado con PyInstaller.
"""

from __future__ import annotations

import os
import signal
import socket
import sys
import threading
import time
import webbrowser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_dir() -> str:
    """Return the directory where the executable (or script) lives.

    When running inside a PyInstaller --onefile bundle, ``sys._MEIPASS``
    points to the temporary extraction folder for *bundled* resources.
    However, the **.env** file lives *next to the .exe*, so we need the
    directory of ``sys.executable`` in that case.
    """
    if getattr(sys, "frozen", False):
        # Running as a PyInstaller bundle — .env is next to the .exe
        return os.path.dirname(sys.executable)
    # Normal Python execution
    return os.path.dirname(os.path.abspath(__file__))


def _resource_dir() -> str:
    """Return the directory where bundled resources (static, templates, etc.) live.

    Inside a PyInstaller --onefile bundle this is ``sys._MEIPASS``.
    In development it is the project root (same as _base_dir).
    """
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _load_env(base: str) -> None:
    """Load .env from *base* directory using python-dotenv."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        # If python-dotenv is not available, skip silently
        return
    env_path = os.path.join(base, ".env")
    if os.path.isfile(env_path):
        load_dotenv(env_path, override=True)
        print(f"  ✔ Archivo .env cargado desde: {env_path}")
    else:
        print(f"  ⚠ No se encontró archivo .env en: {env_path}")


def _check_api_key() -> bool:
    """Verify that GROQ_API_KEY is set in the environment."""
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        print(
            "\n❌ Error: La variable GROQ_API_KEY no está configurada.\n"
            "   Crea un archivo .env en el mismo directorio que el ejecutable\n"
            "   con el contenido:\n\n"
            "       GROQ_API_KEY=tu_clave_aquí\n"
        )
        return False
    print("  ✔ GROQ_API_KEY detectada")
    return True


def _find_free_port(start: int = 8080, end: int = 8099) -> int | None:
    """Find a free TCP port in the range [start, end].

    Returns the port number or ``None`` if no port is available.
    """
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return None


def _wait_for_server(port: int, timeout: float = 60.0) -> bool:
    """Poll the health endpoint until the server is ready."""
    import urllib.request
    import urllib.error

    url = f"http://127.0.0.1:{port}/api/health"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(0.5)
    return False


# ---------------------------------------------------------------------------
# Server runner
# ---------------------------------------------------------------------------

_server_thread: threading.Thread | None = None
_uvicorn_server: object | None = None  # uvicorn.Server instance


def _run_server(port: int) -> None:
    """Start uvicorn serving the FastAPI app in the current thread."""
    global _uvicorn_server

    import uvicorn

    config = uvicorn.Config(
        "app.main:app",
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )
    _uvicorn_server = uvicorn.Server(config)
    _uvicorn_server.run()


def _start_server(port: int) -> threading.Thread:
    """Launch the uvicorn server in a daemon thread."""
    t = threading.Thread(target=_run_server, args=(port,), daemon=True)
    t.start()
    return t


def _shutdown_server() -> None:
    """Signal the uvicorn server to shut down gracefully."""
    global _uvicorn_server
    if _uvicorn_server is not None:
        _uvicorn_server.should_exit = True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    # Configure logging so we can see what's happening
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="  [%(name)s] %(message)s",
    )

    print("=" * 56)
    print("  Mapa de Viabilidad de Negocios — Iniciando…")
    print("=" * 56)
    print()

    # 1. Determine base directory & load .env
    base = _base_dir()
    print(f"  Directorio base: {base}")
    _load_env(base)

    # 2. Verify API key
    if not _check_api_key():
        input("\nPresiona Enter para salir…")
        sys.exit(1)

    # 2b. Set AGEB file path to the CSV (bundled inside PyInstaller or in project root)
    resource = _resource_dir()
    ageb_csv = os.path.join(resource, "ageb_data.csv")
    if os.path.isfile(ageb_csv):
        os.environ["AGEB_FILE_PATH"] = ageb_csv
        print(f"  ✔ Datos AGEB: {ageb_csv}")
    else:
        # Fallback: try the Excel in base dir
        ageb_xlsx = os.path.join(base, "RESAGEBURB_09XLSX20.xlsx")
        if os.path.isfile(ageb_xlsx):
            os.environ["AGEB_FILE_PATH"] = ageb_xlsx
            print(f"  ⚠ Usando archivo Excel AGEB (más lento): {ageb_xlsx}")
        else:
            print("  ⚠ No se encontró archivo de datos AGEB — el análisis demográfico no estará disponible")

    # 3. Find a free port
    print("\n  Buscando puerto disponible…")
    port = _find_free_port()
    if port is None:
        print(
            "\n❌ Error: No se encontró un puerto disponible (8080-8099).\n"
            "   Cierra otras aplicaciones que puedan estar usando esos puertos\n"
            "   e intenta de nuevo."
        )
        input("\nPresiona Enter para salir…")
        sys.exit(1)
    print(f"  ✔ Puerto disponible: {port}")

    # 4. Start the server
    print("\n  Iniciando servidor…")
    global _server_thread
    _server_thread = _start_server(port)

    # 5. Wait for the server to be ready
    print("  Esperando a que el servidor esté listo…")
    if not _wait_for_server(port):
        print(
            "\n❌ Error: El servidor no respondió a tiempo.\n"
            "   Verifica que todas las dependencias estén instaladas\n"
            "   y que el archivo AGEB esté presente."
        )
        _shutdown_server()
        input("\nPresiona Enter para salir…")
        sys.exit(1)

    # 6. Open the default browser
    url = f"http://127.0.0.1:{port}"
    print(f"\n  ✔ Servidor listo en {url}")
    print("  Abriendo navegador…\n")
    webbrowser.open(url)

    print("  La aplicación está corriendo. Cierra esta ventana o presiona")
    print("  Ctrl+C para detener el servidor.\n")

    # 7. Handle shutdown signals
    def _signal_handler(sig: int, frame: object) -> None:
        print("\n\n  Deteniendo servidor…")
        _shutdown_server()

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # 8. Keep the main thread alive until the server exits
    try:
        while _server_thread.is_alive():
            _server_thread.join(timeout=1.0)
    except KeyboardInterrupt:
        print("\n\n  Deteniendo servidor…")
        _shutdown_server()
        _server_thread.join(timeout=5.0)

    print("  ✔ Servidor detenido. ¡Hasta pronto!")


if __name__ == "__main__":
    main()
