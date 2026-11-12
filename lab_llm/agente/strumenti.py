"""Strumento orologio: data e ora attuali in un fuso orario IANA sempre esplicito."""

import logging
from collections.abc import Callable
from datetime import datetime

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


def crea_ora_corrente(fuso_predefinito: str = "Europe/Rome",
                      orologio: Callable[[], datetime] | None = None) -> BaseTool:
    """Costruisce lo strumento `ora_corrente` con il fuso predefinito nella descrizione e nel default.

    `orologio` permette ai test di fissare l'istante; se manca si usa l'ora attuale.
    """
    descrizione = (
        "Restituisce data e ora attuali nel fuso orario IANA indicato "
        '(es. "Europe/Rome", "America/New_York", "Asia/Tokyo"). Se l\'utente non indica '
        f"un luogo, usa il fuso predefinito italiano {fuso_predefinito}."
    )

    @tool("ora_corrente", description=descrizione)
    def ora_corrente(fuso_orario: str = fuso_predefinito) -> str:
        adesso = orologio() if orologio else None
        return calcola_ora(fuso_orario, adesso)

    return ora_corrente
