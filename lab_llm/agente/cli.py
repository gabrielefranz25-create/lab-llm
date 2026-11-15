"""CLI client dell'API dell'agente (lezione 6, step 6): la stessa chat, ma ogni turno è una POST /chat.

La CLI tiene cronologia e riassunto della sessione e li manda a ogni turno; il servizio
(`python -m agente.servizio`) non conserva nulla. Indirizzo da AGENTE_URL.

Avvio: `python -m agente.cli` (serve il servizio già avviato).
"""

import os
import sys
from collections.abc import Callable

import httpx
from dotenv import load_dotenv

from agente.client import CHIUSURA, COMANDI_USCITA
from agente.comandi import ErroreComando, formatta_catalogo, interpreta_riga

# Un turno può durare minuti (modello locale, strumenti, revisore).
TIMEOUT = 600.0


class ErroreServizio(Exception):
    """Servizio non raggiungibile o risposta d'errore: il messaggio è per l'utente."""


class ClienteAgente:
    """Chiamate all'API dell'agente."""

    def __init__(self, url: str, http: httpx.Client | None = None):
        self.url = url.rstrip("/")
        self.http = http or httpx.Client(base_url=self.url, timeout=TIMEOUT)

    def _chiama(self, metodo: str, percorso: str, **opzioni):
        try:
            risposta = self.http.request(metodo, percorso, **opzioni)
        except httpx.HTTPError as errore:
            raise ErroreServizio(f"Servizio dell'agente non raggiungibile su {self.url}: "
                                 f"{type(errore).__name__}.") from errore
        if risposta.status_code >= 400:
            try:
                testo = risposta.json().get("errore") or risposta.text
            except ValueError:
                testo = risposta.text
            raise ErroreServizio(f"{testo} (HTTP {risposta.status_code})")
        return risposta.json()

    def chat(self, messaggio: str | None, cronologia: list[dict], riassunto: str,
             prompt: tuple[str, dict] | None = None) -> dict:
        corpo = {"cronologia": cronologia, "riassunto": riassunto}
        if prompt:
            corpo["prompt"] = {"nome": prompt[0], "argomenti": prompt[1]}
        else:
            corpo["messaggio"] = messaggio
        return self._chiama("POST", "/chat", json=corpo)

    def prompts(self) -> list[dict]:
        return self._chiama("GET", "/prompts")

    def stato(self) -> dict:
        return self._chiama("GET", "/stato")


def avvia_cli(cliente: ClienteAgente, *, leggi: Callable[[str], str] = input,
              scrivi: Callable[[str], None] = print) -> None:
    """Ciclo della chat via API, fino a esci/exit/quit, Ctrl+C o EOF."""
    scrivi(f"Assistente del laboratorio (via API: {cliente.url})")
    scrivi("Scrivi una domanda e premi Invio. Comandi: /prompts, /prompt nome arg=valore. "
           "Per uscire: esci (oppure Ctrl+C).")
    cronologia: list[dict] = []
    riassunto = ""
    while True:
        try:
            testo = leggi("\nTu> ").lstrip("﻿").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not testo:
            continue
        if testo.lower() in COMANDI_USCITA:
            break
        try:
            if testo.startswith("/"):
                comando = testo.split()[0]
                if comando == "/prompts":
                    scrivi(formatta_catalogo(cliente.prompts()))
                    continue
                if comando != "/prompt":
                    raise ErroreComando(f"Comando sconosciuto: {comando}. Comandi: /prompts, /prompt.")
                # Qui solo la sintassi; nome e argomenti li controlla il servizio (prompts/list).
                esito = cliente.chat(None, cronologia, riassunto, prompt=interpreta_riga(testo))
            else:
                esito = cliente.chat(testo, cronologia, riassunto)
        except (ErroreComando, ErroreServizio) as errore:
            scrivi(f"Assistente> [errore] {errore}")
            continue
        except KeyboardInterrupt:
            break
        cronologia, riassunto = esito["cronologia"], esito["riassunto"]
        scrivi(f"Assistente> {esito['risposta']}")
    scrivi(CHIUSURA)


def main() -> int:
    load_dotenv(override=False)
    cliente = ClienteAgente(os.environ.get("AGENTE_URL") or "http://127.0.0.1:8000")
    try:
        stato = cliente.stato()
    except ErroreServizio as errore:
        print(f"Errore: {errore}\nSuggerimento: avvia il servizio con python -m agente.servizio.",
              file=sys.stderr)
        return 1
    print(f"Modello: {stato['modello']['id']}  |  Server MCP: "
          f"{', '.join(f'{n}={s}' for n, s in stato['server_mcp'].items())}")
    avvia_cli(cliente)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
