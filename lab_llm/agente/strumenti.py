"""Strumento orologio: data e ora attuali in un fuso orario IANA sempre esplicito."""

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from langchain_core.tools import BaseTool, tool

logger = logging.getLogger(__name__)

# Tabelle in italiano: il locale di sistema non è affidabile (soprattutto nel container).
GIORNI = ("lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica")
MESI = ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre")


def _offset(locale: datetime) -> str:
    """Scostamento da UTC nella forma +HH:MM / -HH:MM."""
    minuti = int(locale.utcoffset().total_seconds() // 60)
    segno = "+" if minuti >= 0 else "-"
    ore, resto = divmod(abs(minuti), 60)
    return f"{segno}{ore:02d}:{resto:02d}"


def calcola_ora(fuso: str, adesso: datetime | None = None) -> str:
    """Data e ora di `adesso` (UTC aware, default: ora attuale) nel fuso IANA indicato.

    Con un fuso non valido restituisce un messaggio d'errore per il modello invece di sollevare.
    """
    try:
        zona = ZoneInfo(fuso)
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning("strumento ora_corrente: fuso %r non riconosciuto", fuso)
        return f"Errore: fuso orario '{fuso}' non riconosciuto. Usa un nome IANA come 'Europe/Rome'."

    locale = (adesso or datetime.now(timezone.utc)).astimezone(zona).replace(microsecond=0)
    return "\n".join([
        f"Fuso orario: {fuso} ({locale.tzname()}, UTC{_offset(locale)})",
        f"Data: {GIORNI[locale.weekday()]} {locale.day} {MESI[locale.month - 1]} {locale.year}",
        f"Ora: {locale:%H:%M:%S}",
        f"ISO 8601: {locale.isoformat()}",
    ])


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
