"""Prove del revisore con il modello vero di LM Studio: si attivano solo con PROVA_REALE=1.

Il revisore simulato dimostra il cablaggio del grafo; queste prove dimostrano che il modello locale
giudica davvero la coerenza. Con -o log_cli=true --log-cli-level=INFO si vedono le righe
"revisore: coerente=... motivo=... -> ...".
"""

import logging
import os
from dataclasses import replace

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agente.config import carica_config
from agente.graph import PROMPT_REVISORE, DecisioneRevisore, costruisci_grafo, limite_ricorsione
from agente.llm import crea_modello, crea_revisore
from agente.mcp_ponte import ConnessioneMCP, unisci_strumenti
from agente.main import server_da_config
from agente.strumenti import crea_ora_corrente

pytestmark = [
    pytest.mark.reale,
    pytest.mark.skipif(os.environ.get("PROVA_REALE") != "1",
                       reason="prova reale: imposta PROVA_REALE=1"),
]

DOMANDA = "Che ore sono a Tokyo e quanto fa 15 per 12?"


@pytest.fixture(scope="module")
def config():
    return carica_config()


def _giudica(config, risposta: str) -> DecisioneRevisore:
    testo = f"Domanda dell'utente: {DOMANDA}\n\nRisposta proposta: {risposta}"
    return crea_revisore(config).invoke([SystemMessage(PROMPT_REVISORE), HumanMessage(testo)])


def test_risposta_parziale_non_coerente(config):
    decisione = _giudica(config, "A Tokyo sono le 18:30 (fuso Asia/Tokyo).")
    assert isinstance(decisione, DecisioneRevisore)
    assert decisione.coerente is False and decisione.motivo


def test_risposta_completa_coerente(config):
    decisione = _giudica(config, "A Tokyo sono le 18:30 (fuso Asia/Tokyo) e 15 per 12 fa 180.")
    assert isinstance(decisione, DecisioneRevisore)
    assert decisione.coerente is True


def test_grafo_con_domanda_in_due_parti(config, caplog):
    """Grafo vero con orologio e calcolatrice: la risposta finale tratta entrambe le parti."""
    solo_calcolatrice = replace(config, server_mcp=("calcolatrice",), variante_orologio="locale",
                                trasporto_mcp="stdio")
    with ConnessioneMCP(server_da_config(solo_calcolatrice), config.mcp_timeout) as connessione:
        strumenti = unisci_strumenti([crea_ora_corrente(config.fuso_orario_predefinito)],
                                     connessione.strumenti)
        grafo = costruisci_grafo(
            crea_modello(config, strumenti), strumenti,
            max_passi=config.max_passi_strumento,
            max_messaggi_contesto=config.max_messaggi_contesto,
            fuso_predefinito=config.fuso_orario_predefinito,
            revisore=crea_revisore(config), max_revisioni=config.max_revisioni,
        )
        with caplog.at_level(logging.INFO, logger="agente.graph"):
            stato = grafo.invoke(
                {"messages": [HumanMessage(DOMANDA)], "passi_strumento": 0, "revisioni": 0},
                config={"recursion_limit": limite_ricorsione(config.max_passi_strumento,
                                                             config.max_revisioni)},
            )
    risposta = stato["messages"][-1].content
    assert "revisore: coerente=si" in caplog.text
    assert "180" in risposta, risposta
    assert "Tokyo" in risposta or "Asia/Tokyo" in risposta


class PrimaBozzaParziale:
    """Agente vero, tranne la prima risposta: una bozza parziale scritta a mano."""

    def __init__(self, vero):
        self.vero, self.chiamate = vero, 0

    def invoke(self, messaggi):
        self.chiamate += 1
        if self.chiamate == 1:
            return AIMessage("A Tokyo sono le 15:30 (fuso Asia/Tokyo).")
        return self.vero.invoke(messaggi)


def test_bozza_parziale_corretta_dopo_la_revisione(config, caplog):
    """Evidenza dello step 2: rifiuto motivato del revisore vero e nuova risposta completa dell'agente vero."""
    solo_calcolatrice = replace(config, server_mcp=("calcolatrice",), variante_orologio="locale",
                                trasporto_mcp="stdio")
    with ConnessioneMCP(server_da_config(solo_calcolatrice), config.mcp_timeout) as connessione:
        strumenti = unisci_strumenti([crea_ora_corrente(config.fuso_orario_predefinito)],
                                     connessione.strumenti)
        modello = PrimaBozzaParziale(crea_modello(config, strumenti))
        grafo = costruisci_grafo(
            modello, strumenti,
            max_passi=config.max_passi_strumento,
            max_messaggi_contesto=config.max_messaggi_contesto,
            fuso_predefinito=config.fuso_orario_predefinito,
            revisore=crea_revisore(config), max_revisioni=config.max_revisioni,
        )
        with caplog.at_level(logging.INFO, logger="agente.graph"):
            stato = grafo.invoke(
                {"messages": [HumanMessage(DOMANDA)], "passi_strumento": 0, "revisioni": 0},
                config={"recursion_limit": limite_ricorsione(config.max_passi_strumento,
                                                             config.max_revisioni)},
            )
    risposta = stato["messages"][-1].content
    assert "revisore: coerente=no" in caplog.text and "-> agente (revisione 1 di" in caplog.text
    assert "revisore: coerente=si" in caplog.text
    assert stato["revisioni"] >= 1
    assert "180" in risposta, risposta
