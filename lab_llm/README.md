# Assistente del laboratorio

Chat da terminale in Python che usa un grafo LangGraph esplicito per parlare con un modello servito da
**LM Studio** sull'host. Il modello può chiedere l'ora con lo strumento `ora_corrente`, che il
programma esegue davvero e che indica sempre il fuso orario (predefinito `Europe/Rome`).
La cronologia resta in memoria per la durata della sessione: non viene salvata.

Come funziona dentro (grafo, stato, nodi, strumento, log): [docs/COME_FUNZIONA.md](docs/COME_FUNZIONA.md).
Docker su Windows e risoluzione dei problemi: [docs/GUIDA_DOCKER.md](docs/GUIDA_DOCKER.md).

Tutti i comandi qui sotto sono stati eseguiti su Windows 11 con PowerShell 5.1, dalla cartella
`lab_llm/`, e partono da questa cartella.

## Requisiti

- Python 3.13 (launcher `py`).
- LM Studio con il server avviato (Developer → Start Server, porta 1234) e il modello caricato.
  Modello usato nelle prove: `google/gemma-4-e2b`.
- Solo per Docker: Docker Desktop con backend WSL 2.

## Installazione

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

- `requirements.txt` contiene le dipendenze di esecuzione (versioni fissate); `requirements-dev.txt`
  aggiunge `pytest`.
- Se nel terminale è attivo il venv di un altro progetto, prima dai `deactivate`.

## Configurazione (`.env`)

```powershell
Copy-Item .env.example .env
```

Poi completa `.env`. L'identificativo del modello va copiato da quello che restituisce il server:

```powershell
Invoke-RestMethod http://localhost:1234/v1/models | Select-Object -ExpandProperty data | Select-Object id
```

| Variabile | Obbligatoria | Default | Note |
|---|---|---|---|
| `LM_BASE_URL` | sì | — | `http://localhost:1234/v1`; in Docker la sovrascrive `compose.yaml` |
| `LM_MODEL` | sì | — | l'`id` restituito da `/v1/models`, per esempio `google/gemma-4-e2b` |
| `FUSO_ORARIO_PREDEFINITO` | no | `Europe/Rome` | nome IANA, validato all'avvio |
| `MAX_PASSI_STRUMENTO` | no | `3` | giri di strumento per domanda, intero ≥ 1 |
| `MAX_MESSAGGI_CONTESTO` | no | `20` | messaggi della cronologia inviati al modello, intero ≥ 2 |
| `LM_TIMEOUT` | no | `60` | secondi di attesa per una risposta |
| `LOG_LEVEL` | no | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `PROVA_REALE` | no | — | solo per i test con LM Studio vero (vedi sotto) |

`.env` resta fuori da Git; `.env.example` non contiene credenziali (LM Studio non usa chiavi).
Le variabili già impostate nel terminale hanno la precedenza su `.env`.

## Avvio locale

```powershell
.\.venv\Scripts\Activate.ps1
python -m agente
```

```
Assistente del laboratorio
Modello: google/gemma-4-e2b  |  Server: http://localhost:1234/v1  |  Fuso predefinito: Europe/Rome
Scrivi una domanda e premi Invio. Per uscire: esci (oppure Ctrl+C).

Tu> Che ore sono?
... INFO  agente.graph | strumento ora_corrente {} -> Fuso orario: Europe/Rome (CET, UTC+01:00) | ...
Assistente> ...
```

- Per uscire: `esci`, `exit`, `quit`, Ctrl+C oppure Ctrl+Z e Invio.
- I log vanno su stderr, la chat su stdout.
- Prova non interattiva: `"Che ore sono?`nesci" | python -m agente`.

## Avvio con Docker

LM Studio resta sull'host; il container lo raggiunge su `http://host.docker.internal:1234/v1`.

```powershell
docker compose build
docker compose run --rm assistente
```

- Si usa `run` e non `up`, perché la chat ha bisogno di uno stdin interattivo; `--rm` elimina il
  container all'uscita.
- Verificato su questo PC con LM Studio in ascolto su `0.0.0.0:1234` («Serve on Local Network»
  attivo). Il caso con l'opzione disattivata non è stato provato.
- La chat con la tty interattiva va ancora provata nel terminale; è stata verificata con l'input
  passato via pipe: `"Che ore sono?`nesci" | docker compose run --rm -T assistente`.

## Test

```powershell
python -m pytest
```

Esito atteso: tutti i test passano e le 3 prove reali risultano `skipped`. I test non richiedono
LM Studio: il grafo usa un modello finto e lo strumento un istante fissato.

### Prove reali con LM Studio

Richiedono LM Studio acceso con il modello di `.env` caricato. Verificano che il modello chiami davvero
`ora_corrente` (con `Asia/Tokyo` per Tokyo, e con il fuso predefinito quando non c'è un luogo).

```powershell
$env:PROVA_REALE="1"; python -m pytest -m reale -v
Remove-Item Env:PROVA_REALE
```

Esito del 2026-11-03: `3 passed` in circa un minuto.

## Diagnosi

Messaggi verificati provocando ciascun errore. In tutti i casi il programma esce con codice 1, senza
traceback.

| Sintomo | Causa | Soluzione |
|---|---|---|
| `Errore di configurazione: Variabile d'ambiente obbligatoria mancante: LM_BASE_URL (vedi .env.example).` | manca `.env` (o la variabile) | `Copy-Item .env.example .env` e completa i valori |
| `Errore: LM Studio non risponde su http://localhost:1234/v1 (Connection error.).` | LM Studio o il suo server spenti, oppure `LM_BASE_URL` sbagliato | avvia il server in LM Studio e controlla l'indirizzo; il messaggio arriva dopo circa 15 s di tentativi |
| `Errore: Il modello '...' non è disponibile su ...` seguito da `Modelli disponibili: ...` | `LM_MODEL` non corrisponde a un modello del server | carica il modello in LM Studio o copia in `.env` uno degli `id` elencati |
| `Errore di configurazione: FUSO_ORARIO_PREDEFINITO: fuso orario 'Roma' non riconosciuto. ...` | nome del fuso non IANA | usa un nome come `Europe/Rome` |
| `Errore di configurazione: MAX_PASSI_STRUMENTO deve essere almeno 1, non 0.` | valore numerico fuori intervallo | correggi il valore in `.env` |
| `Assistente> [errore] Non riesco a contattare LM Studio su ...` durante la chat | LM Studio si è fermato a sessione avviata | riavvia LM Studio e ripeti la domanda: la sessione e la cronologia restano valide |
| Dal container: `LM Studio non risponde su http://host.docker.internal:1234/v1` | il container non raggiunge l'host | [docs/GUIDA_DOCKER.md](docs/GUIDA_DOCKER.md), sezione 6 |

Se il modello sbaglia il fuso (per esempio passa `"Roma"`), lo strumento gli restituisce un messaggio
d'errore e il modello può riprovare entro `MAX_PASSI_STRUMENTO` giri: il programma non si ferma.

## Struttura

```
lab_llm/
├── agente/            codice: config, strumenti, graph, llm, client, main
├── tests/             test automatici; tests/reale/ = prove con LM Studio (PROVA_REALE=1)
├── docs/              COME_FUNZIONA, GUIDA_DOCKER, specifica e piano (superpowers/)
├── .env.example       variabili d'esempio (.env reale fuori da Git)
├── requirements.txt   requirements-dev.txt   pytest.ini
└── Dockerfile         compose.yaml           .dockerignore
```
