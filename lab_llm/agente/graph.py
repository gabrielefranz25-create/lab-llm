"""Grafo LangGraph dell'assistente: stato, compattazione, router, revisore, finestra di contesto, nodi.

I print didattici "[passo]" sono commentati: togliere il commento per seguire il flusso.
"""

import json
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
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

PROMPT_SISTEMA = (
    "Sei l'assistente del laboratorio. Rispondi in italiano, in modo breve e chiaro.\n"
    "Per qualsiasi domanda su data, ora o giorno attuali usa SEMPRE lo strumento `ora_corrente`: "
    "non inventare l'ora. Se l'utente non indica un luogo usa il fuso predefinito {fuso} "
    "(ora italiana). Per altri luoghi passa il nome IANA del fuso (es. \"Asia/Tokyo\").\n"
    "Nella risposta indica sempre a quale fuso orario si riferisce l'ora.\n"
    "Per il meteo di adesso usa lo strumento `meteo_attuale` e per le previsioni "
    "`previsioni_meteo`: non inventare dati meteorologici e cita la località indicata nel risultato.\n"
    "Se l'utente chiede di ricordare, annotare o salvare qualcosa (\"ricordami\", \"annota\", \"segna\", "
    "\"salva una nota\") DEVI chiamare `aggiungi_nota`: non dire mai che una nota è salvata se "
    "`aggiungi_nota` non l'ha confermato. Per vedere le note usa `elenca_note`. Elimina una nota solo per ID "
    "con `elimina_nota`; se l'ID non è noto, prima chiama `elenca_note`.\n"
    "Se uno strumento restituisce un errore, riferiscilo all'utente senza inventare un risultato."
)

# Istruzioni aggiunte al prompt solo se lo strumento è collegato: citare uno strumento assente confonde
# il modello (prova reale: con questa riga e senza `calcola`, «Che ore sono?» non chiamava `ora_corrente`).
ISTRUZIONI_PER_STRUMENTO = {
    "calcola": "Per i conti usa `calcola` e non farli a mente. In italiano «per» e «x» indicano la "
               "moltiplicazione («15 per 12» = 15*12), «diviso» la divisione (/).",
}

MESSAGGIO_LIMITE = (
    "Ho raggiunto il limite di {n} richieste allo strumento per questa domanda. "
    "Prova a riformularla in modo più semplice."
)

PROMPT_RIASSUNTO = (
    "Riassumi in italiano, in poche frasi, la conversazione che ti viene data. Conserva i fatti "
    "utili per continuarla: nome, preferenze e richieste dell'utente, luoghi e fusi orari citati, "
    "risposte già date. Chiama sempre l'utente \"l'utente\", in terza persona "
    "(es. \"L'utente si chiama ... e vive a ...\"): chi leggerà il riassunto deve capire che quei "
    "fatti riguardano la persona con cui sta parlando. Scrivi solo il riassunto, senza commenti."
)

PROMPT_ROUTER = (
    "Sei il router dell'assistente del laboratorio. Non rispondi all'utente: decidi solo se la sua "
    "ultima domanda rientra nell'ambito dell'assistente.\n"
    "Ambito: {ambito}.\n"
    "Rispondi con la categoria \"conversazione\" se la domanda rientra nell'ambito (anche come seguito "
    "della conversazione recente), altrimenti con \"fuori_ambito\". Rientrano nell'ambito anche le "
    "domande su ciò che l'utente ha detto prima nella conversazione (per esempio il suo nome). "
    "Aggiungi un motivo breve, in italiano."
)

MESSAGGIO_RIFIUTO = "Mi dispiace, posso aiutarti solo con: {ambito}."

PROMPT_REVISORE = (
    "Sei il revisore dell'assistente del laboratorio. Non rispondi all'utente: controlli solo se la "
    "risposta proposta tratta tutto ciò che la domanda chiede.\n"
    "Procedi così: elenca le parti della domanda (una domanda può chiedere più cose); per ognuna guarda "
    "se la risposta ne parla. La risposta è coerente se parla di TUTTE le parti e non devia dal tema.\n"
    "NON controllare se numeri, orari, dati meteo o risultati dei calcoli sono giusti: arrivano dagli "
    "strumenti e vanno considerati corretti anche se ti sembrano sbagliati. Una risposta che spiega di "
    "non poter fare una parte, o che riporta un errore dello strumento, tratta comunque quella parte.\n"
    "Esempio: domanda «Quanto fa 7 per 8?», risposta «7 per 8 fa 56.» → coerente=true (in italiano "
    "«per» indica la moltiplicazione, ma anche con un numero diverso la parte sarebbe trattata).\n"
    "Scrivi prima il motivo breve, in italiano (quali parti sono trattate e quali mancano), poi "
    "coerente=true oppure coerente=false."
)

