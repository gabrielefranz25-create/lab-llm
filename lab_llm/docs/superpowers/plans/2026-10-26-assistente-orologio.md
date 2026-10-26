# Assistente orologio (lab_llm): piano di implementazione

> **Per chi esegue:** SOTTO-SKILL OBBLIGATORIA: `superpowers:executing-plans`, consigliata qui, oppure
> `superpowers:subagent-driven-development`. I passi usano le caselle `- [ ]`.

**Obiettivo**: chat da terminale in Python che usa un grafo LangGraph esplicito per parlare con
`google/gemma-4-e2b` in LM Studio, con uno strumento orologio eseguito davvero, un limite di passaggi,
la cronologia di sessione e l'avvio in Docker Compose.

**Architettura**
- Il pacchetto `agente/` è diviso in moduli piccoli: `config`, `strumenti`, `graph`, `llm`, `client`,
  `main`.
- Il grafo (`llm → strumenti → llm`, più il nodo `limite`) riceve dall'esterno il modello e gli
  strumenti, così i test usano un modello finto.
- Il client tiene la cronologia in una lista.

**Tecnologie**: Python 3.13, langgraph 1.2.17, langchain-openai 1.7.2, langchain-core 1.7.0,
openai 3.37.0, python-dotenv 1.2.4, tzdata 2026.5, pytest 9.1.1, Docker Compose v5.

**Specifica**: `lab_llm/docs/superpowers/specs/2026-10-26-assistente-orologio-design.md` (approvata).
Le sezioni indicate con §N si riferiscono a quella.

## Contesto
La specifica è approvata e la repository è già riordinata (commit `b1ba069`). Questo piano porta
dalla cartella `lab_llm/`, che oggi contiene solo `CLAUDE.md` e la specifica, all'applicazione
completa, testata e documentata.

**Stato al 2026-10-26**:
- specifica approvata e committata, piano salvato qui; nessun task è stato ancora iniziato;
- il piano va riletto e approvato dall'utente all'inizio della prossima sessione;
- modalità di esecuzione consigliata: Native (vedi «Esecuzione»).

## Organizzazione di cartelle e file (stato finale)
```
repo-lab-llm_l4/                       radice della repository (branch dev)
├── .gitignore                         regole comuni + materiali/
├── archivio/                          lezione 3 ed esercizio di lezione (non si tocca)
│   ├── client.py  README.md  requirements.txt  .env.example
│   └── assistente/  (graph.py, __main__.py, base.txt)
├── materiali/                         PDF delle lezioni + altre_info.txt (fuori da Git)
└── lab_llm/                           ◄ PROGETTO
    ├── CLAUDE.md                      regole di lavoro per Claude
    ├── README.md                      configurazione, avvio, test, diagnosi
    ├── .gitignore  .dockerignore
    ├── .env.example                   variabili d'esempio (in Git)
    ├── .env                           variabili reali (fuori da Git)
    ├── .venv/                         ambiente virtuale (fuori da Git)
    ├── requirements.txt               dipendenze di esecuzione (versioni fissate)
    ├── requirements-dev.txt           + pytest
    ├── pytest.ini                     configurazione dei test e marker "reale"
    ├── Dockerfile  compose.yaml       avvio in Docker
    ├── agente/                        CODICE
    │   ├── __init__.py
    │   ├── __main__.py                permette `python -m agente`
    │   ├── main.py                    avvio: log → config → verifica modello → grafo → client
    │   ├── config.py                  variabili d'ambiente → Config
    │   ├── strumenti.py               strumento ora_corrente (fuso predefinito Europe/Rome)
    │   ├── graph.py                   stato, nodi llm/strumenti/limite, instradamento, contesto
    │   ├── llm.py                     ChatOpenAI verso LM Studio + verifica del modello
    │   └── client.py                  chat da terminale e cronologia di sessione
    ├── tests/                         TEST
    │   ├── test_config.py  test_strumenti.py  test_contesto.py
    │   ├── test_grafo.py   test_llm.py        test_client.py
    │   └── reale/test_lm_studio.py    prove con LM Studio vero (PROVA_REALE=1)
    └── docs/                          DOCUMENTAZIONE
        ├── COME_FUNZIONA.md           cosa fa l'agente, grafo, strumenti
        ├── GUIDA_DOCKER.md            Docker su Windows: hypervisor, WSL 2, problemi e soluzioni
        ├── GUIDA_PASSO_PASSO.md       ricostruire tutto da zero
        └── superpowers/
            ├── specs/2026-10-26-assistente-orologio-design.md
            └── plans/2026-10-26-assistente-orologio.md
```

## Vincoli globali
- Si lavora **solo** in `lab_llm/`, sul branch `dev`. Push solo su richiesta dell'utente. `archivio/` e `materiali/` non si
  toccano.
