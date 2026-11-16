# Guida ai test manuali, passo per passo

Questa guida spiega come provare a mano tutto il progetto (fino alla lezione 6): che cosa aprire, dove
cliccare, che tasti premere, che cosa scrivere e che cosa deve comparire. I comandi sono quelli già
verificati nel [README](../README.md); qui sono messi in ordine e spiegati.

> Le etichette di LM Studio e di Docker Desktop possono cambiare leggermente con la versione: se un
> pulsante ha un nome un po' diverso, cerca quello con lo stesso significato.

Convenzioni: **grassetto** = pulsante o voce da cliccare; `codice` = testo da scrivere e poi **Invio**;
`Ctrl+C` = tieni premuto Ctrl e premi C.

---

## 0. Stato in breve (al 2026-11-16)

- **Fatto**: lezioni 3, 4, 5 (blocchi A, B, C) e 6 (step 1–9). `main` e `dev` sono allineati, tag `lezione-6`.
- **Ultima verifica automatica**: `python -m pytest` → 449 passed, 45 skipped.
- **Su GitHub** (`origin`): solo fino alla lezione 5 (`origin/main` = tag `lezione-5`). Tutto il lavoro della
  lezione 6 e i tag `lezione-4` e `lezione-6` sono **solo sul PC**. Per pubblicarli, quando vorrai:
  `git push origin main dev lezione-4 lezione-6`. I feature branch (`feat/...`) non serve pusharli.
- **Che cosa entra in Git**: codice, test, documenti, `Dockerfile`, `compose.yaml`, `.env.example`.
- **Che cosa resta fuori da Git** (per scelta): `.env` (configurazione vera), `.venv/` (ambiente Python),
  `__pycache__/` e `.pytest_cache/` (cache), `dati/` (database SQLite delle note), `materiali/` (PDF delle
  lezioni e appunti), `.claude/` e `.superpowers/` (file di lavoro di Claude Code).
- **Da provare ancora a mano**: la pagina nel browser vero (sezione 4) e la chat Docker con tastiera
  interattiva (sezione 5).

---

## 1. Preparazione (all'inizio di ogni sessione di prova)

### 1.1 LM Studio (il modello)

1. Apri **LM Studio** dal menu Start.
2. Nella barra a sinistra clicca l'icona **Developer** (simbolo `>_`).
3. In alto clicca **Select a model to load** e scegli `google/gemma-4-e2b`. Attendi che la barra di
   caricamento finisca.
4. Accanto a **Status** sposta l'interruttore su **Running** (oppure clicca **Start Server**). Deve comparire
   l'indirizzo `http://localhost:1234` (o `0.0.0.0:1234`).
5. Clicca **Settings** (nella stessa pagina) e attiva **Serve on Local Network**: serve ai container Docker
   per raggiungere LM Studio. Senza questa opzione la chat locale funziona, quella in Docker no.

### 1.2 Docker Desktop (solo per le sezioni 4 e 5)

1. Apri **Docker Desktop** dal menu Start.
2. Attendi in basso a sinistra la scritta **Engine running** (pallino verde). Può servire un minuto.

### 1.3 PowerShell nella cartella del progetto

1. Premi il tasto **Windows**, scrivi `PowerShell`, premi **Invio**.
2. Vai nella cartella del progetto (copia e incolla con tasto destro del mouse nella finestra):

   ```powershell
   cd "C:\Users\GabrieleFranz\Desktop\.g\corso\anno_2\addis paolo\esercizi_lab\repo-lab-llm_l4\lab_llm"
   ```