# Nome del HumanMessage con cui il revisore rimanda all'agente il motivo (un HumanMessage e non un
# SystemMessage: alcuni modelli accettano un solo messaggio di sistema, in testa).
NOME_REVISORE = "revisore"
INTESTAZIONE_REVISORE = "Nota del revisore: "
NOTA_REVISORE = (
    INTESTAZIONE_REVISORE + "la risposta precedente non è completa o coerente con la domanda: {motivo}. "
    "Rispondi di nuovo alla domanda dell'utente, completa."
)

# Messaggi della cronologia (domanda compresa) che il router legge per decidere.
MESSAGGI_ROUTER = 4

# Intestazione con cui il campo `riassunto` dello stato entra nel prompt di sistema del nodo llm.
INTESTAZIONE_RIASSUNTO = (
    "Riassunto della conversazione precedente con l'utente (fatti già detti, usali per rispondere):\n"
)


class DecisioneRouter(BaseModel):
    """Output strutturato del router."""
    categoria: Literal["conversazione", "fuori_ambito"] = Field(
        description="conversazione se la domanda rientra nell'ambito, altrimenti fuori_ambito")
    motivo: str = Field(description="motivo breve della scelta, in italiano")


class DecisioneRevisore(BaseModel):
    """Output strutturato del revisore. Il motivo viene prima: il modello ragiona, poi decide."""
    motivo: str = Field(description="parti della domanda trattate e mancanti, in breve, in italiano")
    coerente: bool = Field(description="true se la risposta tratta tutte le parti della domanda senza "
                                       "deviare dal tema, altrimenti false")


class AgentState(TypedDict):
    # Cronologia (Human/AI/Tool): add_messages accoda i messaggi nuovi restituiti dai nodi.
    messages: Annotated[list[AnyMessage], add_messages]
    # Giri di strumento nel turno corrente: senza reducer, il valore restituito sostituisce il vecchio.
    passi_strumento: int
    # Decisione del router per il turno corrente: "conversazione" o "fuori_ambito".
    categoria: str
    # Revisioni chieste dal revisore nel turno corrente (azzerate dal client a ogni domanda).
    revisioni: int
    # Riassunto dei messaggi vecchi, scritto dal nodo compatta: il nuovo sostituisce il vecchio
    # (che il riassuntore ha già incorporato). Non sta in `messages`.
    riassunto: str


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


def _e_nota_revisore(messaggio: AnyMessage) -> bool:
    return isinstance(messaggio, HumanMessage) and messaggio.name == NOME_REVISORE


def domanda_del_turno(messaggi: list[AnyMessage]) -> str:
    """Testo dell'ultimo HumanMessage dell'utente (le note del revisore non contano)."""
    for m in reversed(messaggi):
        if isinstance(m, HumanMessage) and not _e_nota_revisore(m):
            return m.content
    return ""


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
        if _e_nota_revisore(m):
            righe.append(f"Revisore: {m.content.removeprefix(INTESTAZIONE_REVISORE)}")
        elif isinstance(m, HumanMessage):
            righe.append(f"Utente: {m.content}")
        elif isinstance(m, ToolMessage):
            righe.append(f"Strumento: {m.content}".replace("\n", " | "))
        elif isinstance(m, AIMessage) and m.content:  # le sole tool_call non hanno testo
            righe.append(f"Assistente: {m.content}")
    return "\n".join(righe)


def instrada_dopo_router(stato: AgentState) -> Literal["llm", "rifiuto"]:
    """Dopo il router: conversazione all'agente (nodo llm), fuori ambito al rifiuto."""
    return "rifiuto" if stato["categoria"] == "fuori_ambito" else "llm"


def instrada_dopo_llm(stato: AgentState, max_passi: int) -> Literal["strumenti", "limite", "revisore"]:
    """Dopo il nodo llm: revisore se non ci sono tool_call, altrimenti strumenti o limite."""
    if not _richieste(stato["messages"][-1]):
        # print("[passo] instradamento: nessuna tool_call -> revisore")
        return "revisore"
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


def instrada_dopo_revisore(stato: AgentState) -> Literal["llm", "__end__"]:
    """Dopo il revisore: di nuovo all'agente se ha aggiunto una nota, altrimenti fine del turno."""
    return "llm" if _e_nota_revisore(stato["messages"][-1]) else END


