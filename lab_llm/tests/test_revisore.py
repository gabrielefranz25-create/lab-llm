"""Test del revisore: coerenza tra domanda e risposta, nota all'agente, limite, errori. Tutto simulato."""

import logging

import httpx
import openai
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agente.graph import (MESSAGGIO_LIMITE, MESSAGGIO_RIFIUTO, NOME_REVISORE, DecisioneRevisore,
                          DecisioneRouter, costruisci_grafo, limite_ricorsione, trascrivi)
from agente.strumenti import crea_ora_corrente

DOMANDA = "Che ore sono a Tokyo e quanto fa 15 per 12?"


class ModelloFinto:
    """Agente finto: restituisce in ordine le risposte preparate (l'ultima si ripete)."""

    def __init__(self, *risposte):
        self.risposte = [r if isinstance(r, AIMessage) else AIMessage(r) for r in risposte]
        self.chiamate: list[list] = []

    def invoke(self, messaggi):
        self.chiamate.append(list(messaggi))
        indice = min(len(self.chiamate), len(self.risposte)) - 1
        return self.risposte[indice].model_copy()


class RevisoreFinto:
    """Revisore finto: restituisce in ordine le decisioni preparate (l'ultima si ripete)."""

    def __init__(self, *decisioni):
        self.decisioni = [DecisioneRevisore(coerente=c, motivo=m) for c, m in decisioni]
        self.chiamate: list[list] = []

    def invoke(self, messaggi):
        self.chiamate.append(list(messaggi))
        return self.decisioni[min(len(self.chiamate), len(self.decisioni)) - 1]


class RevisoreGuasto:
    def invoke(self, messaggi):
        raise openai.APIConnectionError(request=httpx.Request("POST", "http://x"))


class RevisoreSenzaRisposta:
    def invoke(self, messaggi):
        return None


class RouterFuoriAmbito:
    def invoke(self, messaggi):
        return DecisioneRouter(categoria="fuori_ambito", motivo="ricetta")


def _grafo(modello, revisore, max_revisioni=2, max_passi=3, router=None):
    return costruisci_grafo(
        modello, [crea_ora_corrente()], max_passi=max_passi, max_messaggi_contesto=20,
        fuso_predefinito="Europe/Rome", router=router, ambito="ora",
        revisore=revisore, max_revisioni=max_revisioni,
    )


def _esegui(grafo, domanda=DOMANDA, cronologia=()):
    return grafo.invoke({"messages": [*cronologia, HumanMessage(domanda)], "passi_strumento": 0,
                         "revisioni": 0},
                        config={"recursion_limit": limite_ricorsione(3, 2)})


def _note(stato):
    return [m for m in stato["messages"] if isinstance(m, HumanMessage) and m.name == NOME_REVISORE]


def test_risposta_coerente_approvata_al_primo_passaggio(caplog):
    modello = ModelloFinto("A Tokyo sono le 18 (Asia/Tokyo); 15 per 12 fa 180.")
    revisore = RevisoreFinto((True, "entrambe le parti trattate"))
    with caplog.at_level(logging.INFO, logger="agente.graph"):
        stato = _esegui(_grafo(modello, revisore))
    assert len(modello.chiamate) == 1 and len(revisore.chiamate) == 1
    assert stato["revisioni"] == 0 and _note(stato) == []
    assert stato["messages"][-1].content.endswith("fa 180.")
    assert "revisore: coerente=si motivo=entrambe le parti trattate -> fine" in caplog.text


def test_risposta_parziale_torna_all_agente_con_il_motivo(caplog):
    modello = ModelloFinto("A Tokyo sono le 18.", "A Tokyo sono le 18; 15 per 12 fa 180.")
    revisore = RevisoreFinto((False, "manca il calcolo 15 per 12"), (True, "completa"))
    with caplog.at_level(logging.INFO, logger="agente.graph"):
        stato = _esegui(_grafo(modello, revisore))
    assert len(modello.chiamate) == 2
    nota, = _note(stato)
    assert "manca il calcolo 15 per 12" in nota.content
    # La seconda chiamata all'agente contiene la bozza scartata e la nota del revisore.
    seconda = modello.chiamate[1]
    assert seconda[-1].content == nota.content and seconda[-2].content == "A Tokyo sono le 18."
    assert stato["messages"][-1].content == "A Tokyo sono le 18; 15 per 12 fa 180."
    assert stato["revisioni"] == 1
    assert "revisore: coerente=no motivo=manca il calcolo 15 per 12 -> agente (revisione 1 di 2)" in caplog.text
    assert "revisore: coerente=si motivo=completa -> fine" in caplog.text
    # La domanda del turno resta quella dell'utente, non la nota.
    assert DOMANDA in revisore.chiamate[1][1].content


