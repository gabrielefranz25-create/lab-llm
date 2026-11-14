"""Test del server MCP `utente` (resource utente://preferenze), con il client fastmcp in memoria."""

import asyncio
import json

import pytest
from fastmcp import Client

from server_mcp.avvio import PORTE_HTTP
from server_mcp.utente import PREFERENZE_PREDEFINITE, URI_PREFERENZE, crea_server

PREFERENZE = {"lingua": "italiano", "fuso_orario": "America/New_York", "stile": "dettagliato"}


def _esegui(percorso, azione):
    async def corpo():
        async with Client(crea_server(percorso)) as client:
            return await azione(client)
    return asyncio.run(corpo())


@pytest.fixture
def file_preferenze(tmp_path):
    percorso = tmp_path / "preferenze.json"
    percorso.write_text(json.dumps(PREFERENZE), encoding="utf-8")
    return percorso


def test_resource_elencata_con_uri_e_mime(file_preferenze):
    (risorsa,) = _esegui(file_preferenze, lambda c: c.list_resources())
    assert str(risorsa.uri) == URI_PREFERENZE == "utente://preferenze"
    assert risorsa.name == "preferenze" and risorsa.mimeType == "application/json"


def test_nessun_tool_nel_catalogo(file_preferenze):
    assert _esegui(file_preferenze, lambda c: c.list_tools()) == []


def test_lettura_restituisce_il_file(file_preferenze):
    contenuti = _esegui(file_preferenze, lambda c: c.read_resource(URI_PREFERENZE))
    assert json.loads(contenuti[0].text) == PREFERENZE


def test_file_cambiato_letto_alla_richiesta_successiva(file_preferenze):
    async def due_letture(client):
        prima = await client.read_resource(URI_PREFERENZE)
        file_preferenze.write_text(json.dumps({**PREFERENZE, "lingua": "inglese"}), encoding="utf-8")
        dopo = await client.read_resource(URI_PREFERENZE)
        return prima[0].text, dopo[0].text

    prima, dopo = _esegui(file_preferenze, due_letture)
    assert json.loads(prima)["lingua"] == "italiano" and json.loads(dopo)["lingua"] == "inglese"


def test_file_mancante_da_errore(tmp_path):
    with pytest.raises(Exception):
        _esegui(tmp_path / "assente.json", lambda c: c.read_resource(URI_PREFERENZE))


def test_file_predefinito_del_progetto_valido():
    dati = json.loads(PREFERENZE_PREDEFINITE.read_text(encoding="utf-8"))
    assert set(dati) == {"lingua", "fuso_orario", "stile"}


def test_porta_http_dedicata():
    assert PORTE_HTTP["utente"] == 8108
