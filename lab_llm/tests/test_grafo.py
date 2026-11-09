"""Test del grafo completo con un modello finto: nodi, ciclo con lo strumento, limite, errori."""

import logging
from datetime import datetime, timezone

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool

from agente.graph import MESSAGGIO_LIMITE, PROMPT_SISTEMA, costruisci_grafo
from agente.strumenti import crea_ora_corrente

INVERNO = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)


class ModelloFinto:
    """Restituisce in ordine le risposte preparate e ricorda i messaggi ricevuti."""

    def __init__(self, risposte: list[AIMessage]):
        self.risposte = list(risposte)
        self.chiamate: list[list] = []

    def invoke(self, messaggi):
        self.chiamate.append(list(messaggi))
        return self.risposte.pop(0)


class ModelloSempreStrumento:
    """Chiede sempre lo strumento, con un id diverso a ogni chiamata."""

    def __init__(self):
        self.chiamate: list[list] = []

    def invoke(self, messaggi):
        self.chiamate.append(list(messaggi))
        return _ai_tool([("ora_corrente", {}, f"c{len(self.chiamate)}")])


def _ai_tool(chiamate: list[tuple[str, dict, str]]) -> AIMessage:
    return AIMessage(content="", tool_calls=[
        {"name": nome, "args": args, "id": id_chiamata} for nome, args, id_chiamata in chiamate
    ])


def _grafo(modello, max_passi=3, max_messaggi_contesto=20):
    return costruisci_grafo(
        modello, [crea_ora_corrente(orologio=lambda: INVERNO)],
        max_passi=max_passi, max_messaggi_contesto=max_messaggi_contesto,
        fuso_predefinito="Europe/Rome",
    )


def _esegui(grafo, messaggi=None):
    messaggi = messaggi or [HumanMessage("Che ore sono?")]
    return grafo.invoke({"messages": messaggi, "passi_strumento": 0})


def _tool_messages(stato) -> list[ToolMessage]:
    return [m for m in stato["messages"] if isinstance(m, ToolMessage)]


def test_risposta_diretta():
    stato = _esegui(_grafo(ModelloFinto([AIMessage("Ciao")])), [HumanMessage("Ciao")])
    assert len(stato["messages"]) == 2
    assert stato["passi_strumento"] == 0


def test_ciclo_con_strumento():
    modello = ModelloFinto([
        _ai_tool([("ora_corrente", {"fuso_orario": "Asia/Tokyo"}, "c1")]),
        AIMessage("Sono le 20"),
    ])
    stato = _esegui(_grafo(modello))
    risultati = _tool_messages(stato)
    assert len(risultati) == 1
    assert risultati[0].tool_call_id == "c1"
    assert "Asia/Tokyo (JST" in risultati[0].content
    assert stato["messages"][-1].content == "Sono le 20"
    assert stato["passi_strumento"] == 1


def test_piu_tool_call_nello_stesso_messaggio():
    modello = ModelloFinto([
        _ai_tool([
            ("ora_corrente", {"fuso_orario": "Europe/Rome"}, "c1"),
            ("ora_corrente", {"fuso_orario": "Asia/Tokyo"}, "c2"),
        ]),
        AIMessage("Ecco le due ore"),
    ])
    stato = _esegui(_grafo(modello))
    assert {m.tool_call_id for m in _tool_messages(stato)} == {"c1", "c2"}


def test_limite_passaggi():
    modello = ModelloSempreStrumento()
    stato = _esegui(_grafo(modello, max_passi=2))
    assert len(modello.chiamate) == 3
    ultimo = stato["messages"][-1]
    assert isinstance(ultimo, AIMessage)
    assert ultimo.content == MESSAGGIO_LIMITE.format(n=2)
    id_richiesti = {tc["id"] for m in stato["messages"] if isinstance(m, AIMessage)
                    for tc in m.tool_calls}
    assert id_richiesti == {m.tool_call_id for m in _tool_messages(stato)}


def test_strumento_sconosciuto():
    modello = ModelloFinto([_ai_tool([("meteo", {}, "c1")]), AIMessage("Non posso")])
    stato = _esegui(_grafo(modello))
    assert _tool_messages(stato)[0].content.startswith("Errore")
    assert stato["messages"][-1].content == "Non posso"


def test_argomenti_non_validi_diventano_toolmessage_errore():
    modello = ModelloFinto([
        _ai_tool([("ora_corrente", {"fuso_orario": None}, "c1")]),
        AIMessage("Riprovo"),
    ])
    stato = _esegui(_grafo(modello))
    assert _tool_messages(stato)[0].content.startswith("Errore")


