"""Logica dell'orologio, condivisa dalle tre varianti: funzione locale, servizio FastAPI, server FastMCP.

Non dipende da `agente/`, così servizio e server possono girare in processi separati.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Tabelle in italiano: il locale di sistema non è affidabile (soprattutto nel container).
GIORNI = ("lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica")
MESI = ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre")


class FusoNonValido(ValueError):
    """Fuso orario non riconosciuto; il messaggio è lo stesso in tutte le varianti."""

    def __init__(self, fuso: str):
        super().__init__(f"fuso orario '{fuso}' non riconosciuto. Usa un nome IANA come 'Europe/Rome'.")


def _offset(locale: datetime) -> str:
    """Scostamento da UTC nella forma +HH:MM / -HH:MM."""
    minuti = int(locale.utcoffset().total_seconds() // 60)
    segno = "+" if minuti >= 0 else "-"
    ore, resto = divmod(abs(minuti), 60)
    return f"{segno}{ore:02d}:{resto:02d}"


def descrivi_ora(fuso: str, adesso: datetime | None = None) -> str:
    """Data e ora di `adesso` (UTC aware, default: ora attuale) nel fuso IANA indicato.

    Solleva `FusoNonValido` se il fuso non esiste: nessuna ora viene inventata.
    """
    try:
        zona = ZoneInfo(fuso)
    except (ZoneInfoNotFoundError, ValueError):
        raise FusoNonValido(fuso) from None

    locale = (adesso or datetime.now(timezone.utc)).astimezone(zona).replace(microsecond=0)
    return "\n".join([
        f"Fuso orario: {fuso} ({locale.tzname()}, UTC{_offset(locale)})",
        f"Data: {GIORNI[locale.weekday()]} {locale.day} {MESI[locale.month - 1]} {locale.year}",
        f"Ora: {locale:%H:%M:%S}",
        f"ISO 8601: {locale.isoformat()}",
    ])
