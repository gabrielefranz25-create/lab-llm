"""Prove reali del server MCP meteo con LM Studio: si attivano solo con PROVA_REALE=1.

Richiedono LM Studio avviato con il modello caricato e la rete attiva (Open-Meteo).
Le prove meteo usano il solo server meteo, quelle sulle note il solo server note con un
NOTE_DB temporaneo (mai il file vero), qualunque cosa dica SERVER_MCP, così restano stabili.
"""

import os
import re
from dataclasses import replace

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agente.config import carica_config
from agente.graph import costruisci_grafo, limite_ricorsione
from agente.llm import crea_modello, crea_riassuntore
from agente.main import server_da_config
from agente.mcp_ponte import ConnessioneMCP, unisci_strumenti
from agente.strumenti import crea_ora_corrente

pytestmark = [
    pytest.mark.reale,
    pytest.mark.skipif(os.environ.get("PROVA_REALE") != "1",
                       reason="prova reale: imposta PROVA_REALE=1"),
]

DATA_ISO = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


@pytest.fixture(scope="module")
def config():
    return carica_config()


@pytest.fixture(scope="module")
def connessione(config):
    """Connessione MCP al solo server meteo, aperta per tutto il modulo."""
    server = server_da_config(replace(config, server_mcp=("meteo",)))
    with ConnessioneMCP(server, config.mcp_timeout) as aperta:
        yield aperta


def crea_chiedi(config, connessione):
    """Funzione che porta una domanda nel grafo vero e restituisce tutti i messaggi del turno."""
    strumenti = unisci_strumenti([crea_ora_corrente(config.fuso_orario_predefinito)],
                                 connessione.strumenti)
    grafo = costruisci_grafo(
        crea_modello(config, strumenti), strumenti,
        max_passi=config.max_passi_strumento,
        max_messaggi_contesto=config.max_messaggi_contesto,
        fuso_predefinito=config.fuso_orario_predefinito,
        riassuntore=crea_riassuntore(config),
        messaggi_da_tenere=config.messaggi_da_tenere,
    )

    def _chiedi(testo: str):
        risultato = grafo.invoke(
            {"messages": [HumanMessage(testo)], "passi_strumento": 0},
            config={"recursion_limit": limite_ricorsione(config.max_passi_strumento)},
        )
        return risultato["messages"]

    return _chiedi


@pytest.fixture(scope="module")
def chiedi(config, connessione):
    return crea_chiedi(config, connessione)


def chiamate(messaggi, nome: str) -> list[dict]:
    """Tool_call (con id e argomenti) del tool indicato fatte dal modello."""
    return [c for m in messaggi if isinstance(m, AIMessage)
            for c in m.tool_calls if c["name"] == nome]


def risultato_di(messaggi, chiamata: dict) -> str:
    """Contenuto del ToolMessage correlato alla chiamata."""
    return "\n".join(str(m.content) for m in messaggi
                     if isinstance(m, ToolMessage) and m.tool_call_id == chiamata["id"])


def test_meteo_attuale_reale(chiedi):
    messaggi = chiedi("Che tempo fa a Udine adesso?")
    trovate = chiamate(messaggi, "meteo_attuale")
    assert trovate, messaggi
    esiti = [risultato_di(messaggi, c) for c in trovate]
    assert any(e and not e.startswith("Errore") and "Udine" in e for e in esiti), messaggi
    ultimo = [m for m in messaggi if isinstance(m, AIMessage)][-1]
    assert "Udine" in str(ultimo.content), messaggi


def test_previsioni_reali(chiedi):
    messaggi = chiedi("Che tempo farà a Tokyo nei prossimi 3 giorni?")
    trovate = [c for c in chiamate(messaggi, "previsioni_meteo") if "Tokyo" in str(c["args"].get("citta", ""))]
    assert trovate, messaggi
    assert any(len(DATA_ISO.findall(risultato_di(messaggi, c))) >= 3 for c in trovate), messaggi


def test_citta_inesistente_diretta(connessione):
    strumento = next(s for s in connessione.strumenti if s.name == "meteo_attuale")
    esito = strumento.invoke({"citta": "Xyzzyqwop"})
    assert esito.startswith("Errore dallo strumento meteo_attuale: città non trovata"), esito


# --- Note: server note con un archivio temporaneo, condiviso dai tre test (in ordine) ---

@pytest.fixture(scope="module")
def config_note(config, tmp_path_factory):
    """Config con NOTE_DB su una cartella temporanea e il solo server note."""
    db = tmp_path_factory.mktemp("note_reali") / "note.sqlite3"
    return replace(config, note_db=str(db), server_mcp=("note",))


@pytest.fixture(scope="module")
def connessione_note(config_note):
    with ConnessioneMCP(server_da_config(config_note), config_note.mcp_timeout) as aperta:
        yield aperta


@pytest.fixture(scope="module")
def chiedi_note(config_note, connessione_note):
    return crea_chiedi(config_note, connessione_note)


def test_aggiungi_nota_reale(chiedi_note):
    messaggi = chiedi_note("Ricordami di consegnare il report venerdì")
    trovate = chiamate(messaggi, "aggiungi_nota")
    assert len(trovate) == 1, messaggi
    assert "salvata" in risultato_di(messaggi, trovate[0]), messaggi


def test_elimina_nota_inesistente_reale(chiedi_note, connessione_note):
    messaggi = chiedi_note("Elimina la nota 99")
    trovate = chiamate(messaggi, "elimina_nota")
    assert trovate, messaggi
    assert any(risultato_di(messaggi, c).startswith("Errore dallo strumento elimina_nota")
               for c in trovate), messaggi
    elenco = next(s for s in connessione_note.strumenti if s.name == "elenca_note").invoke({})
    assert "report" in elenco, elenco


def test_note_dopo_riavvio(config_note):
    # Nuova connessione (nuovo sottoprocesso) sullo stesso NOTE_DB: la nota deve esserci ancora.
    with ConnessioneMCP(server_da_config(config_note), config_note.mcp_timeout) as nuova:
        elenco = next(s for s in nuova.strumenti if s.name == "elenca_note").invoke({})
    assert "report" in elenco, elenco
