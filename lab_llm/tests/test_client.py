"""Test dell'interfaccia da terminale: cronologia, uscita, errori, avvio di main()."""

import logging

import httpx
import openai
import pytest
from langchain_core.messages import AIMessage, HumanMessage

import agente.config
import agente.main
from agente.client import avvia_sessione, rispondi
from agente.graph import costruisci_grafo
from agente.config import carica_config
from agente.main import configura_logging, main, server_da_config, server_utente, strumenti_orologio
from agente.strumenti import crea_ora_corrente

SERVER = "http://h:1/v1"


class ModelloFinto:
    def __init__(self, risposte: list[AIMessage]):
        self.risposte = list(risposte)
        self.chiamate: list[list] = []

    def invoke(self, messaggi):
        self.chiamate.append(list(messaggi))
        return self.risposte.pop(0)


class GrafoFinto:
    """Al primo invoke solleva `errore`, poi risponde con un AIMessage fisso."""

    def __init__(self, errore: Exception):
        self.errore = errore
        self.ricevuti: list[list] = []

    def invoke(self, stato, config=None):
        self.ricevuti.append(list(stato["messages"]))
        if self.errore:
            errore, self.errore = self.errore, None
            raise errore
        return {"messages": stato["messages"] + [AIMessage("ok")], "passi_strumento": 0}


def _grafo(modello):
    return costruisci_grafo(modello, [crea_ora_corrente()], max_passi=3,
                            max_messaggi_contesto=20, fuso_predefinito="Europe/Rome")


def _sessione(grafo, ingressi: list):
    """Esegue la sessione con input da lista (EOF a fine lista) e restituisce l'output."""
    righe: list[str] = []
    coda = iter(ingressi)

    def leggi(_prompt):
        valore = next(coda, EOFError())
        if isinstance(valore, BaseException):
            raise valore
        return valore

    avvia_sessione(grafo, intestazione="Modello: m", server=SERVER, recursion_limit=11,
                   leggi=leggi, scrivi=righe.append)
    return "\n".join(righe)


def test_cronologia_mantenuta_tra_turni():
    modello = ModelloFinto([AIMessage("Ciao!"), AIMessage("Mi hai salutato")])
    _sessione(_grafo(modello), ["Ciao", "Di cosa abbiamo parlato?", "esci"])
    contenuti = [m.content for m in modello.chiamate[1]]
    assert "Ciao" in contenuti and "Ciao!" in contenuti
    assert contenuti[-1] == "Di cosa abbiamo parlato?"


@pytest.mark.parametrize("comando", ["esci", "ESCI", "quit"])
def test_uscita_con_comando(comando):
    uscita = _sessione(_grafo(ModelloFinto([])), [comando])
    assert "Sessione terminata. La cronologia non è stata salvata." in uscita


def test_uscita_con_bom_iniziale():
    # PowerShell 5.1 antepone il BOM UTF-8 all'input passato via pipe ("esci" | python -m agente).
    modello = ModelloFinto([])
    uscita = _sessione(_grafo(modello), ["﻿esci"])
    assert modello.chiamate == []
    assert "Sessione terminata" in uscita


def test_uscita_con_eof():
    uscita = _sessione(_grafo(ModelloFinto([])), [EOFError()])
    assert "Sessione terminata" in uscita


def test_uscita_con_ctrl_c():
    uscita = _sessione(_grafo(ModelloFinto([])), [KeyboardInterrupt()])
    assert "Sessione terminata" in uscita


def test_input_vuoto_ignorato():
    modello = ModelloFinto([])
    _sessione(_grafo(modello), ["", "   ", "esci"])
    assert modello.chiamate == []


def test_errore_collegamento_non_altera_cronologia():
    grafo = GrafoFinto(openai.APIConnectionError(request=httpx.Request("GET", SERVER)))
    uscita = _sessione(grafo, ["prima", "seconda", "esci"])
    assert f"[errore] Non riesco a contattare LM Studio su {SERVER}" in uscita
    assert [m.content for m in grafo.ricevuti[1]] == ["seconda"]
    assert isinstance(grafo.ricevuti[1][0], HumanMessage)


def test_risposta_vuota():
    uscita = _sessione(_grafo(ModelloFinto([AIMessage("")])), ["Ciao", "esci"])
    assert "Assistente> (il modello non ha restituito testo)" in uscita


def test_main_config_mancante(monkeypatch, capsys):
    monkeypatch.setattr(agente.config, "load_dotenv", lambda **_: None)
    monkeypatch.setenv("LM_BASE_URL", SERVER)
    monkeypatch.delenv("LM_MODEL", raising=False)
    assert main() == 1
    assert "LM_MODEL" in capsys.readouterr().err


