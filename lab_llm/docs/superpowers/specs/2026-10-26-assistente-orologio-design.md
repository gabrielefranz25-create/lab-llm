# Specifica: assistente da terminale con grafo LangGraph, LM Studio e strumento orologio

- **Stato**: BOZZA, in attesa di approvazione. Non verrà committata prima dell'approvazione.
- **Data**: 2026-10-26.
- **Branch**: `dev`.
- **Cartella del progetto**: `lab_llm/`.

---

## 1. Contesto e scopo

Esercizio della lezione 4 del corso «Deep Learning e LLM: costruire chatbot e agenti».
Si costruisce un'applicazione Python da terminale che:

1. riceve le domande dell'utente;
2. le passa a un modello locale servito da **LM Studio** sull'host;
3. organizza il flusso in un **grafo LangGraph esplicito**, con stato, nodi e instradamento leggibili;
4. permette al modello di chiedere uno **strumento orologio**, che il programma esegue davvero e il
   cui risultato torna al modello per la risposta finale;
5. conserva la conversazione **solo durante la sessione**;
6. si avvia sia da venv sia con **Docker Compose**.

Il progetto proseguirà nelle lezioni successive, che aggiungeranno altri strumenti, MCP, RAG e così
via. Per questo la struttura deve essere semplice e facile da estendere, senza anticipare nulla.
Il codice serve anche a studiare: ogni passo deve essere comprensibile leggendo il sorgente, i print
didattici (commentati) e il file di spiegazione.

## 2. Obiettivi, non obiettivi, anti-obiettivi

**Obiettivi**
- Chat da terminale funzionante con il modello reale di LM Studio.
- Cronologia in memoria per tutta la sessione; il contesto inviato al modello è controllato (§7).
- Strumento `ora_corrente` richiesto dal modello con il tool calling ed eseguito dal grafo, con il
  fuso orario sempre esplicito e **Europe/Rome come predefinito** (§6).