- Tutti i comandi partono da `lab_llm/`, con il venv `lab_llm/.venv` creato con `py -3.13 -m venv .venv`
  (prima `deactivate` del venv della lezione 3).
- URL e modello solo da variabili d'ambiente. Il modello è `google/gemma-4-e2b`, preso da
  `GET /v1/models`.
- Fuso predefinito `Europe/Rome`. Defaults: `MAX_PASSI_STRUMENTO=3`, `MAX_MESSAGGI_CONTESTO=20`,
  `LM_TIMEOUT=60`, `LOG_LEVEL=INFO`.
- Logger con nome di modulo (`logging.getLogger(__name__)`). I log vanno su stderr, la chat su stdout.
- Print didattici `print("[passo] …")` in ogni nodo, nella decisione di instradamento, prima della
  chiamata al modello e a ogni turno del client.
  - Li tengo attivi mentre verifico.
  - Prima di ogni commit li commento con `# print(...)`.
- Messaggi all'utente, docstring e commenti in italiano.
- Commit con Conventional Commits in italiano. Prima di ogni commit: `git status`, `git diff`, staging
  selettivo. Nessun file `.env`, `.venv` o cache.
- Il trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` va in ogni commit.

## Punti da verificare con attenzione (Review Focus)
1. **Domanda senza luogo** («Che ore sono?»): lo strumento chiamato con `{}` usa `Europe/Rome` →
   `test_ora_corrente_senza_argomenti_usa_predefinito` (Task 2).
2. **Argomenti sbagliati dal modello** (`"Roma"`, `null`, tipo errato): il risultato è un
   `ToolMessage` d'errore, senza eccezioni → `test_fuso_non_valido_*` (Task 2) e
   `test_argomenti_non_validi_diventano_toolmessage_errore` (Task 4).
3. **LM Studio che cade a metà sessione**: compare il messaggio leggibile, la cronologia resta
   invariata e la sessione continua → `test_errore_collegamento_non_altera_cronologia` (Task 6).
4. **Più tool_call nello stesso messaggio**: vengono eseguite tutte, con un `ToolMessage` per ciascun
   `tool_call_id` → `test_piu_tool_call_nello_stesso_messaggio` (Task 4).
5. **Risposta finale vuota** (modelli piccoli, a volte): il client stampa
   `Assistente> (il modello non ha restituito testo)` → `test_risposta_vuota` (Task 6).

---

### Task 1: impalcatura e configurazione

**File**
- Creare `lab_llm/.gitignore` con `.env`, `.venv/`, `__pycache__/`, `.pytest_cache/`.
- Creare `lab_llm/.env.example`, con tutte le variabili del §11, commenti e
  `LM_MODEL=ID_RESTITUITO_DA_GET_v1_models`.
- Creare `lab_llm/.env`, solo in locale e non committato, con il modello reale.
- Creare `lab_llm/requirements.txt` con i 6 pacchetti di esecuzione del §13, in forma `==`.
- Creare `lab_llm/requirements-dev.txt` con `-r requirements.txt` e `pytest==9.1.1`.
- Creare `lab_llm/pytest.ini` con `[pytest]`, `testpaths = tests` e
  `markers = reale: prove con LM Studio reale (richiede PROVA_REALE=1)`.
- Creare `lab_llm/agente/__init__.py`, vuoto con una docstring.
- Creare `lab_llm/agente/config.py` e `lab_llm/tests/test_config.py`.

**Interfacce prodotte**
```python
class ErroreConfigurazione(Exception): ...
@dataclass(frozen=True)
class Config:
    lm_base_url: str; lm_model: str; fuso_orario_predefinito: str
    max_passi_strumento: int; max_messaggi_contesto: int; lm_timeout: float; log_level: str
