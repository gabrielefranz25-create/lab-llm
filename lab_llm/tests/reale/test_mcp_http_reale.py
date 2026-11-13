"""Prove reali con i server MCP raggiunti via Streamable HTTP: si attivano solo con PROVA_REALE=1.

I server (orologio e calcolatrice) sono avviati dal test con MCP_TRASPORTO=http; l'agente vi si
collega con un URL, come con TRASPORTO_MCP=http.
"""

import os
from contextlib import ExitStack

import pytest
from langchain_core.messages import HumanMessage

from agente.config import carica_config
from agente.graph import costruisci_grafo, limite_ricorsione
from agente.llm import crea_modello
from agente.mcp_ponte import ConnessioneMCP, ServerMCP
from tests.reale.test_mcp_reale import chiamate, risultato_di
from tests.test_mcp_http import server_http

pytestmark = [
    pytest.mark.reale,
    pytest.mark.skipif(os.environ.get("PROVA_REALE") != "1",
                       reason="prova reale: imposta PROVA_REALE=1"),
]


@pytest.fixture(scope="module")
def chiedi():
    config = carica_config()
    with ExitStack() as pila:
        servers = [ServerMCP(nome, (), url=pila.enter_context(server_http(nome, {})))
                   for nome in ("orologio", "calcolatrice")]
        connessione = pila.enter_context(ConnessioneMCP(servers, config.mcp_timeout))
        strumenti = connessione.strumenti
        grafo = costruisci_grafo(
            crea_modello(config, strumenti), strumenti,
            max_passi=config.max_passi_strumento,
            max_messaggi_contesto=config.max_messaggi_contesto,
            fuso_predefinito=config.fuso_orario_predefinito,
        )

        def _chiedi(testo: str):
            return grafo.invoke(
                {"messages": [HumanMessage(testo)], "passi_strumento": 0},
                config={"recursion_limit": limite_ricorsione(config.max_passi_strumento)},
            )["messages"]

        yield _chiedi


def test_orologio_via_http(chiedi):
    messaggi = chiedi("Che ore sono a Tokyo?")
    (chiamata,) = chiamate(messaggi, "ora_corrente")
    assert chiamata["args"].get("fuso_orario") == "Asia/Tokyo"
    risultato = risultato_di(messaggi, chiamata)
    assert "Asia/Tokyo (JST, UTC+09:00)" in risultato
    assert risultato.split("Ora: ")[1][:5] in messaggi[-1].content


def test_calcolatrice_via_http(chiedi):
    messaggi = chiedi("Quanto fa 15 per 12?")
    (chiamata, *_) = chiamate(messaggi, "calcola")
    assert "= 180" in risultato_di(messaggi, chiamata)
    assert "180" in messaggi[-1].content
