# repo-lab-llm

Client Python minimo per conversare da terminale con un modello eseguito in locale con LM Studio, con risposte in streaming. Materiale della Lezione 3 del corso Deep Learning e LLM (ITS Alto Adriatico).

## Contenuto della repository

| File | Funzione |
|---|---|
| `client.py` | Client interattivo: domande da terminale, risposte in streaming, memoria della conversazione |
| `requirements.txt` | Dipendenze con versioni fissate |
| `.env.example` | Modello della configurazione locale, senza segreti |
| `CLAUDE.md` | Istruzioni di sviluppo lette da Claude Code |
| `.gitignore` | File esclusi da Git: configurazione locale, ambiente virtuale, pesi, log |

## Prerequisiti

- Windows con PowerShell, Git e VS Code (estensioni Python e Git Graph).
- Python con il launcher `py`.
- LM Studio con il modello `google/gemma-4-e2b`, quantizzazione a 4 bit (`Q4_K_M`).
- Claude Code CLI: guida ufficiale <https://code.claude.com/docs/en/setup>. In PowerShell: `irm https://claude.ai/install.ps1 | iex`, poi riaprire il terminale e verificare con `claude --version`.

## Preparazione

Dalla radice della repository:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

In VS Code selezionare l'interprete `.venv` con **Python: Select Interpreter**.

## Configurazione

1. In LM Studio scaricare e caricare `google/gemma-4-e2b` (4 bit), poi avviare il server dalla sezione Developer.
2. Leggere l'identificativo del modello esposto dal server:

   ```powershell
   $base = "http://localhost:1234/v1"
   (Invoke-RestMethod "$base/models").data | Select-Object id
   ```

3. Creare la configurazione locale, solo se `.env` non esiste già, e inserire l'identificativo letto al punto 2 al posto di `ID_MODELLO_REALE`:

   ```powershell
   Copy-Item .env.example .env
   notepad .env
   ```

`.env` resta sul proprio computer ed è escluso da Git.

## Avvio

```powershell
.\.venv\Scripts\python.exe client.py
```

Il client chiede una domanda alla volta e ignora le righe vuote; si esce scrivendo `esci`. La risposta arriva in streaming e compare man mano che il modello la genera. La conversazione resta in memoria finché il client è aperto: nulla viene salvato su file.

## Diagnosi rapida

| Messaggio | Primo controllo |
|---|---|
| `Connessione fallita` | LM Studio acceso, server avviato, URL e porta in `.env` |
| `Errore HTTP` con messaggio sul modello | Identificativo in `.env`, modello caricato |
| `Attesa scaduta` | Carico del computer, tempi del modello |
| Risposta vuota | `"reasoning_effort": "none"` nel payload: senza, il modello ragiona e consuma i token prima di rispondere |
| `KeyError: 'LM_BASE_URL'` o `'LM_MODEL'` | `.env` mancante o variabile non definita |
| `Errore dal server` | URL e percorso in `.env` (LM Studio segnala alcuni errori con stato 200); se la conversazione è molto lunga, riavviare il client per azzerarla |
| `Stream non valido` | Risposta del server non nel formato atteso: controllare server e versione di LM Studio |

Una risposta arrivata non è necessariamente corretta: va letta e valutata.

## Flusso di lavoro Git

Si sviluppa sul branch `dev`, si prova su `test` e solo dopo le prove si porta tutto su `main`, con un commit per ogni passo:

```powershell
git switch dev
# modifiche, poi:
git add <file>
git commit -m "Descrizione del passo"
git push
git switch test; git merge --ff-only dev; git push
# prove su test, poi:
git switch main; git merge --ff-only test; git push
```
