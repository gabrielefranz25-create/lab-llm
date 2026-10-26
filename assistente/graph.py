import

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

FIXED_ANSWERE = "Il grafo è già in esecuzione"

class State(TypedDict):
    """Stato condiviso con i nodi del grafo"""

    user_text: str
    answer: str

def answer_node(state: State) -> dict:
    """Legge lo stato e restituisce solo le chiavi da aggiornare"""

    print(f"[nodo_answer] testo ricevuto: {state}")

def build_graph