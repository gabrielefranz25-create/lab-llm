# Guida passo-passo: ricostruire il progetto da zero

Questa guida segue l'ordine in cui il progetto è stato costruito (i task del piano in
`docs/superpowers/plans/`). Per ogni file spiega **a che cosa serve** e **che cosa deve contenere**;
il codice completo è nel file reale, a cui si rimanda. Tutti i comandi sono per PowerShell su Windows.

Il metodo è lo stesso a ogni passo: si scrive prima il test, lo si vede fallire, si scrive il codice,
lo si vede passare, poi si fa il commit.

## 0. Prerequisiti

- **Python 3.13**, con il launcher `py` (`py -3.13 --version`).
- **Git** (`git --version`).
- **LM Studio**: scarica il modello `google/gemma-4-e2b`, caricalo e avvia il server
  (Developer → Start Server, porta 1234). Controllo:

  ```powershell
  Invoke-RestMethod http://localhost:1234/v1/models | Select-Object -ExpandProperty data | Select-Object id
  ```
- **Docker Desktop** con backend WSL 2, solo per l'avvio in container. Se non parte:
  [GUIDA_DOCKER.md](GUIDA_DOCKER.md).

## 1. Cartella, venv e Git

```powershell
mkdir lab_llm; cd lab_llm
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1          # se c'è il venv di un altro progetto attivo: prima deactivate
```

Se la repository non esiste ancora: `git init` nella cartella superiore, poi lavora su un branch
(`git switch -c dev`).

Il ciclo di commit, uguale per ogni passo:

```powershell
git status                          # che cosa è cambiato
git diff                            # controllo riga per riga
git add agente\config.py tests\test_config.py   # staging selettivo: solo i file del passo
git commit -m "feat(config): ..."   # Conventional Commits in italiano
```

Mai fare `git add .` senza aver guardato `git status`: `.env` e `.venv` non devono finire in Git.

## 2. Impalcatura e configurazione (Task 1)

| File | Scopo e contenuto |
|---|---|
| `.gitignore` | esclude `.env`, `.venv/`, `__pycache__/`, `.pytest_cache/` |
| `requirements.txt` | dipendenze di esecuzione con versione fissata: `langgraph==1.2.17`, `langchain-openai==1.7.2`, `langchain-core==1.7.0`, `openai==3.37.0`, `python-dotenv==1.2.4`, `tzdata==2026.5` |
| `requirements-dev.txt` | `-r requirements.txt` più `pytest==9.1.1` |
| `pytest.ini` | `testpaths = tests` e il marker `reale` per le prove con LM Studio |
| `.env.example` | tutte le variabili con un commento ciascuna; per `LM_MODEL` un segnaposto, mai un valore inventato |
| `agente/__init__.py` | solo la docstring del pacchetto |
| `agente/config.py` | `carica_config()` legge le variabili (prima `.env` con `load_dotenv(override=False)`), applica i default, valida i valori e solleva `ErroreConfigurazione` con il nome della variabile; restituisce una `Config` (dataclass immutabile) |
| `tests/test_config.py` | variabili obbligatorie mancanti o vuote, default, valori non validi |

```powershell
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env          # poi metti in LM_MODEL l'id restituito da /v1/models
python -m pytest
```

Punto chiave: `carica_config(ambiente)` accetta un dizionario, così i test non toccano il vero
ambiente.

## 3. Strumento orologio (Task 2)

**`agente/strumenti.py`**
- `calcola_ora(fuso, adesso=None)` è la logica pura: converte l'istante nel fuso IANA con `zoneinfo`
  e restituisce quattro righe (fuso con sigla e offset UTC, data in italiano, ora, ISO 8601).
- Giorni e mesi italiani in due tuple: il `locale` di sistema non è affidabile.
- Con un fuso non valido restituisce un testo d'errore e scrive un WARNING, **non** solleva.
- `crea_ora_corrente(fuso_predefinito, orologio=None)` costruisce lo strumento `ora_corrente` con
  `@tool`: il fuso predefinito finisce nella descrizione e nel default dell'argomento. `orologio`
  serve ai test per fissare l'istante.