def limite_ricorsione(max_passi: int, max_revisioni: int = 2) -> int:
    """Rete di sicurezza per invoke(): con i nodi limite e revisore non dovrebbe mai scattare."""
    return 2 * max_passi + 2 * max_revisioni + 6


def costruisci_grafo(modello: Runnable, strumenti: list[BaseTool], *, max_passi: int,
                     max_messaggi_contesto: int, fuso_predefinito: str,
                     riassuntore: Runnable | None = None,
                     messaggi_da_tenere: int = 6, router: Runnable | None = None,
                     ambito: str = "", revisore: Runnable | None = None,
                     max_revisioni: int = 2) -> CompiledStateGraph:
    """Grafo compatta -> router -> (llm -> strumenti -> llm -> revisore | rifiuto), con il nodo limite.

    Il modello ha già gli strumenti collegati; riassuntore, router e revisore no. Senza riassuntore il
    nodo compatta non fa nulla e il contesto è controllato solo dalla finestra scorrevole. Senza router
    ogni domanda passa all'agente; senza revisore ogni risposta è approvata. Router e revisore
    restituiscono un DecisioneRouter e un DecisioneRevisore.
    """
    prompt = "\n".join([PROMPT_SISTEMA.format(fuso=fuso_predefinito),
                        *(testo for nome, testo in ISTRUZIONI_PER_STRUMENTO.items()
                          if any(s.name == nome for s in strumenti))])
    prompt_router = PROMPT_ROUTER.format(ambito=ambito)
    per_nome = {s.name: s for s in strumenti}

    def nodo_compatta(stato: AgentState) -> dict:
        messaggi = stato["messages"]
        if riassuntore is None:
            return {}
        if len(messaggi) <= max_messaggi_contesto:
            # print(f"[passo] nodo compatta: {len(messaggi)} messaggi, nessun riassunto necessario")
            logger.debug("riassunto: %d messaggi, sotto la soglia di %d, nessuna chiamata al modello",
                         len(messaggi), max_messaggi_contesto)
            return {}
        vecchi, recenti = dividi_cronologia(messaggi, messaggi_da_tenere)
        if not vecchi:
            return {}
        testo = trascrivi(vecchi)
        precedente = stato.get("riassunto", "")
        if precedente:  # il riassunto nuovo incorpora il precedente e lo sostituisce
            testo = f"Riassunto precedente: {precedente}\n{testo}"
        # print(f"[passo] nodo compatta: riassumo {len(vecchi)} messaggi, ne tengo {len(recenti)}")
        try:
            risposta = riassuntore.invoke([SystemMessage(PROMPT_RIASSUNTO), HumanMessage(testo)])
        except openai.APIError as errore:
            logger.warning("riassunto non riuscito, cronologia lasciata intera: %s", errore)
            return {}
        riassunto = risposta.content.strip() if isinstance(risposta.content, str) else ""
        if not riassunto:
            logger.warning("riassunto non riuscito: il modello non ha restituito testo")
            return {}
        logger.info("riassunto: messaggi prima=%d dopo=%d (riassunti %d, tenuti %d)",
                    len(messaggi), len(recenti), len(vecchi), len(recenti))
        # REMOVE_ALL_MESSAGES svuota la cronologia: add_messages poi accoda i recenti.
        return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES)] + recenti, "riassunto": riassunto}

    def nodo_router(stato: AgentState) -> dict:
        if router is None:
            return {"categoria": "conversazione"}
        *precedenti, domanda = stato["messages"][-MESSAGGI_ROUTER:]
        testo = f"Domanda da classificare: {domanda.content}"
        if precedenti:
            testo = f"Conversazione recente:\n{trascrivi(precedenti)}\n\n{testo}"
        if stato.get("riassunto"):  # dopo la compressione i fatti vecchi stanno solo qui
            testo = f"Riassunto della conversazione precedente: {stato['riassunto']}\n\n{testo}"
        # print("[passo] nodo router: chiedo al modello se la domanda rientra nell'ambito")
        try:
            decisione = router.invoke([SystemMessage(prompt_router), HumanMessage(testo)])
        except (openai.APIError, ValueError) as errore:  # ValueError: output non valido per lo schema
            logger.warning("router non riuscito, domanda passata all'agente: %s", errore)
            return {"categoria": "conversazione"}
        if not isinstance(decisione, DecisioneRouter):
            logger.warning("router non riuscito, domanda passata all'agente: output %r", decisione)
            return {"categoria": "conversazione"}
        destinazione = "rifiuto" if decisione.categoria == "fuori_ambito" else "agente"
        logger.info("router: categoria=%s motivo=%s -> %s", decisione.categoria,
                    decisione.motivo.replace("\n", " "), destinazione)
        return {"categoria": decisione.categoria}

    def nodo_rifiuto(stato: AgentState) -> dict:
        # print("[passo] nodo rifiuto: domanda fuori ambito, l'agente non viene chiamato")
        return {"messages": [AIMessage(MESSAGGIO_RIFIUTO.format(ambito=ambito))]}

    def nodo_llm(stato: AgentState) -> dict:
        # print("[passo] nodo llm: chiedo al modello la prossima mossa")
        messaggi = stato["messages"]
        sistema = prompt
        if stato.get("riassunto"):
            # Un solo messaggio di sistema in testa: alcuni modelli non ne accettano altri.
            sistema += "\n\n" + INTESTAZIONE_RIASSUNTO + stato["riassunto"]
        da_inviare = [SystemMessage(sistema)] + finestra_contesto(messaggi, max_messaggi_contesto)
        # print(f"[passo] nodo llm: invio {len(da_inviare)} messaggi al modello (prompt di sistema compreso)")
        logger.info("agente: invio %d messaggi al modello", len(da_inviare))
        return {"messages": [modello.invoke(da_inviare)]}

    def nodo_revisore(stato: AgentState) -> dict:
        if revisore is None:
            return {}
        revisioni = stato.get("revisioni", 0)
        testo = (f"Domanda dell'utente: {domanda_del_turno(stato['messages'])}\n\n"
                 f"Risposta proposta: {stato['messages'][-1].content}")
        # print("[passo] nodo revisore: chiedo al modello se la risposta è coerente con la domanda")
        try:
            decisione = revisore.invoke([SystemMessage(PROMPT_REVISORE), HumanMessage(testo)])
        except (openai.APIError, ValueError) as errore:  # ValueError: output non valido per lo schema
            logger.warning("revisore non riuscito, risposta accettata: %s", errore)
            return {}
        if not isinstance(decisione, DecisioneRevisore):
            logger.warning("revisore non riuscito, risposta accettata: output %r", decisione)
            return {}
        motivo = decisione.motivo.replace("\n", " ")
        if decisione.coerente:
            logger.info("revisore: coerente=si motivo=%s -> fine", motivo)
            return {}
        if revisioni >= max_revisioni:
            logger.info("revisore: coerente=no motivo=%s -> fine", motivo)
            logger.warning("revisore: limite di %d revisioni raggiunto, restituita l'ultima risposta",
                           max_revisioni)
            return {}
        logger.info("revisore: coerente=no motivo=%s -> agente (revisione %d di %d)",
                    motivo, revisioni + 1, max_revisioni)
        nota = HumanMessage(NOTA_REVISORE.format(motivo=motivo), name=NOME_REVISORE)
        return {"messages": [nota], "revisioni": revisioni + 1}

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
            origine = (strumento.metadata or {}).get("origine", "locale") if strumento else "-"
            argomenti = tc["args"] if isinstance(tc["args"], str) else json.dumps(tc["args"], ensure_ascii=False)
            logger.info("strumento=%s origine=%s call_id=%s argomenti=%s esito=%s risultato=%s",
                        tc["name"], origine, tc["id"], argomenti,
                        "errore" if testo.startswith("Errore") else "ok", testo.replace("\n", " | "))
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
    grafo.add_node("router", nodo_router)
    grafo.add_node("rifiuto", nodo_rifiuto)
    grafo.add_node("llm", nodo_llm)
    grafo.add_node("strumenti", nodo_strumenti)
    grafo.add_node("limite", nodo_limite)
    grafo.add_node("revisore", nodo_revisore)
    grafo.add_edge(START, "compatta")
    grafo.add_edge("compatta", "router")
    grafo.add_conditional_edges("router", instrada_dopo_router, {"llm": "llm", "rifiuto": "rifiuto"})
    grafo.add_edge("rifiuto", END)
    grafo.add_conditional_edges(
        "llm", lambda stato: instrada_dopo_llm(stato, max_passi),
        {"strumenti": "strumenti", "limite": "limite", "revisore": "revisore"},
    )
    grafo.add_conditional_edges("revisore", instrada_dopo_revisore, {"llm": "llm", END: END})
    grafo.add_edge("strumenti", "llm")
    grafo.add_edge("limite", END)
    return grafo.compile()
