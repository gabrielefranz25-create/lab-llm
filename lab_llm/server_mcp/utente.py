"""Server MCP «Utente»: espone le preferenze dell'utente come resource `utente://preferenze`.

Una resource non è un tool: non la sceglie il modello. La legge l'host (l'agente) a inizio sessione
per preparare il prompt di sistema. Il file viene riletto a ogni richiesta: cambiandolo, la sessione
successiva si comporta diversamente senza toccare il codice. Percorso da PREFERENZE_FILE.
"""

import logging
import os
import sys
from pathlib import Path

from fastmcp import FastMCP

from server_mcp.avvio import avvia

logger = logging.getLogger(__name__)

URI_PREFERENZE = "utente://preferenze"
PREFERENZE_PREDEFINITE = Path(__file__).resolve().parent / "risorse" / "preferenze.json"


def crea_server(percorso: Path = PREFERENZE_PREDEFINITE) -> FastMCP:
    """Server con la sola resource delle preferenze (nessun tool)."""
    server = FastMCP("Utente")

    @server.resource(URI_PREFERENZE, name="preferenze", mime_type="application/json",
                     description="Preferenze dell'utente per le risposte: lingua, fuso orario "
                                 "predefinito e stile (sintetico o dettagliato).")
    def preferenze() -> str:
        testo = Path(percorso).read_text(encoding="utf-8")
        logger.info("resource %s letta da %s", URI_PREFERENZE, percorso)
        return testo

    return server


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stderr, level=os.environ.get("LOG_LEVEL", "INFO").upper())
    avvia(crea_server(Path(os.environ.get("PREFERENZE_FILE") or PREFERENZE_PREDEFINITE)), "utente")
