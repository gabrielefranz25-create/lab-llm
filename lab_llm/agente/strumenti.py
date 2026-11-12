"""Strumento orologio: data e ora attuali in un fuso orario IANA sempre esplicito.

Due delle tre varianti della lezione 5 vivono qui: la funzione locale (`crea_ora_corrente`) e il
wrapper HTTP verso il servizio FastAPI (`crea_ora_corrente_http`). La terza è il server MCP
`server_mcp/orologio.py`, il cui contratto arriva dal catalogo.
"""

import logging
from collections.abc import Callable
from datetime import datetime

import httpx
from langchain_core.tools import BaseTool, tool

from servizio_orologio.logica import FusoNonValido, descrivi_ora

logger = logging.getLogger(__name__)


def calcola_ora(fuso: str, adesso: datetime | None = None) -> str:
    """Data e ora di `adesso` (UTC aware, default: ora attuale) nel fuso IANA indicato.

    Con un fuso non valido restituisce un messaggio d'errore per il modello invece di sollevare.
    """
    try:
        return descrivi_ora(fuso, adesso)
    except FusoNonValido as errore:
        logger.warning("strumento ora_corrente: fuso %r non riconosciuto", fuso)
        return f"Errore: {errore}"


def _descrizione(fuso_predefinito: str) -> str:
    """Descrizione dello strumento, uguale nella variante locale e nel wrapper HTTP."""
    return (
        "Restituisce data e ora attuali nel fuso orario IANA indicato "
        '(es. "Europe/Rome", "America/New_York", "Asia/Tokyo"). Se l\'utente non indica '
        f"un luogo, usa il fuso predefinito italiano {fuso_predefinito}."
    )


def crea_ora_corrente(fuso_predefinito: str = "Europe/Rome",
                      orologio: Callable[[], datetime] | None = None) -> BaseTool:
    """Variante 01 (locale): costruisce lo strumento `ora_corrente` con il fuso predefinito nella
    descrizione e nel default.

    `orologio` permette ai test di fissare l'istante; se manca si usa l'ora attuale.
    """
    @tool("ora_corrente", description=_descrizione(fuso_predefinito))
    def ora_corrente(fuso_orario: str = fuso_predefinito) -> str:
        adesso = orologio() if orologio else None
        return calcola_ora(fuso_orario, adesso)

    return ora_corrente


def crea_ora_corrente_http(url_base: str, timeout: float, fuso_predefinito: str = "Europe/Rome",
                           client: httpx.Client | None = None) -> BaseTool:
    """Variante 02 (FastAPI): wrapper scritto a mano che chiama `GET {url_base}/ora`.

    Nome, descrizione e schema sono gli stessi della variante locale e vanno mantenuti qui:
    non c'è discovery. Il fuso non valido (HTTP 400) diventa un errore dello strumento; servizio
    spento, timeout, stati inattesi e JSON non valido diventano errori di collegamento.
    `client` serve ai test (trasporto simulato).
    """
    http = client or httpx.Client(timeout=timeout)
    url = f"{url_base.rstrip('/')}/ora"

    def collegamento(dettaglio: str) -> str:
        logger.warning("orologio http: errore di collegamento: %s", dettaglio)
        return f"Errore di collegamento HTTP con il servizio orologio: {dettaglio}"

    @tool("ora_corrente", description=_descrizione(fuso_predefinito))
    def ora_corrente(fuso_orario: str = fuso_predefinito) -> str:
        # print(f"[passo] wrapper HTTP: GET {url}?fuso_orario={fuso_orario}")
        try:
            risposta = http.get(url, params={"fuso_orario": fuso_orario}, timeout=timeout)
        except httpx.TimeoutException:
            return collegamento(f"nessuna risposta entro {timeout} secondi")
        except httpx.HTTPError as errore:
            return collegamento(str(errore) or type(errore).__name__)
        logger.info("orologio http: GET %s fuso_orario=%s -> %d", url, fuso_orario, risposta.status_code)
        try:
            corpo = risposta.json()
        except ValueError:
            corpo = None
        if risposta.status_code == 400 and isinstance(corpo, dict) and "detail" in corpo:
            return f"Errore dallo strumento ora_corrente: {corpo['detail']}"
        if risposta.status_code != 200:
            return collegamento(f"stato HTTP {risposta.status_code}")
        if not isinstance(corpo, dict) or not isinstance(corpo.get("risultato"), str):
            return collegamento("risposta non valida dal servizio")
        return corpo["risultato"]

    ora_corrente.metadata = {"origine": "http:orologio"}
    return ora_corrente
