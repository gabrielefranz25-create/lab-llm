# Strumenti MCP: meteo e note — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** due server FastMCP (meteo, note) avviati via stdio dall'agente, scoperti dal catalogo e
usati dal grafo LangGraph sincrono, con log che dimostrano chiamata, correlazione ed esito.

**Architecture:** i server stanno nel pacchetto `server_mcp/`, fuori da `agente/`, con la logica in
funzioni normali e un involucro FastMCP sottile. `agente/mcp_ponte.py` è l'unico modulo asincrono:
un thread con event loop tiene aperti i `fastmcp.Client` stdio e trasforma il catalogo in
`StructuredTool` sincroni. Il grafo resta quello della lezione 4; cambiano il log del nodo
strumenti e il prompt.

**Tech Stack:** Python 3.13, LangGraph 1.2.17, langchain-core 1.7.0, fastmcp 4.1.6 (mcp 2.3.0),
httpx 0.28.1, sqlite3 (libreria standard), pytest 9.1.1.

**Spec:** `lab_llm/docs/superpowers/specs/2026-11-09-strumenti-mcp-design.md`

## Global Constraints
- Comandi dalla cartella `lab_llm/` con il venv attivo (`.venv\Scripts\python.exe`).
- Pin nuovi in `requirements.txt`: `fastmcp==4.1.6`, `mcp==2.3.0`, `httpx==0.28.1`. Nessun
  `langchain-mcp-adapters`, nessuna nuova dipendenza di sviluppo. Se `pip install` fallisce, fermarsi
  e chiedere all'utente.
- Nome, descrizione e schema dei tool MCP vengono **solo** da `list_tools()`, mai scritti
  nell'agente.
- I server non scrivono niente su stdout (riservato al protocollo); i log vanno su stderr con
  `logging`.
- Codice, identificatori, messaggi e commenti in italiano. Print didattici `# print("[passo] ...")`
  commentati.
- Grafo e client restano sincroni; `asyncio` compare solo in `agente/mcp_ponte.py`, nei server e
  dentro `asyncio.run(...)` nei test.
- Prefissi degli esiti che il modello legge nel `ToolMessage`:
  - `Errore dallo strumento <nome>: <messaggio>`
  - `Errore di collegamento MCP con il server <server>: <dettaglio>`
- Test automatici senza modello e senza rete; prove reali solo con `PROVA_REALE=1`.
- Commit in Conventional Commits in italiano, con staging selettivo e il trailer
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Niente push.
- Le API di fastmcp 4.1.6 (`Client`, trasporto stdio con `cwd` ed `env`, `ToolError`, struttura del
  risultato di `call_tool`/`list_tools`) vanno verificate sulla libreria installata prima di
  scrivere il codice che le usa.

## Review Focus
Sono i casi che la specifica implica ma che nessun test coprirebbe da solo. Ciascuno ha un test
nel task indicato.

1. **Città con accenti o spazi** («Reggio Emilia», «São Paulo»): deve arrivare intatta al
   geocoding, codificata nell'URL. → Task 1, `test_citta_con_spazi_e_accenti_arriva_intatta`.