def carica_config(ambiente: Mapping[str, str] | None = None) -> Config
```
- Con `ambiente=None` chiama `load_dotenv(override=False)` e poi legge `os.environ`.
- Un valore stringa vuota conta come assente.

**Passi**
- [ ] Creare il venv:
  `deactivate` (se attivo), poi `py -3.13 -m venv .venv`, `.\.venv\Scripts\Activate.ps1`,
  `python -m pip install -r requirements-dev.txt`.
  - Atteso: installazione riuscita.
  - Se fallisce per incompatibilità: **STOP**, lo segnalo e non cambio le versioni.
- [ ] Scrivere `tests/test_config.py`:
  - `test_valori_minimi_e_default`: con `{"LM_BASE_URL": "http://h:1/v1", "LM_MODEL": "m"}` si ottiene
    fuso `"Europe/Rome"`, passi `3`, contesto `20`, timeout `60.0` e log `"INFO"`.
  - `test_variabile_obbligatoria_mancante` (parametrizzato su `LM_BASE_URL` e `LM_MODEL`): solleva
    `ErroreConfigurazione` e il messaggio contiene il nome della variabile.
  - `test_valori_personalizzati`: tutte le variabili impostate vengono lette, convertite e il livello
    di log diventa maiuscolo.
  - `test_valori_non_validi` (parametrizzato): `MAX_PASSI_STRUMENTO="0"`, `"tre"`,
    `MAX_MESSAGGI_CONTESTO="1"`, `LM_TIMEOUT="-5"`, `FUSO_ORARIO_PREDEFINITO="Roma"` e
    `LOG_LEVEL="CHIACCHIERA"` sollevano tutti `ErroreConfigurazione` con il nome della variabile.
- [ ] Eseguire `python -m pytest tests/test_config.py -v`.
  - Atteso: FAIL, `ModuleNotFoundError: agente.config`.
- [ ] Implementare `config.py`:
  - limiti dal §11 (passi ≥ 1, contesto ≥ 2, timeout > 0);
  - fuso validato con `ZoneInfo` (gestendo `ZoneInfoNotFoundError` e `ValueError`);
  - livello di log tra `DEBUG`, `INFO`, `WARNING`, `ERROR`.
- [ ] Eseguire `python -m pytest -v`. Atteso: tutti PASS.
- [ ] Fare il commit `feat(config): impalcatura del progetto e lettura delle variabili d'ambiente`.
  - Includere: `.gitignore`, `.env.example`, requirements, `pytest.ini`, `agente/__init__.py`,
    `config.py`, il test.
  - Controllare che `git status` **non** mostri `.env` né `.venv`.

### Task 2: strumento orologio

**File**: creare `lab_llm/agente/strumenti.py` e `lab_llm/tests/test_strumenti.py`.

**Interfacce**
```python
def calcola_ora(fuso: str, adesso: datetime | None = None) -> str
def crea_ora_corrente(fuso_predefinito: str = "Europe/Rome",
                      orologio: Callable[[], datetime] | None = None) -> BaseTool  # nome "ora_corrente"
```
- `adesso` e `orologio` restituiscono datetime **aware** in UTC. Se mancano si usa
  `datetime.now(timezone.utc)`.
- Lo strumento si costruisce con `langchain_core.tools.tool("ora_corrente", description=...)`. La
  descrizione nomina il predefinito ed è il testo del §6.
- Argomento `fuso_orario: str = fuso_predefinito`.
- Formato di uscita (4 righe, §6):
  `Fuso orario: {fuso} ({sigla}, UTC{±HH:MM})`, `Data: {giorno} {g} {mese} {aaaa}`, `Ora: HH:MM:SS`,
  `ISO 8601: {isoformat senza microsecondi}`.
- Giorni e mesi vengono da tuple `GIORNI` e `MESI` in italiano.
- Con un fuso non valido restituisce esattamente
  `Errore: fuso orario '{fuso}' non riconosciuto. Usa un nome IANA come 'Europe/Rome'.` e scrive un
  log WARNING.

**Passi**
- [ ] Scrivere i test, con `INVERNO = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)` e
  `ESTATE = datetime(2026, 7, 15, 10, 0, tzinfo=timezone.utc)`:
  - `test_roma_inverno`: il risultato contiene `"Europe/Rome (CET, UTC+01:00)"`,
    `"Data: giovedì 15 gennaio 2026"`, `"Ora: 11:00:00"` e
    `"ISO 8601: 2026-01-15T11:00:00+01:00"`.
  - `test_roma_estate`: `"(CEST, UTC+02:00)"`, `"mercoledì 15 luglio 2026"`, `"Ora: 12:00:00"`.
  - `test_tokyo_cambia_giorno`: `calcola_ora("Asia/Tokyo", datetime(2026,10,26,16,42,tzinfo=utc))`
    contiene `"(JST, UTC+09:00)"`, `"martedì 27 ottobre 2026"`, `"Ora: 01:42:00"`.
  - `test_new_york_offset_negativo`: contiene `"UTC-05:00"` in inverno.
  - `test_fuso_non_valido_restituisce_errore`: con `"Roma"` il risultato inizia con
    `"Errore: fuso orario 'Roma' non riconosciuto"` e non solleva eccezioni.
  - `test_fuso_non_valido_registra_warning` (caplog): c'è un record WARNING che contiene `Roma`.
  - `test_ora_corrente_senza_argomenti_usa_predefinito`:
    `crea_ora_corrente(orologio=lambda: INVERNO).invoke({})` contiene `"Europe/Rome"`.
  - `test_ora_corrente_con_fuso`: `.invoke({"fuso_orario": "Asia/Tokyo"})` contiene
    `"Asia/Tokyo"`.
  - `test_schema_strumento`: `name == "ora_corrente"`, la `description` contiene `"Europe/Rome"`, e
    `fuso_orario` sta in `tool.args`.
