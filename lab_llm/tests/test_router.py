"""Test del router: conversazione → agente, fuori ambito → rifiuto, con router e modello finti."""

import logging

import httpx
import openai
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agente.graph import MESSAGGIO_RIFIUTO, DecisioneRouter, costruisci_grafo
from agente.strumenti import crea_ora_corrente

AMBITO = "ora, meteo e note"


class ModelloFinto:
    """Agente finto: restituisce sempre la stessa risposta e ricorda i messaggi ricevuti."""

    def __init__(self, risposta: str = "Sono le 10"):
        self.risposta = risposta
        self.chiamate: list[list] = []

    def invoke(self, messaggi):
        self.chiamate.append(list(messaggi))
        return AIMessage(self.risposta)


class RouterFinto:
    """Router finto: restituisce la decisione preparata e ricorda i messaggi ricevuti."""

    def __init__(self, categoria: str, motivo: str = "motivo di prova"):
        self.decisione = DecisioneRouter(categoria=categoria, motivo=motivo)
        self.chiamate: list[list] = []

    def invoke(self, messaggi):
        self.chiamate.append(list(messaggi))
        return self.decisione


class RouterGuasto:
    def invoke(self, messaggi):
        raise openai.APIConnectionError(request=httpx.Request("POST", "http://x"))


class RouterSenzaRisposta:
    """Come with_structured_output quando il modello non restituisce un oggetto valido."""

    def invoke(self, messaggi):
        return None


def _grafo(modello, router):
    return costruisci_grafo(
        modello, [crea_ora_corrente()], max_passi=3, max_messaggi_contesto=20,
        fuso_predefinito="Europe/Rome", router=router, ambito=AMBITO,
    )


def _esegui(grafo, domanda, cronologia=()):
    return grafo.invoke({"messages": [*cronologia, HumanMessage(domanda)], "passi_strumento": 0})


def test_conversazione_passa_all_agente(caplog):
    modello = ModelloFinto()
    with caplog.at_level(logging.INFO, logger="agente.graph"):
        stato = _esegui(_grafo(modello, RouterFinto("conversazione", "chiede l'ora")), "Che ore sono?")
    assert len(modello.chiamate) == 1
    assert stato["categoria"] == "conversazione"
    assert stato["messages"][-1].content == "Sono le 10"
    assert "router: categoria=conversazione motivo=chiede l'ora -> agente" in caplog.text
    assert "agente: invio" in caplog.text


def test_fuori_ambito_rifiutata_senza_agente(caplog):
    modello = ModelloFinto()
    with caplog.at_level(logging.INFO, logger="agente.graph"):
        stato = _esegui(_grafo(modello, RouterFinto("fuori_ambito", "chiede una ricetta")),
                        "Ricetta della carbonara?")
    assert modello.chiamate == []
    assert stato["categoria"] == "fuori_ambito"
    assert stato["messages"][-1] == AIMessage(MESSAGGIO_RIFIUTO.format(ambito=AMBITO),
                                              id=stato["messages"][-1].id)
    assert "router: categoria=fuori_ambito motivo=chiede una ricetta -> rifiuto" in caplog.text
    assert "agente: invio" not in caplog.text


def test_router_riceve_ambito_e_conversazione_recente_ma_non_gli_strumenti():
    router = RouterFinto("conversazione")
    cronologia = [HumanMessage("Che tempo fa a Roma?"), AIMessage("Sereno, 20 gradi")]
    _esegui(_grafo(ModelloFinto(), router), "e domani?", cronologia)
    sistema, utente = router.chiamate[0]
    assert isinstance(sistema, SystemMessage) and AMBITO in sistema.content
    assert "ora_corrente" not in sistema.content
    assert "Che tempo fa a Roma?" in utente.content
    assert "Domanda da classificare: e domani?" in utente.content


def test_router_in_errore_passa_all_agente(caplog):
    modello = ModelloFinto()
    with caplog.at_level(logging.WARNING, logger="agente.graph"):
        stato = _esegui(_grafo(modello, RouterGuasto()), "Che ore sono?")
    assert len(modello.chiamate) == 1
    assert stato["categoria"] == "conversazione"
    assert "router non riuscito" in caplog.text


def test_router_senza_risposta_valida_passa_all_agente(caplog):
    modello = ModelloFinto()
    with caplog.at_level(logging.WARNING, logger="agente.graph"):
        _esegui(_grafo(modello, RouterSenzaRisposta()), "Che ore sono?")
    assert len(modello.chiamate) == 1
    assert "router non riuscito" in caplog.text


def test_senza_router_si_va_sempre_all_agente():
    modello = ModelloFinto()
    stato = _esegui(_grafo(modello, None), "Ricetta della carbonara?")
    assert len(modello.chiamate) == 1
    assert stato["categoria"] == "conversazione"


def test_router_riceve_il_riassunto_della_conversazione():
    router = RouterFinto("conversazione")
    _grafo(ModelloFinto(), router).invoke(
        {"messages": [HumanMessage("Come mi chiamo?")], "passi_strumento": 0,
         "riassunto": "L'utente si chiama Gabriele."})
    sistema, utente = router.chiamate[0]
    assert "L'utente si chiama Gabriele." in utente.content
    assert "Domanda da classificare: Come mi chiamo?" in utente.content
    assert "ciò che l'utente ha detto" in sistema.content
