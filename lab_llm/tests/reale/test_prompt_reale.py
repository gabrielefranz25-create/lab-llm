"""Prove dei prompt MCP con il modello vero (PROVA_REALE=1): /prompt passa dal grafo completo.

Sessione come quella di `python -m agente` (router, revisore, orologio, calcolatrice, server utente),
pilotata con un elenco di righe. Con -o log_cli=true --log-cli-level=INFO si vedono le righe
"prompt: richiamato …", "prompt: messaggio …", "router: …" e "revisore: …".
"""

import logging
import os
from dataclasses import replace

import pytest

from agente.client import avvia_sessione
from agente.comandi import ComandiPrompt
from agente.config import carica_config
from agente.graph import costruisci_grafo, limite_ricorsione
from agente.llm import crea_modello, crea_revisore, crea_riassuntore, crea_router
from agente.main import server_da_config, server_utente
from agente.mcp_ponte import ConnessioneMCP, unisci_strumenti
from agente.strumenti import crea_ora_corrente

pytestmark = [
    pytest.mark.reale,
    pytest.mark.skipif(os.environ.get("PROVA_REALE") != "1",
                       reason="prova reale: imposta PROVA_REALE=1"),
]


def _sessione(righe: list[str]) -> list[str]:
    """Esegue la chat con le righe date e restituisce le risposte (`Assistente> …`)."""
    config = replace(carica_config(), server_mcp=("calcolatrice",), variante_orologio="locale",
                     trasporto_mcp="stdio")
    uscita: list[str] = []
    coda = iter(righe + ["esci"])
    with ConnessioneMCP(server_da_config(config) + [server_utente(config)], config.mcp_timeout) as conn:
        strumenti = unisci_strumenti([crea_ora_corrente(config.fuso_orario_predefinito)], conn.strumenti)
        grafo = costruisci_grafo(
            crea_modello(config, strumenti), strumenti, max_passi=config.max_passi_strumento,
            max_messaggi_contesto=config.max_messaggi_contesto,
            fuso_predefinito=config.fuso_orario_predefinito, riassuntore=crea_riassuntore(config),
            messaggi_da_tenere=config.messaggi_da_tenere, router=crea_router(config),
            ambito=config.ambito, revisore=crea_revisore(config), max_revisioni=config.max_revisioni,
        )
        avvia_sessione(grafo, intestazione="prova", server=config.lm_base_url,
                       recursion_limit=limite_ricorsione(config.max_passi_strumento, config.max_revisioni),
                       leggi=lambda _p: next(coda), scrivi=uscita.append, comandi=ComandiPrompt(conn))
    return [r for r in uscita if r.startswith("Assistente>") or r.startswith("Prompt del server")]


def test_spiega_a_livello_base(caplog):
    with caplog.at_level(logging.INFO):
        risposte = _sessione(["/prompts", '/prompt spiega argomento="Model Context Protocol" livello=base'])
    elenco, risposta = risposte
    assert "spiega" in elenco and "riassumi_conversazione" in elenco
    assert ('prompt: richiamato spiega argomenti={"argomento": "Model Context Protocol", "livello": "base"}'
            in caplog.text)
    assert "prompt: messaggio 1 (user): Spiegami «Model Context Protocol» a livello base" in caplog.text
    assert "router: categoria=conversazione" in caplog.text
    assert "[errore]" not in risposta and "Mi dispiace" not in risposta, risposta
    assert "MCP" in risposta or "Model Context Protocol" in risposta or "protocollo" in risposta.lower(), risposta


def test_argomento_mancante_bloccato_senza_modello(caplog):
    with caplog.at_level(logging.INFO):
        (risposta,) = _sessione(["/prompt spiega livello=base"])
    assert "[errore] Argomento obbligatorio mancante: argomento." in risposta
    assert "agente: invio" not in caplog.text and "router:" not in caplog.text


def test_riassumi_conversazione_della_sessione(caplog):
    with caplog.at_level(logging.INFO):
        risposte = _sessione(["Che ore sono a Tokyo?", "Quanto fa 15 per 12?",
                              "/prompt riassumi_conversazione stile=dettagliato"])
    riassunto = risposte[-1].lower()
    assert "prompt: richiamato riassumi_conversazione" in caplog.text
    assert "tokyo" in riassunto and "180" in riassunto, riassunto
