"""Server MCP del catalogo locale: ricerca e dettaglio sugli stessi corsi (dati inventati)."""

import json
import logging
import os
import sys
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from server_mcp.avvio import avvia

logger = logging.getLogger(__name__)

PERCORSO_CORSI = Path(__file__).resolve().parent / "risorse" / "corsi.json"
RISULTATI_MAX = 10
# Parole che il modello può copiare dalla domanda ma che non identificano un corso.
PAROLE_IGNORATE = {"corso", "corsi", "a", "di", "su", "in", "da", "per", "con", "il", "lo", "la", "i", "gli",
                   "le", "del", "della", "dei", "che", "ci", "sono", "quali"}


class ErroreCatalogo(Exception):
    """Ricerca o codice non validi, con un messaggio leggibile dal modello."""


def carica_corsi(percorso: Path = PERCORSO_CORSI) -> list[dict]:
    """Legge il catalogo (riletto a ogni chiamata del server)."""
    return json.loads(Path(percorso).read_text(encoding="utf-8"))


def _testo_ricercabile(corso: dict) -> str:
    return " ".join(str(corso[campo]) for campo in ("codice", "titolo", "sede", "descrizione")).lower()


def cerca(corsi: list[dict], testo: str, max_risultati: int) -> list[dict]:
    """Corsi che contengono tutte le parole significative del testo, nell'ordine del catalogo.

    Si ignorano le parole di PAROLE_IGNORATE («corsi», «a», «di», «su», …).
    """
    parole = [p for p in (testo or "").lower().split() if p not in PAROLE_IGNORATE]
    if not parole:
        raise ErroreCatalogo("testo di ricerca mancante")
    if not 1 <= max_risultati <= RISULTATI_MAX:
        raise ErroreCatalogo(f"max_risultati deve essere tra 1 e {RISULTATI_MAX}")
    trovati = [c for c in corsi if all(p in _testo_ricercabile(c) for p in parole)]
    return trovati[:max_risultati]


def dettaglio(corsi: list[dict], codice: str) -> dict:
    chiave = (codice or "").strip().upper()
    for corso in corsi:
        if corso["codice"].upper() == chiave:
            return corso
    raise ErroreCatalogo(f"nessun corso con codice «{chiave}»")


def descrivi_ricerca(corsi: list[dict], testo: str, max_risultati: int) -> str:
    trovati = cerca(corsi, testo, max_risultati)
    richiesta = testo.strip()
    if not trovati:
        return f"Nessun corso trovato per «{richiesta}»."
    righe = [f"{c['codice']} – {c['titolo']} ({c['sede']})" for c in trovati]
    return f"Trovati {len(trovati)} corsi per «{richiesta}»:\n" + "\n".join(righe)


def descrivi_dettaglio(corsi: list[dict], codice: str) -> str:
    corso = dettaglio(corsi, codice)
    return "\n".join([
        f"Codice: {corso['codice']}", f"Titolo: {corso['titolo']}", f"Sede: {corso['sede']}",
        f"Durata: {corso['durata_ore']} ore", f"Descrizione: {corso['descrizione']}",
    ])


mcp = FastMCP("Catalogo corsi")


def _esegui(calcolo, *argomenti) -> str:
    try:
        return calcolo(carica_corsi(), *argomenti)
    except ErroreCatalogo as errore:
        logger.info("catalogo: richiesta rifiutata: %s", errore)
        raise ToolError(str(errore)) from errore


@mcp.tool
def cerca_corsi(testo: str, max_risultati: int = 5) -> str:
    """Cerca nel catalogo dei corsi per parole (argomento, titolo, sede o codice) e restituisce l'elenco di codice, titolo e sede. Da usare per sapere quali corsi ci sono. testo: solo parole chiave, per esempio "Udine" o "Docker". max_risultati da 1 a 10."""
    return _esegui(descrivi_ricerca, testo, max_risultati)


@mcp.tool
def dettaglio_corso(codice: str) -> str:
    """Restituisce tutti i dettagli (titolo, sede, durata, descrizione) di un corso di cui conosci già il codice, per esempio "IA-101". Se non conosci il codice, usa prima cerca_corsi."""
    return _esegui(descrivi_dettaglio, codice)


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stderr, level=os.environ.get("LOG_LEVEL", "INFO").upper())
    avvia(mcp, "catalogo")
