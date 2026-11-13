"""Variante 03 dell'orologio: la stessa logica esposta come tool MCP con FastMCP.

Nome, descrizione e schema arrivano all'agente dal catalogo (`list_tools()`), non sono scritti
nell'agente. Il fuso predefinito arriva da FUSO_ORARIO (lo passa l'agente).
"""

import logging
import os
import sys

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from server_mcp.avvio import avvia
from servizio_orologio.logica import FusoNonValido, descrivi_ora

logger = logging.getLogger(__name__)


def crea_server(fuso_predefinito: str = "Europe/Rome") -> FastMCP:
    """Server «Orologio» con il solo tool `ora_corrente`."""
    server = FastMCP("Orologio")

    @server.tool(description=(
        "Restituisce data e ora attuali nel fuso orario IANA indicato "
        '(es. "Europe/Rome", "America/New_York", "Asia/Tokyo"). Se l\'utente non indica '
        f"un luogo, usa il fuso predefinito italiano {fuso_predefinito}."
    ))
    def ora_corrente(fuso_orario: str = fuso_predefinito) -> str:
        try:
            risultato = descrivi_ora(fuso_orario)
        except FusoNonValido as errore:
            logger.info("orologio: fuso=%s esito=errore", fuso_orario)
            raise ToolError(str(errore)) from errore
        logger.info("orologio: fuso=%s esito=ok", fuso_orario)
        return risultato

    return server


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stderr, level=os.environ.get("LOG_LEVEL", "INFO").upper())
    avvia(crea_server(os.environ.get("FUSO_ORARIO", "Europe/Rome")), "orologio")