**`tests/test_strumenti.py`**: istanti fissi in UTC (estate e inverno per Roma, Tokyo, New York),
strumento senza argomenti → `Europe/Rome`, fusi non validi → messaggio d'errore.

## 4. Funzioni pure del grafo (Task 3)

**`agente/graph.py`**, prima parte:
- `AgentState`: `messages` con il reducer `add_messages` e `passi_strumento: int` senza reducer.
- `finestra_contesto(messaggi, n)`: ultimi `n` messaggi, poi taglia in avanti finché il primo è un
  `HumanMessage`.
- `instrada_dopo_llm(stato, max_passi)`: `END` se non ci sono tool_call, `"strumenti"` se
  `passi_strumento < max_passi`, altrimenti `"limite"`.

**`tests/test_contesto.py`**: finestra corta, coppie tool_call/ToolMessage mai spezzate, ultimo turno
più lungo di `n`, le tre uscite dell'instradamento.

*Pausa di sessione consigliata: `/clear`.*

## 5. Nodi e costruzione del grafo (Task 4)

**`agente/graph.py`**, seconda parte: `costruisci_grafo(modello, strumenti, *, max_passi,
max_messaggi_contesto, fuso_predefinito)`.
- Il prompt di sistema (in italiano) dice di usare **sempre** `ora_corrente` per l'ora e di indicare il
  fuso nella risposta.
- Nodo `llm`: `[prompt] + finestra_contesto(...)` → `modello.invoke` → un `AIMessage`.
- Nodo `strumenti`: per ogni tool_call esegue lo strumento; nome sconosciuto o argomenti sbagliati
  diventano testo d'errore; log INFO; un `ToolMessage` per ogni `tool_call_id`; `passi_strumento + 1`.
- Nodo `limite`: un `ToolMessage` «Non eseguito» per ogni tool_call in sospeso, poi un `AIMessage`
  per l'utente; log WARNING.
- Archi: `START → llm`, `llm ⇢ (strumenti | limite | END)`, `strumenti → llm`, `limite → END`.
- `limite_ricorsione(max_passi) = 2 * max_passi + 5`.

**`tests/test_grafo.py`**: un `ModelloFinto` con risposte preparate (risposta diretta, giro con lo
strumento vero e istante fisso, limite, strumento sconosciuto, argomenti sbagliati, più tool_call
nello stesso messaggio, log, prompt e finestra inviati al modello).

## 6. Collegamento a LM Studio (Task 5)

**`agente/llm.py`**
- `crea_modello(config, strumenti)`: `ChatOpenAI(base_url, model, api_key="lm-studio",
  temperature=0, timeout, max_retries=1).bind_tools(strumenti)`. La chiave è fittizia: LM Studio non
  la controlla.
- `verifica_modello(config, client=None)`: `GET /models` con il client `openai`; se il server non
  risponde o `LM_MODEL` non è nell'elenco solleva `ErroreModello` con l'elenco e un suggerimento.

**`tests/test_llm.py`**: client finto, nessuna chiamata di rete.

## 7. Chat da terminale e avvio (Task 6)

**`agente/client.py`**
- `rispondi(grafo, cronologia, testo, recursion_limit)`: un turno; restituisce la nuova cronologia e
  il testo (o «(il modello non ha restituito testo)»).
- `avvia_sessione(...)`: ciclo `Tu> ` / `Assistente> `; esce con `esci`/`exit`/`quit`, Ctrl+C, EOF;
  ignora l'input vuoto e il BOM che PowerShell aggiunge all'input via pipe; con `openai.APIError` o
  `GraphRecursionError` stampa un errore leggibile e **non** tocca la cronologia.
- `leggi` e `scrivi` sono parametri (default `input` e `print`): i test li sostituiscono.

