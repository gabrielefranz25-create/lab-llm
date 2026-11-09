"""Prove con il modello vero di LM Studio: si attivano solo con PROVA_REALE=1.

Leggono .env dalla cartella lab_llm/ e richiedono LM Studio avviato con il modello caricato.
Una risposta simulata non dimostra che il modello sappia usare lo strumento: queste sì.
"""

import os

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from agente.config import carica_config
from agente.graph import NOME_RIASSUNTO, costruisci_grafo, limite_ricorsione
from agente.llm import crea_modello, crea_riassuntore, verifica_modello
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
def chiedi(config):
    """Funzione che porta una domanda nel grafo vero e restituisce tutti i messaggi del turno."""
    strumenti = [crea_ora_corrente(config.fuso_orario_predefinito)]
    grafo = costruisci_grafo(
        crea_modello(config, strumenti), strumenti,
        max_passi=config.max_passi_strumento,
        max_messaggi_contesto=config.max_messaggi_contesto,
        fuso_predefinito=config.fuso_orario_predefinito,
    )

    def _chiedi(testo: str):
        risultato = grafo.invoke(
            {"messages": [HumanMessage(testo)], "passi_strumento": 0},
            config={"recursion_limit": limite_ricorsione(config.max_passi_strumento)},
        )
        return risultato["messages"]

    return _chiedi


def chiamate_ora_corrente(messaggi) -> list[dict]:
    """Argomenti di tutte le tool_call ora_corrente fatte dal modello."""
    return [c["args"] for m in messaggi if isinstance(m, AIMessage)
            for c in m.tool_calls if c["name"] == "ora_corrente"]


def test_modello_disponibile(config):
    verifica_modello(config)


def test_ora_tokyo_usa_lo_strumento(chiedi):
    messaggi = chiedi("Che ore sono a Tokyo?")
    assert any(a.get("fuso_orario") == "Asia/Tokyo" for a in chiamate_ora_corrente(messaggi)), messaggi
    assert any(isinstance(m, ToolMessage) and "Asia/Tokyo" in m.content for m in messaggi), messaggi
    ultimo = [m for m in messaggi if isinstance(m, AIMessage)][-1]
    assert str(ultimo.content).strip(), messaggi


def test_ora_senza_luogo_usa_predefinito(chiedi):
    messaggi = chiedi("Che ore sono?")
    chiamate = chiamate_ora_corrente(messaggi)
    assert any(a == {} or a.get("fuso_orario") == "Europe/Rome" for a in chiamate), messaggi


def test_compattazione_conserva_il_nome(config):
    """Soglia bassa: il nome detto al primo turno sopravvive solo grazie al riassunto."""
    strumenti = [crea_ora_corrente(config.fuso_orario_predefinito)]
    grafo = costruisci_grafo(
        crea_modello(config, strumenti), strumenti,
        max_passi=config.max_passi_strumento, max_messaggi_contesto=6,
        fuso_predefinito=config.fuso_orario_predefinito,
        riassuntore=crea_riassuntore(config), messaggi_da_tenere=2,
    )
    cronologia = []
    domande = ["Ciao, mi chiamo Gabriele e studio a Udine.", "Qual è la capitale della Francia?",
               "E quella della Spagna?", "E quella del Portogallo?", "Come mi chiamo?"]
    for testo in domande:
        cronologia = grafo.invoke(
            {"messages": cronologia + [HumanMessage(testo)], "passi_strumento": 0},
            config={"recursion_limit": limite_ricorsione(config.max_passi_strumento)},
        )["messages"]
    assert isinstance(cronologia[0], SystemMessage) and cronologia[0].name == NOME_RIASSUNTO, cronologia
    assert "Gabriele" in str(cronologia[-1].content), cronologia
