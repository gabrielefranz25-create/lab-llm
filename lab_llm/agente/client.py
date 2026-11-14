"""Chat da terminale: legge le domande, invoca il grafo e tiene la cronologia di sessione.

La cronologia vive solo in memoria: all'uscita si perde. I print didattici "[passo]" sono
commentati: togliere il commento per seguire il flusso.
"""

import logging
from collections.abc import Callable

import openai
from langchain_core.messages import AnyMessage, HumanMessage
from langgraph.errors import GraphRecursionError

from agente.comandi import ErroreComando

logger = logging.getLogger(__name__)

COMANDI_USCITA = {"esci", "exit", "quit"}
TESTO_VUOTO = "(il modello non ha restituito testo)"
CHIUSURA = "Sessione terminata. La cronologia non è stata salvata."


def rispondi(grafo, cronologia: list[AnyMessage], testo: str, recursion_limit: int,
             riassunto: str = "", nuovi: list[AnyMessage] | None = None) -> tuple[list[AnyMessage], str, str]:
    """Un turno: domanda in coda alla cronologia, grafo; nuova cronologia, nuovo riassunto e risposta.

    `nuovi`, se c'è, sostituisce la domanda: sono i messaggi compilati da un prompt MCP (/prompt).
    """
    # print(f"[passo] client: invio la domanda con {len(cronologia)} messaggi di cronologia")
    risultato = grafo.invoke(
        {"messages": cronologia + (nuovi or [HumanMessage(testo)]), "passi_strumento": 0, "revisioni": 0,
         "riassunto": riassunto},
        config={"recursion_limit": recursion_limit},
    )
    messaggi = risultato["messages"]
    risposta = messaggi[-1].content if messaggi else ""
    if not isinstance(risposta, str):  # alcuni modelli restituiscono una lista di parti
        risposta = "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in risposta)
    # print(f"[passo] client: turno concluso, la cronologia ora ha {len(messaggi)} messaggi")
    return messaggi, risultato.get("riassunto", riassunto), risposta.strip() or TESTO_VUOTO


def avvia_sessione(grafo, *, intestazione: str, server: str, recursion_limit: int,
                   leggi: Callable[[str], str] = input,
                   scrivi: Callable[[str], None] = print, comandi=None) -> None:
    """Ciclo della chat fino a esci/exit/quit, Ctrl+C o EOF.

    `comandi` (un ComandiPrompt) gestisce /prompts e /prompt; le righe che iniziano con «/» non vanno
    mai al modello come testo.
    """
    scrivi("Assistente del laboratorio")
    scrivi(intestazione)
    scrivi("Scrivi una domanda e premi Invio. Comandi: /prompts, /prompt nome arg=valore. "
           "Per uscire: esci (oppure Ctrl+C).")
    cronologia: list[AnyMessage] = []
    riassunto = ""  # riassunto dei messaggi vecchi, aggiornato dal nodo compatta
    while True:
        try:
            # lstrip del BOM: PowerShell 5.1 lo antepone all'input passato via pipe.
            testo = leggi("\nTu> ").lstrip("﻿").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not testo:
            continue
        if testo.lower() in COMANDI_USCITA:
            break
        nuovi = None
        if testo.startswith("/"):
            comando = testo.split()[0]
            if comando not in ("/prompts", "/prompt"):
                scrivi(f"Assistente> [errore] Comando sconosciuto: {comando}. Comandi: /prompts, /prompt.")
                continue
            if comandi is None or not comandi.disponibili:
                scrivi("Assistente> [errore] Prompt non disponibili: server utente non raggiungibile.")
                continue
            if comando == "/prompts":
                scrivi(comandi.elenco())
                continue
            try:
                nuovi = comandi.richiama(testo)
            except ErroreComando as errore:  # richiesta bloccata: né server né modello
                scrivi(f"Assistente> [errore] {errore}")
                continue
        try:
            cronologia, riassunto, risposta = rispondi(grafo, cronologia, testo, recursion_limit, riassunto,
                                                       nuovi)
        except KeyboardInterrupt:  # Ctrl+C mentre si aspetta il modello: si esce senza traceback
            break
        except openai.APIError as errore:
            # La domanda fallita non entra nella cronologia: la sessione continua da dov'era.
            logger.error("LM Studio non raggiungibile su %s: %s", server, errore)
            scrivi(f"Assistente> [errore] Non riesco a contattare LM Studio su {server}: "
                   f"{type(errore).__name__}.")
            continue
        except GraphRecursionError as errore:
            logger.error("limite di ricorsione del grafo superato: %s", errore)
            scrivi("Assistente> [errore] Il grafo ha superato il numero massimo di passaggi "
                   "per questa domanda. Prova a riformularla.")
            continue
        scrivi(f"Assistente> {risposta}")
    scrivi(CHIUSURA)
