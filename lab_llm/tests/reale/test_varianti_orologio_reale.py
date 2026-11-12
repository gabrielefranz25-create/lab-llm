"""Prove reali delle tre varianti dell'orologio con LM Studio: si attivano solo con PROVA_REALE=1.

Stessa domanda, stesso modello, stesso contratto `ora_corrente`: cambia solo il percorso
(funzione locale, servizio FastAPI avviato qui come sottoprocesso, server FastMCP via stdio).
"""

import os
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import replace

import httpx
import pytest
from langchain_core.messages import HumanMessage

from agente.config import carica_config
from agente.graph import costruisci_grafo, limite_ricorsione
from agente.llm import crea_modello
from agente.main import server_da_config, strumenti_orologio
from agente.mcp_ponte import CARTELLA_PROGETTO, ConnessioneMCP, unisci_strumenti
from agente.strumenti import crea_ora_corrente_http
from tests.reale.test_mcp_reale import chiamate, risultato_di

pytestmark = [
    pytest.mark.reale,
    pytest.mark.skipif(os.environ.get("PROVA_REALE") != "1",
                       reason="prova reale: imposta PROVA_REALE=1"),
]

DOMANDA = "Che ore sono a Tokyo?"


def _porta_libera() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextmanager
def servizio_fastapi():
    """Avvia `python -m servizio_orologio.api` su una porta libera e ne restituisce l'URL."""
    porta = _porta_libera()
    processo = subprocess.Popen(
        [sys.executable, "-m", "servizio_orologio.api"], cwd=str(CARTELLA_PROGETTO),
        env={**os.environ, "OROLOGIO_API_PORTA": str(porta)},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{porta}"
    try:
        for _ in range(50):
            try:
                if httpx.get(f"{url}/salute", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.2)
        else:
            pytest.fail("il servizio FastAPI dell'orologio non è partito")
        yield url
    finally:
        processo.terminate()
        processo.wait(10)


def _chiedi(config):
    """Porta DOMANDA nel grafo con l'orologio della variante in `config` (e nessun altro server)."""
    config = replace(config, server_mcp=())
    with ConnessioneMCP(server_da_config(config), config.mcp_timeout) as connessione:
        strumenti = unisci_strumenti(strumenti_orologio(config), connessione.strumenti)
        assert [s.name for s in strumenti] == ["ora_corrente"]
        grafo = costruisci_grafo(
            crea_modello(config, strumenti), strumenti,
            max_passi=config.max_passi_strumento,
            max_messaggi_contesto=config.max_messaggi_contesto,
            fuso_predefinito=config.fuso_orario_predefinito,
        )
        risultato = grafo.invoke(
            {"messages": [HumanMessage(DOMANDA)], "passi_strumento": 0},
            config={"recursion_limit": limite_ricorsione(config.max_passi_strumento)},
        )
        return risultato["messages"], strumenti[0]


def _verifica_turno(messaggi):
    (chiamata,) = chiamate(messaggi, "ora_corrente")
    assert chiamata["args"].get("fuso_orario") == "Asia/Tokyo"
    risultato = risultato_di(messaggi, chiamata)  # ToolMessage con lo stesso tool_call_id
    assert "Fuso orario: Asia/Tokyo (JST, UTC+09:00)" in risultato
    ora = risultato.split("Ora: ")[1][:5]  # HH:MM
    assert ora in messaggi[-1].content


def test_variante_locale():
    messaggi, strumento = _chiedi(replace(carica_config(), variante_orologio="locale"))
    assert not strumento.metadata
    _verifica_turno(messaggi)


def test_variante_fastapi():
    with servizio_fastapi() as url:
        config = replace(carica_config(), variante_orologio="fastapi", orologio_api_url=url)
        messaggi, strumento = _chiedi(config)
    assert strumento.metadata == {"origine": "http:orologio"}
    _verifica_turno(messaggi)


def test_variante_mcp():
    messaggi, strumento = _chiedi(replace(carica_config(), variante_orologio="mcp"))
    assert strumento.metadata == {"origine": "mcp:orologio"}
    _verifica_turno(messaggi)


def test_fuso_errato_con_chiamata_diretta():
    """Il modello correggerebbe il fuso: per provocare l'errore si chiama lo strumento direttamente."""
    with servizio_fastapi() as url:
        http = crea_ora_corrente_http(url, timeout=5.0).invoke({"fuso_orario": "Mars/Olympus"})
    assert http.startswith("Errore dallo strumento ora_corrente: fuso orario 'Mars/Olympus'")
    config = replace(carica_config(), variante_orologio="mcp", server_mcp=())
    with ConnessioneMCP(server_da_config(config), config.mcp_timeout) as connessione:
        mcp = connessione.strumenti[0].invoke({"fuso_orario": "Mars/Olympus"})
    assert mcp.startswith("Errore dallo strumento ora_corrente: fuso orario 'Mars/Olympus'")


def test_servizio_spento_e_errore_di_collegamento():
    url = f"http://127.0.0.1:{_porta_libera()}"
    risultato = crea_ora_corrente_http(url, timeout=2.0).invoke({"fuso_orario": "Asia/Tokyo"})
    assert risultato.startswith("Errore di collegamento HTTP con il servizio orologio: ")