def test_ctrl_c_durante_la_risposta_chiude_la_sessione():
    grafo = GrafoFinto(KeyboardInterrupt())
    uscita = _sessione(grafo, ["Che ore sono?", "seconda"])
    assert "Sessione terminata. La cronologia non è stata salvata." in uscita
    assert len(grafo.ricevuti) == 1


def test_main_ctrl_c_durante_la_verifica(monkeypatch, capsys):
    def interrotta(_config):
        raise KeyboardInterrupt
    monkeypatch.setattr(agente.config, "load_dotenv", lambda **_: None)
    monkeypatch.setenv("LM_BASE_URL", SERVER)
    monkeypatch.setenv("LM_MODEL", "m")
    monkeypatch.setattr(agente.main, "verifica_modello", interrotta)
    assert main() == 130
    assert "Interrotto" in capsys.readouterr().err


@pytest.mark.parametrize("nome", ["httpx", "httpx2", "httpcore", "openai"])
def test_configura_logging_silenzia_librerie_http(nome):
    configura_logging("INFO")
    assert logging.getLogger(nome).level == logging.WARNING


def _config(**extra):
    base = {"LM_BASE_URL": SERVER, "LM_MODEL": "m", "METEO_TIMEOUT": "4", "MCP_TIMEOUT": "30"}
    return carica_config({**base, **extra})


def test_server_da_config():
    (meteo,) = server_da_config(_config(SERVER_MCP="meteo"))
    assert meteo.nome == "meteo"
    assert meteo.argomenti == ("-m", "server_mcp.meteo")
    assert meteo.env["METEO_TIMEOUT"] == "4.0"
    assert server_da_config(_config(SERVER_MCP="")) == []


def test_server_da_config_note_in_ordine():
    meteo, note = server_da_config(_config(SERVER_MCP="meteo,note", NOTE_DB="x/n.sqlite3"))
    assert (meteo.nome, note.nome) == ("meteo", "note")
    assert note.argomenti == ("-m", "server_mcp.note")
    assert note.env["NOTE_DB"] == "x/n.sqlite3"
    assert note.env["LOG_LEVEL"] == "INFO" and note.env["FASTMCP_LOG_LEVEL"] == "WARNING"


def test_server_da_config_tutti_i_server():
    servers = server_da_config(_config())
    assert [s.nome for s in servers] == ["meteo", "note", "unita", "calcolatrice", "scadenze", "catalogo"]
    for server in servers:
        assert server.argomenti == ("-m", f"server_mcp.{server.nome}")
        assert server.env["LOG_LEVEL"] == "INFO" and server.env["FASTMCP_LOG_LEVEL"] == "WARNING"


def test_server_da_config_scadenze_riceve_il_fuso():
    (scadenze,) = server_da_config(_config(SERVER_MCP="scadenze", FUSO_ORARIO_PREDEFINITO="Asia/Tokyo"))
    assert scadenze.env["FUSO_ORARIO"] == "Asia/Tokyo"


def test_server_da_config_log_server_e_framework():
    (meteo,) = server_da_config(_config(SERVER_MCP="meteo", LOG_LEVEL="DEBUG"))
    assert meteo.env["LOG_LEVEL"] == "DEBUG"  # i log del nostro server seguono l'agente
    assert meteo.env["FASTMCP_LOG_LEVEL"] == "WARNING"  # niente "Starting MCP server" nella chat


def test_server_da_config_orologio_mcp_solo_con_la_variante_mcp():
    assert "orologio" not in [s.nome for s in server_da_config(_config())]
    orologio, meteo = server_da_config(_config(SERVER_MCP="meteo", VARIANTE_OROLOGIO="mcp",
                                               FUSO_ORARIO_PREDEFINITO="Asia/Tokyo"))
    assert (orologio.nome, meteo.nome) == ("orologio", "meteo")
    assert orologio.argomenti == ("-m", "server_mcp.orologio")
    assert orologio.env["FUSO_ORARIO"] == "Asia/Tokyo"
    assert orologio.env["FASTMCP_LOG_LEVEL"] == "WARNING"


def test_server_da_config_stdio_forza_il_trasporto_dei_sottoprocessi():
    # un MCP_TRASPORTO=http rimasto nel .env non deve trasformare i sottoprocessi in server HTTP
    assert all(s.env["MCP_TRASPORTO"] == "stdio" for s in server_da_config(_config(VARIANTE_OROLOGIO="mcp")))


def test_server_da_config_stdio_senza_url():
    assert all(s.url is None for s in server_da_config(_config(VARIANTE_OROLOGIO="mcp")))


