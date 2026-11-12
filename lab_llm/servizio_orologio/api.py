"""Variante 02 dell'orologio: la stessa logica esposta come servizio HTTP con FastAPI.

Il servizio non sa nulla di modelli o agenti: risponde a `GET /ora?fuso_orario=...`.
Nell'agente un wrapper scritto a mano (`agente.strumenti.crea_ora_corrente_http`) lo chiama.

Avvio: `python -m servizio_orologio.api` (host e porta da OROLOGIO_API_HOST e OROLOGIO_API_PORTA).
"""

import logging
import os
import sys

from fastapi import FastAPI, HTTPException

from servizio_orologio.logica import FusoNonValido, descrivi_ora

logger = logging.getLogger(__name__)


def crea_app(fuso_predefinito: str = "Europe/Rome") -> FastAPI:
    """App FastAPI con gli endpoint `/ora` e `/salute`."""
    app = FastAPI(title="Orologio ITS")

    @app.get("/ora")
    def ora(fuso_orario: str = fuso_predefinito) -> dict:
        # print(f"[passo] servizio FastAPI: GET /ora fuso_orario={fuso_orario}")
        try:
            risultato = descrivi_ora(fuso_orario)
        except FusoNonValido as errore:
            logger.info("api orologio: fuso=%s esito=errore", fuso_orario)
            raise HTTPException(status_code=400, detail=str(errore)) from None
        logger.info("api orologio: fuso=%s esito=ok", fuso_orario)
        return {"fuso_orario": fuso_orario, "risultato": risultato}

    @app.get("/salute")
    def salute() -> dict:
        return {"stato": "ok"}

    return app


if __name__ == "__main__":
    import uvicorn

    livello = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(stream=sys.stderr, level=livello,
                        format="%(asctime)s %(levelname)-5s %(name)s | %(message)s")
    uvicorn.run(
        crea_app(os.environ.get("FUSO_ORARIO", "Europe/Rome")),
        host=os.environ.get("OROLOGIO_API_HOST", "127.0.0.1"),
        port=int(os.environ.get("OROLOGIO_API_PORTA", "8001")),
        log_level=livello.lower(),
    )
