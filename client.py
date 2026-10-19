"""Client minimo per il server locale di LM Studio.

Legge le domande da terminale e stampa le risposte del modello in
streaming, man mano che vengono generate.
Ogni domanda e' indipendente (nessuna cronologia); le righe vuote
vengono ignorate e si esce scrivendo "esci".
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


def chiedi(domanda):
    """Invia la domanda, stampa la risposta in streaming e la restituisce."""
    messages = [system, {"role": "user", "content": domanda}]

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
        pezzo = json.loads(dati)["choices"][0]["delta"].get("content")
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

    try:
        risposta = chiedi(domanda)
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
