"""Test del front-end: server dei file statici con config.js e contratto con l'OpenAPI del back-end."""

import re
import threading
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.api import crea_app
from backend.archivio import ArchivioMemoria
from frontend.__main__ import ErroreConfigurazione, carica_config, crea_server

STATICI = Path(__file__).resolve().parents[1] / "frontend" / "static"


@pytest.fixture
def server():
    srv = crea_server(carica_config({"FRONTEND_BACKEND_URL": "http://backend.prova:8080/", "FRONTEND_PORTA": "0"}))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def test_config_predefinita_e_porta_non_valida():
    config = carica_config({})
    assert (config.backend_url, config.ascolto, config.porta) == ("http://127.0.0.1:8080", "127.0.0.1", 8090)
    with pytest.raises(ErroreConfigurazione, match="FRONTEND_PORTA"):
        carica_config({"FRONTEND_PORTA": "otto"})


def test_config_js_con_l_indirizzo_del_back_end(server):
    risposta = httpx.get(f"{server}/config.js")
    assert risposta.status_code == 200 and "javascript" in risposta.headers["content-type"]
    assert risposta.text == 'window.CONFIGURAZIONE = {"backend": "http://backend.prova:8080"};\n'


def test_file_statici(server):
    pagina = httpx.get(f"{server}/")
    assert pagina.status_code == 200 and '<script src="config.js"></script>' in pagina.text
    assert httpx.get(f"{server}/app.js").status_code == 200
    assert httpx.get(f"{server}/../backend/config.py").status_code == 404


def test_ogni_chiamata_di_app_js_esiste_nell_openapi_del_back_end():
    """Il contratto: metodo e percorso di ogni chiamata del front-end sono nel documento OpenAPI."""
    codice = (STATICI / "app.js").read_text(encoding="utf-8")
    chiamate = {(metodo.lower(), re.sub(r"\$\{[^}]+\}", "{chat_id}", percorso))
                for metodo, percorso in re.findall(r'chiama\("(\w+)", [`"]([^`"]+)[`"]', codice)}
    percorsi = TestClient(crea_app(ArchivioMemoria(), agente=None)).get("/openapi.json").json()["paths"]
    assert chiamate == {("get", "/stato"), ("get", "/chat"), ("post", "/chat"), ("get", "/chat/{chat_id}"),
                        ("delete", "/chat/{chat_id}"), ("post", "/chat/{chat_id}/messaggi")}
    for metodo, percorso in chiamate:
        assert metodo in percorsi.get(percorso, {}), (metodo, percorso)


def test_i_dati_non_finiscono_in_inner_html():
    codice = (STATICI / "app.js").read_text(encoding="utf-8")
    assert "innerHTML" not in codice and "textContent" in codice