def test_server_da_config_http_con_url_per_ogni_server():
    servers = server_da_config(_config(TRASPORTO_MCP="http", MCP_HTTP_HOST="server-mcp",
                                       VARIANTE_OROLOGIO="mcp"))
    assert {s.nome: s.url for s in servers} == {
        "orologio": "http://server-mcp:8107/mcp", "meteo": "http://server-mcp:8101/mcp",
        "note": "http://server-mcp:8102/mcp", "unita": "http://server-mcp:8103/mcp",
        "calcolatrice": "http://server-mcp:8104/mcp", "scadenze": "http://server-mcp:8105/mcp",
        "catalogo": "http://server-mcp:8106/mcp",
    }


def test_strumenti_orologio_locale(caplog):
    with caplog.at_level(logging.INFO, logger="agente.main"):
        (strumento,) = strumenti_orologio(_config())
    assert strumento.name == "ora_corrente" and not strumento.metadata
    assert "orologio: variante=locale percorso=funzione locale" in caplog.text


def test_strumenti_orologio_fastapi(caplog):
    with caplog.at_level(logging.INFO, logger="agente.main"):
        (strumento,) = strumenti_orologio(_config(VARIANTE_OROLOGIO="fastapi",
                                                  OROLOGIO_API_URL="http://o:9"))
    assert strumento.name == "ora_corrente"
    assert strumento.metadata == {"origine": "http:orologio"}
    assert "orologio: variante=fastapi percorso=GET http://o:9/ora" in caplog.text


def test_strumenti_orologio_mcp_arriva_dal_catalogo(caplog):
    with caplog.at_level(logging.INFO, logger="agente.main"):
        assert strumenti_orologio(_config(VARIANTE_OROLOGIO="mcp")) == []
    assert "orologio: variante=mcp percorso=server MCP orologio (stdio)" in caplog.text


def _avvia_main_con_mcp(monkeypatch, connessione, preferenze=None):
    monkeypatch.setattr(agente.config, "load_dotenv", lambda **_: None)
    monkeypatch.setenv("LM_BASE_URL", SERVER)
    monkeypatch.setenv("LM_MODEL", "m")
    monkeypatch.setattr(agente.main, "verifica_modello", lambda _config: None)
    monkeypatch.setattr(agente.main, "crea_modello", lambda _config, _strumenti: object())
    monkeypatch.setattr(agente.main, "crea_riassuntore", lambda _config: object())
    monkeypatch.setattr(agente.main, "ConnessioneMCP", connessione)
    monkeypatch.setattr(agente.main, "leggi_preferenze", lambda server, timeout, base: preferenze or base)
    return main()


def test_main_ctrl_c_durante_l_avvio_dei_server(monkeypatch, capsys):
    class Interrotta:
        def __init__(self, *_):
            pass

        def __enter__(self):
            raise KeyboardInterrupt

        def __exit__(self, *_):
            return False

    assert _avvia_main_con_mcp(monkeypatch, Interrotta) == 130
    assert "Interrotto" in capsys.readouterr().err


def test_main_intestazione_con_strumenti_mcp(monkeypatch):
    from langchain_core.tools import StructuredTool
    finto = StructuredTool.from_function(func=lambda: "x", name="meteo_attuale", description="d")
    visto = {}

    class Finta:
        def __init__(self, servers, timeout):
            visto["servers"] = servers
            self.strumenti = [finto]

        def elenca_prompt(self, server):
            return []

        def __enter__(self):
            return self

        def __exit__(self, *_):
            visto["chiusa"] = True
            return False

    monkeypatch.setattr(agente.main, "avvia_sessione",
                        lambda grafo, intestazione, server, recursion_limit, comandi: visto.update(
                            testata=intestazione, limite=recursion_limit, comandi=comandi))
    assert _avvia_main_con_mcp(monkeypatch, Finta) == 0
    assert "Strumenti: ora_corrente, meteo_attuale" in visto["testata"]
    assert visto["limite"] == 16  # 2*3 passi + 2*2 revisioni + 6
    assert visto["servers"][0].nome == "meteo" and visto["chiusa"]
    # Il server utente (prompt MCP) entra nella connessione, per ultimo; i suoi prompt vanno alla chat.
    assert visto["servers"][-1].nome == "utente" and visto["comandi"] is not None


def test_rispondi_azzera_passi_e_revisioni():
    grafo = GrafoFinto(None)
    stati = []
    grafo.invoke = lambda stato, config=None: stati.append(stato) or {"messages": stato["messages"] + [AIMessage("ok")]}
    rispondi(grafo, [], "ciao", recursion_limit=16)
    assert stati[0]["passi_strumento"] == 0 and stati[0]["revisioni"] == 0


def test_rispondi_passa_e_restituisce_il_riassunto():
    stati = []

    class Grafo:
        def invoke(self, stato, config=None):
            stati.append(stato)
            return {"messages": stato["messages"] + [AIMessage("ok")], "riassunto": "nuovo"}

    messaggi, riassunto, risposta = rispondi(Grafo(), [], "ciao", recursion_limit=16, riassunto="vecchio")
    assert stati[0]["riassunto"] == "vecchio"
    assert riassunto == "nuovo" and risposta == "ok" and len(messaggi) == 2


