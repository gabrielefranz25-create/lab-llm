"""Test delle funzioni pure del grafo: finestra di contesto e instradamento."""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import END

from agente.graph import finestra_contesto, instrada_dopo_llm, limite_ricorsione


def _ai_con_tool_call(id_chiamata: str) -> AIMessage:
    return AIMessage(content="", tool_calls=[
        {"name": "ora_corrente", "args": {}, "id": id_chiamata},
    ])


def test_finestra_cronologia_corta_invariata():
    messaggi = [HumanMessage("ciao"), AIMessage("salve")]
    assert finestra_contesto(messaggi, 20) == messaggi


def test_finestra_taglia_agli_ultimi_n():
    messaggi = [HumanMessage(f"d{i}") if i % 2 == 0 else AIMessage(f"r{i}") for i in range(30)]
    finestra = finestra_contesto(messaggi, 20)
    assert len(finestra) <= 20
    assert isinstance(finestra[0], HumanMessage)
    assert finestra[-1] is messaggi[-1]


def test_finestra_non_parte_da_toolmessage():
    messaggi = [
        HumanMessage("che ore sono?"), _ai_con_tool_call("c1"),
        ToolMessage("ore 10", tool_call_id="c1"), AIMessage("sono le 10"),
        HumanMessage("grazie"), AIMessage("prego"),
    ]
    finestra = finestra_contesto(messaggi, 4)
    assert isinstance(finestra[0], HumanMessage)
    id_chiamate = {tc["id"] for m in finestra if isinstance(m, AIMessage) for tc in m.tool_calls}
    assert all(m.tool_call_id in id_chiamate for m in finestra if isinstance(m, ToolMessage))


def test_finestra_ultimo_turno_piu_lungo_di_n():
    messaggi = [
        HumanMessage("che ore sono?"), _ai_con_tool_call("c1"), ToolMessage("x", tool_call_id="c1"),
        _ai_con_tool_call("c2"), ToolMessage("y", tool_call_id="c2"), AIMessage("fatto"),
    ]
    assert finestra_contesto(messaggi, 2) == messaggi


def test_instrada_fine_senza_tool_call():
    stato = {"messages": [HumanMessage("ciao"), AIMessage("salve")], "passi_strumento": 0}
    assert instrada_dopo_llm(stato, 3) == END


def test_instrada_strumenti_sotto_limite():
    stato = {"messages": [HumanMessage("ora?"), _ai_con_tool_call("c1")], "passi_strumento": 2}
    assert instrada_dopo_llm(stato, 3) == "strumenti"


def test_instrada_limite_raggiunto():
    stato = {"messages": [HumanMessage("ora?"), _ai_con_tool_call("c1")], "passi_strumento": 3}
    assert instrada_dopo_llm(stato, 3) == "limite"


def test_limite_ricorsione():
    assert limite_ricorsione(3) == 11