- [ ] Eseguirli. Atteso: FAIL (modulo assente).
- [ ] Implementare `strumenti.py`.
- [ ] Eseguire `python -m pytest -v`. Atteso: tutti PASS.
- [ ] Fare il commit `feat(strumenti): strumento ora_corrente con fuso esplicito e predefinito italiano`.

### Task 3: funzioni pure del grafo (finestra di contesto e instradamento)

**File**: creare `lab_llm/agente/graph.py` (prima parte) e `lab_llm/tests/test_contesto.py`.

**Interfacce**
```python
class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    passi_strumento: int
def finestra_contesto(messaggi: list[AnyMessage], n: int) -> list[AnyMessage]
def instrada_dopo_llm(stato: AgentState, max_passi: int) -> Literal["strumenti", "limite", "__end__"]
def limite_ricorsione(max_passi: int) -> int   # 2 * max_passi + 5
```
- Algoritmo di `finestra_contesto`:
  1. prendere `messaggi[-n:]`;
  2. scartare dall'inizio finché il primo messaggio non è `HumanMessage`;
  3. se così la finestra resta vuota, restituire tutto dall'ultimo `HumanMessage` in poi (oppure
     `messaggi` interi se non ce n'è nessuno).
- Se taglia, scrive un log DEBUG `contesto: inviati X di Y messaggi`.
- `instrada_dopo_llm` restituisce `END` se l'ultimo messaggio non ha `tool_calls`, `"strumenti"` se
  `passi_strumento < max_passi`, altrimenti `"limite"`.

**Passi**
- [ ] Scrivere i test:
  - `test_finestra_cronologia_corta_invariata`;
  - `test_finestra_taglia_agli_ultimi_n`: 30 messaggi Human/AI alternati con n=20 danno una finestra
    lunga ≤ 20 che inizia con `HumanMessage` e finisce con l'ultimo messaggio;
  - `test_finestra_non_parte_da_toolmessage`: cronologia `[H, AI(tool_calls), Tool, AI, H, AI]` con
    n=4: il primo elemento è `HumanMessage` e nessun `ToolMessage` resta senza il suo `AIMessage`;
  - `test_finestra_ultimo_turno_piu_lungo_di_n`: `[H, AI(tc), Tool, AI(tc), Tool, AI]` con n=2 dà
    tutto da `H`;
  - `test_instrada_fine_senza_tool_call`;
  - `test_instrada_strumenti_sotto_limite` (passi=2, max=3);
  - `test_instrada_limite_raggiunto` (passi=3, max=3 → `"limite"`);
  - `test_limite_ricorsione` (3 → 11).
- [ ] Eseguirli. Atteso: FAIL.
- [ ] Implementare.
- [ ] Eseguirli. Atteso: PASS.
- [ ] Fare il commit `feat(grafo): stato, finestra di contesto e instradamento`.

### Task 4: nodi e costruzione del grafo

**File**: modificare `lab_llm/agente/graph.py` e creare `lab_llm/tests/test_grafo.py` (con il modello
finto definito lì).

**Interfacce**
- Consuma: `AgentState`, `finestra_contesto` e `instrada_dopo_llm` (Task 3), `crea_ora_corrente`
  (Task 2).
- Produce:
```python
PROMPT_SISTEMA: str          # testo del §7 con il segnaposto {fuso}
MESSAGGIO_LIMITE: str        # "Ho raggiunto il limite di {n} richieste allo strumento per questa domanda. Prova a riformularla in modo più semplice."
def costruisci_grafo(modello: Runnable, strumenti: list[BaseTool], *, max_passi: int,
                     max_messaggi_contesto: int, fuso_predefinito: str) -> CompiledStateGraph
```
- `modello` è qualsiasi oggetto con `.invoke(list[BaseMessage]) -> AIMessage`, a cui gli strumenti
  sono già collegati. Il grafo **non** chiama `bind_tools`.
- Nodi con nome esatto `"llm"`, `"strumenti"`, `"limite"` e archi come nel §5.4, scritti come
  closure dentro `costruisci_grafo`.
- Il nodo `strumenti` cerca lo strumento per nome e chiama `strumento.invoke(tc["args"])`.
  - Qualsiasi eccezione, così come un nome sconosciuto, diventa
    `ToolMessage(content="Errore: ...", tool_call_id=tc["id"])`.
  - Scrive un log INFO `strumento {nome} {args} -> {risultato su una riga}` (`\n` sostituito da
    ` | `).
- Il nodo `limite` scrive un log WARNING
  `limite di {max} passaggi raggiunto: {k} tool_call non eseguite`.

**Modello finto (nei test)**: `ModelloFinto(risposte: list[AIMessage])`. Il suo `invoke(messaggi)`
salva `messaggi` in `self.chiamate` e restituisce la risposta successiva.