def test_sessione_conserva_il_riassunto_tra_i_turni():
    stati = []

    class Grafo:
        def invoke(self, stato, config=None):
            stati.append(stato)
            return {"messages": stato["messages"][-1:] + [AIMessage("ok")],
                    "riassunto": f"riassunto {len(stati)}"}

    _sessione(Grafo(), ["uno", "due", "esci"])
    assert stati[0]["riassunto"] == "" and stati[1]["riassunto"] == "riassunto 1"
    assert [m.content for m in stati[1]["messages"]] == ["uno", "ok", "due"]


def test_main_applica_le_preferenze_lette_dalla_resource(monkeypatch):
    from agente.preferenze import Preferenze
    visto = {}

    class Finta:
        def __init__(self, servers, timeout):
            visto["servers"] = servers
            self.strumenti = []

        def elenca_prompt(self, server):
            return []

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def grafo_finto(modello, strumenti, **argomenti):
        visto.update(argomenti)
        return object()

    monkeypatch.setattr(agente.main, "costruisci_grafo", grafo_finto)
    monkeypatch.setattr(agente.main, "avvia_sessione",
                        lambda grafo, intestazione, server, recursion_limit, comandi: visto.update(
                            testata=intestazione))
    preferenze = Preferenze("inglese", "America/New_York", "dettagliato")
    assert _avvia_main_con_mcp(monkeypatch, Finta, preferenze) == 0
    assert visto["fuso_predefinito"] == "America/New_York"
    assert visto["preferenze"].startswith("Rispondi sempre in inglese")
    scadenze = next(s for s in visto["servers"] if s.nome == "scadenze")
    assert scadenze.env["FUSO_ORARIO"] == "America/New_York"
    assert "Fuso predefinito: America/New_York" in visto["testata"]
    assert "Preferenze: lingua=inglese, stile=dettagliato" in visto["testata"]


def test_server_utente_stdio_e_http():
    config = _config(PREFERENZE_FILE="dati/pref.json")
    server = server_utente(config)
    assert server.argomenti == ("-m", "server_mcp.utente") and server.url is None
    assert server.env["PREFERENZE_FILE"] == "dati/pref.json" and server.env["MCP_TRASPORTO"] == "stdio"
    http = server_utente(_config(TRASPORTO_MCP="http", MCP_HTTP_HOST="server-mcp"))
    assert http.url == "http://server-mcp:8108/mcp"


class ComandiFinti:
    """Come ComandiPrompt: /prompt valido → un HumanMessage; con «errore» → ErroreComando."""

    disponibili = True

    def elenco(self):
        return "Prompt del server utente:\n- spiega: Spiega un argomento."

    def richiama(self, riga):
        from agente.comandi import ErroreComando
        if "errore" in riga:
            raise ErroreComando("Argomento obbligatorio mancante: argomento.")
        return [HumanMessage("Spiegami «MCP» a livello base")]


def _sessione_con_comandi(grafo, ingressi, comandi=None):
    righe: list[str] = []
    coda = iter(ingressi + ["esci"])
    avvia_sessione(grafo, intestazione="Modello: m", server=SERVER, recursion_limit=16,
                   leggi=lambda _p: next(coda), scrivi=righe.append, comandi=comandi)
    return "\n".join(righe)


def test_comando_prompts_elenca_senza_chiamare_il_grafo():
    grafo = GrafoFinto(None)
    uscita = _sessione_con_comandi(grafo, ["/prompts"], ComandiFinti())
    assert "spiega: Spiega un argomento." in uscita and grafo.ricevuti == []


def test_comando_prompt_manda_i_messaggi_del_server_al_grafo():
    grafo = GrafoFinto(None)
    uscita = _sessione_con_comandi(grafo, ["/prompt spiega argomento=MCP"], ComandiFinti())
    assert [m.content for m in grafo.ricevuti[0]] == ["Spiegami «MCP» a livello base"]
    assert "Assistente> ok" in uscita


def test_comando_prompt_non_valido_non_chiama_il_grafo():
    grafo = GrafoFinto(None)
    uscita = _sessione_con_comandi(grafo, ["/prompt spiega errore"], ComandiFinti())
    assert grafo.ricevuti == [] and "[errore] Argomento obbligatorio mancante" in uscita


def test_comando_sconosciuto_o_senza_prompt_non_va_al_modello():
    grafo = GrafoFinto(None)
    uscita = _sessione_con_comandi(grafo, ["/aiuto", "/prompts"])
    assert grafo.ricevuti == []
    assert "Comando sconosciuto: /aiuto" in uscita and "Prompt non disponibili" in uscita
