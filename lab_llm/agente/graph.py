"""Grafo LangGraph dell'assistente: stato, finestra di contesto, instradamento, nodi.

I print didattici "[passo]" sono commentati: togliere il commento per seguire il flusso.
"""

import logging
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AnyMessage, HumanMessage
from langgraph.graph import END
from langgraph.graph.message import add_messages

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    # Cronologia (Human/AI/Tool): add_messages accoda i messaggi nuovi restituiti dai nodi.
    messages: Annotated[list[AnyMessage], add_messages]
    # Giri di strumento nel turno corrente: senza reducer, il valore restituito sostituisce il vecchio.
    passi_strumento: int


def finestra_contesto(messaggi: list[AnyMessage], n: int) -> list[AnyMessage]:
    """Ultimi `n` messaggi da inviare al modello, sempre a partire da un HumanMessage.

    Così la finestra non inizia mai con un ToolMessage orfano o con un AIMessage la cui
    tool_call ha la risposta fuori dalla finestra. Se l'ultimo turno da solo supera `n`,
    si tiene comunque tutto dall'ultimo HumanMessage in poi.
    """
    finestra = messaggi[-n:]
    while finestra and not isinstance(finestra[0], HumanMessage):
        finestra = finestra[1:]
    if not finestra:
        indici_umani = [i for i, m in enumerate(messaggi) if isinstance(m, HumanMessage)]
        finestra = messaggi[indici_umani[-1]:] if indici_umani else messaggi
    if len(finestra) < len(messaggi):
        logger.debug("contesto: inviati %d di %d messaggi", len(finestra), len(messaggi))
    return finestra


def instrada_dopo_llm(stato: AgentState, max_passi: int) -> Literal["strumenti", "limite", "__end__"]:
    """Dopo il nodo llm: fine se non ci sono tool_call, altrimenti strumenti o limite."""
    ultimo = stato["messages"][-1]
    if not getattr(ultimo, "tool_calls", None):
        # print("[passo] instradamento: nessuna tool_call -> fine del turno")
        return END
    if stato["passi_strumento"] < max_passi:
        # print(f"[passo] instradamento: tool_call, passo {stato['passi_strumento'] + 1} di {max_passi} -> strumenti")
        return "strumenti"
    # print(f"[passo] instradamento: tool_call ma limite di {max_passi} passaggi raggiunto -> limite")
    return "limite"


def limite_ricorsione(max_passi: int) -> int:
    """Rete di sicurezza per invoke(): con il nodo limite non dovrebbe mai scattare."""
    return 2 * max_passi + 5