**Passi**
- [ ] Scrivere i test, con lo strumento `crea_ora_corrente(orologio=lambda: INVERNO)`:
  - `test_risposta_diretta`: un solo `AIMessage("Ciao")` → lo stato finale ha 2 messaggi e
    `passi_strumento == 0`.
  - `test_ciclo_con_strumento`:
    - risposte `[AI(tool_calls=[{"name":"ora_corrente","args":{"fuso_orario":"Asia/Tokyo"},"id":"c1"}]), AI("Sono le 20")]`;
    - nei messaggi c'è un `ToolMessage` con `tool_call_id == "c1"` e contenuto che include
      `"Asia/Tokyo (JST"`;
    - l'ultimo messaggio è `"Sono le 20"` e `passi_strumento == 1`.
  - `test_piu_tool_call_nello_stesso_messaggio`: due tool_call (`c1` Rome, `c2` Tokyo) producono 2
    `ToolMessage` con id `{"c1","c2"}`.
  - `test_limite_passaggi`:
    - con `max_passi=2` il modello finto risponde sempre con una tool_call;
    - il modello viene chiamato 3 volte;
    - l'ultimo messaggio è `AIMessage` con il contenuto di `MESSAGGIO_LIMITE.format(n=2)`;
    - ogni `tool_call_id` presente negli `AIMessage` ha il suo `ToolMessage`.
  - `test_strumento_sconosciuto`: la tool_call `"meteo"` dà un `ToolMessage` che inizia con
    `"Errore"` e la risposta finale arriva lo stesso.
  - `test_argomenti_non_validi_diventano_toolmessage_errore`: con
    `args={"fuso_orario": None}` si ottiene un `ToolMessage` `"Errore..."` e nessuna eccezione.
  - `test_log_chiamata_strumento` (caplog INFO): c'è un record che contiene
    `"strumento ora_corrente"` e `"Asia/Tokyo"`.
  - `test_prompt_e_finestra_al_modello`:
    - con `max_messaggi_contesto=2` e una cronologia iniziale di 6 messaggi;
    - `chiamate[0][0]` è `SystemMessage` e contiene `"Europe/Rome"`;
    - `len(chiamate[0]) <= 3`.
  - `test_grafo_ha_i_nodi_attesi`: `{"llm","strumenti","limite"}` ⊆ `get_graph().nodes`.
- [ ] Eseguirli. Atteso: FAIL.
- [ ] Implementare.
- [ ] Eseguire `python -m pytest -v`. Atteso: tutti PASS.
- [ ] Fare il commit `feat(grafo): nodi llm, strumenti e limite con costruzione del grafo`.

### Task 5: collegamento a LM Studio

**File**: creare `lab_llm/agente/llm.py` e `lab_llm/tests/test_llm.py`.

**Interfacce**
```python
class ErroreModello(Exception): ...
def crea_modello(config: Config, strumenti: list[BaseTool]) -> Runnable
def elenca_modelli(config: Config, client: OpenAI | None = None) -> list[str]
def verifica_modello(config: Config, client: OpenAI | None = None) -> None
```
- `crea_modello` costruisce un `ChatOpenAI` con i parametri del §7 e poi chiama `.bind_tools(strumenti)`.
- `elenca_modelli` usa `client.models.list()` e restituisce gli `.id`. Se `client` manca, crea
  `OpenAI(base_url=..., api_key="lm-studio", timeout=config.lm_timeout)`.
- `verifica_modello` solleva `ErroreModello` in due casi:
  - il server non è raggiungibile (`openai.APIError`): il messaggio contiene l'URL e «avvia LM Studio
    e il server»;
  - il modello non è nell'elenco: il messaggio contiene l'id, i modelli disponibili e «carica il
    modello o correggi LM_MODEL».

**Passi**
- [ ] Scrivere i test (il client finto ha `.models.list()` che restituisce `SimpleNamespace(id=...)`):
  - `test_verifica_modello_presente`;
  - `test_verifica_modello_assente_elenca_disponibili`;
  - `test_verifica_server_irraggiungibile`: il client finto solleva
    `openai.APIConnectionError(request=httpx.Request("GET", "http://x"))`;
  - `test_crea_modello_parametri`:
    - l'oggetto restituito ha
      `.bound.model_name == "m"`, `.bound.temperature == 0` e `.bound.openai_api_base == url`;
    - `kwargs["tools"][0]["function"]["name"] == "ora_corrente"`;
    - non si fa nessuna chiamata di rete.
- [ ] Eseguirli. Atteso: FAIL.
- [ ] Implementare.
- [ ] Eseguirli. Atteso: PASS.
- [ ] Fare il commit `feat(llm): collegamento a LM Studio e verifica del modello all'avvio`.

### Task 6: interfaccia da terminale e avvio

**File**: creare `lab_llm/agente/client.py`, `lab_llm/agente/main.py`, `lab_llm/agente/__main__.py`
e `lab_llm/tests/test_client.py`.

