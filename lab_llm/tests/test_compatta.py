"""Test del nodo compatta: riassunto come campo dello stato oltre la soglia, con modelli finti."""

import logging

import httpx
import openai
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from agente.graph import INTESTAZIONE_RIASSUNTO, costruisci_grafo
from agente.strumenti import crea_ora_corrente


class ModelloFinto:
    """Restituisce sempre la stessa risposta e ricorda i messaggi ricevuti."""

    def __init__(self, risposta: str):
        self.risposta = risposta
        self.chiamate: list[list] = []

    def invoke(self, messaggi):
        self.chiamate.append(list(messaggi))
        return AIMessage(self.risposta)


class RiassuntoreGuasto:
    def invoke(self, messaggi):
        raise openai.APIConnectionError(request=httpx.Request("POST", "http://x"))


def _grafo(modello, riassuntore, max_messaggi_contesto=6, messaggi_da_tenere=3):
    return costruisci_grafo(
        modello, [crea_ora_corrente()], max_passi=3,
        max_messaggi_contesto=max_messaggi_contesto, fuso_predefinito="Europe/Rome",
        riassuntore=riassuntore, messaggi_da_tenere=messaggi_da_tenere,
    )


def _conversazione(turni: int) -> list:
    """`turni` scambi domanda/risposta già conclusi, il primo con un nome da ricordare."""
    messaggi = []
    for i in range(turni):
        messaggi += [HumanMessage("Mi chiamo Gabriele" if i == 0 else f"domanda {i}"),
                     AIMessage(f"risposta {i}")]
    return messaggi


def _esegui(grafo, cronologia, domanda="e adesso?", riassunto=""):
    return grafo.invoke({"messages": cronologia + [HumanMessage(domanda)], "passi_strumento": 0,
                         "riassunto": riassunto})


def _testi(messaggi) -> list[str]:
    return [m.content for m in messaggi]


def test_sotto_soglia_non_chiama_il_modello(caplog):
    riassuntore = ModelloFinto("riassunto")
    with caplog.at_level(logging.DEBUG, logger="agente.graph"):
        stato = _esegui(_grafo(ModelloFinto("ok"), riassuntore), _conversazione(2))  # 5 messaggi
    assert riassuntore.chiamate == []
    assert len(stato["messages"]) == 6 and stato["riassunto"] == ""
    assert "riassunto: 5 messaggi, sotto la soglia di 6, nessuna chiamata al modello" in caplog.text


def test_sopra_soglia_riassunto_nel_campo_e_recenti_intatti(caplog):
    riassuntore = ModelloFinto("L'utente si chiama Gabriele.")
    with caplog.at_level(logging.INFO, logger="agente.graph"):
        stato = _esegui(_grafo(ModelloFinto("ok"), riassuntore), _conversazione(4))  # 9 messaggi
    assert stato["riassunto"] == "L'utente si chiama Gabriele."
    # Il riassunto non sta in messages: restano solo gli ultimi 3 (più la risposta nuova).
    assert not any(isinstance(m, SystemMessage) for m in stato["messages"])
    assert _testi(stato["messages"]) == ["domanda 3", "risposta 3", "e adesso?", "ok"]
    assert "riassunto: messaggi prima=9 dopo=3 (riassunti 6, tenuti 3)" in caplog.text


def test_taglio_sempre_su_un_human_message():
    cronologia = [
        HumanMessage("Mi chiamo Gabriele"), AIMessage("piacere"),
        HumanMessage("che ore sono?"),
        AIMessage("", tool_calls=[{"name": "ora_corrente", "args": {}, "id": "c1"}]),
        ToolMessage("Ora: 10:00", tool_call_id="c1"),
        AIMessage("Sono le 10"),
    ]
    stato = _esegui(_grafo(ModelloFinto("ok"), ModelloFinto("riassunto"), messaggi_da_tenere=4), cronologia)
    # Gli ultimi 4 (prima della risposta) iniziavano con un AIMessage con tool_call: il taglio va
    # alla domanda nuova, così nessuna tool_call resta senza la sua richiesta.
    assert _testi(stato["messages"]) == ["e adesso?", "ok"]


def test_il_riassuntore_riceve_la_conversazione_vecchia_come_testo():
    riassuntore = ModelloFinto("riassunto")
    _esegui(_grafo(ModelloFinto("ok"), riassuntore), _conversazione(4))
    (chiamata,) = riassuntore.chiamate
    assert isinstance(chiamata[0], SystemMessage)
    trascrizione = chiamata[-1].content
    assert "Utente: Mi chiamo Gabriele" in trascrizione
    assert "Assistente: risposta 2" in trascrizione
    assert "domanda 3" not in trascrizione and "e adesso?" not in trascrizione
    assert "Riassunto precedente" not in trascrizione


def test_riassunto_precedente_incluso_e_sostituito():
    riassuntore = ModelloFinto("nuovo riassunto")
    stato = _esegui(_grafo(ModelloFinto("ok"), riassuntore), _conversazione(4),
                    riassunto="L'utente si chiama Gabriele.")
    assert "Riassunto precedente: L'utente si chiama Gabriele." in riassuntore.chiamate[0][-1].content
    assert stato["riassunto"] == "nuovo riassunto"  # aggiornato, non accumulato


def test_il_riassunto_arriva_al_modello_nel_prompt_di_sistema():
    modello = ModelloFinto("ok")
    _esegui(_grafo(modello, ModelloFinto("L'utente si chiama Gabriele.")), _conversazione(4))
    inviati = modello.chiamate[0]
    # Un solo messaggio di sistema in testa: alcuni modelli non ne accettano altri.
    assert [type(m) for m in inviati] == [SystemMessage, HumanMessage, AIMessage, HumanMessage]
    assert INTESTAZIONE_RIASSUNTO + "L'utente si chiama Gabriele." in inviati[0].content
    assert "ora_corrente" in inviati[0].content


def test_riassunto_di_un_turno_precedente_usato_anche_sotto_la_soglia():
    modello = ModelloFinto("ok")
    _esegui(_grafo(modello, ModelloFinto("x")), _conversazione(1), riassunto="L'utente vive a Udine.")
    assert "L'utente vive a Udine." in modello.chiamate[0][0].content


def test_errore_del_riassuntore_lascia_cronologia_e_riassunto_invariati(caplog):
    with caplog.at_level(logging.WARNING, logger="agente.graph"):
        stato = _esegui(_grafo(ModelloFinto("ok"), RiassuntoreGuasto()), _conversazione(4),
                        riassunto="vecchio")
    assert len(stato["messages"]) == 10 and stato["riassunto"] == "vecchio"
    assert "riassunto non riuscito" in caplog.text


def test_senza_riassuntore_non_compatta():
    stato = _esegui(_grafo(ModelloFinto("ok"), None), _conversazione(4))
    assert len(stato["messages"]) == 10
