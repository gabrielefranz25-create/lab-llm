"""Test della lettura e validazione delle variabili d'ambiente."""

import pytest

from agente.config import (AMBITO_PER_SERVER, AMBITO_PREDEFINITO, SERVER_MCP_NOTI, ErroreConfigurazione,
                           ambito_predefinito, carica_config)

MINIMO = {"LM_BASE_URL": "http://h:1/v1", "LM_MODEL": "m"}


def test_valori_minimi_e_default():
    config = carica_config(MINIMO)
    assert config.lm_base_url == "http://h:1/v1"
    assert config.lm_model == "m"
    assert config.fuso_orario_predefinito == "Europe/Rome"
    assert config.max_passi_strumento == 3
    assert config.max_messaggi_contesto == 20
    assert config.messaggi_da_tenere == 6
    assert config.lm_timeout == 60.0
    assert config.log_level == "INFO"


@pytest.mark.parametrize("nome", ["LM_BASE_URL", "LM_MODEL"])
def test_variabile_obbligatoria_mancante(nome):
    ambiente = {k: v for k, v in MINIMO.items() if k != nome}
    with pytest.raises(ErroreConfigurazione, match=nome):
        carica_config(ambiente)


def test_variabile_obbligatoria_vuota_conta_come_assente():
    with pytest.raises(ErroreConfigurazione, match="LM_MODEL"):
        carica_config({**MINIMO, "LM_MODEL": ""})


def test_valori_personalizzati():
    config = carica_config({
        **MINIMO,
        "FUSO_ORARIO_PREDEFINITO": "Asia/Tokyo",
        "MAX_PASSI_STRUMENTO": "5",
        "MAX_MESSAGGI_CONTESTO": "8",
        "MESSAGGI_DA_TENERE": "4",
        "LM_TIMEOUT": "12.5",
        "LOG_LEVEL": "debug",
    })
    assert config.fuso_orario_predefinito == "Asia/Tokyo"
    assert config.max_passi_strumento == 5
    assert config.max_messaggi_contesto == 8
    assert config.messaggi_da_tenere == 4
    assert config.lm_timeout == 12.5
    assert config.log_level == "DEBUG"


@pytest.mark.parametrize("nome, valore", [
    ("MAX_PASSI_STRUMENTO", "0"),
    ("MAX_PASSI_STRUMENTO", "tre"),
    ("MAX_MESSAGGI_CONTESTO", "1"),
    ("MESSAGGI_DA_TENERE", "1"),
    ("MESSAGGI_DA_TENERE", "20"),  # deve restare sotto MAX_MESSAGGI_CONTESTO (default 20)
    ("LM_TIMEOUT", "-5"),
    ("FUSO_ORARIO_PREDEFINITO", "Roma"),
    ("LOG_LEVEL", "CHIACCHIERA"),
])
def test_valori_non_validi(nome, valore):
    with pytest.raises(ErroreConfigurazione, match=nome):
        carica_config({**MINIMO, nome: valore})


def test_valori_predefiniti_mcp():
    config = carica_config(MINIMO)
    assert config.mcp_timeout == 30.0
    assert config.meteo_timeout == 10.0
    assert config.note_db == "dati/note.sqlite3"
    assert config.server_mcp == SERVER_MCP_NOTI


def test_server_mcp_noti():
    assert SERVER_MCP_NOTI == ("meteo", "note", "unita", "calcolatrice", "scadenze", "catalogo")
    assert set(AMBITO_PER_SERVER) == set(SERVER_MCP_NOTI)


def test_server_mcp_nuovi_nomi():
    config = carica_config({**MINIMO, "SERVER_MCP": "calcolatrice, catalogo,unita,scadenze"})
    assert config.server_mcp == ("calcolatrice", "catalogo", "unita", "scadenze")


def test_server_mcp_vuoto_non_avvia_nulla():
    assert carica_config({**MINIMO, "SERVER_MCP": ""}).server_mcp == ()


def test_server_mcp_elenco():
    config = carica_config({**MINIMO, "SERVER_MCP": " meteo , meteo , note"})
    assert config.server_mcp == ("meteo", "note")


def test_server_mcp_sconosciuto():
    with pytest.raises(ErroreConfigurazione, match="posta"):
        carica_config({**MINIMO, "SERVER_MCP": "meteo,posta"})


def test_timeout_mcp_troppo_basso():
    with pytest.raises(ErroreConfigurazione, match="MCP_TIMEOUT"):
        carica_config({**MINIMO, "MCP_TIMEOUT": "15", "METEO_TIMEOUT": "10"})
    config = carica_config({**MINIMO, "MCP_TIMEOUT": "21", "METEO_TIMEOUT": "10"})
    assert config.mcp_timeout == 21.0


def test_ambito_predefinito():
    config = carica_config(MINIMO)
    assert config.ambito == AMBITO_PREDEFINITO
    assert "meteo" in config.ambito


def test_ambito_personalizzato():
    config = carica_config({**MINIMO, "AMBITO_AGENTE": "  solo il meteo  "})
    assert config.ambito == "solo il meteo"