- Ogni chiamata allo strumento è visibile nei log (§10).
- Il numero di giri di strumento per domanda ha un limite (§5.4).
- Avvio con `docker compose run` e LM Studio sull'host (§9).
- Test automatici senza modello e prove reali separate, attivate esplicitamente (§11).
- Documentazione: `README.md`, `docs/COME_FUNZIONA.md` (cosa fa l'agente, quali strumenti usa) e,
  a lavoro finito, `docs/GUIDA_PASSO_PASSO.md` (come rifare tutto da zero con PowerShell).

**Non obiettivi (per ora)**
- MCP, RAG, workflow, altri strumenti oltre all'orologio.
- Interfacce web o grafiche, servizi cloud, persistenza su disco della cronologia.
- Streaming dei token (le risposte arrivano intere).
- Riassunto della cronologia generato dal modello (nodo di compattazione con LLM).
- Comandi speciali in chat oltre all'uscita.

**Anti-obiettivi (sarebbe un fallimento anche se "funziona")**
- Presentare un test con un modello finto come prova che gemma usa davvero lo strumento.
- Scrivere nel codice l'URL di LM Studio o l'identificativo del modello.
- L'ora data dal modello "a memoria", senza passare dallo strumento.
- Modificare `archivio/` (lezione 3 ed esercizio `assistente/`) o altre lezioni.
- Versionare `.env`, `.venv/`, cache o pesi dei modelli.

## 3. Ambiente verificato (2026-10-26)

| Elemento | Valore verificato | Conseguenza |
|---|---|---|
| Python | 3.13.14 (presente anche 3.10; **3.14 non installato**) | venv con `py -3.13 -m venv .venv`; immagine `python:3.13-slim` |
| Docker Compose | **v5.1.4** (plugin, la linea che segue la v2; la v1 non c'è) | comando `docker compose` (con lo spazio); file `compose.yaml` senza la chiave `version:` |
| Docker Engine | 29 installato; demone **spento** al momento del controllo | va avviato Docker Desktop prima della prova Docker |
| LM Studio | in ascolto su `http://localhost:1234`, API compatibile OpenAI | `LM_BASE_URL=http://localhost:1234/v1` in locale |
| Modello | `google/gemma-4-e2b`, Q4_K_M, `loaded`, capacità `tool_use`, **contesto caricato 8192 token** (max 131072) | finestra di contesto prudente (§7) |

Nota: nella shell corrente è attivo il venv della lezione 3. Prima di creare quello nuovo serve
`deactivate`.

## 4. Riordino della repository (già fatto, commit `b1ba069`)

```
repo-lab-llm_l4/
  .gitignore          (aggiunta la riga materiali/)
  archivio/           client.py, README.md, requirements.txt, .env.example, assistente/  (invariati)
  materiali/          PDF delle lezioni + altre_info.txt (ignorata da Git)
  lab_llm/            progetto nuovo (CLAUDE.md + questa specifica)
```

## 5. Architettura

### 5.1 Struttura dei file

```
lab_llm/
  CLAUDE.md
  README.md                 configurazione, avvio, test, diagnosi (solo comandi verificati)
  .gitignore                .env, .venv/, __pycache__/, .pytest_cache/
  .env.example              variabili d'ambiente di esempio (nessuna credenziale)
  .dockerignore             .venv, .env, tests, docs, cache
  requirements.txt          dipendenze di esecuzione, versioni fissate
  requirements-dev.txt      -r requirements.txt + pytest
  pytest.ini                testpaths, marker "reale"
  Dockerfile
  compose.yaml
  agente/
    __init__.py
    __main__.py             permette `python -m agente`
    main.py                 avvio: logging, configurazione, verifica modello, grafo, client
    config.py               lettura e validazione delle variabili d'ambiente
    llm.py                  collegamento a LM Studio (ChatOpenAI) e verifica del modello
    strumenti.py            strumento orologio
    graph.py                stato, nodi, instradamento, costruzione del grafo, finestra di contesto
    client.py               interfaccia da terminale (ciclo domanda/risposta, cronologia di sessione)
  tests/
    test_config.py
    test_strumenti.py
    test_contesto.py
    test_grafo.py
    test_client.py
    reale/
      test_lm_studio.py     prove con il modello vero (solo con PROVA_REALE=1)
  docs/
    COME_FUNZIONA.md
    GUIDA_PASSO_PASSO.md    (scritta alla fine)
    superpowers/specs/      questa specifica
    superpowers/plans/      il piano
```

Il nome del pacchetto è `agente/`. Così non si confonde con `archivio/assistente/` ed è il nome
che usa `python -m agente`.

### 5.2 Responsabilità dei moduli e dipendenze fra loro

```
main.py ──► config.py
   │──────► llm.py ──────► (langchain-openai, openai)
   │──────► strumenti.py
   │──────► graph.py ────► (langgraph)   riceve modello e strumenti già pronti
   └──────► client.py ───► usa solo il grafo compilato
```

- `graph.py` non importa `llm.py`: il modello gli viene passato da fuori. In questo modo i test
  usano un modello finto e nelle lezioni future si possono aggiungere strumenti senza cambiare il
  grafo.
- `client.py` non sa nulla di LM Studio: invoca il grafo e stampa la risposta.

### 5.3 Stato del grafo (agent state)

```python
class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]  # cronologia (Human/AI/Tool)
    passi_strumento: int                                   # giri di strumento nel turno corrente
```

- `messages` usa il reducer `add_messages`: i nodi restituiscono solo i messaggi **nuovi**, che
  vengono accodati.
- `passi_strumento` non ha reducer, quindi il valore restituito sostituisce quello precedente. Il
  client lo azzera a 0 a ogni nuova domanda.
- Il prompt di sistema **non** viene salvato nello stato: il nodo `llm` lo aggiunge ogni volta in
  testa a quanto invia al modello.
- Ogni nodo restituisce solo le chiavi che aggiorna, come visto a lezione.

### 5.4 Nodi, instradamento, limite

```
          ┌────────────────────────────────────────────┐
          ▼                                            │
START ─► llm ─► instrada_dopo_llm ─┬─ nessuna tool_call ──────────► END
                                   ├─ tool_call e passi < MAX ─► strumenti
                                   └─ tool_call e passi ≥ MAX ─► limite ─► END
```

| Nodo | Legge | Fa | Restituisce |
|---|---|---|---|
| `llm` | `messages` | costruisce `[SystemMessage] + finestra_contesto(messages)` e chiama il modello con gli strumenti collegati | `{"messages": [AIMessage]}` |
| `strumenti` | ultimo `AIMessage`, `passi_strumento` | esegue **ogni** tool_call dell'ultimo messaggio, registra un log per ciascuna, converte gli errori in testo | `{"messages": [ToolMessage, ...], "passi_strumento": passi + 1}` |
| `limite` | ultimo `AIMessage` | per ogni tool_call rimasta in sospeso aggiunge un `ToolMessage` «non eseguito: limite di N passaggi raggiunto», così la cronologia resta valida per l'API OpenAI; poi aggiunge un `AIMessage` per l'utente; registra un WARNING | `{"messages": [ToolMessage..., AIMessage]}` |

- `instrada_dopo_llm(state, max_passi)` è una funzione pura, testata da sola.
- Il nodo `strumenti` è scritto a mano e non usa `ToolNode` di LangGraph: così log, contatore e
  gestione degli errori restano visibili e didattici.
- Uno strumento sconosciuto (nome inventato dal modello) produce un `ToolMessage` di errore e non fa
  cadere il programma.
- **Rete di sicurezza**: `invoke(..., config={"recursion_limit": 2 * MAX_PASSI_STRUMENTO + 5})`.
  Con il nodo `limite` non dovrebbe mai scattare. Se scatta, il client mostra un errore leggibile.
- Testo del messaggio di limite: «Ho raggiunto il limite di N richieste allo strumento per questa
  domanda. Prova a riformularla in modo più semplice.»

### 5.5 Libreria LangGraph e API usate

- `langgraph==1.2.17`, l'ultima stabile al 2026-10-26.
- API usate:
  - `StateGraph(AgentState)`, `add_node`, `add_edge(START, "llm")`;
  - `add_conditional_edges("llm", instrada, {...})`, `add_edge("strumenti", "llm")`,
    `add_edge("limite", END)`;
  - `compile()`, `invoke()`.
- `add_messages` viene da `langgraph.graph.message`; i messaggi da `langchain_core.messages`.
- **Niente** checkpointer né `MemorySaver`: la cronologia di sessione la tiene il client (§8). È più
  esplicito, si testa facilmente e non c'è nulla da persistere.
- **Niente** prebuilt (`create_react_agent`, `ToolNode`), perché il grafo deve restare esplicito.
- `costruisci_grafo(modello, strumenti, max_passi, max_messaggi_contesto)` restituisce il grafo
  compilato.

## 6. Strumento orologio e gestione del fuso

**Firma vista dal modello**

```python
@tool
def ora_corrente(fuso_orario: str = "Europe/Rome") -> str:
    """Restituisce data e ora attuali nel fuso orario IANA indicato
    (es. "Europe/Rome", "America/New_York", "Asia/Tokyo"). Se l'utente non indica
    un luogo, usa il fuso predefinito italiano Europe/Rome."""
```

**Gestione del fuso**
- Il predefinito è `Europe/Rome`, configurabile con `FUSO_ORARIO_PREDEFINITO`. La docstring e il
  default dello strumento vengono costruiti con quel valore.
- Il nome IANA è validato con `zoneinfo.ZoneInfo`. Il database dei fusi arriva dal pacchetto
  `tzdata`, che serve perché né Windows né `python:3.13-slim` lo includono.
- **Esplicito sempre**: l'output riporta il nome del fuso, la sigla e l'offset UTC, anche quando si
  usa il predefinito.
- L'ora legale è gestita da `zoneinfo`: per esempio Roma è CEST (+02:00) d'estate e CET (+01:00)
  d'inverno.

**Output** (stringa, in italiano):
```
Fuso orario: Europe/Rome (CET, UTC+01:00)
Data: lunedì 26 ottobre 2026
Ora: 17:42:10
ISO 8601: 2026-10-26T17:42:10+01:00
```
- Giorni e mesi in italiano vengono da tabelle nel codice, non dal `locale` di sistema, che nel
  container non è affidabile.

**Errori**: con un fuso non valido (es. `"Roma"`) restituisce al modello
«Errore: fuso orario 'Roma' non riconosciuto. Usa un nome IANA come 'Europe/Rome'.», con un log
WARNING. Il programma non si ferma e il modello può riprovare entro il limite di passaggi.

**Testabilità**: la logica pura è `calcola_ora(fuso: str, adesso: datetime | None = None) -> str`.
I test passano un istante fisso in UTC (es. `2026-07-15T10:00:00Z` e `2026-01-15T10:00:00Z`).

## 7. Modello e contesto

**Collegamento** (`llm.py`)
```python
ChatOpenAI(
    base_url=LM_BASE_URL, model=LM_MODEL,
    api_key="lm-studio",        # LM Studio non verifica la chiave: valore fittizio, non una credenziale
    temperature=0,              # risposte più stabili, tool calling più affidabile
    timeout=LM_TIMEOUT,         # default 60 s
    max_retries=1,
).bind_tools([ora_corrente])
```
- Libreria: `langchain-openai==1.7.2`. Motivo: `bind_tools` traduce lo strumento nello schema
  OpenAI, e i messaggi prodotti (`AIMessage.tool_calls`) sono quelli che LangGraph gestisce con
  `add_messages`.
- **Verifica all'avvio** (`verifica_modello`):
  - chiama `GET {LM_BASE_URL}/models` con il client `openai==3.37.0` (già dipendenza di
    langchain-openai, dichiarata esplicitamente perché la importiamo);
  - controlla che `LM_MODEL` sia nell'elenco;
  - se il server non risponde, o il modello non c'è, stampa un messaggio con l'elenco dei modelli
    disponibili e il suggerimento pratico ("avvia LM Studio", "carica il modello",
    "controlla LM_BASE_URL"), poi esce con codice 1.

**Prompt di sistema** (in italiano, nel codice di `graph.py`):
> Sei l'assistente del laboratorio. Rispondi in italiano, in modo breve e chiaro.
> Per qualsiasi domanda su data, ora o giorno attuali usa SEMPRE lo strumento `ora_corrente`:
> non inventare l'ora. Se l'utente non indica un luogo usa il fuso predefinito {FUSO}
> (ora italiana). Per altri luoghi passa il nome IANA del fuso (es. "Asia/Tokyo").
> Nella risposta indica sempre a quale fuso orario si riferisce l'ora.

**Finestra di contesto** (`finestra_contesto(messaggi, n)`, funzione pura in `graph.py`):
- Lo stato conserva l'intera cronologia. Al modello arrivano solo gli ultimi `n` messaggi
  (`MAX_MESSAGGI_CONTESTO`, default 20).
- La finestra viene spostata in avanti finché il primo messaggio è un `HumanMessage`. In questo modo
  non parte mai da un `ToolMessage` orfano o da un `AIMessage` con tool_call senza risposta.
- Se l'ultimo turno da solo supera `n` (caso estremo), si tiene comunque dall'ultimo `HumanMessage`
  in poi.
- Con 8192 token caricati, 20 messaggi brevi stanno ampiamente nel contesto. Il valore si può
  cambiare da variabile d'ambiente.
- Quando la finestra taglia qualcosa viene scritto un log DEBUG
  («contesto: inviati 20 di 34 messaggi»).

## 8. Sessione tipica (UX)

**Avvio locale**: `python -m agente` (dalla cartella `lab_llm/`, con il venv attivo).

```
Assistente del laboratorio
Modello: google/gemma-4-e2b  |  Server: http://localhost:1234/v1  |  Fuso predefinito: Europe/Rome
Scrivi una domanda e premi Invio. Per uscire: esci (oppure Ctrl+C).

Tu> Ciao, chi sei?
Assistente> Sono l'assistente del laboratorio: posso rispondere alle tue domande e dirti l'ora
in qualsiasi fuso orario.

Tu> Che ore sono?
2026-10-26 17:42:10 INFO  agente.graph | strumento ora_corrente {'fuso_orario': 'Europe/Rome'} -> Fuso orario: Europe/Rome (CET, UTC+01:00) | Data: lunedì 26 ottobre 2026 | Ora: 17:42:10 | ...
Assistente> Sono le 17:42 di lunedì 26 ottobre 2026, ora italiana (Europe/Rome, CET).

Tu> E a Tokyo?
2026-10-26 17:42:31 INFO  agente.graph | strumento ora_corrente {'fuso_orario': 'Asia/Tokyo'} -> ...
Assistente> A Tokyo sono le 01:42 di martedì 27 ottobre 2026 (Asia/Tokyo, JST, UTC+09:00).

Tu> Di cosa abbiamo parlato?
Assistente> Mi hai salutato e mi hai chiesto l'ora in Italia e poi a Tokyo.

Tu> esci
Sessione terminata. La cronologia non è stata salvata.
```

**Regole dell'interfaccia** (`client.py`)
- Il prompt è `Tu> ` e le risposte iniziano con `Assistente> `. Le righe di log vanno su **stderr**,
  la chat su **stdout**.
- Comandi di uscita: `esci`, `exit`, `quit` (senza distinzione tra maiuscole e minuscole), Ctrl+C, e
  EOF (Ctrl+Z e Invio su Windows). Tutti terminano senza traceback, con il messaggio di chiusura.
- Un input vuoto o fatto di soli spazi viene ignorato e il prompt viene riproposto.
- Cronologia: `cronologia: list[AnyMessage]` nel client. A ogni turno
  `risultato = grafo.invoke({"messages": cronologia + [HumanMessage(testo)], "passi_strumento": 0})`
  e poi `cronologia = risultato["messages"]`.
- Se LM Studio si interrompe durante la sessione (connessione rifiutata, timeout, errore HTTP):
  - si stampa `Assistente> [errore] Non riesco a contattare LM Studio su <URL>: <motivo breve>.`;
  - si registra un log ERROR;
  - la domanda fallita **non** entra nella cronologia e la sessione continua.
- Nessun comando di reset: per ripartire si esce e si rientra (la cronologia si perde comunque).

## 9. Docker

**Dockerfile**
```dockerfile
FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY agente/ agente/
RUN useradd --create-home appuser
USER appuser
CMD ["python", "-m", "agente"]
```
- Nell'immagine ci sono solo le dipendenze di esecuzione: niente test, niente pytest.

**compose.yaml**
```yaml
services:
  assistente:
    build: .
    env_file: .env
    environment:
      LM_BASE_URL: http://host.docker.internal:1234/v1   # dal container, l'host non è "localhost"
    extra_hosts:
      - "host.docker.internal:host-gateway"
    stdin_open: true
    tty: true
```

**Comandi** (PowerShell, dalla cartella `lab_llm/`):
```powershell
docker compose build
docker compose run --rm assistente
```
- Si usa `run` e non `up`, perché la chat ha bisogno di uno stdin interattivo. `--rm` elimina il
  container all'uscita: coerente con «nessuna persistenza».
- LM Studio resta sull'host. Se il container non lo raggiunge, va attivata in LM Studio l'opzione
  «Serve on Local Network» (Developer → Server Settings).
  - Lo verifichiamo nella prova reale e documentiamo nel README quello che risulta davvero
    necessario.

## 10. Log e print didattici

**Log** (modulo `logging`, configurato in `main.py`)
- Output su stderr, con formato `%(asctime)s %(levelname)-5s %(name)s | %(message)s` e date nel
  formato `%Y-%m-%d %H:%M:%S`.
- Il livello viene da `LOG_LEVEL` (default `INFO`).
- I logger rumorosi di terze parti (`httpx`, `openai`, `httpcore`) sono forzati a `WARNING`;
  altrimenti ogni richiesta HTTP verrebbe stampata.

| Evento | Livello | Esempio |
|---|---|---|
| avvio | INFO | `avvio: modello=google/gemma-4-e2b server=http://localhost:1234/v1 max_passi=3 contesto=20` |
| chiamata allo strumento (sempre) | INFO | `strumento ora_corrente {'fuso_orario': 'Asia/Tokyo'} -> <risultato su una riga>` |
| fuso non valido / strumento sconosciuto | WARNING | `strumento ora_corrente: fuso 'Roma' non riconosciuto` |
| limite raggiunto | WARNING | `limite di 3 passaggi raggiunto: 1 tool_call non eseguite` |
| finestra di contesto applicata | DEBUG | `contesto: inviati 20 di 34 messaggi` |
| errore di collegamento | ERROR | `LM Studio non raggiungibile su ...: Connection refused` |

**Print didattici** (richiesta da `altre_info.txt`)
- C'è un `print("[passo] ...")` con una breve spiegazione:
  - all'ingresso di ogni nodo;
  - a ogni decisione di instradamento;
  - prima di ogni chiamata al modello (quanti messaggi vengono inviati);
  - a ogni turno nel client.
- Li tengo attivi mentre verifico ogni incremento. Nel codice committato sono **commentati** (`#
  print(...)`), così non sporcano la chat né i test, e per studiarli basta togliere il commento.

## 11. Variabili d'ambiente

| Variabile | Obbligatoria | Default | Locale (`.env`) | Docker | Note |
|---|---|---|---|---|---|
| `LM_BASE_URL` | sì | — | `http://localhost:1234/v1` | sovrascritta in compose: `http://host.docker.internal:1234/v1` | |
| `LM_MODEL` | sì | — | `google/gemma-4-e2b` | da `.env` | va copiato da `GET /v1/models`; in `.env.example` c'è un segnaposto |
| `FUSO_ORARIO_PREDEFINITO` | no | `Europe/Rome` | | | validato all'avvio |
| `MAX_PASSI_STRUMENTO` | no | `3` | | | intero ≥ 1 |
| `MAX_MESSAGGI_CONTESTO` | no | `20` | | | intero ≥ 2 |
| `LM_TIMEOUT` | no | `60` | | | secondi |
| `LOG_LEVEL` | no | `INFO` | | | `DEBUG` mostra anche la finestra di contesto |
| `PROVA_REALE` | no | non impostata | | | solo per i test reali (§12) |

- `config.py` carica `.env` con `python-dotenv` senza sovrascrivere le variabili già impostate. In
  questo modo, in Docker, il valore di `environment:` vince su `.env`.
- Una variabile obbligatoria mancante, o un valore non valido, produce un errore chiaro con il nome
  della variabile e l'uscita con codice 1, senza traceback.
- `.env.example` (committato) contiene tutte le variabili con commenti e il segnaposto
  `LM_MODEL=ID_RESTITUITO_DA_GET_v1_models`. `.env` (non committato) contiene il valore reale.

## 12. Test e verifiche

**Test automatici** (`pytest`, senza modello, senza rete, ripetibili)

| File | Cosa verifica |
|---|---|
| `test_strumenti.py` | ora in un istante fisso per Europe/Rome in inverno (CET +01:00) e in estate (CEST +02:00), Asia/Tokyo, America/New_York; giorno e mese in italiano; fuso predefinito usato quando l'argomento manca; fuso non valido → messaggio d'errore e nessuna eccezione |
| `test_contesto.py` | finestra più corta della cronologia; la finestra parte sempre da `HumanMessage`; le coppie tool_call/ToolMessage non vengono spezzate; caso dell'ultimo turno più lungo di `n` |
| `test_grafo.py` | con un **modello finto** a risposte predefinite: (a) risposta diretta → END; (b) tool_call → strumento eseguito davvero (con l'istante controllato) → ToolMessage → risposta finale; (c) tool_call ripetute → nodo `limite` dopo MAX passaggi, con ToolMessage di chiusura per ogni chiamata in sospeso; (d) strumento sconosciuto; (e) log INFO della chiamata (caplog); (f) il prompt di sistema e la finestra arrivano al modello |
| `test_client.py` | cronologia mantenuta su due turni; uscita con `esci`/EOF; input vuoto ignorato; errore di collegamento simulato → messaggio leggibile e cronologia invariata (I/O simulato con monkeypatch) |
| `test_config.py` | variabili obbligatorie mancanti → errore chiaro; default; valori non validi |

Comando: `python -m pytest`. I test reali vengono saltati.

**Prove reali** (attivate in modo esplicito, richiedono LM Studio acceso)
- `tests/reale/test_lm_studio.py`, con il marker `reale`, saltato se `PROVA_REALE` non vale `1`:
  1. `verifica_modello` trova `LM_MODEL` sul server;
  2. alla domanda «Che ore sono a Tokyo?», la cronologia contiene un `AIMessage` con tool_call
     `ora_corrente`, argomento `Asia/Tokyo`, e il relativo `ToolMessage`. La risposta finale non è
     vuota;
  3. alla domanda «Che ore sono?» viene chiamato `ora_corrente` con il predefinito (assente o
     `Europe/Rome`).
- Comando: `$env:PROVA_REALE="1"; python -m pytest -m reale -v`.
- Se gemma non chiama lo strumento il test **fallisce**, e lo riporto così com'è. Un modello finto non
  conta come prova.

**Prova Docker (manuale)**, con passi ed esito attesi nel README:
1. Docker Desktop avviato.
2. `docker compose build` termina con successo.
3. `docker compose run --rm assistente` mostra l'intestazione con il server `host.docker.internal`.
4. «Che ore sono?» produce un log dello strumento e una risposta con l'ora italiana.
5. `esci` chiude e il container viene rimosso.

## 13. Dipendenze (versioni fissate, ultime stabili al 2026-10-26)

| Pacchetto | Versione | Motivo |
|---|---|---|
| `langgraph` | 1.2.17 | grafo esplicito (stato, nodi, archi condizionali) |
| `langchain-openai` | 1.7.2 | `ChatOpenAI` verso l'API compatibile OpenAI di LM Studio, `bind_tools` |
| `langchain-core` | 1.7.0 | messaggi e decoratore `@tool` (importato direttamente, quindi fissato) |
| `openai` | 3.37.0 | elenco dei modelli per la verifica all'avvio (importato direttamente) |
| `python-dotenv` | 1.2.4 | lettura di `.env` |
| `tzdata` | 2026.5 | database dei fusi IANA per `zoneinfo` su Windows e nell'immagine slim |
| `pytest` (solo dev) | 9.1.1 | test |

Le versioni vengono ricontrollate all'installazione nel venv. Se una combinazione risulta
incompatibile, mi fermo e te lo segnalo prima di cambiarla.

## 14. Git e incrementi

- Branch `dev`, Conventional Commits in italiano, `git status` e controllo del diff prima di ogni
  commit, staging selettivo, nessun push.
- Il venv sta in `lab_llm/.venv`, ignorato da Git.
- Gli incrementi previsti, ciascuno con verifica prima del commit, saranno dettagliati nel piano:
  1. impalcatura: `.gitignore`, `.env.example`, requirements, `pytest.ini`, venv;
  2. config;
  3. strumento orologio con test;
  4. finestra di contesto con test;
  5. grafo con test;
  6. llm e verifica del modello;
  7. client e main con test;
  8. prova reale;
  9. Docker e prova Docker;
  10. README e `COME_FUNZIONA.md`;
  11. `GUIDA_PASSO_PASSO.md`.

## 15. Documentazione finale

- `README.md`: requisiti, configurazione (`.env`), avvio locale, avvio Docker, test, prove reali,
  diagnosi (LM Studio spento, modello non caricato, container che non raggiunge l'host, fuso non
  valido). Solo comandi verificati.
- `docs/COME_FUNZIONA.md`: che cosa è stato fatto, che cosa fa l'agente, schema del grafo (anche in
  Mermaid, generato con `get_graph().draw_mermaid()`), stato, nodi, strumento, contesto, log.
- `docs/GUIDA_PASSO_PASSO.md`: da zero al risultato, con i file da creare e cosa scrivere in
  ciascuno, più i comandi PowerShell (venv, git, Docker, test, prova reale con LM Studio).

## 16. Lasciato a chi implementa

- I nomi delle funzioni interne non elencati qui e la formulazione esatta dei messaggi di
  log e print.
- La forma del modello finto nei test, purché supporti `bind_tools` o venga iniettato al suo posto.
- La formattazione su una riga del risultato dello strumento nei log.