**Interfacce**
```python
# client.py
COMANDI_USCITA = {"esci", "exit", "quit"}
def rispondi(grafo, cronologia: list[AnyMessage], testo: str, recursion_limit: int) -> tuple[list[AnyMessage], str]
def avvia_sessione(grafo, *, intestazione: str, server: str, recursion_limit: int,
                   leggi: Callable[[str], str] = input, scrivi: Callable[[str], None] = print) -> None
# main.py
def configura_logging(livello: str) -> None   # stderr, formato §10, httpx/httpcore/openai a WARNING
def main() -> int                              # 0 se ok, 1 per ErroreConfigurazione o ErroreModello (messaggio su stderr, nessun traceback)
# __main__.py: raise SystemExit(main())
```
- `rispondi` invoca il grafo come nel §8 e restituisce la nuova cronologia e il testo dell'ultimo
  `AIMessage`. Se il testo è vuoto restituisce `"(il modello non ha restituito testo)"`.
- `avvia_sessione` funziona così:
  - stampa l'intestazione del §8;
  - continua il ciclo finché non arriva un comando di uscita, `EOFError` o `KeyboardInterrupt`, poi
    stampa `Sessione terminata. La cronologia non è stata salvata.`;
  - salta gli input vuoti;
  - per `openai.APIError` stampa
    `Assistente> [errore] Non riesco a contattare LM Studio su {server}: {tipo errore}.`, scrive un
    log ERROR e lascia la cronologia com'era;
  - per `GraphRecursionError` stampa un messaggio analogo.
- `main` esegue, in ordine: `carica_config`, `configura_logging`, log INFO di avvio,
  `verifica_modello`, `crea_ora_corrente`, `crea_modello`, `costruisci_grafo`, `avvia_sessione`.

**Passi**
- [ ] Scrivere i test, con un grafo finto oppure il grafo vero con `ModelloFinto` e `leggi`/`scrivi`
  simulati da liste:
  - `test_cronologia_mantenuta_tra_turni`: al secondo turno il modello finto riceve anche la prima
    domanda e la prima risposta;
  - `test_uscita_con_comando` (parametrizzato `esci`, `ESCI`, `quit`): nell'output c'è il messaggio
    di chiusura;
  - `test_uscita_con_eof` e `test_uscita_con_ctrl_c`: `leggi` solleva l'eccezione, la funzione
    termina senza propagarla e stampa il messaggio di chiusura;
  - `test_input_vuoto_ignorato`: con `["", "   ", "esci"]` il modello non viene mai chiamato;
  - `test_errore_collegamento_non_altera_cronologia`:
    - al primo turno il grafo finto solleva `APIConnectionError`, al secondo risponde;
    - l'output contiene `"[errore] Non riesco a contattare LM Studio su http://h:1/v1"`;
    - il secondo invoke riceve solo la seconda domanda;
  - `test_risposta_vuota`: con un `AIMessage("")` si stampa
    `"Assistente> (il modello non ha restituito testo)"`;
  - `test_main_config_mancante`: con monkeypatch dell'ambiente senza `LM_MODEL` (e
    `load_dotenv` disattivato), `main()` restituisce 1 e lo stderr contiene `LM_MODEL`.
- [ ] Eseguirli. Atteso: FAIL.
- [ ] Implementare.
- [ ] Eseguire `python -m pytest -v`. Atteso: tutti PASS.
- [ ] **Prova manuale con LM Studio**: lanciare `python -m agente` e fare la sessione del §8 («Ciao»,
  «Che ore sono?», «E a Tokyo?», «Di cosa abbiamo parlato?», `esci`).
  - Annotare nel resoconto quello che succede davvero, cioè se gemma chiama lo strumento e con quali
    argomenti.
  - Poi rifare la prova con LM Studio fermo (oppure con un URL sbagliato): `main` deve restituire 1
    con un messaggio chiaro.
- [ ] Fare il commit `feat(client): interfaccia da terminale e avvio dell'applicazione`.

### Task 7: prove reali con LM Studio

**File**: creare `lab_llm/tests/reale/__init__.py` (vuoto) e
`lab_llm/tests/reale/test_lm_studio.py`.

- `pytestmark = [pytest.mark.reale, pytest.mark.skipif(os.environ.get("PROVA_REALE") != "1", reason="prova reale: imposta PROVA_REALE=1")]`.
- Una fixture costruisce il grafo vero a partire da `carica_config()`, che legge `.env`.

