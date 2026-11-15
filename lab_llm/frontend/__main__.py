"""Front-end in locale: `python -m frontend` serve la pagina di chat (cartella static/) e `/config.js`.

L'indirizzo del back-end viene da FRONTEND_BACKEND_URL, non è scritto nel codice della pagina.
Solo libreria standard: in Docker (step 9) gli stessi file li serve nginx.
"""

import json
import logging
import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from dotenv import load_dotenv

STATICI = Path(__file__).resolve().parent / "static"
logger = logging.getLogger("frontend")


class ErroreConfigurazione(Exception):
    """Variabile non valida: il messaggio dice quale."""


@dataclass(frozen=True)
class ConfigFrontend:
    backend_url: str = "http://127.0.0.1:8080"
    ascolto: str = "127.0.0.1"
    porta: int = 8090


def carica_config(ambiente: Mapping[str, str] | None = None) -> ConfigFrontend:
    if ambiente is None:
        load_dotenv(override=False)
        ambiente = os.environ

    def leggi(nome: str, default: str) -> str:
        return (ambiente.get(nome) or "").strip() or default

    testo = leggi("FRONTEND_PORTA", "8090")
    if not testo.isdigit():
        raise ErroreConfigurazione(f"FRONTEND_PORTA deve essere un numero, non '{testo}'.")
    return ConfigFrontend(backend_url=leggi("FRONTEND_BACKEND_URL", "http://127.0.0.1:8080").rstrip("/"),
                          ascolto=leggi("FRONTEND_ASCOLTO", "127.0.0.1"), porta=int(testo))


def config_js(backend_url: str) -> str:
    return f"window.CONFIGURAZIONE = {json.dumps({'backend': backend_url})};\n"


class Gestore(SimpleHTTPRequestHandler):
    """File di static/ più /config.js generato dalla configurazione."""

    def __init__(self, *args, config_js: str, **kwargs):
        self.config_js = config_js.encode("utf-8")
        super().__init__(*args, directory=str(STATICI), **kwargs)

    def do_GET(self):
        if self.path.split("?")[0] == "/config.js":
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(self.config_js)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(self.config_js)
            return
        super().do_GET()

    def log_message(self, formato, *argomenti):
        logger.info("frontend: %s", formato % argomenti)


def crea_server(config: ConfigFrontend) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((config.ascolto, config.porta), partial(Gestore, config_js=config_js(config.backend_url)))


def main() -> int:
    try:
        config = carica_config()
    except ErroreConfigurazione as errore:
        print(f"Errore di configurazione: {errore}", file=sys.stderr)
        return 1
    logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                        format="%(asctime)s %(levelname)-5s %(name)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    server = crea_server(config)
    logger.info("frontend: http://%s:%d, back-end su %s", config.ascolto, config.porta, config.backend_url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
