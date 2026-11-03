"""Chat da terminale: legge le domande, invoca il grafo e tiene la cronologia di sessione.

La cronologia vive solo in memoria: all'uscita si perde. I print didattici "[passo]" sono
commentati: togliere il commento per seguire il flusso.
"""

import logging
from collections.abc import Callable

import openai
from langchain_core.messages import AnyMessage, HumanMessage
from langgraph.errors import GraphRecursionError

logger = logging.getLogger(__name__)

COMANDI_USCITA = {"esci", "exit", "quit"}
TESTO_VUOTO = "(il modello non ha restituito testo)"
CHIUSURA = "Sessione terminata. La cronologia non è stata salvata."


def rispondi(grafo, cronologia: list[AnyMessage], testo: str,
             recursion_limit: int) -> tuple[list[AnyMessage], str]:
    """Un turno: domanda in coda alla cronologia, grafo, nuova cronologia e testo della risposta."""
    # print(f"[passo] client: invio la domanda con {len(cronologia)} messaggi di cronologia")
    risultato = grafo.invoke(
        {"messages": cronologia + [HumanMessage(testo)], "passi_strumento": 0},
        config={"recursion_limit": recursion_limit},
    )
    messaggi = risultato["messages"]
    risposta = messaggi[-1].content if messaggi else ""
    if not isinstance(risposta, str):  # alcuni modelli restituiscono una lista di parti
        risposta = "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in risposta)
    # print(f"[passo] client: turno concluso, la cronologia ora ha {len(messaggi)} messaggi")
    return messaggi, risposta.strip() or TESTO_VUOTO


def avvia_sessione(grafo, *, intestazione: str, server: str, recursion_limit: int,
                   leggi: Callable[[str], str] = input,
                   scrivi: Callable[[str], None] = print) -> None:
    """Ciclo della chat fino a esci/exit/quit, Ctrl+C o EOF."""
    scrivi("Assistente del laboratorio")
    scrivi(intestazione)
    scrivi("Scrivi una domanda e premi Invio. Per uscire: esci (oppure Ctrl+C).")
    cronologia: list[AnyMessage] = []
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
        try:
            cronologia, risposta = rispondi(grafo, cronologia, testo, recursion_limit)
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
