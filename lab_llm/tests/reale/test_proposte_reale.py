"""Prove reali dei server delle proposte (unita, calcolatrice, scadenze, catalogo) con LM Studio.

Si attivano solo con PROVA_REALE=1. Ogni gruppo usa il solo server provato, così la selezione del tool
non dipende dagli altri; l'ultima prova attiva tutti i server e il router, per vedere se il modello
sceglie ancora lo strumento giusto con il catalogo completo.
"""

import os
from dataclasses import replace

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from agente.config import SERVER_MCP_NOTI, ambito_predefinito
from agente.graph import costruisci_grafo, limite_ricorsione
from agente.llm import crea_modello, crea_riassuntore, crea_router
from agente.main import server_da_config
from agente.mcp_ponte import ConnessioneMCP, unisci_strumenti
from agente.strumenti import crea_ora_corrente
from tests.reale.test_mcp_reale import chiamate, crea_chiedi, risultato_di

pytestmark = [
    pytest.mark.reale,
    pytest.mark.skipif(os.environ.get("PROVA_REALE") != "1",
                       reason="prova reale: imposta PROVA_REALE=1"),
]


@pytest.fixture(scope="module")
def config(tmp_path_factory):
    from agente.config import carica_config
    # NOTE_DB temporaneo: la prova con tutti i server avvia anche il server note.
    db = tmp_path_factory.mktemp("proposte_reali") / "note.sqlite3"
    return replace(carica_config(), note_db=str(db))


def _connessione(config, *server):
    return ConnessioneMCP(server_da_config(replace(config, server_mcp=server)), config.mcp_timeout)


def _strumento(connessione, nome):
    return next(s for s in connessione.strumenti if s.name == nome)


def test_calcolatrice_reale(config):
    with _connessione(config, "calcolatrice") as connessione:
        messaggi = crea_chiedi(config, connessione)("Quanto fa 17*23?")
        trovate = chiamate(messaggi, "calcola")
        assert trovate, messaggi
        assert any("391" in risultato_di(messaggi, c) for c in trovate), messaggi
        assert "391" in str([m for m in messaggi if isinstance(m, AIMessage)][-1].content), messaggi
        esito = _strumento(connessione, "calcola").invoke({"espressione": "__import__('os')"})
        assert esito.startswith("Errore dallo strumento calcola: elemento non consentito"), esito


def test_unita_reale(config):
    with _connessione(config, "unita") as connessione:
        messaggi = crea_chiedi(config, connessione)("Quanti chilometri sono 10 miglia?")
        trovate = chiamate(messaggi, "converti_unita")
        assert trovate, messaggi
        assert any("16.0934 km" in risultato_di(messaggi, c) for c in trovate), messaggi
        esito = _strumento(connessione, "converti_unita").invoke({"valore": 1, "da": "km", "a": "kg"})
        assert esito.startswith("Errore dallo strumento converti_unita: impossibile convertire"), esito


def test_scadenze_reale(config):
    with _connessione(config, "scadenze") as connessione:
        messaggi = crea_chiedi(config, connessione)(
            "Quanti giorni lavorativi ci sono tra il 2026-12-20 e il 2027-01-10?")
        trovate = chiamate(messaggi, "giorni_tra")
        assert trovate, messaggi
        assert any("12 giorni lavorativi" in risultato_di(messaggi, c) for c in trovate), messaggi
        esito = _strumento(connessione, "aggiungi_giorni").invoke({"data": "31/12/2026", "giorni": 3})
        assert esito.startswith("Errore dallo strumento aggiungi_giorni: data non valida"), esito


def test_catalogo_ricerca_poi_dettaglio_reale(config):
    with _connessione(config, "catalogo") as connessione:
        messaggi = crea_chiedi(config, connessione)(
            "Che corsi ci sono a Udine? Dammi i dettagli del primo che trovi.")
        ricerche, dettagli = chiamate(messaggi, "cerca_corsi"), chiamate(messaggi, "dettaglio_corso")
        assert ricerche and dettagli, messaggi
        ordine = [c["name"] for m in messaggi if isinstance(m, AIMessage) for c in m.tool_calls]
        assert ordine.index("cerca_corsi") < ordine.index("dettaglio_corso"), ordine
        esito = _strumento(connessione, "dettaglio_corso").invoke({"codice": "XX-99"})
        assert esito.startswith("Errore dallo strumento dettaglio_corso: nessun corso"), esito


def test_tutti_i_server_con_router_reale(config):
    """Catalogo completo (11 tool MCP + orologio) e router: la domanda di calcolo va ancora a `calcola`."""
    completa = replace(config, server_mcp=SERVER_MCP_NOTI, ambito=ambito_predefinito(SERVER_MCP_NOTI))
    with ConnessioneMCP(server_da_config(completa), completa.mcp_timeout) as connessione:
        strumenti = unisci_strumenti([crea_ora_corrente(completa.fuso_orario_predefinito)],
                                     connessione.strumenti)
        grafo = costruisci_grafo(
            crea_modello(completa, strumenti), strumenti,
            max_passi=completa.max_passi_strumento,
            max_messaggi_contesto=completa.max_messaggi_contesto,
            fuso_predefinito=completa.fuso_orario_predefinito,
            riassuntore=crea_riassuntore(completa),
            messaggi_da_tenere=completa.messaggi_da_tenere,
            router=crea_router(completa), ambito=completa.ambito,
        )
        risultato = grafo.invoke(
            {"messages": [HumanMessage("Quanto fa 128 diviso 4 più 7?")], "passi_strumento": 0},
            config={"recursion_limit": limite_ricorsione(completa.max_passi_strumento)},
        )
    assert risultato["categoria"] == "conversazione", risultato["messages"]
    messaggi = risultato["messages"]
    trovate = chiamate(messaggi, "calcola")
    assert trovate, messaggi
    assert any("39" in risultato_di(messaggi, c) for c in trovate), messaggi