def test_revisore_che_rifiuta_sempre_si_ferma_al_limite(caplog):
    modello = ModelloFinto("prima", "seconda", "terza", "quarta")
    revisore = RevisoreFinto((False, "incompleta"))
    with caplog.at_level(logging.INFO, logger="agente.graph"):
        stato = _esegui(_grafo(modello, revisore, max_revisioni=2))
    assert len(modello.chiamate) == 3 and len(revisore.chiamate) == 3
    assert len(_note(stato)) == 2 and stato["revisioni"] == 2
    assert stato["messages"][-1].content == "terza"
    assert "revisore: limite di 2 revisioni raggiunto, restituita l'ultima risposta" in caplog.text


def test_max_revisioni_zero_solo_osservatore(caplog):
    modello = ModelloFinto("parziale")
    revisore = RevisoreFinto((False, "incompleta"))
    with caplog.at_level(logging.INFO, logger="agente.graph"):
        stato = _esegui(_grafo(modello, revisore, max_revisioni=0))
    assert len(modello.chiamate) == 1 and _note(stato) == []
    assert stato["messages"][-1].content == "parziale"
    assert "revisore: coerente=no motivo=incompleta" in caplog.text
    assert "limite di 0 revisioni raggiunto" in caplog.text


def test_revisore_in_errore_accetta_la_risposta(caplog):
    modello = ModelloFinto("risposta")
    with caplog.at_level(logging.WARNING, logger="agente.graph"):
        stato = _esegui(_grafo(modello, RevisoreGuasto()))
    assert stato["messages"][-1].content == "risposta" and len(modello.chiamate) == 1
    assert "revisore non riuscito" in caplog.text


def test_revisore_senza_output_valido_accetta_la_risposta(caplog):
    modello = ModelloFinto("risposta")
    with caplog.at_level(logging.WARNING, logger="agente.graph"):
        stato = _esegui(_grafo(modello, RevisoreSenzaRisposta()))
    assert stato["messages"][-1].content == "risposta"
    assert "revisore non riuscito" in caplog.text


def test_revisore_riceve_domanda_e_risposta_ma_non_gli_strumenti():
    revisore = RevisoreFinto((True, "ok"))
    _esegui(_grafo(ModelloFinto("Sono le 18."), revisore), "Che ore sono a Tokyo?")
    sistema, utente = revisore.chiamate[0]
    assert isinstance(sistema, SystemMessage) and "ora_corrente" not in sistema.content
    assert "Che ore sono a Tokyo?" in utente.content and "Sono le 18." in utente.content


def test_senza_revisore_la_risposta_e_approvata():
    modello = ModelloFinto("risposta")
    stato = _esegui(_grafo(modello, None))
    assert stato["messages"][-1].content == "risposta" and len(modello.chiamate) == 1


def test_rifiuto_del_router_non_revisionato():
    revisore = RevisoreFinto((False, "no"))
    stato = _esegui(_grafo(ModelloFinto("x"), revisore, router=RouterFuoriAmbito()))
    assert revisore.chiamate == []
    assert stato["messages"][-1].content == MESSAGGIO_RIFIUTO.format(ambito="ora")


def test_messaggio_del_limite_di_strumenti_non_revisionato():
    chiede_sempre = AIMessage("", tool_calls=[{"name": "ora_corrente", "args": {}, "id": "c1"}])
    revisore = RevisoreFinto((False, "no"))
    stato = _esegui(_grafo(ModelloFinto(chiede_sempre), revisore, max_passi=1))
    assert revisore.chiamate == []
    assert stato["messages"][-1].content == MESSAGGIO_LIMITE.format(n=1)


def test_turno_successivo_azzera_le_revisioni_e_usa_la_nuova_domanda():
    modello = ModelloFinto("parziale", "completa", "seconda risposta")
    revisore = RevisoreFinto((False, "incompleta"), (True, "ok"), (True, "ok"))
    grafo = _grafo(modello, revisore)
    stato = _esegui(grafo)
    stato = _esegui(grafo, "E a Roma?", stato["messages"])
    assert stato["revisioni"] == 0
    assert "E a Roma?" in revisore.chiamate[-1][1].content


def test_trascrivi_mostra_la_nota_del_revisore():
    nota = HumanMessage("Nota del revisore: manca il calcolo", name=NOME_REVISORE)
    assert trascrivi([HumanMessage("ciao"), nota]) == "Utente: ciao\nRevisore: manca il calcolo"


def test_limite_ricorsione_conta_le_revisioni():
    assert limite_ricorsione(3) == limite_ricorsione(3, 2)
    assert limite_ricorsione(3, 4) > limite_ricorsione(3, 2)