**Passi**
- [ ] Scrivere tre test:
  - `test_modello_disponibile`: `verifica_modello` non solleva errori;
  - `test_ora_tokyo_usa_lo_strumento`: si trova un `AIMessage` con una tool_call `ora_corrente`
    e args `fuso_orario == "Asia/Tokyo"`, c'è un `ToolMessage` con `"Asia/Tokyo"` e l'ultimo
    `AIMessage` non è vuoto;
  - `test_ora_senza_luogo_usa_predefinito`: c'è una tool_call `ora_corrente` con args `{}` oppure
    `fuso_orario == "Europe/Rome"`.
- [ ] `python -m pytest -v`. Atteso: i 3 test reali risultano SKIPPED e gli altri PASS.
- [ ] `$env:PROVA_REALE="1"; python -m pytest -m reale -v; Remove-Item Env:PROVA_REALE`. Riporto
  l'esito **così com'è**. Se gemma non usa lo strumento, il test fallisce e me ne occupo con
  `superpowers:systematic-debugging`, senza indebolire il test.
- [ ] Fare il commit `test(reale): prove con il modello di LM Studio attivate da PROVA_REALE`.

### Task 8: Docker e guida alla risoluzione dei problemi

**File**
- Creare `lab_llm/Dockerfile`, `lab_llm/compose.yaml` e `lab_llm/.dockerignore` (esclude `.venv`,
  `.env`, `tests`, `docs`, `__pycache__`, `.pytest_cache`, `.git*`). Il contenuto è quello del §9.