def test_ambito_vuoto_usa_il_predefinito():
    assert carica_config({**MINIMO, "AMBITO_AGENTE": " "}).ambito == AMBITO_PREDEFINITO


def test_ambito_composto_dai_server_attivi():
    config = carica_config({**MINIMO, "SERVER_MCP": "calcolatrice"})
    assert config.ambito == ambito_predefinito(("calcolatrice",))
    assert AMBITO_PER_SERVER["calcolatrice"] in config.ambito
    assert AMBITO_PER_SERVER["meteo"] not in config.ambito
    assert "data e ora" in config.ambito and "saluti" in config.ambito


def test_ambito_senza_server():
    ambito = carica_config({**MINIMO, "SERVER_MCP": ""}).ambito
    assert "data e ora" in ambito
    assert not any(frase in ambito for frase in AMBITO_PER_SERVER.values())


def test_ambito_predefinito_contiene_tutti_i_server():
    assert all(frase in AMBITO_PREDEFINITO for frase in AMBITO_PER_SERVER.values())


def test_ambito_personalizzato_vince_sui_server():
    config = carica_config({**MINIMO, "SERVER_MCP": "calcolatrice", "AMBITO_AGENTE": "solo conti"})
    assert config.ambito == "solo conti"


def test_variante_orologio_predefinita_locale():
    config = carica_config(MINIMO)
    assert config.variante_orologio == "locale"
    assert config.orologio_api_url == "http://localhost:8001"
    assert config.orologio_api_timeout == 5.0


@pytest.mark.parametrize("valore, atteso", [("fastapi", "fastapi"), ("MCP", "mcp"), (" locale ", "locale")])
def test_variante_orologio_valida(valore, atteso):
    assert carica_config({**MINIMO, "VARIANTE_OROLOGIO": valore}).variante_orologio == atteso


def test_variante_orologio_sconosciuta():
    with pytest.raises(ErroreConfigurazione, match="VARIANTE_OROLOGIO deve essere uno tra locale, fastapi, mcp"):
        carica_config({**MINIMO, "VARIANTE_OROLOGIO": "grpc"})


def test_url_e_timeout_del_servizio_orologio():
    config = carica_config({**MINIMO, "OROLOGIO_API_URL": "http://orologio-api:8001",
                            "OROLOGIO_API_TIMEOUT": "2.5"})
    assert config.orologio_api_url == "http://orologio-api:8001"
    assert config.orologio_api_timeout == 2.5


def test_timeout_del_servizio_orologio_non_valido():
    with pytest.raises(ErroreConfigurazione, match="OROLOGIO_API_TIMEOUT"):
        carica_config({**MINIMO, "OROLOGIO_API_TIMEOUT": "0"})


def test_trasporto_mcp_predefinito_stdio():
    config = carica_config(MINIMO)
    assert config.trasporto_mcp == "stdio"
    assert config.mcp_http_host == "127.0.0.1"


def test_trasporto_mcp_http():
    config = carica_config({**MINIMO, "TRASPORTO_MCP": "HTTP", "MCP_HTTP_HOST": "server-mcp"})
    assert (config.trasporto_mcp, config.mcp_http_host) == ("http", "server-mcp")


def test_trasporto_mcp_sconosciuto():
    with pytest.raises(ErroreConfigurazione, match="TRASPORTO_MCP deve essere uno tra stdio, http"):
        carica_config({**MINIMO, "TRASPORTO_MCP": "sse"})


def test_max_revisioni_predefinito():
    assert carica_config(MINIMO).max_revisioni == 2


@pytest.mark.parametrize("valore, atteso", [("0", 0), ("4", 4)])
def test_max_revisioni_valido(valore, atteso):
    assert carica_config({**MINIMO, "MAX_REVISIONI": valore}).max_revisioni == atteso


@pytest.mark.parametrize("valore", ["-1", "due"])
def test_max_revisioni_non_valido(valore):
    with pytest.raises(ErroreConfigurazione, match="MAX_REVISIONI"):
        carica_config({**MINIMO, "MAX_REVISIONI": valore})


def test_file_delle_preferenze():
    assert carica_config(MINIMO).preferenze_file == "server_mcp/risorse/preferenze.json"
    assert carica_config({**MINIMO, "PREFERENZE_FILE": "dati/pref.json"}).preferenze_file == "dati/pref.json"


def test_ambito_predefinito_comprende_i_prompt_mcp():
    # Step 5: /prompt spiega e /prompt riassumi_conversazione passano dal router come le domande.
    assert "spiegazioni di concetti" in AMBITO_PREDEFINITO and "riassunti della conversazione" in AMBITO_PREDEFINITO


def test_indirizzi_del_servizio_dell_agente():
    config = carica_config(MINIMO)
    assert (config.agente_ascolto, config.agente_porta, config.agente_url) == (
        "127.0.0.1", 8000, "http://127.0.0.1:8000")
    altra = carica_config({**MINIMO, "AGENTE_ASCOLTO": "0.0.0.0", "AGENTE_PORTA": "9000",
                           "AGENTE_URL": "http://agente:9000"})
    assert (altra.agente_ascolto, altra.agente_porta, altra.agente_url) == ("0.0.0.0", 9000, "http://agente:9000")
