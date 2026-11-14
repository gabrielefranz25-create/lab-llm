"""Prove del servizio HTTP dell'agente con il modello vero (PROVA_REALE=1).

Il servizio gira in-process (TestClient) sopra lo stesso Agente della chat locale: la stessa domanda
fatta all'API e al nucleo usa lo stesso strumento con gli stessi argomenti.
"""

import os
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from agente.config import carica_config
from agente.main import costruisci_agente
from agente.servizio import crea_app

pytestmark = [
    pytest.mark.reale,
    pytest.mark.skipif(os.environ.get("PROVA_REALE") != "1",
                       reason="prova reale: imposta PROVA_REALE=1"),
]


@pytest.fixture(scope="module")
def agente():
    config = replace(carica_config(), server_mcp=("calcolatrice",), variante_orologio="locale",
                     trasporto_mcp="stdio")
    with costruisci_agente(config) as (agente, _intestazione):
        yield agente


def test_chat_via_api_con_strumento_e_cronologia(agente):
    client = TestClient(crea_app(agente))
    primo = client.post("/chat", json={"messaggio": "Che ore sono a Tokyo?"})
    assert primo.status_code == 200, primo.text
    corpo = primo.json()
    assert {"nome": "ora_corrente", "argomenti": {"fuso_orario": "Asia/Tokyo"}, "esito": "ok"} in corpo["strumenti"]
    secondo = client.post("/chat", json={"messaggio": "Quanto fa 15 per 12?", "cronologia": corpo["cronologia"],
                                         "riassunto": corpo["riassunto"]}).json()
    assert [s["nome"] for s in secondo["strumenti"]] == ["calcola"] and "180" in secondo["risposta"]
    assert len(secondo["cronologia"]) > len(corpo["cronologia"])


def test_stessa_risposta_da_api_e_da_chat_locale(agente):
    # «Che ore sono a Tokyo?» e non «15 per 12»: senza cronologia gemma-4-e2b a volte risponde a
    # «15 per 12» senza chiamare `calcola` (anche nella chat locale), e il confronto non direbbe nulla.
    via_api = TestClient(crea_app(agente)).post("/chat", json={"messaggio": "Che ore sono a Tokyo?"}).json()
    locale = agente.turno([], "", testo="Che ore sono a Tokyo?")
    assert via_api["strumenti"] == locale.strumenti == [
        {"nome": "ora_corrente", "argomenti": {"fuso_orario": "Asia/Tokyo"}, "esito": "ok"}]
    assert "Tokyo" in via_api["risposta"] and "Tokyo" in locale.risposta


def test_stato_e_prompt(agente):
    client = TestClient(crea_app(agente))
    stato = client.get("/stato")
    assert stato.status_code == 200
    assert stato.json()["server_mcp"] == {"calcolatrice": "ok", "utente": "ok"}
    assert {p["nome"] for p in client.get("/prompts").json()} == {"spiega", "riassumi_conversazione"}
