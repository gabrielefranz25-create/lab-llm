"""Chiamate del back-end all'agente (POST /chat dello step 6): il front-end non lo conosce."""

import httpx


class AgenteNonDisponibile(Exception):
    """Agente irraggiungibile o in errore: `codice` HTTP da restituire e messaggio comprensibile."""

    def __init__(self, codice: int, messaggio: str):
        super().__init__(messaggio)
        self.codice = codice


class ClienteAgente:
    def __init__(self, url: str, timeout: float = 600.0, http: httpx.Client | None = None):
        self.url = url.rstrip("/")
        self.http = http or httpx.Client(base_url=self.url, timeout=timeout)

    def chat(self, messaggio: str, cronologia: list, riassunto: str) -> dict:
        """Un turno: risposta, cronologia e riassunto aggiornati, strumenti usati."""
        try:
            risposta = self.http.post("/chat", json={"messaggio": messaggio, "cronologia": cronologia,
                                                     "riassunto": riassunto})
        except httpx.HTTPError as errore:
            raise AgenteNonDisponibile(503, f"L'agente non è raggiungibile su {self.url} "
                                            f"({type(errore).__name__}). Riprova più tardi.") from errore
        if risposta.status_code >= 400:
            try:
                testo = risposta.json().get("errore") or risposta.text
            except ValueError:
                testo = risposta.text
            raise AgenteNonDisponibile(risposta.status_code, f"Errore dell'agente: {testo}")
        return risposta.json()

    def stato(self) -> dict:
        try:
            risposta = self.http.get("/stato")
            return {"raggiungibile": True, **risposta.json()}
        except (httpx.HTTPError, ValueError) as errore:
            return {"raggiungibile": False, "errore": f"{type(errore).__name__}: {errore}"}
