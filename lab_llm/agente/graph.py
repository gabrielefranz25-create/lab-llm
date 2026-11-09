"""Grafo LangGraph dell'assistente: stato, compattazione, finestra di contesto, instradamento, nodi.

I print didattici "[passo]" sono commentati: togliere il commento per seguire il flusso.
"""

import logging
from typing import Annotated, Literal, TypedDict

import openai
from langchain_core.messages import (AIMessage, AnyMessage, HumanMessage, RemoveMessage,
                                     SystemMessage, ToolMessage)
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import REMOVE_ALL_MESSAGES, add_messages
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

PROMPT_RIASSUNTO = (
    "Riassumi in italiano, in poche frasi, la conversazione che ti viene data. Conserva i fatti "
    "utili per continuarla: nome, preferenze e richieste dell'utente, luoghi e fusi orari citati, "
    "risposte già date. Scrivi solo il riassunto, senza commenti."
)

# Nome del SystemMessage che, in testa alla cronologia, contiene il riassunto dei messaggi vecchi.
NOME_RIASSUNTO = "riassunto"
INTESTAZIONE_RIASSUNTO = "Riassunto della conversazione precedente:\n"


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


def _e_riassunto(messaggio: AnyMessage) -> bool:
    return isinstance(messaggio, SystemMessage) and messaggio.name == NOME_RIASSUNTO


def dividi_cronologia(messaggi: list[AnyMessage], da_tenere: int) -> tuple[list[AnyMessage], list[AnyMessage]]:
    """(vecchi, recenti): recenti sono gli ultimi `da_tenere` messaggi, a partire da un HumanMessage.

    Stessa regola di finestra_contesto: il taglio non separa mai una tool_call dalla sua risposta.
    """
    inizio = max(len(messaggi) - da_tenere, 0)
    while inizio < len(messaggi) and not isinstance(messaggi[inizio], HumanMessage):
        inizio += 1
    return messaggi[:inizio], messaggi[inizio:]


def trascrivi(messaggi: list[AnyMessage]) -> str:
    """Conversazione come testo semplice, da dare al riassuntore (che non conosce gli strumenti)."""
    righe = []
    for m in messaggi:
        if _e_riassunto(m):
            righe.append(f"Riassunto precedente: {m.content.removeprefix(INTESTAZIONE_RIASSUNTO)}")
        elif isinstance(m, HumanMessage):
            righe.append(f"Utente: {m.content}")
        elif isinstance(m, ToolMessage):
            righe.append(f"Strumento: {m.content}".replace("\n", " | "))
        elif isinstance(m, AIMessage) and m.content:  # le sole tool_call non hanno testo
            righe.append(f"Assistente: {m.content}")
    return "\n".join(righe)


def instrada_dopo_llm(stato: AgentState, max_passi: int) -> Literal["strumenti", "limite", "__end__"]:
    """Dopo il nodo llm: fine se non ci sono tool_call, altrimenti strumenti o limite."""
    if not _richieste(stato["messages"][-1]):
        # print("[passo] instradamento: nessuna tool_call -> fine del turno")
        return END
    if stato["passi_strumento"] < max_passi:
        # print(f"[passo] instradamento: tool_call, passo {stato['passi_strumento'] + 1} di {max_passi} -> strumenti")
        return "strumenti"
    # print(f"[passo] instradamento: tool_call ma limite di {max_passi} passaggi raggiunto -> limite")
    return "limite"


def _richieste(messaggio: AnyMessage) -> list[dict]:
    """Tool_call da chiudere con un ToolMessage, comprese quelle con argomenti non JSON.

    Le chiamate malformate stanno in invalid_tool_calls, ma l'API le rimanda al modello come
    tool_call: senza risposta la cronologia non sarebbe più valida.
    """
    return ((getattr(messaggio, "tool_calls", None) or [])
            + (getattr(messaggio, "invalid_tool_calls", None) or []))


def limite_ricorsione(max_passi: int) -> int:
    """Rete di sicurezza per invoke(): con il nodo limite non dovrebbe mai scattare."""
    return 2 * max_passi + 5