- Creare `lab_llm/docs/GUIDA_DOCKER.md` (richiesta dell'utente). Ogni sezione ha questa forma:
  **sintomo → causa → comandi PowerShell per controllare → soluzione**.
  - **Controlli iniziali**: `docker version`, `docker info`, `docker compose version`, `wsl --status`,
    `wsl -l -v`, `systeminfo` (riga «Requisiti Hyper-V» / «Virtualizzazione abilitata nel firmware»).
  - **Virtualizzazione nel BIOS/UEFI** (Intel VT-x / AMD-V): come controllare con Gestione attività →
    Prestazioni → CPU → «Virtualizzazione» e dove si attiva.
  - **WSL 2 e la piattaforma per macchine virtuali**, che è il backend consigliato per Docker Desktop:
    `wsl --install`, `wsl --update`, `wsl --set-default-version 2`, e
    `dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart` (da
    PowerShell come amministratore, poi riavvio).
  - **Hypervisor e Hyper-V, attivare e disattivare**:
    - `bcdedit /enum | Select-String hypervisorlaunchtype`;
    - `bcdedit /set hypervisorlaunchtype auto` (attiva) oppure `off` (disattiva), poi riavvio;
    - `Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -All` e
      `Disable-WindowsOptionalFeature ...` (solo Windows Pro/Enterprise);
    - quando serve disattivarlo: per altri hypervisor. Su questo PC è installato **VMware
      Workstation**, che dalla 15.5 convive con Hyper-V e WSL 2 ma è più lento; spiego i
      compromessi.
  - **Demone non avviato** (`failed to connect to the docker API ... dockerDesktopLinuxEngine`, che è
    l'errore visto il 2026-10-26): avviare Docker Desktop, aspettare «Engine running», usare
    `wsl --shutdown` e riavviare Docker Desktop, «Troubleshoot → Restart / Reset to factory defaults».
  - **Il container non raggiunge LM Studio**:
    - `host.docker.internal`;
    - «Serve on Local Network» in LM Studio;
    - controllo con
      `docker compose run --rm assistente python -c "import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:1234/v1/models').read()[:200])"`;
    - firewall di Windows sulla porta 1234 (`Get-NetFirewallRule`, consentire LM Studio sulle reti
      private).
  - **Build fallita**: rete o proxy, `docker compose build --no-cache`, spazio su disco
    (`docker system df`, `docker system prune`).
  - **Chat che non riceve input**: usare `run`, non `up`; `stdin_open` e `tty`; terminale
    PowerShell oppure Windows Terminal.
  - **Pulizia**: `docker compose down --rmi local`, `docker image prune`.
  - Il §9 e il README rimandano a questa guida.
  - Quello che **verifico davvero** su questa macchina lo segno come «verificato»; il resto lo segno
    come «procedura documentata, non eseguita qui». In particolare non attivo e non disattivo
    l'hypervisor, né riavvio il PC, senza il tuo permesso esplicito.

**Passi**
- [ ] **Prerequisito**: Docker Desktop avviato, cosa che ti chiederò di fare. Controllo con
  `docker info`.
- [ ] `docker compose config`: il servizio `assistente` ha
  `LM_BASE_URL=http://host.docker.internal:1234/v1`.
- [ ] `docker compose build`: build completata.
- [ ] Verifica non interattiva della rete container→host:
  `docker compose run --rm assistente python -c "from agente.llm import verifica_modello; from agente.config import carica_config; verifica_modello(carica_config()); print('ok')"`.
  - Atteso: `ok`.
  - Se fallisce per la rete, attivo in LM Studio «Serve on Local Network», ripeto la prova e annoto
    nel README che cosa è servito davvero.
- [ ] Prova interattiva: `docker compose run --rm assistente`, poi «Che ore sono?», controllo del log
  dello strumento e della risposta, infine `esci`. Lo fai tu nel terminale, oppure io con
  input passato via pipe se la tty lo consente; nel resoconto indico chi l'ha eseguita.
- [ ] Rileggere `GUIDA_DOCKER.md` e controllare che i comandi marcati «verificato» siano stati
  eseguiti davvero.
- [ ] Fare il commit `build(docker): immagine e compose per l'avvio con LM Studio sull'host`, con la
  guida Docker in un commit separato `docs(docker): ...`.

### Task 9: documentazione

**File**
- Creare `lab_llm/README.md` e `lab_llm/docs/COME_FUNZIONA.md` (contenuti del §15).
- Modificare `lab_llm/CLAUDE.md`, dove aggiorno solo le convenzioni stabili:
  - sostituisco la riga «all'inizio contiene soltanto questo file» con la struttura;
  - aggiungo i comandi di test (`python -m pytest`, la prova reale) e l'avvio.

**Passi**
- [ ] Generare il Mermaid con `python -c "from agente.graph import ...; print(g.get_graph().draw_mermaid())"`,
  usando il modello finto o una lambda, e incollarlo in `COME_FUNZIONA.md`.
- [ ] Nel README mettere solo comandi eseguiti davvero nei Task 1–8, con la diagnosi per LM Studio
  spento, modello assente, container che non raggiunge l'host e `.env` mancante.
- [ ] Rileggere la documentazione rispetto al codice: nomi delle variabili, comandi, output.
- [ ] Fare il commit `docs: README, spiegazione dell'agente e convenzioni aggiornate`.

### Task 10: verifica finale e guida passo-passo

- [ ] `superpowers:verification-before-completion`:
  - eseguire `python -m pytest -v`, che deve risultare tutto PASS con le prove reali SKIPPED;
  - prova reale di nuovo;
  - `git status` pulito;
  - `git log --oneline` per rivedere la storia.
- [ ] Controllare che **tutti** i print didattici siano commentati:
  `Select-String -Path agente\*.py -Pattern '^\s*print\("\[passo\]'` non deve trovare nulla.
- [ ] Revisione finale con `superpowers:requesting-code-review`, affidata a un revisore nuovo su tutto
  il diff da `b1ba069`.
- [ ] Creare `lab_llm/docs/GUIDA_PASSO_PASSO.md`, che spiega come rifare tutto da zero:
  - prerequisiti;
  - creazione della cartella;
  - venv;
  - `git` (staging, commit);
  - ogni file nell'ordine dei Task, con lo scopo e i punti chiave del contenuto, rimandando al file
    reale per il codice completo;
  - comandi PowerShell per test, prova reale, Docker e diagnosi.
- [ ] Fare il commit `docs: guida passo-passo per ricostruire il progetto da zero`.
- [ ] Resoconto finale: che cosa è stato eseguito, con quale esito, e che cosa resta da provare.

## Punti di pausa: riavviare e pulire la sessione (richiesta dell'utente)
Alla fine di questi task ti ricordo di pulire la sessione (`/clear`) o di riavviare Claude Code, così
il contesto resta leggero:
- dopo il **Task 3** (fondamenta pronte);
- dopo il **Task 6** (app funzionante in locale);
- dopo il **Task 8** (Docker).

Si riparte senza perdere nulla:
- tutto è nei commit e in `lab_llm/docs/superpowers/plans/2026-10-26-assistente-orologio.md`, dove
  le caselle `- [x]` vengono aggiornate a ogni task;
- nella nuova sessione basta scrivere: «continua il piano
  `lab_llm/docs/superpowers/plans/2026-10-26-assistente-orologio.md` dal primo task non completato».

## Verifica d'insieme
| Cosa | Comando | Esito atteso |
|---|---|---|
| Test automatici | `python -m pytest -v` | tutti PASS, `reale` SKIPPED |
| Prova reale | `$env:PROVA_REALE="1"; python -m pytest -m reale -v` | 3 PASS, con gemma che chiama davvero `ora_corrente` |
| Chat locale | `python -m agente` | la sessione del §8 con il log dello strumento |
| Docker | `docker compose build` + `docker compose run --rm assistente` | come la chat locale, server `host.docker.internal` |

## Esecuzione
Consiglio **Native** (`superpowers:executing-plans`), cioè implemento io i task in questa sessione con
una revisione finale indipendente. I task sono strettamente in sequenza (ognuno usa le interfacce del
precedente), il progetto è piccolo, e i passi con LM Studio e Docker richiedono comunque la tua
presenza. In alternativa: **Subagent-driven**, con un subagente e un revisore per ogni task, che è più
lento e più costoso.
