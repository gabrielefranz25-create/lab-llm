"""Client minimo per il server locale di LM Studio.

Legge le domande da terminale e stampa le risposte del modello in
streaming, man mano che vengono generate.
La conversazione resta in memoria finche' il programma e' aperto
(nulla viene salvato su file); le righe vuote vengono ignorate e si
esce scrivendo "esci".
"""

import json
import os

import requests
from dotenv import load_dotenv

# --- Configurazione -------------------------------------------------------
load_dotenv()
base_url = os.environ["LM_BASE_URL"]
model = os.environ["LM_MODEL"]

# --- Messaggi -------------------------------------------------------------
system = {
    "role": "system",
    "content": "Sei un assistente che risponde sempre in italiano, "
    "in modo breve e preciso.",
}
# Memoria della conversazione: system, poi domande e risposte alternate.
messages = [system]


def chiedi(messages):
    """Invia la conversazione, stampa la risposta in streaming e la restituisce."""
    # --- Payload ----------------------------------------------------------
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 300,
        "reasoning_effort": "none",
        "stream": True,
    }

    # --- Chiamata in streaming --------------------------------------------
    response = requests.post(
        f"{base_url}/chat/completions", json=payload, timeout=120, stream=True
    )
    response.raise_for_status()
    # LM Studio puo' segnalare un errore con stato 200 e un JSON al posto
    # dello stream di eventi.
    if response.headers.get("content-type", "").startswith("application/json"):
        raise RuntimeError(response.json().get("error", response.text))

    pezzi = []
    for riga in response.iter_lines():
        # Gli eventi arrivano come righe "data: {json}"; decodifica esplicita
        # in UTF-8 perche' il server non dichiara il charset.
        riga = riga.decode("utf-8")
        if not riga.startswith("data: "):
            continue
        dati = riga[len("data: "):]
        if dati == "[DONE]":
            break
        evento = json.loads(dati)
        if "error" in evento:
            raise RuntimeError(evento["error"])
        pezzo = evento["choices"][0]["delta"].get("content")
        if pezzo:
            print(pezzo, end="", flush=True)
            pezzi.append(pezzo)
    print()
    return "".join(pezzi)


# --- Ciclo delle domande --------------------------------------------------
while True:
    domanda = input("Domanda (esci per terminare): ").strip()
    if not domanda:
        continue
    if domanda.lower() == "esci":
        break

    messages.append({"role": "user", "content": domanda})
    risposta = ""
    try:
        risposta = chiedi(messages)
        if not risposta:
            print("Risposta vuota: controllare reasoning_effort e max_tokens.")
    except requests.exceptions.Timeout:
        print("Attesa scaduta: controllare server, carico e tempi.")
    except requests.exceptions.ConnectionError:
        print("Connessione fallita: controllare server, URL e porta.")
    except requests.exceptions.HTTPError as errore:
        print("Errore HTTP:", errore.response.status_code, errore.response.text)
    except (json.JSONDecodeError, KeyError, IndexError):
        print("Stream non valido: evento data non interpretabile.")
    except RuntimeError as errore:
        print("Errore dal server:", errore)

    # Restano in memoria solo gli scambi riusciti: dopo un errore o una
    # risposta vuota la domanda viene tolta.
    if risposta:
        messages.append({"role": "assistant", "content": risposta})
    else:
        messages.pop()
