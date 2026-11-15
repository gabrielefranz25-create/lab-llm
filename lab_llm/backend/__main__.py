"""Avvio del back-end: `python -m backend` (DATABASE_URL obbligatoria, AGENTE_URL per l'agente)."""

import logging
import sys

import uvicorn

from backend.agente_remoto import ClienteAgente
from backend.api import crea_app
from backend.archivio import ArchivioPostgres
from backend.config import ErroreConfigurazione, carica_config

logger = logging.getLogger("backend")


def main() -> int:
    try:
        config = carica_config()
    except ErroreConfigurazione as errore:
        print(f"Errore di configurazione: {errore}", file=sys.stderr)
        return 1
    logging.basicConfig(level=config.log_level, stream=sys.stderr, force=True,
                        format="%(asctime)s %(levelname)-5s %(name)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    for rumoroso in ("httpx", "httpcore"):
        logging.getLogger(rumoroso).setLevel(logging.WARNING)
    try:
        archivio = ArchivioPostgres(config.database_url)
    except Exception as errore:  # database spento o credenziali sbagliate: messaggio chiaro e uscita
        print(f"Errore: PostgreSQL non raggiungibile ({errore}).", file=sys.stderr)
        return 1
    logger.info("backend: http://%s:%d (documentazione su /docs), agente su %s", config.ascolto, config.porta,
                config.agente_url)
    app = crea_app(archivio, ClienteAgente(config.agente_url, config.agente_timeout))
    uvicorn.run(app, host=config.ascolto, port=config.porta, log_level=config.log_level.lower())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
