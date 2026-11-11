"""Server MCP della calcolatrice: espressioni aritmetiche valutate con `ast`, mai con `eval`."""

import ast
import logging
import math
import operator
import os
import sys

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

logger = logging.getLogger(__name__)

LUNGHEZZA_MAX = 200
ESPONENTE_MAX = 100
RISULTATO_MAX = 1e100

# Simboli che le persone scrivono spesso al posto di quelli di Python.
SOSTITUZIONI = {"^": "**", "×": "*", "÷": "/"}

OPERATORI_BINARI = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow,
}
OPERATORI_UNARI = {ast.UAdd: operator.pos, ast.USub: operator.neg}

# Nomi leggibili per gli elementi rifiutati più comuni.
NON_CONSENTITI = {
    ast.Call: "chiamata di funzione", ast.Attribute: "attributo", ast.Compare: "confronto",
    ast.Tuple: "elenco di valori (usa il punto per i decimali)",
}


class ErroreCalcolo(Exception):
    """Espressione rifiutata o non calcolabile, con un messaggio leggibile dal modello."""


def _controlla(valore):
    """Rifiuta risultati complessi, infiniti o oltre RISULTATO_MAX."""
    if isinstance(valore, complex):
        raise ErroreCalcolo("risultato non reale")
    if (isinstance(valore, float) and not math.isfinite(valore)) or abs(valore) > RISULTATO_MAX:
        raise ErroreCalcolo(f"risultato troppo grande (massimo {RISULTATO_MAX:g} in valore assoluto)")
    return valore


def _visita(nodo: ast.AST):
    if isinstance(nodo, ast.Constant) and type(nodo.value) in (int, float):
        return _controlla(nodo.value)
    if isinstance(nodo, ast.UnaryOp) and type(nodo.op) in OPERATORI_UNARI:
        return OPERATORI_UNARI[type(nodo.op)](_visita(nodo.operand))
    if isinstance(nodo, ast.BinOp) and type(nodo.op) in OPERATORI_BINARI:
        sinistra, destra = _visita(nodo.left), _visita(nodo.right)
        if isinstance(nodo.op, ast.Pow) and abs(destra) > ESPONENTE_MAX:
            raise ErroreCalcolo(f"esponente troppo grande (massimo {ESPONENTE_MAX} in valore assoluto)")
        try:
            risultato = OPERATORI_BINARI[type(nodo.op)](sinistra, destra)
        except ZeroDivisionError:
            raise ErroreCalcolo("divisione per zero") from None
        except OverflowError:
            raise ErroreCalcolo("risultato troppo grande") from None
        return _controlla(risultato)
    if isinstance(nodo, ast.Name):
        raise ErroreCalcolo(f"elemento non consentito: nome «{nodo.id}» (solo numeri e operatori)")
    descrizione = NON_CONSENTITI.get(type(nodo), type(nodo).__name__)
    raise ErroreCalcolo(f"elemento non consentito: {descrizione} (solo numeri, + - * / // % ** e parentesi)")


def valuta(espressione: str) -> int | float:
    """Valore dell'espressione; solleva ErroreCalcolo per tutto ciò che non è aritmetica semplice."""
    testo = (espressione or "").strip()
    if not testo:
        raise ErroreCalcolo("espressione mancante")
    if len(testo) > LUNGHEZZA_MAX:
        raise ErroreCalcolo(f"espressione troppo lunga (massimo {LUNGHEZZA_MAX} caratteri)")
    for simbolo, sostituto in SOSTITUZIONI.items():
        testo = testo.replace(simbolo, sostituto)
    try:
        albero = ast.parse(testo, mode="eval")
    except SyntaxError:
        raise ErroreCalcolo("espressione non valida") from None
    return _visita(albero.body)


def formatta(valore: int | float) -> str:
    """Interi così come sono, decimali con al massimo 10 cifre significative."""
    return str(valore) if isinstance(valore, int) else format(valore, ".10g")


mcp = FastMCP("Calcolatrice")


@mcp.tool
def calcola(espressione: str) -> str:
    """Calcola un'espressione aritmetica con numeri, + - * / // % ** (o ^) e parentesi, per esempio "17*23" o "(2+3)/4". Da usare per qualsiasi conto invece di farlo a mente. Non accetta variabili né funzioni."""
    try:
        valore = valuta(espressione)
    except ErroreCalcolo as errore:
        logger.info("calcolatrice: espressione rifiutata: %s", errore)
        raise ToolError(str(errore)) from errore
    return f"{espressione.strip()} = {formatta(valore)}"


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stderr, level=os.environ.get("LOG_LEVEL", "INFO").upper())
    mcp.run(show_banner=False)
