"""Test dei comandi /prompts e /prompt: controllo degli argomenti nell'host, prima del server e del modello."""

import logging
from types import SimpleNamespace as NS

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from agente.comandi import ComandiPrompt, ErroreComando
from agente.mcp_ponte import ErroreMCP


def _prompt(nome, descrizione, *argomenti):
    return NS(name=nome, description=descrizione,
              arguments=[NS(name=n, description=d, required=r) for n, d, r in argomenti])


CATALOGO = [
    _prompt("spiega", "Spiega un argomento al livello richiesto.",
            ("argomento", "concetto da spiegare", True), ("livello", "base, intermedio o avanzato", False)),
    _prompt("riassumi_conversazione", "Riassume la conversazione.", ("stile", "sintetico o dettagliato", False)),
]


class ConnessioneFinta:
    def __init__(self, catalogo=CATALOGO, messaggi=None, errore=None):
        self.catalogo, self.errore = catalogo, errore
        self.messaggi = messaggi or [("user", "Spiegami «MCP» a livello base: …")]
        self.richieste: list = []

    def elenca_prompt(self, server):
        if self.catalogo is None:
            raise ErroreMCP("server MCP utente non disponibile")
        return self.catalogo

    def ottieni_prompt(self, server, nome, argomenti):
        self.richieste.append((server, nome, argomenti))
        if self.errore:
            raise ErroreMCP(self.errore)
        return self.messaggi


def test_catalogo_letto_una_volta_e_nei_log(caplog):
    with caplog.at_level(logging.INFO, logger="agente.comandi"):
        comandi = ComandiPrompt(ConnessioneFinta())
    assert comandi.disponibili
    assert "prompt: catalogo del server utente [spiega, riassumi_conversazione]" in caplog.text


def test_elenco_con_descrizione_e_argomenti():
    testo = ComandiPrompt(ConnessioneFinta()).elenco()
    assert "spiega: Spiega un argomento al livello richiesto." in testo
    assert "argomento (obbligatorio): concetto da spiegare" in testo
    assert "livello (facoltativo): base, intermedio o avanzato" in testo
    assert "riassumi_conversazione" in testo
    assert '/prompt spiega argomento="Model Context Protocol" livello=base' in testo


def test_prompt_valido_diventa_messaggi_con_log(caplog):
    connessione = ConnessioneFinta(messaggi=[("user", "Spiegami «Model Context Protocol» a livello base"),
                                             ("assistant", "Va bene.")])
    comandi = ComandiPrompt(connessione)
    with caplog.at_level(logging.INFO, logger="agente.comandi"):
        messaggi = comandi.richiama('/prompt spiega argomento="Model Context Protocol" livello=base')
    assert connessione.richieste == [("utente", "spiega",
                                      {"argomento": "Model Context Protocol", "livello": "base"})]
    assert isinstance(messaggi[0], HumanMessage) and isinstance(messaggi[1], AIMessage)
    assert messaggi[0].content == "Spiegami «Model Context Protocol» a livello base"
    assert ('prompt: richiamato spiega argomenti={"argomento": "Model Context Protocol", "livello": "base"} '
            "dal server utente: 2 messaggi") in caplog.text
    assert "prompt: messaggio 1 (user): Spiegami «Model Context Protocol» a livello base" in caplog.text


def test_argomenti_facoltativi_omessi():
    connessione = ConnessioneFinta()
    ComandiPrompt(connessione).richiama("/prompt riassumi_conversazione")
    assert connessione.richieste == [("utente", "riassumi_conversazione", {})]


@pytest.mark.parametrize("riga, motivo", [
    ("/prompt", "Uso: /prompt"),
    ("/prompt sconosciuto a=1", "prompt sconosciuto"),
    ("/prompt spiega livello=base", "argomento obbligatorio mancante: argomento"),
    ("/prompt spiega argomento=MCP colore=blu", "argomento sconosciuto: colore"),
    ("/prompt spiega MCP", "atteso nome=valore"),
    ('/prompt spiega argomento="MCP', "virgolette"),
])
def test_richieste_non_valide_bloccate_senza_chiamare_il_server(riga, motivo):
    connessione = ConnessioneFinta()
    with pytest.raises(ErroreComando, match="(?i)" + motivo):
        ComandiPrompt(connessione).richiama(riga)
    assert connessione.richieste == []


def test_errore_del_server_diventa_errore_del_comando():
    comandi = ComandiPrompt(ConnessioneFinta(errore="server MCP utente: livello 'x' non valido"))
    with pytest.raises(ErroreComando, match="livello 'x' non valido"):
        comandi.richiama("/prompt spiega argomento=MCP livello=x")


def test_server_non_disponibile(caplog):
    with caplog.at_level(logging.WARNING, logger="agente.comandi"):
        comandi = ComandiPrompt(ConnessioneFinta(catalogo=None))
    assert not comandi.disponibili and "prompt non disponibili" in caplog.text
    assert "Prompt non disponibili" in comandi.elenco()
    with pytest.raises(ErroreComando, match="non disponibili"):
        comandi.richiama("/prompt spiega argomento=MCP")
