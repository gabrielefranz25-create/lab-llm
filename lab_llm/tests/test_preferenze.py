"""Test delle preferenze dell'utente lette dall'host (resource utente://preferenze)."""

import json
import logging

from agente.config import carica_config
from agente.mcp_ponte import ServerMCP
from agente.preferenze import (URI_PREFERENZE, Preferenze, interpreta, istruzioni, leggi_preferenze,
                               predefinite)

PREDEFINITE = Preferenze(lingua="italiano", fuso_orario="Europe/Rome", stile="sintetico")


def test_predefinite_dalla_configurazione():
    config = carica_config({"LM_BASE_URL": "http://h:1/v1", "LM_MODEL": "m",
                            "FUSO_ORARIO_PREDEFINITO": "Asia/Tokyo"})
    assert predefinite(config) == Preferenze("italiano", "Asia/Tokyo", "sintetico")


def test_interpreta_preferenze_valide():
    testo = json.dumps({"lingua": "inglese", "fuso_orario": "America/New_York", "stile": "dettagliato"})
    assert interpreta(testo, PREDEFINITE) == Preferenze("inglese", "America/New_York", "dettagliato")


def test_campi_non_validi_tornano_al_predefinito(caplog):
    testo = json.dumps({"lingua": " ", "fuso_orario": "Roma", "stile": "poetico"})
    with caplog.at_level(logging.WARNING, logger="agente.preferenze"):
        assert interpreta(testo, PREDEFINITE) == PREDEFINITE
    assert "fuso_orario" in caplog.text and "stile" in caplog.text and "lingua" in caplog.text


def test_campi_mancanti_tornano_al_predefinito():
    assert interpreta('{"stile": "dettagliato"}', PREDEFINITE) == Preferenze("italiano", "Europe/Rome",
                                                                            "dettagliato")


def test_json_non_valido_solleva_errore():
    for testo in ("non json", "[1, 2]"):
        try:
            interpreta(testo, PREDEFINITE)
        except ValueError:
            continue
        raise AssertionError(testo)


def test_istruzioni_per_il_prompt():
    testo = istruzioni(Preferenze("inglese", "America/New_York", "dettagliato"))
    assert testo == ("Preferenze dell'utente: rispondi sempre in inglese, in modo dettagliato, "
                     "con spiegazioni ed esempi.")
    # Il fuso non sta in questa riga: arriva al prompt come fuso predefinito (vedi la docstring).
    assert "America/New_York" not in testo and "resource" not in testo
    assert "breve" in istruzioni(PREDEFINITE)


def test_leggi_preferenze_dal_server(tmp_path, caplog):
    file = tmp_path / "preferenze.json"
    file.write_text(json.dumps({"lingua": "inglese", "fuso_orario": "America/New_York",
                                "stile": "sintetico"}), encoding="utf-8")
    server = ServerMCP("utente", ("-m", "server_mcp.utente"), {"PREFERENZE_FILE": str(file)})
    with caplog.at_level(logging.INFO, logger="agente.preferenze"):
        lette = leggi_preferenze(server, 20, PREDEFINITE)
    assert lette == Preferenze("inglese", "America/New_York", "sintetico")
    assert (f"resource: {URI_PREFERENZE} letta dal server utente: lingua=inglese "
            "fuso_orario=America/New_York stile=sintetico") in caplog.text


def test_file_mancante_usa_le_predefinite(tmp_path, caplog):
    server = ServerMCP("utente", ("-m", "server_mcp.utente"),
                       {"PREFERENZE_FILE": str(tmp_path / "assente.json")})
    with caplog.at_level(logging.WARNING, logger="agente.preferenze"):
        assert leggi_preferenze(server, 20, PREDEFINITE) == PREDEFINITE
    assert f"preferenze: resource {URI_PREFERENZE} non disponibile, uso i valori predefiniti" in caplog.text


def test_server_non_disponibile_usa_le_predefinite(caplog):
    server = ServerMCP("utente", ("-m", "modulo_inesistente_xyz"))
    with caplog.at_level(logging.WARNING, logger="agente.preferenze"):
        assert leggi_preferenze(server, 20, PREDEFINITE) == PREDEFINITE
    assert "non disponibile" in caplog.text


def test_senza_server_usa_le_predefinite(caplog):
    with caplog.at_level(logging.WARNING, logger="agente.preferenze"):
        assert leggi_preferenze(None, 20, PREDEFINITE) == PREDEFINITE
    assert "non disponibile" in caplog.text
