"""Test del ponte MCP sincrono: server stdio veri (meteo e server di prova), nessuna rete."""

import logging
import time
from pathlib import Path

from langchain_core.tools import tool

from agente.mcp_ponte import ConnessioneMCP, ServerMCP, unisci_strumenti

TIMEOUT = 20
METEO = ServerMCP("meteo", ("-m", "server_mcp.meteo"))
MORENTE = ServerMCP("morente", (str(Path(__file__).with_name("server_morente.py")),))
ROTTO = ServerMCP("rotto", ("-m", "modulo_inesistente_xyz"))


def strumento(connessione: ConnessioneMCP, nome: str):
    """Il tool del ponte con il nome indicato."""
    return next(t for t in connessione.strumenti if t.name == nome)


def test_discovery_dal_server():
    with ConnessioneMCP([METEO], TIMEOUT) as connessione:
        assert {t.name for t in connessione.strumenti} == {"meteo_attuale", "previsioni_meteo"}
        catalogo = {voce.name: voce for voce in connessione.cataloghi["meteo"]}
        for t in connessione.strumenti:
            assert t.metadata["origine"] == "mcp:meteo"
            assert "citta" in t.args
            assert t.description == catalogo[t.name].description


def test_chiamata_sincrona_riuscita():
    with ConnessioneMCP([MORENTE], TIMEOUT) as connessione:
        assert strumento(connessione, "eco").invoke({"testo": "ciao"}) == "ciao"


def test_errore_dello_strumento():
    # Con una città vuota il server solleva ToolError prima di qualunque accesso alla rete.
    with ConnessioneMCP([METEO], TIMEOUT) as connessione:
        esito = strumento(connessione, "meteo_attuale").invoke({"citta": " "})
    assert esito.startswith("Errore dallo strumento meteo_attuale:")


def test_argomenti_non_validi_diventano_errore_dello_strumento():
    # Con uno schema JSON (dizionario) LangChain non valida gli argomenti: li inoltra al server,
    # che li rifiuta con un ToolError. Il ponte lo restituisce come testo, senza sollevare.
    with ConnessioneMCP([MORENTE], TIMEOUT) as connessione:
        eco = strumento(connessione, "eco")
        mancante = eco.invoke({})
        tipo_errato = eco.invoke({"testo": 3})
    assert mancante.startswith("Errore dallo strumento eco:")
    assert tipo_errato.startswith("Errore dallo strumento eco:")


def test_server_che_non_parte(caplog):
    with caplog.at_level(logging.WARNING, logger="agente.mcp_ponte"):
        with ConnessioneMCP([ROTTO], TIMEOUT) as connessione:
            assert connessione.strumenti == []
    assert any("rotto" in r.getMessage() for r in caplog.records if r.levelno == logging.WARNING)


def test_server_che_non_parte_non_blocca_gli_altri(caplog):
    with caplog.at_level(logging.WARNING, logger="agente.mcp_ponte"):
        with ConnessioneMCP([ROTTO, METEO], TIMEOUT) as connessione:
            nomi = {t.name for t in connessione.strumenti}
    assert nomi == {"meteo_attuale", "previsioni_meteo"}
    assert any("rotto" in r.getMessage() for r in caplog.records if r.levelno == logging.WARNING)


def test_server_che_muore():
    with ConnessioneMCP([MORENTE], TIMEOUT) as connessione:
        strumento(connessione, "muori").invoke({})
        inizio = time.monotonic()
        esito = strumento(connessione, "eco").invoke({"testo": "x"})
        durata = time.monotonic() - inizio
    assert esito.startswith("Errore di collegamento MCP con il server morente:")
    assert durata < TIMEOUT


def test_uscita_chiude_il_thread():
    with ConnessioneMCP([MORENTE], TIMEOUT) as connessione:
        thread = connessione._thread
        assert thread.is_alive()
    assert not thread.is_alive()


def test_unisci_strumenti_scarta_duplicati(caplog):
    @tool
    def doppio(x: str) -> str:
        """Primo."""
        return "primo"

    primo = doppio

    @tool
    def doppio(x: str) -> str:  # noqa: F811 (stesso nome di proposito)
        """Secondo."""
        return "secondo"

    with caplog.at_level(logging.WARNING, logger="agente.mcp_ponte"):
        uniti = unisci_strumenti([primo], [doppio])
    assert uniti == [primo]
    assert "strumento duplicato scartato: doppio" in caplog.text


def test_discovery_note_via_stdio(tmp_path):
    note = ServerMCP("note", ("-m", "server_mcp.note"), {"NOTE_DB": str(tmp_path / "n.sqlite3")})
    with ConnessioneMCP([note], TIMEOUT) as connessione:
        assert {t.name for t in connessione.strumenti} == {"aggiungi_nota", "elenca_note", "elimina_nota"}
        assert all(t.metadata["origine"] == "mcp:note" for t in connessione.strumenti)
        assert "salvata" in strumento(connessione, "aggiungi_nota").invoke({"testo": "prova"})
        assert "prova" in strumento(connessione, "elenca_note").invoke({})
