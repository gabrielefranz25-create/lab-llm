"""Server MCP del convertitore di unità: elenco chiuso di unità per grandezza, errori espliciti."""

import logging
import math
import os
import sys

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

logger = logging.getLogger(__name__)

# Fattori verso l'unità base di ogni grandezza (m, kg, l, m/s). La temperatura usa formule.
FATTORI = {
    "lunghezza": {"mm": 0.001, "cm": 0.01, "m": 1.0, "km": 1000.0,
                  "in": 0.0254, "ft": 0.3048, "yd": 0.9144, "mi": 1609.344},
    "massa": {"mg": 1e-6, "g": 0.001, "kg": 1.0, "t": 1000.0, "oz": 0.028349523125, "lb": 0.45359237},
    "volume": {"ml": 0.001, "cl": 0.01, "l": 1.0, "m3": 1000.0, "gal": 3.785411784},
    "velocità": {"m/s": 1.0, "km/h": 1 / 3.6, "mph": 0.44704, "kn": 1852 / 3600},
}
# Da e verso kelvin.
TEMPERATURE = {
    "°C": (lambda v: v + 273.15, lambda k: k - 273.15),
    "°F": (lambda v: (v - 32) * 5 / 9 + 273.15, lambda k: (k - 273.15) * 9 / 5 + 32),
    "K": (lambda v: v, lambda k: k),
}
# Nomi italiani e scritture alternative (in minuscolo) → simbolo.
ALIAS = {
    "millimetro": "mm", "millimetri": "mm", "centimetro": "cm", "centimetri": "cm",
    "metro": "m", "metri": "m", "chilometro": "km", "chilometri": "km",
    "pollice": "in", "pollici": "in", "piede": "ft", "piedi": "ft", "iarda": "yd", "iarde": "yd",
    "miglio": "mi", "miglia": "mi",
    "milligrammo": "mg", "milligrammi": "mg", "grammo": "g", "grammi": "g",
    "chilogrammo": "kg", "chilogrammi": "kg", "chilo": "kg", "chili": "kg",
    "tonnellata": "t", "tonnellate": "t", "oncia": "oz", "once": "oz", "libbra": "lb", "libbre": "lb",
    "millilitro": "ml", "millilitri": "ml", "centilitro": "cl", "centilitri": "cl",
    "litro": "l", "litri": "l", "m³": "m3", "metro cubo": "m3", "metri cubi": "m3",
    "gallone": "gal", "galloni": "gal",
    "metri al secondo": "m/s", "chilometri orari": "km/h", "chilometri all'ora": "km/h", "kmh": "km/h",
    "miglia orarie": "mph", "nodo": "kn", "nodi": "kn",
    "c": "°C", "celsius": "°C", "gradi celsius": "°C", "f": "°F", "fahrenheit": "°F",
    "gradi fahrenheit": "°F", "kelvin": "K",
}

# Simbolo in minuscolo → (grandezza, simbolo).
_SIMBOLI = {s.lower(): (g, s) for g, unita in FATTORI.items() for s in unita}
_SIMBOLI.update({s.lower(): ("temperatura", s) for s in TEMPERATURE})


class ErroreUnita(Exception):
    """Conversione impossibile, con un messaggio leggibile dal modello."""


def _ammesse() -> str:
    gruppi = [f"{g}: {', '.join(u)}" for g, u in FATTORI.items()]
    gruppi.append(f"temperatura: {', '.join(TEMPERATURE)}")
    return "; ".join(gruppi)


def _riconosci(nome: str) -> tuple[str, str]:
    """(grandezza, simbolo) dell'unità indicata con simbolo o nome italiano."""
    chiave = (nome or "").strip().lower()
    chiave = ALIAS.get(chiave, chiave).lower()
    if chiave not in _SIMBOLI:
        raise ErroreUnita(f"unità «{(nome or '').strip()}» non riconosciuta. Unità ammesse: {_ammesse()}")
    return _SIMBOLI[chiave]


def converti(valore: float, da: str, a: str) -> tuple[float, str]:
    """Valore convertito e nome della grandezza."""
    if not math.isfinite(valore):
        raise ErroreUnita("valore non valido: serve un numero finito")
    grandezza_da, simbolo_da = _riconosci(da)
    grandezza_a, simbolo_a = _riconosci(a)
    if grandezza_da != grandezza_a:
        raise ErroreUnita(f"impossibile convertire {simbolo_da} ({grandezza_da}) "
                          f"in {simbolo_a} ({grandezza_a})")
    if grandezza_da == "temperatura":
        kelvin = TEMPERATURE[simbolo_da][0](valore)
        if kelvin < 0:
            raise ErroreUnita(f"{valore:g} {simbolo_da} è sotto lo zero assoluto")
        return TEMPERATURE[simbolo_a][1](kelvin), grandezza_da
    fattori = FATTORI[grandezza_da]
    risultato = valore * fattori[simbolo_da] / fattori[simbolo_a]
    if not math.isfinite(risultato):
        raise ErroreUnita("risultato fuori scala: valore troppo grande per questa conversione")
    return risultato, grandezza_da


def descrivi_conversione(valore: float, da: str, a: str) -> str:
    """Risultato per il modello, con 6 cifre significative e unità esplicite."""
    risultato, grandezza = converti(valore, da, a)
    simbolo_da, simbolo_a = _riconosci(da)[1], _riconosci(a)[1]
    return f"{valore:.6g} {simbolo_da} = {risultato:.6g} {simbolo_a} ({grandezza})"


mcp = FastMCP("Unità di misura")


@mcp.tool
def converti_unita(valore: float, da: str, a: str) -> str:
    """Converte un valore tra unità di misura della stessa grandezza: lunghezza (mm, cm, m, km, in, ft, yd, mi), massa (mg, g, kg, t, oz, lb), volume (ml, cl, l, m3, gal), velocità (m/s, km/h, mph, kn), temperatura (C, F, K). Accetta anche i nomi italiani, es. "miglia", "chilometri"."""
    try:
        return descrivi_conversione(valore, da, a)
    except ErroreUnita as errore:
        logger.info("unita: conversione rifiutata: %s", errore)
        raise ToolError(str(errore)) from errore


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stderr, level=os.environ.get("LOG_LEVEL", "INFO").upper())
    mcp.run(show_banner=False)