2. **Geocoding senza regione** (manca il campo `admin1`, frequente fuori dall'Italia): la località
   va formattata senza `None` e senza eccezioni. → Task 1, `test_localita_senza_regione`.
3. **Valori nulli nelle previsioni** (`precipitation_probability_max` a `null`): deve comparire
   «n.d.», non un errore e non uno zero. → Task 1, `test_previsioni_con_valori_nulli`.
4. **Argomenti sbagliati dal modello a un tool MCP** (tipo errato o argomento mancante): deve
   arrivare un testo `Errore dallo strumento …`, non un'eccezione che rompe il turno. → Task 4,
   `test_argomenti_non_validi_diventano_errore_dello_strumento`.
5. **Testo di nota con apostrofi o SQL** (`l'esame; DROP TABLE note`): va salvato letteralmente
   (query parametrizzate). → Task 7, `test_testo_con_apostrofi_e_sql_salvato_letteralmente`.

---

### Task 1: Dipendenze e logica del meteo

**Files:**
- Modify: `requirements.txt`
- Create: `server_mcp/__init__.py` (docstring di una riga), `server_mcp/meteo.py`
- Test: `tests/test_meteo.py`

**Interfaces:**
- Produces, in `server_mcp/meteo.py`:
  - `class ErroreMeteo(Exception)`
  - `@dataclass(frozen=True) class Localita: nome: str; regione: str | None; paese: str | None; latitudine: float; longitudine: float`, con il metodo `descrizione() -> str` (es. `"Udine (Friuli-Venezia Giulia, Italia)"`, oppure `"Udine (Italia)"` senza regione)
  - `URL_GEOCODING = "https://geocoding-api.open-meteo.com/v1/search"`
  - `URL_PREVISIONI = "https://api.open-meteo.com/v1/forecast"`
  - `descrivi_codice(codice: int | None) -> str`
  - `cerca_localita(client: httpx.Client, citta: str) -> tuple[Localita, list[Localita]]` (la scelta e le alternative)
  - `testo_meteo_attuale(client: httpx.Client, citta: str) -> str`
  - `testo_previsioni(client: httpx.Client, citta: str, giorni: int) -> str`
  - `crea_client() -> httpx.Client`: timeout da `METEO_TIMEOUT` (default 10 secondi)

- [ ] **Step 1: installare le dipendenze**

Aggiungere a `requirements.txt` le righe `fastmcp==4.1.6`, `mcp==2.3.0`, `httpx==0.28.1`.
Run: `.venv\Scripts\python.exe -m pip install -r requirements-dev.txt`
Expected: l'installazione termina senza `ERROR`. Poi `python -c "import fastmcp, mcp, httpx;
print(fastmcp.__version__)"` stampa `4.1.6`.

- [ ] **Step 2: scrivere i test che falliscono**

Il file contiene un helper `_client(risposte)` che costruisce
`httpx.Client(transport=httpx.MockTransport(gestore))`. Il gestore risponde in base a
`request.url.host` (`geocoding-api.open-meteo.com` oppure `api.open-meteo.com`) e registra le
richieste ricevute. I JSON finti seguono il formato reale di Open-Meteo: `results` con `name`,
`admin1`, `country`, `latitude`, `longitude`; `current` con `time`, `temperature_2m`,
`relative_humidity_2m`, `weather_code`, `wind_speed_10m`; `daily` con `time`, `weather_code`,
`temperature_2m_max`, `temperature_2m_min`, `precipitation_probability_max`; `timezone`.

Test:
- `test_meteo_attuale_formattato`: il testo contiene `"Località: Udine (Friuli-Venezia Giulia, Italia)"`, `"12.3 °C"`, `"80 %"`, `"9.4 km/h"` e `"cielo coperto"` (codice 3).
- `test_previsioni_una_riga_per_giorno`: con `giorni=3` ci sono 3 righe che iniziano con la data ISO; la richiesta di previsione ha `forecast_days=3`.
- `test_citta_ambigua_dichiarata`: con 2 risultati, il testo contiene la prima località e `"Altre località con questo nome:"` seguito dalla seconda.
- `test_citta_non_trovata`: con `{}` come risposta del geocoding si ha `ErroreMeteo` con il testo `"città non trovata: Atlantide"`; nessuna richiesta a `api.open-meteo.com`.
- `test_timeout_distinto_da_http_500`: il gestore che solleva `httpx.ConnectTimeout` dà `"servizio meteo non raggiungibile"`; quello che risponde 500 dà `"servizio meteo non disponibile (HTTP 500)"`.
- `test_risposta_non_valida`: un JSON senza `current` dà `"risposta del servizio meteo non valida"`.
- `test_argomenti_non_validi`: `citta="  "` e `giorni=0` / `giorni=8` danno `ErroreMeteo`, senza nessuna richiesta HTTP.
- `test_codice_sconosciuto`: `descrivi_codice(42) == "condizioni non classificate (codice 42)"`.
- `test_citta_con_spazi_e_accenti_arriva_intatta`: per `"São Paulo"` il parametro `name` della richiesta, decodificato, è `"São Paulo"`.
- `test_localita_senza_regione`: senza `admin1`, il testo contiene `"Località: Tokyo (Giappone)"` e non contiene `"None"`.
- `test_previsioni_con_valori_nulli`: con `precipitation_probability_max: [null, 40]`, la prima riga contiene `"pioggia n.d."`.

- [ ] **Step 3: verificare che falliscano**

Run: `python -m pytest tests/test_meteo.py -v`
Expected: FAIL (ImportError su `server_mcp.meteo`).

- [ ] **Step 4: implementare la logica in `server_mcp/meteo.py`**

- Geocoding con `params={"name": citta, "count": 5, "language": "it", "format": "json"}`.
- Previsioni con `latitude`, `longitude`, `timezone="auto"` e:
  - per il meteo attuale: `current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m`;
  - per le previsioni: `daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max` e `forecast_days`.
- Conversione degli errori:
  - `httpx.TimeoutException` e `httpx.TransportError` diventano «servizio meteo non raggiungibile»;
  - `response.status_code >= 400` diventa «servizio meteo non disponibile (HTTP N)»;
  - `KeyError`, `IndexError`, `TypeError` e `ValueError` sul JSON diventano «risposta del servizio meteo non valida».
- Tabella WMO con i codici 0, 1, 2, 3, 45, 48, 51-57, 61-67, 71-77, 80-82, 85, 86, 95, 96 e 99, in italiano.
- `logger = logging.getLogger(__name__)`: un INFO per ogni richiesta riuscita e un WARNING per ogni `ErroreMeteo`.

- [ ] **Step 5: verificare che passino**

Run: `python -m pytest tests/test_meteo.py -v`, poi `python -m pytest`
Expected: tutto PASS (i 71 test precedenti più i nuovi).

- [ ] **Step 6: commit**

```bash
git add requirements.txt server_mcp/__init__.py server_mcp/meteo.py tests/test_meteo.py
git commit -m "feat(meteo): logica Open-Meteo con geocoding, previsioni ed errori distinti"
```

### Task 2: Server FastMCP del meteo

**Files:**
- Modify: `server_mcp/meteo.py`
- Test: `tests/test_meteo.py`

**Interfaces:**
- Consumes: `testo_meteo_attuale`, `testo_previsioni`, `crea_client` e `ErroreMeteo` (Task 1).
- Produces:
  - `mcp = FastMCP("Meteo")`, con i tool `meteo_attuale(citta: str) -> str` e `previsioni_meteo(citta: str, giorni: int = 3) -> str`;
  - avvio con `python -m server_mcp.meteo` (stdio).

- [ ] **Step 1: scrivere i test che falliscono** (in memoria, con `asyncio.run` e `fastmcp.Client(mcp)`)

- `test_catalogo_meteo`: `list_tools()` restituisce esattamente `{"meteo_attuale", "previsioni_meteo"}`. Lo `inputSchema` di `previsioni_meteo` ha le proprietà `citta` e `giorni`, e `required == ["citta"]`. Le due descrizioni non sono vuote e sono diverse.
- `test_errore_diventa_iserror`: `call_tool("meteo_attuale", {"citta": " "})` produce un errore del tool (`ToolError` sollevato dal client, oppure `is_error` vero se si usa `raise_on_error=False`). Il messaggio contiene `"città"`.

- [ ] **Step 2: verificare che falliscano**

Run: `python -m pytest tests/test_meteo.py -k "catalogo or iserror" -v`
Expected: FAIL (manca `mcp`).

- [ ] **Step 3: implementare l'involucro**

- Le docstring dei tool distinguono «condizioni di adesso» e «previsioni giorno per giorno, da 1 a 7 giorni».
- Ogni tool apre un `crea_client()` con `with`, chiama la logica e converte `ErroreMeteo` in `fastmcp.exceptions.ToolError`.
- Il blocco `if __name__ == "__main__":` configura `logging.basicConfig(stream=sys.stderr, level=INFO)` e chiama `mcp.run()` senza banner su stdout.

- [ ] **Step 4: verificare**

Run: `python -m pytest tests/test_meteo.py -v`
Expected: PASS.
Run: `python -c "import subprocess,sys; p=subprocess.run([sys.executable,'-m','server_mcp.meteo'],input=b'',capture_output=True,timeout=20); print(repr(p.stdout[:200]))"`
Expected: stdout vuoto (`b''`): il server non scrive niente su stdout fuori dal protocollo.

- [ ] **Step 5: commit**

```bash
git add server_mcp/meteo.py tests/test_meteo.py
git commit -m "feat(meteo): server FastMCP con meteo_attuale e previsioni_meteo"
```

### Task 3: Configurazione MCP

**Files:**
- Modify: `agente/config.py`, `.env.example`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces nuovi campi di `Config`:
  - `mcp_timeout: float`: `MCP_TIMEOUT`, default 30;
  - `meteo_timeout: float`: `METEO_TIMEOUT`, default 10;
  - `note_db: str`: `NOTE_DB`, default `"dati/note.sqlite3"`;
  - `server_mcp: tuple[str, ...]`: `SERVER_MCP`.
- Produces anche `SERVER_MCP_NOTI = ("meteo",)` in `config.py` (il Task 7 lo porta a `("meteo", "note")`).

- [ ] **Step 1: scrivere i test che falliscono**

- `test_valori_predefiniti_mcp`: `mcp_timeout == 30.0`, `meteo_timeout == 10.0`, `note_db == "dati/note.sqlite3"`, `server_mcp == ("meteo",)`.
- `test_server_mcp_vuoto_non_avvia_nulla`: `SERVER_MCP=""`. Attenzione: `_leggi` tratta la stringa vuota come assente, quindi `SERVER_MCP` va letta direttamente da `ambiente` per distinguere «assente» da «vuota». Risultato atteso: `server_mcp == ()`.
- `test_server_mcp_elenco`: `" meteo , meteo "` dà `("meteo",)` (spazi tolti, duplicati rimossi, ordine conservato).
- `test_server_mcp_sconosciuto`: `"meteo,posta"` solleva `ErroreConfigurazione`, con un messaggio che contiene `"posta"`.
- `test_timeout_mcp_troppo_basso`: `MCP_TIMEOUT=15` con `METEO_TIMEOUT=10` solleva `ErroreConfigurazione` (serve `MCP_TIMEOUT > 2 × METEO_TIMEOUT`); con `MCP_TIMEOUT=21` passa.

- [ ] **Step 2: verificare che falliscano**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL sui nuovi test.

- [ ] **Step 3: implementare**

- Aggiungere i campi, un helper `_elenco_server(ambiente) -> tuple[str, ...]` e il controllo dei timeout accanto a quello di `MESSAGGI_DA_TENERE`.
- Documentare le quattro variabili in `.env.example`, nello stile delle altre (commento, campo facoltativo, valore predefinito).
- `SERVER_MCP` va lasciata commentata in `.env.example`, così vale il default.

- [ ] **Step 4: verificare**

Run: `python -m pytest`
Expected: PASS.

- [ ] **Step 5: commit**

```bash
git add agente/config.py .env.example tests/test_config.py
git commit -m "feat(config): variabili per i server MCP, i timeout e l'archivio note"
```

### Task 4: Ponte MCP sincrono

**Files:**
- Create: `agente/mcp_ponte.py`, `tests/server_morente.py` (server FastMCP di prova con un tool `muori()` che chiama `os._exit(1)` e un tool `eco(testo: str) -> str`)
- Test: `tests/test_mcp_ponte.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class ServerMCP: nome: str; argomenti: tuple[str, ...]; env: Mapping[str, str] = field(default_factory=dict)`. Il comando è `sys.executable` seguito da `argomenti`, per esempio `("-m", "server_mcp.meteo")`.
  - `CARTELLA_PROGETTO: Path`, la cartella `lab_llm/` (cioè `Path(__file__).resolve().parents[1]`): è la cartella di lavoro dei sottoprocessi.
  - `class ConnessioneMCP`:
    - `__init__(self, servers: Sequence[ServerMCP], timeout: float)`;
    - `__enter__() -> ConnessioneMCP` e `__exit__(...)`;
    - attributi `strumenti: list[BaseTool]` (nell'ordine dei server) e `cataloghi: dict[str, list]`.
  - `unisci_strumenti(*gruppi: Sequence[BaseTool]) -> list[BaseTool]`: tiene il primo tool per nome e registra un WARNING `"strumento duplicato scartato: <nome>"` per ogni scarto.
- L'ambiente del sottoprocesso è `{**os.environ, **server.env}`.
- Ogni tool ha `metadata == {"origine": f"mcp:{server.nome}"}`.

- [ ] **Step 1: scrivere i test che falliscono** (server stdio veri, nessuna rete; il timeout della connessione nei test è 20)

- `test_discovery_dal_server`: `ConnessioneMCP([ServerMCP("meteo", ("-m","server_mcp.meteo"))], 20)`. I nomi dei tool sono `{"meteo_attuale", "previsioni_meteo"}`; per ciascuno `metadata["origine"] == "mcp:meteo"`. `tool.args` contiene `"citta"`. La descrizione è uguale a quella di `cataloghi["meteo"]`.
- `test_chiamata_sincrona_riuscita`: con il server `tests/server_morente.py`, `strumento("eco").invoke({"testo": "ciao"}) == "ciao"`.
- `test_errore_dello_strumento`: `meteo_attuale.invoke({"citta": " "})` restituisce un testo che inizia con `"Errore dallo strumento meteo_attuale:"`.
- `test_argomenti_non_validi_diventano_errore_dello_strumento`: `eco.invoke({})`, chiamato con l'argomento obbligatorio mancante, restituisce un testo che inizia con `"Errore"` e non solleva eccezioni. Se lo schema LangChain rifiuta gli argomenti prima della chiamata, l'eccezione viene comunque gestita dal nodo strumenti; in quel caso il test va scritto sul nodo, nel Task 5.
- `test_server_che_non_parte`: `ServerMCP("rotto", ("-m","modulo_inesistente_xyz"))` produce un WARNING che contiene `"rotto"`, nessun tool e nessuna eccezione. Se insieme c'è anche il server meteo, i tool del meteo restano disponibili.
- `test_server_che_muore`: dopo `muori.invoke({})`, la chiamata successiva a `eco.invoke({"testo": "x"})` restituisce un testo che inizia con `"Errore di collegamento MCP con il server morente:"` entro il timeout.
- `test_uscita_chiude_il_thread`: dopo il `with`, il thread del ponte non è più vivo.
- `test_unisci_strumenti_scarta_duplicati`: con due tool finti con lo stesso nome viene tenuto il primo e compare il WARNING.

- [ ] **Step 2: verificare che falliscano**

Run: `python -m pytest tests/test_mcp_ponte.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: implementare `agente/mcp_ponte.py`**

Schema del funzionamento:
- `__enter__` crea `asyncio.new_event_loop()` e un `threading.Thread(daemon=True)` che esegue `loop.run_forever()`.
- Per ogni server avvia con `run_coroutine_threadsafe` una coroutine «custode»: questa apre `async with Client(trasporto_stdio)`, esegue `list_tools()`, segnala che è pronta tramite un `Future` e poi attende un `asyncio.Event` di chiusura. In questo modo la sessione resta aperta nello stesso task che l'ha aperta, condizione necessaria per anyio.
- Il thread principale attende la segnalazione «pronto» con il timeout. Se scade o arriva un'eccezione, registra un WARNING e passa al server successivo.
- Ogni tool è `StructuredTool.from_function(func=..., name=..., description=..., args_schema=voce.inputSchema, metadata=...)`. La `func` chiama `run_coroutine_threadsafe(client.call_tool(nome, argomenti), loop).result(timeout)` e converte l'esito:
  - successo: i blocchi di testo del contenuto uniti con `"\n"`;
  - `ToolError`: `Errore dallo strumento …`;
  - qualsiasi altra eccezione, `TimeoutError` compreso: `Errore di collegamento MCP …`.
- `__exit__` imposta gli eventi di chiusura, attende i custodi (con il timeout), poi esegue `loop.call_soon_threadsafe(loop.stop)` e `thread.join`.
- Un INFO per server: `server MCP <nome>: catalogo [<tool>, ...]`.

- [ ] **Step 4: verificare**

Run: `python -m pytest tests/test_mcp_ponte.py -v`, poi `python -m pytest`
Expected: PASS, senza test bloccati. Se un test supera i 60 secondi, va trattato come un fallimento.

- [ ] **Step 5: commit**

```bash
git add agente/mcp_ponte.py tests/server_morente.py tests/test_mcp_ponte.py
git commit -m "feat(mcp): ponte sincrono con discovery stdio ed esiti distinti"
```

### Task 5: Grafo e avvio con i tool MCP

**Files:**
- Modify: `agente/graph.py` (`PROMPT_SISTEMA`, il log in `nodo_strumenti`), `agente/main.py`
- Test: `tests/test_grafo.py`, più eventuali test di `main` esistenti in `tests/test_client.py`

**Interfaces:**
- Consumes: `ConnessioneMCP`, `ServerMCP`, `unisci_strumenti` e `CARTELLA_PROGETTO` (Task 4); i campi `Config` (Task 3).
- Produces: in `main.py`, `server_da_config(config: Config) -> list[ServerMCP]`. Il meteo diventa `ServerMCP("meteo", ("-m", "server_mcp.meteo"), {"METEO_TIMEOUT": str(config.meteo_timeout)})`.

- [ ] **Step 1: scrivere o aggiornare i test che falliscono**

- `test_log_chiamata_strumento` (esistente): l'asserzione diventa `"strumento=ora_corrente"`, `"origine=locale"`, `"call_id="` e `"esito=ok"` nello stesso record, che contiene anche `Asia/Tokyo`.
- `test_log_origine_mcp_ed_esito_errore`: si usa uno `StructuredTool` finto con nome `meteo_attuale`, `metadata={"origine":"mcp:meteo"}` e risultato `"Errore dallo strumento meteo_attuale: città non trovata: X"`. Il record contiene `"origine=mcp:meteo"`, `"call_id=m1"` ed `"esito=errore"`. Il `ToolMessage` ha `tool_call_id == "m1"`.
- `test_tool_mcp_insieme_all_orologio`: con due tool_call nello stesso messaggio (`ora_corrente`, `meteo_attuale` finto), ogni `ToolMessage` è correlato al proprio id.
- `test_server_da_config`: `server_da_config` con `server_mcp=("meteo",)` restituisce un server con nome `"meteo"`, argomenti `("-m","server_mcp.meteo")` ed env `METEO_TIMEOUT`; con `()` restituisce la lista vuota.
- I test esistenti di `main()` non devono avviare sottoprocessi: impostano `SERVER_MCP=""` nell'ambiente oppure fanno il monkeypatch di `ConnessioneMCP`.

- [ ] **Step 2: verificare che falliscano**

Run: `python -m pytest tests/test_grafo.py -v`
Expected: FAIL sui nuovi test e sull'asserzione aggiornata.

- [ ] **Step 3: implementare**

- **Log** in `nodo_strumenti`: sostituisce la riga attuale.
  ```python
  logger.info("strumento=%s origine=%s call_id=%s argomenti=%s esito=%s risultato=%s", ...)
  ```
  - `origine` vale `(strumento.metadata or {}).get("origine", "locale")`, oppure `"-"` per uno strumento sconosciuto.
  - `argomenti` è `json.dumps(tc["args"], ensure_ascii=False)`, oppure il testo grezzo per le `invalid_tool_call`.
  - `esito` vale `"errore"` se il testo inizia con `"Errore"`.
- **`PROMPT_SISTEMA`**: aggiungere tre righe, lasciando invariate quelle sull'orologio:
  - per il meteo di adesso e per le previsioni usare gli strumenti meteo, senza inventare dati, e citare la località indicata nel risultato;
  - se uno strumento restituisce un errore, riferirlo senza inventare un risultato.

  Le righe sulle note arrivano nel Task 7.
- **`main()`**:
  - dopo `verifica_modello`, usare `with ConnessioneMCP(server_da_config(config), config.mcp_timeout) as connessione:`;
  - unire gli strumenti con `strumenti = unisci_strumenti([crea_ora_corrente(...)], connessione.strumenti)`;
  - costruire il grafo e chiamare `avvia_sessione` dentro il `with`;
  - l'intestazione aggiunge `Strumenti: <nomi separati da virgola>`;
  - Ctrl+C durante l'avvio dei server deve restituire 130, come oggi.

- [ ] **Step 4: verificare**

Run: `python -m pytest`
Expected: PASS.
Run (manuale, con LM Studio acceso): `python -m agente` e la domanda «Che tempo fa a Udine adesso?»
Expected: su stderr compaiono `server MCP meteo: catalogo [meteo_attuale, previsioni_meteo]` e
una riga `strumento=meteo_attuale origine=mcp:meteo call_id=… esito=ok`.

- [ ] **Step 5: commit**

```bash
git add agente/graph.py agente/main.py tests/test_grafo.py tests/test_client.py
git commit -m "feat(grafo): tool MCP del meteo nel grafo con log di origine, call_id ed esito"
```

### Task 6: Prova reale del meteo (traguardo minimo della lezione)

**Files:**
- Create: `tests/reale/test_mcp_reale.py`

**Interfaces:**
- Consumes: `ConnessioneMCP` e `unisci_strumenti` (Task 4), `server_da_config` (Task 5), più lo schema di `tests/reale/test_lm_studio.py`: `pytestmark` con il marker `reale` e `skipif(PROVA_REALE != "1")`.

- [ ] **Step 1: scrivere le prove**

La fixture di modulo apre `ConnessioneMCP` con il solo meteo, costruisce il grafo come `main()` e
fornisce `chiedi(testo) -> list[messaggi]`.

- `test_meteo_attuale_reale`: «Che tempo fa a Udine adesso?». Esiste un `AIMessage` con una tool_call `meteo_attuale` e un `ToolMessage` con lo stesso `tool_call_id`, il cui contenuto non inizia con `"Errore"` e contiene `"Udine"`. Anche l'ultima risposta contiene `"Udine"`.
- `test_previsioni_reali`: «Che tempo farà a Tokyo nei prossimi 3 giorni?». Esiste una tool_call `previsioni_meteo` con `citta` che contiene `"Tokyo"`, e il `ToolMessage` correlato contiene almeno 3 date ISO.
- `test_citta_inesistente_diretta`: chiamata diretta del tool, senza modello, con `{"citta": "Xyzzyqwop"}`. Il risultato inizia con `"Errore dallo strumento meteo_attuale: città non trovata"`.

- [ ] **Step 2: eseguire** (LM Studio con `google/gemma-4-e2b`, rete attiva)

Run: `$env:PROVA_REALE="1"; python -m pytest tests/reale/test_mcp_reale.py -v -o log_cli=true --log-cli-level=INFO`
Expected: 3 PASS, con le righe `origine=mcp:meteo … esito=ok` nel log.
Se il modello non sceglie il tool, si registra nel resoconto il punto esatto (catalogo presente, chiamata assente) e si ferma qui. Non si modifica il test per farlo passare.

- [ ] **Step 3: verificare che senza `PROVA_REALE` le prove risultino skipped**

Run: `python -m pytest`
Expected: PASS, con i test reali skipped.

- [ ] **Step 4: commit**

```bash
git add tests/reale/test_mcp_reale.py
git commit -m "test(reale): prova del meteo via MCP con LM Studio"
```

### Task 7: Server delle note e collegamento

**Files:**
- Create: `server_mcp/note.py`
- Modify: `agente/config.py` (`SERVER_MCP_NOTI = ("meteo", "note")`, default `("meteo", "note")`), `agente/main.py` (`server_da_config`), `agente/graph.py` (prompt), `.gitignore` (`dati/`), `tests/reale/test_mcp_reale.py`, `tests/test_config.py`
- Test: `tests/test_note.py`, `tests/test_mcp_ponte.py`

**Interfaces:**
- Produces, in `server_mcp/note.py`:
  - `class ErroreNote(Exception)`;
  - `@dataclass(frozen=True) class Nota: id: int; testo: str; creata: str`;
  - `class ArchivioNote` con:
    - `__init__(self, percorso: Path)`: crea la cartella e la tabella;
    - `aggiungi(testo: str) -> Nota`;
    - `elenca(limite: int) -> list[Nota]`;
    - `elimina(id_nota: int) -> Nota`;
  - `mcp = FastMCP("Note")` con i tool `aggiungi_nota(testo: str) -> str`, `elenca_note(limite: int = 10) -> str` e `elimina_nota(id_nota: int) -> str`; l'archivio è aperto sul percorso di `NOTE_DB` (default `dati/note.sqlite3`) a ogni chiamata.
- Formati di testo dalla spec, §6.2:
  - `"Nota N salvata il AAAA-MM-GG HH:MM: testo"`
  - `"Nessuna nota salvata."`
  - `"Nota N eliminata: testo"`
  - `"nessuna nota con ID N"`
  - `"archivio note non accessibile"`
- In `main.py`: `ServerMCP("note", ("-m", "server_mcp.note"), {"NOTE_DB": config.note_db})`.

- [ ] **Step 1: scrivere i test che falliscono** (`ArchivioNote(tmp_path / "n.sqlite3")`)

- `test_aggiungi_restituisce_id_e_data`
- `test_elenca_dalla_piu_recente_e_limite`
- `test_elenco_vuoto`: il tool `elenca_note` in memoria, con `NOTE_DB` puntato su `tmp_path` tramite monkeypatch, restituisce `"Nessuna nota salvata."`
- `test_elimina_per_id`
- `test_id_inesistente_non_cancella_niente`: con 2 note, `elimina(99)` solleva `ErroreNote("nessuna nota con ID 99")` e l'elenco ne contiene ancora 2.
- `test_testo_vuoto_o_troppo_lungo`: `"   "` e `"x"*501` sono rifiutati, `"x"*500` è accettato.
- `test_limite_fuori_intervallo`: 0 e 51 sono rifiutati.
- `test_persistenza_dopo_riapertura`: un nuovo `ArchivioNote` sullo stesso file vede la nota.
- `test_testo_con_apostrofi_e_sql_salvato_letteralmente`: `"l'esame; DROP TABLE note"` viene salvato e riletto identico, e la tabella esiste ancora.
- `test_archivio_non_accessibile`: se `percorso` è una cartella, si ha `ErroreNote("archivio note non accessibile")`.
- `test_catalogo_note`: in memoria ci sono i tre tool; le descrizioni di `aggiungi_nota` ed `elimina_nota` contengono `"modifica"`.
- In `tests/test_mcp_ponte.py`, `test_discovery_note_via_stdio`: `ServerMCP("note", ("-m","server_mcp.note"), {"NOTE_DB": str(tmp_path/"n.sqlite3")})`; `aggiungi_nota` e poi `elenca_note` via ponte restituiscono la nota, con `origine == "mcp:note"`.
- In `tests/test_config.py` vanno aggiornati il default (`("meteo", "note")`) e l'elenco dei server noti.

- [ ] **Step 2: verificare che falliscano**

Run: `python -m pytest tests/test_note.py tests/test_mcp_ponte.py tests/test_config.py -v`
Expected: FAIL sui nuovi test.

- [ ] **Step 3: implementare**

- **Archivio**: sqlite3 con query parametrizzate (`?`) e `ORDER BY id DESC LIMIT ?`. `creata` viene da `datetime.now().isoformat(timespec="minutes")`. Un'`sqlite3.Error` all'apertura diventa «archivio note non accessibile».
- **Log**: un INFO su stderr per ogni aggiunta ed eliminazione, con l'ID.
- **Tool**: convertono `ErroreNote` in `ToolError`.
- **`PROMPT_SISTEMA`**: aggiungere la riga «per ricordare, elencare o eliminare note usa gli strumenti delle note; elimina solo per ID; se l'ID non è noto, prima elenca le note».
- **`.gitignore`**: aggiungere `dati/`.

- [ ] **Step 4: aggiungere le prove reali** in `tests/reale/test_mcp_reale.py`

Usano una fixture separata con `NOTE_DB` in `tmp_path_factory`, mai il file vero.

- `test_aggiungi_nota_reale`: «Ricordami di consegnare il report venerdì» produce esattamente una tool_call `aggiungi_nota`, un `ToolMessage` correlato con `"salvata"`.
- `test_elimina_nota_inesistente_reale`: «Elimina la nota 99» produce un `ToolMessage` che inizia con `"Errore dallo strumento elimina_nota"`; poi una chiamata diretta a `elenca_note` mostra che la nota del test precedente esiste ancora.
- `test_note_dopo_riavvio`: si chiude la connessione e se ne apre una nuova sullo stesso `NOTE_DB`; la chiamata diretta `elenca_note` contiene `"report"`.

- [ ] **Step 5: verificare**

Run: `python -m pytest`
Expected: PASS.
Run: `$env:PROVA_REALE="1"; python -m pytest tests/reale/test_mcp_reale.py -v -o log_cli=true --log-cli-level=INFO`
Expected: tutte PASS, con le righe `origine=mcp:note`. Un eventuale fallimento va registrato con il punto esatto, come nel Task 6.

- [ ] **Step 6: commit**

```bash
git add server_mcp/note.py agente/config.py agente/main.py agente/graph.py .gitignore tests/test_note.py tests/test_mcp_ponte.py tests/test_config.py tests/reale/test_mcp_reale.py
git commit -m "feat(note): server MCP delle note su SQLite come secondo server dell'agente"
```

### Task 8: Docker

**Files:**
- Modify: `Dockerfile`, `compose.yaml`

- [ ] **Step 1: modificare**

- **`Dockerfile`**: aggiungere `COPY server_mcp/ server_mcp/` e, prima di `USER appuser`, `RUN mkdir -p /app/dati && chown appuser /app/dati` (l'utente deve esistere prima del `chown`, quindi la riga va dopo `useradd`).
- **`compose.yaml`**: aggiungere `volumes: [note:/app/dati]` al servizio e un blocco `volumes: { note: {} }` in fondo.

- [ ] **Step 2: verificare** (Docker Desktop acceso, LM Studio acceso)

Run: `docker compose build`
Expected: la build termina senza errori.
Run: `docker compose run --rm assistente python -c "import httpx; print(httpx.get('https://api.open-meteo.com/v1/forecast?latitude=46&longitude=13&current=temperature_2m', timeout=10).status_code)"`
Expected: `200`, cioè il container raggiunge Open-Meteo.
Run: `"Che tempo fa a Udine?`nRicordami di comprare il pane`nesci" | docker compose run --rm -T assistente`, poi `"Elenca le mie note`nesci" | docker compose run --rm -T assistente`
Expected: nella seconda esecuzione compare la nota «comprare il pane», quindi il volume la conserva. `esci` è in `COMANDI_USCITA` di `client.py`.

- [ ] **Step 3: commit**

```bash
git add Dockerfile compose.yaml
git commit -m "build(docker): server MCP nel container e volume per le note"
```

### Task 9: Documentazione

**Files:**
- Modify: `README.md`, `docs/COME_FUNZIONA.md`, `docs/GUIDA_DOCKER.md`, `docs/GUIDA_PASSO_PASSO.md`, `CLAUDE.md`, `docs/PROSSIMA_SESSIONE.md`

- [ ] **Step 1: aggiornare** riportando solo i comandi verificati nei task precedenti.

- **README**:
  - nuove variabili;
  - come si vede la traccia MCP nei log;
  - diagnosi per livelli, dalla tabella della slide 24: processo non avviato, catalogo assente, chiamata assente, risultato corretto con risposta errata;
  - MCP Inspector, facoltativo.
- **`COME_FUNZIONA.md`**:
  - ruoli host, client e server;
  - percorso `tools/list` → `StructuredTool` → `bind_tools` → `tools/call` → `ToolMessage`;
  - differenza tra `tool_call_id` e ID JSON-RPC;
  - perché il ponte ha un thread.
- **`GUIDA_DOCKER.md`**: il volume `note` e come svuotarlo (`docker volume rm`).
- **`GUIDA_PASSO_PASSO.md`**: la sezione della lezione 5.
- **`CLAUDE.md`**:
  - struttura con `server_mcp/` e `mcp_ponte`;
  - nei «Confini», MCP non è più fra le cose da non anticipare (restano workflow e RAG);
  - le note sono persistenti, quindi l'obiettivo «nessuna persistenza» vale per la cronologia;
  - comando per la prova reale MCP.
- **`PROSSIMA_SESSIONE.md`**: stato al termine, con che cosa è stato eseguito e che cosa resta da provare.

- [ ] **Step 2: verificare**

Run: `python -m pytest`
Expected: PASS. Controllare che `git status` mostri solo file di documentazione.

- [ ] **Step 3: commit**

```bash
git add README.md CLAUDE.md docs/COME_FUNZIONA.md docs/GUIDA_DOCKER.md docs/GUIDA_PASSO_PASSO.md docs/PROSSIMA_SESSIONE.md
git commit -m "docs: strumenti MCP meteo e note in guide, README e CLAUDE.md"
```