**`agente/main.py`**: configurazione → log su stderr (librerie HTTP a WARNING) → verifica del modello
→ grafo → sessione. Restituisce 1, senza traceback, se configurazione o modello non vanno.

**`agente/__main__.py`**: `raise SystemExit(main())`, così funziona `python -m agente`.

**`tests/test_client.py`**: cronologia su due turni, uscite, input vuoto, BOM, errore di collegamento,
risposta vuota, `main()` con configurazione mancante.

```powershell
python -m pytest
python -m agente                     # prova a mano: «Che ore sono?», «E a Tokyo?», esci
```

*Pausa di sessione consigliata: `/clear`.*

## 8. Prove reali con LM Studio (Task 7)

**`tests/reale/test_lm_studio.py`** (con `tests/reale/__init__.py` vuoto): marker `reale`, saltate se
`PROVA_REALE` non vale `1`. Usano il grafo vero e controllano nella cronologia che il modello abbia
chiamato `ora_corrente` con `Asia/Tokyo` per Tokyo e con il predefinito per «Che ore sono?».

```powershell
$env:PROVA_REALE="1"; python -m pytest -m reale -v
Remove-Item Env:PROVA_REALE
```

Una risposta simulata non dimostra che il modello sappia usare lo strumento: queste prove sì.

## 9. Docker (Task 8)

| File | Scopo e contenuto |
|---|---|
| `Dockerfile` | `python:3.13-slim`, installa solo `requirements.txt`, copia `agente/`, utente non root, `CMD ["python", "-m", "agente"]` |
| `compose.yaml` | servizio `assistente`: `env_file: .env`, `LM_BASE_URL` sovrascritto con `http://host.docker.internal:1234/v1`, `extra_hosts: host.docker.internal:host-gateway`, `stdin_open` e `tty` |
| `.dockerignore` | esclude `.venv`, `.env`, `tests`, `docs`, cache, `.git*` |
| `docs/GUIDA_DOCKER.md` | per ogni problema: sintomo → causa → controlli PowerShell → soluzione |

```powershell
docker info                          # Docker Desktop deve essere avviato
docker compose config                # controlla LM_BASE_URL
docker compose build
docker compose run --rm -T assistente python -c "from agente.llm import verifica_modello; from agente.config import carica_config; verifica_modello(carica_config()); print('ok')"
docker compose run --rm assistente   # la chat
```

LM Studio deve essere raggiungibile dal container: «Serve on Local Network» attivo (Developer →
Server Settings).

*Pausa di sessione consigliata: `/clear`.*

## 10. Documentazione (Task 9)

- `README.md`: requisiti, `.env`, avvio locale e Docker, test, prove reali, tabella di diagnosi.
  Solo comandi eseguiti davvero.
- `docs/COME_FUNZIONA.md`: grafo (anche in Mermaid, generato con `get_graph().draw_mermaid()`), stato,
  nodi, strumento, contesto, log.
- `CLAUDE.md`: struttura e comandi stabili.

## 11. Verifica finale (Task 10)

```powershell
python -m pytest -v                                         # tutto PASS, prove reali SKIPPED
$env:PROVA_REALE="1"; python -m pytest -m reale -v; Remove-Item Env:PROVA_REALE
Select-String -Path agente\*.py -Pattern '^\s*print\(f?.\[passo\]'   # nessun risultato: print commentati
git status                                                   # pulito
git log --oneline
```

## Diagnosi rapida

| Problema | Dove guardare |
|---|---|
| errori all'avvio (`.env`, LM Studio spento, modello assente, fuso non valido) | README, sezione «Diagnosi» |
| Docker non parte, il container non raggiunge LM Studio, la chat non riceve input | [GUIDA_DOCKER.md](GUIDA_DOCKER.md) |
| capire che cosa succede a ogni passo | togli il `#` ai `print("[passo] ...")` nel codice, oppure `LOG_LEVEL=DEBUG` |
