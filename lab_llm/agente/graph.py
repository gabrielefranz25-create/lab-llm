"""Grafo LangGraph dell'assistente: stato, finestra di contesto, instradamento, nodi.

I print didattici "[passo]" sono commentati: togliere il commento per seguire il flusso.
"""

import logging
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph

logger = logging.getLogger(__name__)

PROMPT_SISTEMA = (
    "Sei l'assistente del laboratorio. Rispondi in italiano, in modo breve e chiaro.\n"
    "Per qualsiasi domanda su data, ora o giorno attuali usa SEMPRE lo strumento `ora_corrente`: "
    "non inventare l'ora. Se l'utente non indica un luogo usa il fuso predefinito {fuso} "
    "(ora italiana). Per altri luoghi passa il nome IANA del fuso (es. \"Asia/Tokyo\").\n"
    "Nella risposta indica sempre a quale fuso orario si riferisce l'ora."
)

MESSAGGIO_LIMITE = (
    "Ho raggiunto il limite di {n} richieste allo strumento per questa domanda. "
    "Prova a riformularla in modo più semplice."
)


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


def costruisci_grafo(modello: Runnable, strumenti: list[BaseTool], *, max_passi: int,
                     max_messaggi_contesto: int, fuso_predefinito: str) -> CompiledStateGraph:
    """Grafo llm -> strumenti -> llm, con il nodo limite. Il modello ha già gli strumenti collegati."""
    prompt = SystemMessage(PROMPT_SISTEMA.format(fuso=fuso_predefinito))
    per_nome = {s.name: s for s in strumenti}

    def nodo_llm(stato: AgentState) -> dict:
        # print("[passo] nodo llm: chiedo al modello la prossima mossa")
        da_inviare = [prompt] + finestra_contesto(stato["messages"], max_messaggi_contesto)
        # print(f"[passo] nodo llm: invio {len(da_inviare)} messaggi al modello (prompt di sistema compreso)")
        return {"messages": [modello.invoke(da_inviare)]}

    def nodo_strumenti(stato: AgentState) -> dict:
        richieste = stato["messages"][-1].tool_calls
        # print(f"[passo] nodo strumenti: eseguo {len(richieste)} tool_call")
        risultati = []
        for tc in richieste:
            strumento = per_nome.get(tc["name"])
            if strumento is None:
                logger.warning("strumento sconosciuto richiesto dal modello: %s", tc["name"])
                testo = f"Errore: lo strumento '{tc['name']}' non esiste."
            else:
                try:
                    testo = str(strumento.invoke(tc["args"]))
                except Exception as errore:  # argomenti sbagliati del modello: diventano testo
                    testo = f"Errore: argomenti non validi per {tc['name']}: {errore}"
            logger.info("strumento %s %s -> %s", tc["name"], tc["args"], testo.replace("\n", " | "))
            risultati.append(ToolMessage(content=testo, tool_call_id=tc["id"]))
        return {"messages": risultati, "passi_strumento": stato["passi_strumento"] + 1}

    def nodo_limite(stato: AgentState) -> dict:
        richieste = stato["messages"][-1].tool_calls
        # print(f"[passo] nodo limite: {len(richieste)} tool_call non eseguite, chiudo il turno")
        logger.warning("limite di %d passaggi raggiunto: %d tool_call non eseguite",
                       max_passi, len(richieste))
        # Ogni tool_call deve avere la sua risposta, altrimenti la cronologia non è valida per l'API.
        sospese = [ToolMessage(content=f"Non eseguito: limite di {max_passi} passaggi raggiunto.",
                               tool_call_id=tc["id"]) for tc in richieste]
        return {"messages": sospese + [AIMessage(MESSAGGIO_LIMITE.format(n=max_passi))]}

    grafo = StateGraph(AgentState)
    grafo.add_node("llm", nodo_llm)
    grafo.add_node("strumenti", nodo_strumenti)
    grafo.add_node("limite", nodo_limite)
    grafo.add_edge(START, "llm")
    grafo.add_conditional_edges(
        "llm", lambda stato: instrada_dopo_llm(stato, max_passi),
        {"strumenti": "strumenti", "limite": "limite", END: END},
    )
    grafo.add_edge("strumenti", "llm")
    grafo.add_edge("limite", END)
    return grafo.compile()