def _ai_tool_malformata(id_chiamata: str) -> AIMessage:
    # Argomenti non JSON: langchain-openai mette la chiamata in invalid_tool_calls, non in tool_calls.
    return AIMessage(content="", invalid_tool_calls=[
        {"name": "ora_corrente", "args": "{fuso", "id": id_chiamata, "error": "JSON non valido"}
    ])


def test_tool_call_malformata_riceve_toolmessage_errore():
    modello = ModelloFinto([_ai_tool_malformata("c1"), AIMessage("Riprovo")])
    stato = _esegui(_grafo(modello))
    risposte = _tool_messages(stato)
    assert [m.tool_call_id for m in risposte] == ["c1"]
    assert risposte[0].content.startswith("Errore")
    assert stato["messages"][-1].content == "Riprovo"


def test_tool_call_malformata_al_limite_riceve_risposta():
    modello = ModelloFinto([_ai_tool_malformata("c1")])
    stato = _grafo(modello, max_passi=1).invoke(
        {"messages": [HumanMessage("Che ore sono?")], "passi_strumento": 1})
    assert [m.tool_call_id for m in _tool_messages(stato)] == ["c1"]
    assert stato["messages"][-1].content == MESSAGGIO_LIMITE.format(n=1)


def test_log_chiamata_strumento(caplog):
    modello = ModelloFinto([
        _ai_tool([("ora_corrente", {"fuso_orario": "Asia/Tokyo"}, "c1")]),
        AIMessage("Fatto"),
    ])
    with caplog.at_level(logging.INFO):
        _esegui(_grafo(modello))
    assert any(all(parte in r.getMessage() for parte in
                   ("strumento=ora_corrente", "origine=locale", "call_id=c1", "esito=ok", "Asia/Tokyo"))
               for r in caplog.records)


def _meteo_finto(risultato: str) -> StructuredTool:
    return StructuredTool.from_function(
        func=lambda citta="": risultato, name="meteo_attuale", description="finto",
        metadata={"origine": "mcp:meteo"},
    )


def _grafo_con(modello, *strumenti):
    return costruisci_grafo(modello, [crea_ora_corrente(orologio=lambda: INVERNO), *strumenti],
                            max_passi=3, max_messaggi_contesto=20, fuso_predefinito="Europe/Rome")


def test_log_origine_mcp_ed_esito_errore(caplog):
    errore = "Errore dallo strumento meteo_attuale: città non trovata: X"
    modello = ModelloFinto([_ai_tool([("meteo_attuale", {"citta": "X"}, "m1")]), AIMessage("Boh")])
    with caplog.at_level(logging.INFO):
        stato = _esegui(_grafo_con(modello, _meteo_finto(errore)))
    assert any(all(parte in r.getMessage() for parte in
                   ("origine=mcp:meteo", "call_id=m1", "esito=errore", "strumento=meteo_attuale"))
               for r in caplog.records)
    assert _tool_messages(stato)[0].tool_call_id == "m1"
    assert _tool_messages(stato)[0].content == errore


def test_tool_mcp_insieme_all_orologio():
    modello = ModelloFinto([
        _ai_tool([("ora_corrente", {}, "o1"), ("meteo_attuale", {"citta": "Udine"}, "m1")]),
        AIMessage("Ecco"),
    ])
    stato = _esegui(_grafo_con(modello, _meteo_finto("Udine: 10 gradi")))
    per_id = {m.tool_call_id: m.content for m in _tool_messages(stato)}
    assert set(per_id) == {"o1", "m1"}
    assert per_id["m1"] == "Udine: 10 gradi"
    assert "Europe/Rome" in per_id["o1"]


def test_prompt_cita_meteo_ed_errori():
    assert "meteo_attuale" in PROMPT_SISTEMA and "previsioni_meteo" in PROMPT_SISTEMA
    assert "errore" in PROMPT_SISTEMA.lower()
    assert "elimina solo per ID" in PROMPT_SISTEMA


def test_prompt_e_finestra_al_modello():
    cronologia = [HumanMessage("d1"), AIMessage("r1"), HumanMessage("d2"),
                  AIMessage("r2"), HumanMessage("d3"), AIMessage("r3"), HumanMessage("d4")]
    cronologia = cronologia[1:]  # 6 messaggi, l'ultimo è la domanda nuova
    modello = ModelloFinto([AIMessage("ok")])
    _esegui(_grafo(modello, max_messaggi_contesto=2), cronologia)
    inviati = modello.chiamate[0]
    assert isinstance(inviati[0], SystemMessage)
    assert "Europe/Rome" in inviati[0].content
    assert len(inviati) <= 3


def test_grafo_ha_i_nodi_attesi():
    nodi = _grafo(ModelloFinto([])).get_graph().nodes
    assert {"llm", "strumenti", "limite"} <= set(nodi)