3. Attiva l'ambiente Python:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

   All'inizio della riga deve comparire `(.venv)`. Se compare un errore su «esecuzione di script
   disabilitata», scrivi una volta `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, conferma con `S`
   e riprova.
4. Controlla che LM Studio risponda:

   ```powershell
   Invoke-RestMethod http://localhost:1234/v1/models | Select-Object -ExpandProperty data | Select-Object id
   ```

   Nell'elenco deve esserci `google/gemma-4-e2b`.
5. Controlla il file `.env` (si apre nel Blocco note con `notepad .env`): devono esserci
   `LM_MODEL=google/gemma-4-e2b` e, per Docker, le tre righe `POSTGRES_USER`, `POSTGRES_PASSWORD`,
   `POSTGRES_DB`. Se `.env` manca: `Copy-Item .env.example .env` e completa i valori.

---

## 2. Test automatici (2–3 minuti, LM Studio non serve)

```powershell
python -m pytest -q
```

- Alla fine deve comparire una riga simile a `449 passed, 45 skipped`.
- **passed** = test riuscito. **skipped** = test saltato apposta: sono le prove con LM Studio vero o con
  PostgreSQL vero, che partono solo se le attivi (sezione 6). Non sono errori.
- Se compare **failed** o **error**: leggi il nome del test in rosso e il messaggio sopra.

---

## 3. Chat da terminale (senza Docker)

```powershell
python -m agente
```

Dopo qualche secondo compare `Assistente del laboratorio` e il cursore `Tu>`. Le righe con `INFO` sono il
log (mostra che cosa fa il programma dentro). Scrivi una domanda alla volta e premi **Invio**; la risposta
può richiedere da 10 secondi a oltre un minuto.

| Scrivi | Che cosa deve succedere (nel log e nella risposta) |
|---|---|
| `Che ore sono a Tokyo?` | log `router: categoria=conversazione … -> agente`, poi `strumento=ora_corrente … Asia/Tokyo … esito=ok`; risposta con l'ora di Tokyo |
| `Quanto fa 15 per 12?` | `strumento=calcola … esito=ok`; risposta 180 |
| `Che tempo fa a Udine?` | `strumento=meteo_attuale` (serve Internet) |
| `Ricordami di comprare il pane` | `strumento=aggiungi_nota … esito=ok` |
| `Elenca le mie note` | `strumento=elenca_note`, compare la nota appena scritta |
| `Scrivimi la ricetta della carbonara` | `router: categoria=fuori_ambito … -> rifiuto`; risposta «Mi dispiace, posso aiutarti solo con: …»; **nessuna** riga `agente: invio` |
| `/prompts` | elenco dei prompt `spiega` e `riassumi_conversazione` con gli argomenti |
| `/prompt spiega argomento="Model Context Protocol" livello=base` | spiegazione dell'argomento |
| `/prompt spiega livello=base` | errore immediato: manca l'argomento obbligatorio, il modello **non** viene chiamato |
| `/prompt riassumi_conversazione stile=dettagliato` | riassunto delle domande fatte finora |
| `esci` | il programma termina |

Anche `Ctrl+C` chiude la chat.

---

## 4. Applicazione completa nel browser (Docker Compose) — prova principale

### 4.1 Avvio

Con Docker Desktop acceso e LM Studio in **Running**:

```powershell
docker compose up -d --build
```

La prima volta scarica e costruisce le immagini (qualche minuto). Alla fine:

```powershell
docker compose ps
```

Devono esserci quattro righe: `agente`, `backend`, `db` (con `healthy`), `frontend` (con `0.0.0.0:8090->80/tcp`).
Nessun'altra porta pubblicata.

### 4.2 La pagina

1. Apri **Chrome** (o Edge) e scrivi nella barra degli indirizzi `http://localhost:8090`, poi **Invio**.
2. In alto a sinistra, sotto **Assistente**, c'è lo stato:
   - pallino rosso con **non pronto: agente non raggiungibile** nei primi ~20 secondi (l'agente sta leggendo
     i cataloghi MCP): è normale. Premi **F5** dopo mezzo minuto.
   - pallino verde con **pronto**: si può iniziare.
3. Clicca **+ Nuova chat** (a sinistra). A destra il titolo diventa **Nuova chat**.
4. Clicca nella casella in basso (*Scrivi una domanda…*), scrivi `Che ore sono a Tokyo?` e premi **Invio**
   (oppure clicca **Invia**). `Maiusc+Invio` va a capo senza inviare.
5. Durante l'attesa: casella e pulsanti disabilitati, il pulsante dice **Attendi…** e compare
   «L'assistente sta rispondendo… (N s)» con i secondi che salgono.
6. Arriva la risposta. Sotto c'è lo strumento usato, per esempio `ora_corrente(fuso_orario=Asia/Tokyo)`
   (in rosso se lo strumento ha dato errore). Nella colonna a sinistra compare la chat con il titolo
   uguale all'inizio della domanda e la data.
