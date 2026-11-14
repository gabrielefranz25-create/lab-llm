"""Preferenze dell'utente: lette dall'host come resource MCP `utente://preferenze` a inizio sessione.

Una resource la sceglie l'applicazione, non il modello: qui la si legge una volta, prima della prima
domanda, e il risultato va in cima al prompt di sistema. Se non è disponibile si usano i valori
predefiniti, e lo si scrive nei log.
"""

import json
import logging
from dataclasses import dataclass, replace
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from agente.config import Config
from agente.mcp_ponte import ConnessioneMCP, ErroreMCP, ServerMCP

logger = logging.getLogger(__name__)

URI_PREFERENZE = "utente://preferenze"
STILI = {
    "sintetico": "in modo breve e chiaro",
    "dettagliato": "in modo dettagliato, con spiegazioni ed esempi",
}


@dataclass(frozen=True)
class Preferenze:
    lingua: str
    fuso_orario: str
    stile: str


def predefinite(config: Config) -> Preferenze:
    """Valori usati quando la resource o un suo campo mancano."""
    return Preferenze(lingua="italiano", fuso_orario=config.fuso_orario_predefinito, stile="sintetico")


def _fuso_valido(nome) -> bool:
    try:
        ZoneInfo(nome)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        return False
    return True


def interpreta(testo: str, base: Preferenze) -> Preferenze:
    """Preferenze dal JSON della resource; un campo mancante o non valido resta quello di `base`.

    Solleva ValueError se il testo non è un oggetto JSON.
    """
    dati = json.loads(testo)
    if not isinstance(dati, dict):
        raise ValueError("le preferenze devono essere un oggetto JSON")
    valide = {
        "lingua": lambda v: isinstance(v, str) and v.strip(),
        "fuso_orario": lambda v: isinstance(v, str) and _fuso_valido(v),
        "stile": lambda v: v in STILI,
    }
    scelte = {}
    for campo, valida in valide.items():
        if campo not in dati:
            continue
        valore = dati[campo]
        if valida(valore):
            scelte[campo] = valore.strip()
        else:
            logger.warning("preferenze: %s=%r non valido, uso %r", campo, valore, getattr(base, campo))
    return replace(base, **scelte)


def istruzioni(preferenze: Preferenze) -> str:
    """Riga da mettere in cima al prompt di sistema."""
    return (f"Preferenze dell'utente (resource {URI_PREFERENZE}): rispondi sempre in "
            f"{preferenze.lingua}, {STILI[preferenze.stile]} (stile {preferenze.stile}). "
            f"Fuso orario predefinito dell'utente: {preferenze.fuso_orario}.")


def leggi_preferenze(server: ServerMCP | None, timeout: float, base: Preferenze) -> Preferenze:
    """Legge la resource dal server `utente` con una connessione dedicata, chiusa subito dopo.

    Server assente o spento, file mancante o JSON non valido: valori di `base` e WARNING.
    """
    try:
        if server is None:
            raise ErroreMCP("nessun server utente configurato")
        with ConnessioneMCP([server], timeout) as connessione:
            testo = connessione.leggi_risorsa(server.nome, URI_PREFERENZE)
        preferenze = interpreta(testo, base)
    except (ErroreMCP, ValueError) as errore:
        logger.warning("preferenze: resource %s non disponibile, uso i valori predefiniti "
                       "(lingua=%s fuso_orario=%s stile=%s): %s", URI_PREFERENZE, base.lingua,
                       base.fuso_orario, base.stile, errore)
        return base
    logger.info("resource: %s letta dal server %s: lingua=%s fuso_orario=%s stile=%s", URI_PREFERENZE,
                server.nome, preferenze.lingua, preferenze.fuso_orario, preferenze.stile)
    return preferenze
