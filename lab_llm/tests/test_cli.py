"""Test della CLI client dell'API (python -m agente.cli) con httpx.MockTransport: nessun servizio vero."""

import json

import httpx

from agente.cli import ClienteAgente, ErroreServizio, avvia_cli

URL = "http://agente:8000"
CATALOGO = [{"nome": "spiega", "descrizione": "Spiega un argomento.",
             "argomenti": [{"nome": "argomento", "descrizione": "concetto", "obbligatorio": True}]}]


def _servizio(richieste, errore=None):
    """Servizio finto: /chat accoda alla cronologia ricevuta una domanda e una risposta."""

    def gestisci(request: httpx.Request) -> httpx.Response:
        richieste.append(request)
        if errore:
            return httpx.Response(errore[0], json={"errore": errore[1]})
        if request.url.path == "/prompts":
            return httpx.Response(200, json=CATALOGO)
        corpo = json.loads(request.content)
        cronologia = corpo["cronologia"] + [{"type": "human", "data": {"content": corpo.get("messaggio", "")}},
                                            {"type": "ai", "data": {"content": "ok"}}]
        return httpx.Response(200, json={"risposta": f"risposta {len(richieste)}", "cronologia": cronologia,
                                         "riassunto": corpo["riassunto"] + "r", "strumenti": []})

    return httpx.Client(base_url=URL, transport=httpx.MockTransport(gestisci))


def _sessione(cliente, ingressi):
    righe = []
    coda = iter(ingressi + ["esci"])
    avvia_cli(cliente, leggi=lambda _p: next(coda), scrivi=righe.append)
    return "\n".join(righe)


def test_turni_con_cronologia_e_riassunto_ripassati():
    richieste = []
    uscita = _sessione(ClienteAgente(URL, _servizio(richieste)), ["uno", "due"])
    assert "Assistente> risposta 1" in uscita and "Assistente> risposta 2" in uscita
    secondo = json.loads(richieste[1].content)
    assert secondo["messaggio"] == "due" and secondo["riassunto"] == "r"
    assert [m["data"]["content"] for m in secondo["cronologia"]] == ["uno", "ok"]


def test_prompts_e_prompt_via_api():
    richieste = []
    cliente = ClienteAgente(URL, _servizio(richieste))
    uscita = _sessione(cliente, ["/prompts", '/prompt spiega argomento="Model Context Protocol"'])
    assert "argomento (obbligatorio): concetto" in uscita
    corpo = json.loads(richieste[1].content)
    assert corpo["prompt"] == {"nome": "spiega", "argomenti": {"argomento": "Model Context Protocol"}}


def test_riga_non_valida_non_chiama_il_servizio():
    richieste = []
    uscita = _sessione(ClienteAgente(URL, _servizio(richieste)), ['/prompt spiega argomento="x', "/aiuto"])
    assert richieste == []
    assert "[errore] Virgolette non chiuse" in uscita and "[errore] Comando sconosciuto: /aiuto" in uscita


def test_errore_del_servizio_mostrato_e_sessione_continua():
    richieste = []
    uscita = _sessione(ClienteAgente(URL, _servizio(richieste, (503, "Il modello non è raggiungibile."))),
                       ["uno", "due"])
    assert uscita.count("[errore] Il modello non è raggiungibile. (HTTP 503)") == 2


def test_servizio_spento():
    def rifiuta(request):
        raise httpx.ConnectError("rifiutata", request=request)
    cliente = ClienteAgente(URL, httpx.Client(base_url=URL, transport=httpx.MockTransport(rifiuta)))
    try:
        cliente.chat("ciao", [], "")
    except ErroreServizio as errore:
        assert f"non raggiungibile su {URL}" in str(errore)
    else:
        raise AssertionError("attesa ErroreServizio")