7. Nella stessa chat scrivi `Quanto fa 15 per 12?` → sotto la risposta `calcola(...)`.
8. Clicca **+ Nuova chat**, fai un'altra domanda: a sinistra ora ci sono due chat. Cliccandone una si
   riaprono i suoi messaggi.
9. Eliminazione: clicca il cestino **🗑** a destra della chat nella colonna di sinistra (diventa rosso
   passandoci sopra); nella finestra
   «Eliminare la chat «…» e tutti i suoi messaggi?» clicca **OK**. La chat sparisce.

### 4.3 Le chat restano dopo lo spegnimento

```powershell
docker compose down
docker compose up -d
```

Attendi ~30 secondi, torna nel browser e premi **F5**: le chat ci sono ancora (sono nel volume `postgres`).

### 4.4 Errore mostrato bene quando l'agente è spento

1. In PowerShell: `docker compose stop agente`.
2. Nel browser premi **F5**: lo stato diventa rosso (**non pronto: agente non raggiungibile**).
3. Scrivi una domanda e premi **Invio**: in alto compare un **banner rosso** con un messaggio leggibile
   («L'agente non è raggiungibile su http://agente:8000 … Riprova più tardi.»); la domanda **torna nella
   casella** e nella chat non viene salvato nulla.
4. Clicca la **×** a destra del banner: il banner sparisce (non deve restare un riquadro rosso vuoto).
5. In PowerShell: `docker compose start agente`. Attendi ~20 secondi, **F5**, stato verde **pronto**.
6. Premi di nuovo **Invia**: ora la risposta arriva.

### 4.5 Guardare i log

```powershell
docker compose logs -f agente
```

Mentre fai domande dal browser compaiono le righe `strumento=… esito=ok` e
`api: POST /chat … -> 200 strumenti=[…]`. Per uscire dai log premi **Ctrl+C** (i container restano accesi).

---

## 5. Chat da terminale dentro Docker (con la tastiera) — mai provata a mano

```powershell
docker compose run --rm assistente
```

Compare la stessa chat della sezione 3. Scrivi `Che ore sono?` e **Invio**: la risposta deve arrivare
normalmente, digitando dalla tastiera. Poi `esci`. Il container si cancella da solo (`--rm`).
Se la chat non legge la tastiera, vedi [GUIDA_DOCKER.md](GUIDA_DOCKER.md), sezione 8.

---

## 6. Prove facoltative

- **Prove reali con LM Studio** (durano molti minuti: tieni il PC sveglio, altrimenti durano ore):

  ```powershell
  $env:PROVA_REALE="1"; python -m pytest -m reale -v
  Remove-Item Env:PROVA_REALE
  ```

  Per provarne solo una, usa i comandi della sezione «Test» del README (per esempio
  `tests/reale/test_router_reale.py`).
- **Pagina di prova delle API** (Swagger) dell'agente, senza Docker: `python -m agente.servizio`, poi apri
  `http://127.0.0.1:8000/docs`, clicca **POST /chat** → **Try it out**, nel riquadro scrivi
  `{"messaggio": "Che ore sono a Tokyo?"}` e clicca **Execute**. La risposta compare sotto, in
  **Response body**. `Ctrl+C` nel terminale per fermare il servizio.
- **Preferenze**: apri `server_mcp\risorse\preferenze.json` con `notepad`, cambia `"stile": "sintetico"` in
  `"dettagliato"`, salva (**Ctrl+S**), riavvia `python -m agente`: le risposte diventano più lunghe. Rimetti
  poi il valore originale.
- **Varianti dell'orologio**: sezione «Le tre varianti dell'orologio» del README.

---

## 7. Chiusura

```powershell
docker compose down        # ferma i container; le chat restano
deactivate                 # esce dall'ambiente Python
```

- **Non** usare `docker compose down -v`: cancella anche i volumi, cioè tutte le chat e le note.
- In LM Studio sposta **Status** su spento (o **Stop Server**) e scarica il modello per liberare memoria.

---

## 8. Se qualcosa non va

| Sintomo | Causa probabile | Che cosa fare |
|---|---|---|
| `Errore: LM Studio non risponde su http://localhost:1234/v1` | server di LM Studio spento | sezione 1.1, punto 4 |
| Pagina: **non pronto** per più di un minuto | agente fermo o LM Studio non raggiungibile da Docker | `docker compose logs agente`; controlla **Serve on Local Network** (1.1, punto 5) |
| `docker compose` si ferma con `imposta POSTGRES_PASSWORD nel file .env` | mancano le credenziali | aggiungi le tre righe `POSTGRES_*` al `.env` (sezione 1.3, punto 5) |
| `error during connect` / `docker daemon is not running` | Docker Desktop spento | sezione 1.2 |
| `port is already allocated` sulla 8090 | un altro programma usa la porta (per esempio `python -m frontend` aperto) | chiudi l'altro programma e rilancia `docker compose up -d` |
| Il browser dice «Impossibile raggiungere il sito» | container `frontend` non avviato | `docker compose ps`; se manca, `docker compose up -d --build` |
| Risposta che non usa lo strumento | comportamento del modello piccolo | riprova la domanda; vedi «Diagnosi per livelli» nel README |
| `.\.venv\Scripts\Activate.ps1` non parte | criteri di esecuzione di PowerShell | sezione 1.3, punto 3 |

Altri problemi Docker (WSL, virtualizzazione, firewall): [GUIDA_DOCKER.md](GUIDA_DOCKER.md).

---

## 9. Checklist

- [ ] `python -m pytest -q` → nessun failed
- [ ] Chat locale: ora, calcolo, meteo, nota, rifiuto fuori ambito, `/prompts`, `/prompt` valido e bloccato
- [ ] Compose: quattro servizi, solo la porta 8090
- [ ] Browser: stato **pronto**, conversazione con strumento mostrato sotto la risposta
- [ ] Browser: più chat, apertura ed eliminazione
- [ ] Chat presenti dopo `down` / `up`
- [ ] Agente fermato: banner leggibile, domanda di nuovo nella casella, nulla salvato; × chiude il banner
- [ ] Agente riavviato: invio di nuovo funzionante
- [ ] `docker compose run --rm assistente` con la tastiera
- [ ] (facoltativo) prove reali

---

## 10. Lavorare con Claude Code: meno token, progetto migliore

**Skill da installare: nessuna obbligatoria.** Superpowers (già installato) copre specifica, piano, TDD,
verifica e revisione. Già disponibili, basta richiamarle:

- `/fewer-permission-prompts`: aggiunge al progetto i comandi di sola lettura più usati, così Claude chiede
  meno conferme.
- `/code-review` a fine step e `/simplify` sul diff, al posto di revisioni lunghe fatte a mano.
- Facoltativa: una piccola skill di progetto (`.claude/skills/`) con i comandi di avvio e di test, così una
  sessione nuova non deve ricercarli.

**Come spendere meno token:**

1. `/clear` tra uno step e l'altro; `/compact` quando una sessione si allunga.
2. A inizio sessione far leggere solo `CLAUDE.md` e `docs/PROSSIMA_SESSIONE.md` (che è corto apposta).
3. Aggiornare README e documenti **una volta a fine step**, non dopo ogni commit.
4. Test con poco output: `python -m pytest -q -x` (si ferma al primo errore). Prove reali solo quelle dello
   step in corso (`-k nome`), non tutta la suite `-m reale` (molti minuti di log nel contesto).
5. Per step piccoli chiedere «specifica e piano brevi, una pagina», o saltare il brainstorming se le
   decisioni sono già scritte nel prompt.
6. `/model`: Sonnet per lavori di routine (documenti, piccole correzioni), Opus per progettazione e debug.

**Prompt di ripartenza consigliato:**

```
Leggi CLAUDE.md e docs/PROSSIMA_SESSIONE.md, poi git status. Step: <nome> della lezione N
(materiali/LLM_Lez_N.pdf, slide X–Y). Spec e piano brevi in docs/superpowers/, branch da dev,
test con modello simulato + una prova reale mirata, documenti aggiornati solo a fine step, merge in dev, niente push.
```

**Handoff a fine sessione**: `docs/PROSSIMA_SESSIONE.md` viene riscritto da capo alla fine di ogni sessione
con un modello fisso (fatto, esiti, stato Git, cosa resta, prossimo passo, prompt). Le versioni precedenti
restano nella cronologia Git (`git log -p docs/PROSSIMA_SESSIONE.md`).
