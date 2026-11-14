"""Prove della resource utente://preferenze con il modello vero di LM Studio (PROVA_REALE=1).

Il server `utente` vero legge un file temporaneo; l'host lo interpreta e lo mette in cima al prompt.
Cambiando solo il file cambia il comportamento: fuso predefinito, lingua e stile.
"""

import json
import logging
import os
from dataclasses import replace

import pytest
from langchain_core.messages import HumanMessage

from agente.config import carica_config
from agente.graph import costruisci_grafo, limite_ricorsione
from agente.llm import crea_modello
from agente.main import server_utente
from agente.preferenze import istruzioni, leggi_preferenze, predefinite
from agente.strumenti import crea_ora_corrente
from tests.reale.test_mcp_reale import chiamate

pytestmark = [
    pytest.mark.reale,
    pytest.mark.skipif(os.environ.get("PROVA_REALE") != "1",
                       reason="prova reale: imposta PROVA_REALE=1"),
]


def _sessione(tmp_path, caplog, preferenze: dict, domanda: str):
    """Come main(): legge la resource, applica il fuso, costruisce il grafo e fa una domanda."""
    file = tmp_path / "preferenze.json"
    file.write_text(json.dumps(preferenze), encoding="utf-8")
    config = replace(carica_config(), preferenze_file=str(file), trasporto_mcp="stdio")
    with caplog.at_level(logging.INFO):
        lette = leggi_preferenze(server_utente(config), config.mcp_timeout, predefinite(config))
        config = replace(config, fuso_orario_predefinito=lette.fuso_orario)
        strumenti = [crea_ora_corrente(config.fuso_orario_predefinito)]
        grafo = costruisci_grafo(
            crea_modello(config, strumenti), strumenti,
            max_passi=config.max_passi_strumento, max_messaggi_contesto=config.max_messaggi_contesto,
            fuso_predefinito=config.fuso_orario_predefinito, preferenze=istruzioni(lette),
        )
        stato = grafo.invoke({"messages": [HumanMessage(domanda)], "passi_strumento": 0},
                             config={"recursion_limit": limite_ricorsione(config.max_passi_strumento)})
    return stato["messages"]


def test_fuso_dalle_preferenze_senza_chiederlo(tmp_path, caplog):
    messaggi = _sessione(tmp_path, caplog, {"lingua": "italiano", "fuso_orario": "America/New_York",
                                            "stile": "sintetico"}, "Che ore sono?")
    assert "resource: utente://preferenze letta dal server utente" in caplog.text
    risultati = [m.content for m in messaggi if m.type == "tool"]
    assert chiamate(messaggi, "ora_corrente") and any("America/New_York" in r for r in risultati), messaggi
    assert "New York" in messaggi[-1].content or "New_York" in messaggi[-1].content, messaggi[-1].content


def test_lingua_e_stile_dalle_preferenze(tmp_path, caplog):
    messaggi = _sessione(tmp_path, caplog, {"lingua": "inglese", "fuso_orario": "Europe/Rome",
                                            "stile": "dettagliato"}, "Che ore sono a Tokyo?")
    risposta = messaggi[-1].content.lower()
    assert any(parola in f" {risposta} " for parola in (" the ", " is ", " time ")), risposta
    assert "tokyo" in risposta
