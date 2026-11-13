"""Server MCP di giorni e scadenze: date ISO, fine settimana e festività da un file locale."""

import json
import logging
import os
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from server_mcp.avvio import avvia

logger = logging.getLogger(__name__)

PERCORSO_FESTIVITA = Path(__file__).resolve().parent / "risorse" / "festivita.json"
GIORNI_MAX = 3650
GIORNI_SETTIMANA = ("lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica")
FORMATO_ISO = re.compile(r"\d{4}-\d{2}-\d{2}")
AVVERTENZA = "Calcolo indicativo, non normativo."


class ErroreScadenze(Exception):
    """Data o intervallo non validi, con un messaggio leggibile dal modello."""


@dataclass(frozen=True)
class Festivita:
    """Festività fisse (`MM-GG` → nome) e mobili (data → nome), più gli anni coperti dalle mobili."""

    fisse: dict[str, str]
    mobili: dict[date, str]

    @property
    def anni_mobili(self) -> set[int]:
        return {giorno.year for giorno in self.mobili}

    def nome(self, giorno: date) -> str | None:
        return self.mobili.get(giorno) or self.fisse.get(f"{giorno:%m-%d}")


def carica_festivita(percorso: Path = PERCORSO_FESTIVITA) -> Festivita:
    """Legge il file delle festività (riletto a ogni chiamata del server)."""
    dati = json.loads(Path(percorso).read_text(encoding="utf-8"))
    return Festivita(dict(dati["fisse"]), {date.fromisoformat(d): n for d, n in dati["mobili"].items()})


def oggi_locale() -> date:
    """Data di oggi nel fuso FUSO_ORARIO (lo stesso dell'orologio dell'agente), non in quello del processo:
    in Docker il processo è in UTC e tra mezzanotte e le 2 «oggi» sarebbe ancora ieri."""
    return datetime.now(ZoneInfo(os.environ.get("FUSO_ORARIO", "Europe/Rome"))).date()


def leggi_data(testo: str, oggi: date | None = None) -> date:
    """Data ISO `AAAA-MM-GG` oppure `oggi` (nel fuso configurato, o la data passata dai test)."""
    pulito = (testo or "").strip()
    if pulito.lower() == "oggi":
        return oggi or oggi_locale()
    try:
        if not FORMATO_ISO.fullmatch(pulito):
            raise ValueError
        return date.fromisoformat(pulito)
    except ValueError:
        raise ErroreScadenze(f"data non valida: «{pulito}» (usa il formato AAAA-MM-GG oppure «oggi»)") from None


def _lavorativo(giorno: date, festivita: Festivita) -> bool:
    return giorno.weekday() < 5 and festivita.nome(giorno) is None


def _scoperti(giorni: list[date], festivita: Festivita) -> list[int]:
    """Anni toccati dal calcolo per cui il file non ha le festività mobili."""
    return sorted({g.year for g in giorni} - festivita.anni_mobili)


def conta_giorni(inizio: date, fine: date, festivita: Festivita) -> tuple[int, int, list[int]]:
    """Giorni di calendario e lavorativi in (inizio, fine], più gli anni senza festività mobili note."""
    if fine < inizio:
        raise ErroreScadenze(f"la data di fine {fine} precede quella di inizio {inizio}")
    calendario = (fine - inizio).days
    if calendario > GIORNI_MAX:
        raise ErroreScadenze(f"intervallo troppo ampio (massimo {GIORNI_MAX} giorni)")
    giorni = [inizio + timedelta(days=n) for n in range(1, calendario + 1)]
    lavorativi = sum(_lavorativo(g, festivita) for g in giorni)
    return calendario, lavorativi, _scoperti(giorni, festivita)


def sposta(data: date, giorni: int, solo_lavorativi: bool, festivita: Festivita) -> tuple[date, list[int]]:
    """Data spostata di `giorni` (di calendario o lavorativi), più gli anni senza festività mobili note."""
    if not -GIORNI_MAX <= giorni <= GIORNI_MAX:
        raise ErroreScadenze(f"giorni deve essere tra -{GIORNI_MAX} e {GIORNI_MAX}")
    if not solo_lavorativi:
        return data + timedelta(days=giorni), []
    passo = timedelta(days=1 if giorni >= 0 else -1)
    attuale, visti, mancanti = data, [], abs(giorni)
    while mancanti:
        attuale += passo
        visti.append(attuale)
        if _lavorativo(attuale, festivita):
            mancanti -= 1
    return attuale, _scoperti(visti, festivita)


def _chiusura(scoperti: list[int]) -> str:
    nota = f" Festività mobili non note per: {', '.join(map(str, scoperti))}." if scoperti else ""
    return f"{nota} {AVVERTENZA}"


def descrivi_intervallo(data_inizio: str, data_fine: str, festivita: Festivita) -> str:
    inizio, fine = leggi_data(data_inizio), leggi_data(data_fine)
    calendario, lavorativi, scoperti = conta_giorni(inizio, fine, festivita)
    return (f"Dal {inizio} al {fine}: {calendario} giorni di calendario, {lavorativi} giorni lavorativi "
            f"(lunedì-venerdì escluse le festività).{_chiusura(scoperti)}")


def descrivi_spostamento(data: str, giorni: int, solo_lavorativi: bool, festivita: Festivita) -> str:
    partenza = leggi_data(data)
    risultato, scoperti = sposta(partenza, giorni, solo_lavorativi, festivita)
    segno = "+" if giorni >= 0 else "-"
    tipo = " lavorativi" if solo_lavorativi else ""
    testo = f"{partenza} {segno} {abs(giorni)} giorni{tipo} = {risultato} ({GIORNI_SETTIMANA[risultato.weekday()]})."
    festa = festivita.nome(risultato)
    if festa:
        testo += f" Attenzione: è festivo ({festa})."
    return testo + _chiusura(scoperti)


mcp = FastMCP("Scadenze")


def _esegui(calcolo, *argomenti) -> str:
    try:
        return calcolo(*argomenti, carica_festivita())
    except ErroreScadenze as errore:
        logger.info("scadenze: richiesta rifiutata: %s", errore)
        raise ToolError(str(errore)) from errore


@mcp.tool
def giorni_tra(data_inizio: str, data_fine: str) -> str:
    """Conta i giorni di calendario e i giorni lavorativi (lunedì-venerdì, escluse le festività italiane) tra due date AAAA-MM-GG; si può scrivere "oggi". Da usare per domande come "quanti giorni mancano a...", "quanti giorni lavorativi ci sono tra...". """
    return _esegui(descrivi_intervallo, data_inizio, data_fine)


@mcp.tool
def aggiungi_giorni(data: str, giorni: int, solo_lavorativi: bool = False) -> str:
    """Calcola la data che si ottiene aggiungendo (o togliendo, con un numero negativo) giorni a una data AAAA-MM-GG o a "oggi". Con solo_lavorativi=true conta solo i giorni lavorativi (salta sabati, domeniche e festività). Da usare per scadenze come "tra 30 giorni" o "entro 10 giorni lavorativi"."""
    return _esegui(descrivi_spostamento, data, giorni, solo_lavorativi)


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stderr, level=os.environ.get("LOG_LEVEL", "INFO").upper())
    avvia(mcp, "scadenze")
