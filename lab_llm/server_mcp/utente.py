"""Server MCP «Utente»: le preferenze dell'utente come resource `utente://preferenze` e due prompt.

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

LIVELLI = {
    "base": "usa parole semplici e un esempio della vita quotidiana, senza termini tecnici.",
    "intermedio": "dai una definizione precisa, come funziona e un esempio pratico.",
    "avanzato": "entra nei dettagli tecnici, nei componenti e nei limiti, con la terminologia corretta.",
}
STILI_RIASSUNTO = {
    "sintetico": "Usa al massimo tre frasi.",
    "dettagliato": "Fai un elenco puntato, un punto per ogni domanda, con la risposta data.",
}


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

    # Prompt (lezione 6, step 5): modelli di istruzioni richiamati dall'utente con /prompt nella CLI.
    @server.prompt
    def spiega(argomento: str, livello: str = "base") -> str:
        """Spiega un argomento al livello richiesto.

        Args:
            argomento: concetto da spiegare
            livello: base, intermedio o avanzato
        """
        if livello not in LIVELLI:
            raise ValueError(f"livello '{livello}' non valido: usa {', '.join(LIVELLI)}")
        logger.info("prompt spiega: argomento=%s livello=%s", argomento, livello)
        return f"Spiegami «{argomento}» a livello {livello}: {LIVELLI[livello]}"

    @server.prompt
    def riassumi_conversazione(stile: str = "sintetico") -> str:
        """Riassume i turni della conversazione corrente.

        Args:
            stile: sintetico o dettagliato
        """
        if stile not in STILI_RIASSUNTO:
            raise ValueError(f"stile '{stile}' non valido: usa {', '.join(STILI_RIASSUNTO)}")
        logger.info("prompt riassumi_conversazione: stile=%s", stile)
        return ("Riassumi la nostra conversazione fino a questo momento: le domande che ti ho fatto e le "
                f"risposte che mi hai dato. {STILI_RIASSUNTO[stile]} Non usare strumenti.")

    return server


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stderr, level=os.environ.get("LOG_LEVEL", "INFO").upper())
    avvia(crea_server(Path(os.environ.get("PREFERENZE_FILE") or PREFERENZE_PREDEFINITE)), "utente")