def costruisci_grafo(modello: Runnable, strumenti: list[BaseTool], *, max_passi: int,
                     max_messaggi_contesto: int, fuso_predefinito: str,
                     riassuntore: Runnable | None = None,
                     messaggi_da_tenere: int = 6) -> CompiledStateGraph:
    """Grafo compatta -> llm -> strumenti -> llm, con il nodo limite.

    Il modello ha già gli strumenti collegati; il riassuntore no. Senza riassuntore il nodo
    compatta non fa nulla e il contesto è controllato solo dalla finestra scorrevole.
    """
    prompt = PROMPT_SISTEMA.format(fuso=fuso_predefinito)
    per_nome = {s.name: s for s in strumenti}

    def nodo_compatta(stato: AgentState) -> dict:
        messaggi = stato["messages"]
        if riassuntore is None or len(messaggi) <= max_messaggi_contesto:
            # print(f"[passo] nodo compatta: {len(messaggi)} messaggi, nessun riassunto necessario")
            return {}
        vecchi, recenti = dividi_cronologia(messaggi, messaggi_da_tenere)
        if not vecchi or (len(vecchi) == 1 and _e_riassunto(vecchi[0])):
            return {}
        # print(f"[passo] nodo compatta: riassumo {len(vecchi)} messaggi, ne tengo {len(recenti)}")
        try:
            risposta = riassuntore.invoke([SystemMessage(PROMPT_RIASSUNTO), HumanMessage(trascrivi(vecchi))])
        except openai.APIError as errore:
            logger.warning("riassunto non riuscito, cronologia lasciata intera: %s", errore)
            return {}
        testo = risposta.content.strip() if isinstance(risposta.content, str) else ""
        if not testo:
            logger.warning("riassunto non riuscito: il modello non ha restituito testo")
            return {}
        logger.info("compattati %d messaggi, tenuti %d", len(vecchi), len(recenti))
        riassunto = SystemMessage(INTESTAZIONE_RIASSUNTO + testo, name=NOME_RIASSUNTO)
        # REMOVE_ALL_MESSAGES svuota la cronologia: add_messages poi accoda riassunto e recenti.
        return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), riassunto] + recenti}

    def nodo_llm(stato: AgentState) -> dict:
        # print("[passo] nodo llm: chiedo al modello la prossima mossa")
        messaggi = stato["messages"]
        sistema = prompt
        if messaggi and _e_riassunto(messaggi[0]):
            # Un solo messaggio di sistema in testa: alcuni modelli non ne accettano altri.
            sistema += "\n\n" + messaggi[0].content
            messaggi = messaggi[1:]
        da_inviare = [SystemMessage(sistema)] + finestra_contesto(messaggi, max_messaggi_contesto)
        # print(f"[passo] nodo llm: invio {len(da_inviare)} messaggi al modello (prompt di sistema compreso)")
        return {"messages": [modello.invoke(da_inviare)]}

    def nodo_strumenti(stato: AgentState) -> dict:
        richieste = _richieste(stato["messages"][-1])
        # print(f"[passo] nodo strumenti: eseguo {len(richieste)} tool_call")
        risultati = []
        for tc in richieste:
            strumento = per_nome.get(tc["name"])
            if "error" in tc:  # invalid_tool_call: args è il testo grezzo, non un dizionario
                logger.warning("tool_call malformata dal modello: %s %r", tc["name"], tc["args"])
                testo = f"Errore: argomenti non validi per {tc['name']}: non sono JSON valido."
            elif strumento is None:
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
        richieste = _richieste(stato["messages"][-1])
        # print(f"[passo] nodo limite: {len(richieste)} tool_call non eseguite, chiudo il turno")
        logger.warning("limite di %d passaggi raggiunto: %d tool_call non eseguite",
                       max_passi, len(richieste))
        # Ogni tool_call deve avere la sua risposta, altrimenti la cronologia non è valida per l'API.
        sospese = [ToolMessage(content=f"Non eseguito: limite di {max_passi} passaggi raggiunto.",
                               tool_call_id=tc["id"]) for tc in richieste]
        return {"messages": sospese + [AIMessage(MESSAGGIO_LIMITE.format(n=max_passi))]}

    grafo = StateGraph(AgentState)
    grafo.add_node("compatta", nodo_compatta)
    grafo.add_node("llm", nodo_llm)
    grafo.add_node("strumenti", nodo_strumenti)
    grafo.add_node("limite", nodo_limite)
    grafo.add_edge(START, "compatta")
    grafo.add_edge("compatta", "llm")
    grafo.add_conditional_edges(
        "llm", lambda stato: instrada_dopo_llm(stato, max_passi),
        {"strumenti": "strumenti", "limite": "limite", END: END},
    )
    grafo.add_edge("strumenti", "llm")
    grafo.add_edge("limite", END)
    return grafo.compile()
