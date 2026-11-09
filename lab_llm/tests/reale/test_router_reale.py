"""Prove del router con il modello vero di LM Studio: si attivano solo con PROVA_REALE=1.

Il router simulato dimostra il cablaggio del grafo; queste prove dimostrano che il modello locale
classifica davvero le domande. Con -o log_cli=true --log-cli-level=INFO si vedono le righe
"router: categoria=... motivo=... -> ..." e "agente: invio ...".
"""

import logging
import os

import pytest
from langchain_core.messages import HumanMessage

from agente.config import carica_config
from agente.graph import MESSAGGIO_RIFIUTO, costruisci_grafo, limite_ricorsione
from agente.llm import crea_modello, crea_router
from agente.strumenti import crea_ora_corrente

pytestmark = [
    pytest.mark.reale,
    pytest.mark.skipif(os.environ.get("PROVA_REALE") != "1",
                       reason="prova reale: imposta PROVA_REALE=1"),
]


@pytest.fixture(scope="module")
def config():
    return carica_config()


@pytest.fixture(scope="module")
def grafo(config):
    strumenti = [crea_ora_corrente(config.fuso_orario_predefinito)]
    return costruisci_grafo(
        crea_modello(config, strumenti), strumenti,
        max_passi=config.max_passi_strumento,
        max_messaggi_contesto=config.max_messaggi_contesto,
        fuso_predefinito=config.fuso_orario_predefinito,
        router=crea_router(config), ambito=config.ambito,
    )


def _chiedi(grafo, config, testo):
    return grafo.invoke({"messages": [HumanMessage(testo)], "passi_strumento": 0},
                        config={"recursion_limit": limite_ricorsione(config.max_passi_strumento)})


def test_domanda_in_ambito_passa_all_agente(grafo, config, caplog):
    with caplog.at_level(logging.INFO, logger="agente.graph"):
        stato = _chiedi(grafo, config, "Che ore sono a Tokyo?")
    assert stato["categoria"] == "conversazione"
    assert "router: categoria=conversazione" in caplog.text and "-> agente" in caplog.text
    assert "agente: invio" in caplog.text
    assert stato["messages"][-1].content != MESSAGGIO_RIFIUTO.format(ambito=config.ambito)


def test_domanda_fuori_ambito_rifiutata_senza_agente(grafo, config, caplog):
    with caplog.at_level(logging.INFO, logger="agente.graph"):
        stato = _chiedi(grafo, config, "Scrivimi la ricetta della carbonara")
    assert stato["categoria"] == "fuori_ambito"
    assert "router: categoria=fuori_ambito" in caplog.text and "-> rifiuto" in caplog.text
    assert "agente: invio" not in caplog.text
    assert stato["messages"][-1].content == MESSAGGIO_RIFIUTO.format(ambito=config.ambito)
