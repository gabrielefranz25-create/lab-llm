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


def test_trasporto_scelto_dal_server():
    from fastmcp.client.transports import StdioTransport, StreamableHttpTransport

    from agente.mcp_ponte import crea_trasporto

    assert isinstance(crea_trasporto(METEO), StdioTransport)
    http = crea_trasporto(ServerMCP("meteo", ("-m", "server_mcp.meteo"), url="http://127.0.0.1:8101/mcp"))
    assert isinstance(http, StreamableHttpTransport)
    assert http.url == "http://127.0.0.1:8101/mcp"


def test_server_http_spento(caplog):
    spento = ServerMCP("calcolatrice", (), url="http://127.0.0.1:9/mcp")  # porta 9: nessun servizio
    with caplog.at_level(logging.WARNING), ConnessioneMCP([spento], timeout=10) as connessione:
        assert connessione.strumenti == []
    assert "server MCP calcolatrice non disponibile" in caplog.text


UTENTE = ServerMCP("utente", ("-m", "server_mcp.utente"))


def test_leggi_risorsa_dal_server(tmp_path):
    preferenze = tmp_path / "preferenze.json"
    preferenze.write_text('{"lingua": "inglese"}', encoding="utf-8")
    server = ServerMCP("utente", ("-m", "server_mcp.utente"), {"PREFERENZE_FILE": str(preferenze)})
    with ConnessioneMCP([server], TIMEOUT) as connessione:
        assert connessione.strumenti == []
        assert connessione.leggi_risorsa("utente", "utente://preferenze") == '{"lingua": "inglese"}'


def test_leggi_risorsa_sconosciuta_solleva_errore():
    with ConnessioneMCP([UTENTE], TIMEOUT) as connessione:
        try:
            connessione.leggi_risorsa("utente", "utente://inesistente")
        except Exception as errore:
            assert "utente://inesistente" in str(errore)
        else:
            raise AssertionError("attesa un'eccezione")


def test_leggi_risorsa_da_server_non_disponibile():
    with ConnessioneMCP([ROTTO], TIMEOUT) as connessione:
        try:
            connessione.leggi_risorsa("rotto", "utente://preferenze")
        except Exception as errore:
            assert "rotto" in str(errore)
        else:
            raise AssertionError("attesa un'eccezione")


def test_elenca_e_ottieni_prompt():
    with ConnessioneMCP([UTENTE], TIMEOUT) as connessione:
        elenco = {p.name: p for p in connessione.elenca_prompt("utente")}
        assert set(elenco) == {"spiega", "riassumi_conversazione"}
        messaggi = connessione.ottieni_prompt("utente", "spiega", {"argomento": "MCP", "livello": "base"})
    assert messaggi == [("user", messaggi[0][1])] and "«MCP» a livello base" in messaggi[0][1]


def test_ottieni_prompt_con_errore_del_server():
    with ConnessioneMCP([UTENTE], TIMEOUT) as connessione:
        try:
            connessione.ottieni_prompt("utente", "spiega", {"argomento": "MCP", "livello": "esperto"})
        except Exception as errore:
            assert "utente" in str(errore)
        else:
            raise AssertionError("attesa un'eccezione")
