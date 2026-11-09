# Docker su Windows: avvio e risoluzione dei problemi

Questa guida accompagna `Dockerfile` e `compose.yaml` del progetto. Ogni sezione segue lo schema
**sintomo → causa → controlli (PowerShell) → soluzione**.

Legenda:
- **verificato**: comando eseguito davvero su questo PC il 2026-11-03, con l'esito riportato;
- **procedura documentata, non eseguita qui**: passaggio corretto secondo la documentazione di
  Docker/Microsoft, ma non provato su questa macchina (per esempio perché richiede di riavviare il PC
  o di cambiare la configurazione dell'hypervisor).

Tutti i comandi partono dalla cartella `lab_llm/`.

## Avvio normale (verificato)

```powershell
docker compose build
docker compose run --rm assistente
```

- `run` e non `up`: la chat ha bisogno di uno stdin interattivo.
- `--rm` elimina il container all'uscita (le note restano nel volume `note`, sezione 10).
- `compose.yaml` sovrascrive `LM_BASE_URL` con `http://host.docker.internal:1234/v1`: dal container,
  `localhost` è il container stesso, non il PC.
- Gli orari nei **log** del container sono in UTC (il container non ha un fuso impostato). L'ora
  restituita dallo strumento invece è corretta, perché lo strumento usa sempre un fuso IANA esplicito.

Esito della prova del 2026-11-03 (input passato via pipe, senza tty):

```powershell
"Che ore sono?`nesci" | docker compose run --rm -T assistente
```
```
INFO  agente.graph | strumento ora_corrente {} -> Fuso orario: Europe/Rome (CET, UTC+01:00) | ...
Assistente> Attualmente sono le 11:19:06 nel fuso orario Europe/Rome (CET, UTC+01:00).
```

---

## 1. Controlli iniziali

**Sintomo**: non sai da dove partire, oppure Docker «non funziona» senza un errore preciso.

**Controlli** (verificati, esito su questo PC):

| Comando | Cosa guardare | Esito qui |
|---|---|---|
| `docker version` | sezioni Client **e** Server | client 29.5.3 / server 29.5.3 |
| `docker info` | nessun errore di connessione | OK |
| `docker compose version` | Compose v2 o successivo | v5.1.4 |
| `wsl --status` | versione predefinita 2 | 2, distribuzione `docker-desktop` |
| `wsl -l -v` | `docker-desktop` in stato `Running`, versione 2 | Running, 2 |
| `systeminfo` | righe «Requisiti Hyper-V» e «Virtualizzazione» | «Rilevato hypervisor» |

```powershell
docker version
docker info
docker compose version
wsl --status
wsl -l -v
systeminfo | Select-String "Hyper-V|Virtualizzazione"
```

- Se `docker version` mostra solo il Client e un errore sul Server → sezione 5 (demone non avviato).
- Se `systeminfo` dice «Rilevato hypervisor. Le funzionalità necessarie per Hyper-V non verranno
  visualizzate.» va bene: un hypervisor è già attivo (quello di WSL 2/Hyper-V).
- L'output di `wsl` può comparire con spazi tra le lettere (è in UTF-16). Per leggerlo meglio:
  `$env:WSL_UTF8 = "1"` prima del comando.

## 2. Virtualizzazione nel BIOS/UEFI (Intel VT-x / AMD-V)

**Sintomo**: Docker Desktop all'avvio dice «Virtualization support not detected» oppure WSL 2 non parte
(`0x80370102`, «La macchina virtuale non può essere avviata...»).

**Causa**: la virtualizzazione hardware della CPU è disattivata nel firmware.

**Controlli**:
- Gestione attività → Prestazioni → CPU → voce **«Virtualizzazione: Abilitato»**.
- `systeminfo | Select-String "Virtualizzazione"`: se c'è la riga «Virtualizzazione abilitata nel
  firmware: Sì» va bene; se compare «Rilevato hypervisor» la virtualizzazione è già attiva.
- Attenzione: `(Get-CimInstance Win32_Processor).VirtualizationFirmwareEnabled` restituisce `False`
  anche quando la virtualizzazione è attiva, se un hypervisor è già in esecuzione. Su questo PC dà
  `False` pur con WSL 2 funzionante (verificato): non basarsi solo su questo valore.

**Soluzione** (procedura documentata, non eseguita qui):
1. Riavvia ed entra nel BIOS/UEFI (di solito F2, F10, Canc o Esc all'accensione; oppure
   Impostazioni → Sistema → Ripristino → Avvio avanzato → Opzioni avanzate → Impostazioni firmware UEFI).
2. Cerca **Intel Virtualization Technology (VT-x)** oppure **SVM Mode / AMD-V**, di solito nei menu
   «Advanced», «CPU Configuration» o «Security».
3. Imposta **Enabled**, salva e riavvia.

## 3. WSL 2 e la piattaforma per macchine virtuali

**Sintomo**: Docker Desktop chiede di installare o aggiornare WSL, oppure `wsl --status` non mostra
la versione 2.

**Causa**: WSL 2 è il backend consigliato per Docker Desktop su Windows; richiede la funzionalità
«Piattaforma macchina virtuale».

**Controlli** (verificati): `wsl --status`, `wsl -l -v`.

**Soluzione** (procedura documentata, non eseguita qui: su questo PC WSL 2 è già attivo). In PowerShell
**come amministratore**:

```powershell
wsl --install
wsl --update
wsl --set-default-version 2
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
```

Poi riavvia il PC.

## 4. Hypervisor e Hyper-V: attivare e disattivare

**Sintomo**: un altro programma di virtualizzazione (per esempio VMware Workstation) è lento o si
rifiuta di partire, oppure, al contrario, Docker/WSL 2 non partono dopo aver disattivato qualcosa.

**Causa**: Windows decide all'avvio se caricare il proprio hypervisor (`hypervisorlaunchtype`). WSL 2
e Docker Desktop **ne hanno bisogno**.

**Controlli** (PowerShell come amministratore; senza privilegi `bcdedit` non mostra nulla, come è
successo qui):

```powershell
bcdedit /enum | Select-String hypervisorlaunchtype
```

**Soluzione** (procedura documentata, non eseguita qui: non va cambiata la configurazione
dell'hypervisor senza una ragione precisa):

```powershell
bcdedit /set hypervisorlaunchtype auto   # attiva l'hypervisor (serve a Docker e WSL 2)
bcdedit /set hypervisorlaunchtype off    # lo disattiva (Docker e WSL 2 smettono di funzionare)
```

Dopo ogni modifica bisogna riavviare il PC.

La funzionalità Hyper-V completa (gestore di macchine virtuali, solo Windows Pro/Enterprise) si
attiva o disattiva così, sempre da amministratore e poi con un riavvio:

```powershell
Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -All
Disable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All
```

Docker Desktop con backend WSL 2 **non** richiede la funzionalità Hyper-V completa: bastano
l'hypervisor e la «Piattaforma macchina virtuale».

**Convivenza con VMware Workstation** (installato su questo PC):
- dalla versione 15.5 VMware Workstation funziona anche con l'hypervisor di Windows attivo, usando le
  API di Hyper-V (Windows Hypervisor Platform);
- il compromesso: le macchine VMware diventano più lente e alcune funzioni (per esempio la
  virtualizzazione annidata) possono non essere disponibili;
- disattivare l'hypervisor (`off`) restituisce a VMware le prestazioni piene, ma ferma Docker
  Desktop e WSL 2 fino a quando non lo riattivi (`auto`) e riavvii.
- In pratica: lasciare `auto` se si usa Docker per questo corso; passare a `off` solo per un lavoro
  in VMware che lo richieda davvero, ricordando di tornare indietro.

## 5. Demone Docker non avviato

**Sintomo** (errore visto il 2026-10-26):

```
failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine ...
```

**Causa**: Docker Desktop non è avviato, o il suo motore Linux non è ancora pronto.

**Controlli**: `docker version` (manca la sezione Server), `wsl -l -v` (`docker-desktop` non è
`Running`).

**Soluzione**:
1. Avvia Docker Desktop e aspetta che in basso a sinistra compaia **«Engine running»**. Poi riprova
   `docker info` (verificato: dopo l'avvio di Docker Desktop risponde con il server 29.5.3).
2. Se resta bloccato (procedura documentata, non eseguita qui): chiudi Docker Desktop, esegui
   `wsl --shutdown`, riapri Docker Desktop.
3. Ancora niente: Docker Desktop → icona del bug (**Troubleshoot**) → **Restart**; come ultima
   risorsa **Reset to factory defaults** (cancella immagini e container locali).

## 6. Il container non raggiunge LM Studio

**Sintomo**: dal container l'avvio si ferma con «LM Studio non risponde su
http://host.docker.internal:1234/v1».

**Cause possibili**:
- LM Studio o il suo server non sono avviati sull'host;
- il server di LM Studio ascolta solo su `127.0.0.1`;
- il firewall di Windows blocca la porta 1234.

**Controlli**:

```powershell
# Su quale indirizzo ascolta LM Studio (0.0.0.0 = tutte le interfacce)
netstat -ano | Select-String ":1234 "

# Prova dal container, senza avviare la chat
docker compose run --rm -T assistente python -c "import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:1234/v1/models').read()[:200])"

# Verifica che il modello configurato sia disponibile, dal container
docker compose run --rm -T assistente python -c "from agente.llm import verifica_modello; from agente.config import carica_config; verifica_modello(carica_config()); print('ok')"

# Regole del firewall per LM Studio
Get-NetFirewallRule -DisplayName "*LM Studio*" | Select-Object DisplayName, Enabled, Direction, Action, Profile
```

Esiti su questo PC (verificati il 2026-11-03):
- LM Studio ascolta su `0.0.0.0:1234`, quindi «Serve on Local Network» era già attivo;
- la prova con `urllib` stampa l'inizio dell'elenco dei modelli (`"id": "google/gemma-4-e2b"`, ...);
- la verifica del modello dal container stampa `ok`;
- esistono regole in ingresso «lm studio.exe» abilitate (Allow, profilo Public).

Non è stato provato se il container raggiunge LM Studio anche con «Serve on Local Network»
disattivato: con l'opzione attiva funziona.

**Soluzione**:
1. In LM Studio avvia il server (Developer → Start Server) e carica il modello.
2. Attiva **«Serve on Local Network»** (Developer → Server Settings).
3. `compose.yaml` contiene già `extra_hosts: host.docker.internal:host-gateway`, che serve anche su
   motori Docker diversi da Docker Desktop.
4. Se il firewall blocca (procedura documentata, non eseguita qui): Sicurezza di Windows → Firewall e
   protezione rete → Consenti app attraverso il firewall → spunta LM Studio per le reti **private**
   (e pubbliche solo se necessario).

## 7. Build fallita

**Sintomo**: `docker compose build` si interrompe durante `pip install` o durante il download
dell'immagine `python:3.13-slim`.

**Cause**: rete assente o proxy aziendale, cache corrotta, disco pieno.

**Controlli**:

```powershell
docker system df          # spazio usato da immagini, container, volumi e cache (verificato)
```

**Soluzione**:
- rete/proxy: verifica la connessione; con un proxy, configurarlo in Docker Desktop → Settings →
  Resources → Proxies (procedura documentata, non eseguita qui);
- ricostruire senza cache: `docker compose build --no-cache` (procedura documentata, non eseguita qui);
- liberare spazio: `docker system prune` (elimina container fermi, reti inutilizzate, immagini
  orfane e cache di build; chiede conferma). Procedura documentata, non eseguita qui.

## 8. La chat non riceve input

**Sintomo**: il container parte ma non accetta quello che scrivi, oppure esce subito.

**Causa**: avviato con `docker compose up` (che non collega lo stdin del terminale), oppure terminale
che non supporta la tty.

**Soluzione**:
- usa sempre `docker compose run --rm assistente`;
- `compose.yaml` ha `stdin_open: true` e `tty: true`: non toglierli;
- usa PowerShell o Windows Terminal; in terminali che non hanno tty (per esempio alcuni pannelli
  integrati) si può passare l'input via pipe con `-T`, come nella prova riportata all'inizio
  (verificato).

## 9. Pulizia

```powershell
docker compose down --rmi local   # rimuove rete del progetto e immagine lab_llm-assistente
docker image prune                # rimuove le immagini orfane (chiede conferma)
```

Procedura documentata, non eseguita qui: l'immagine è stata lasciata per le prove successive.

## 10. Le note e il volume `note`

L'immagine contiene anche `server_mcp/`: i server MCP partono dentro il container, come
sottoprocessi dell'agente. Il server `note` salva in `dati/note.sqlite3` (`NOTE_DB`), cioè in
`/app/dati`, che `compose.yaml` collega al **volume con nome** `note`. Il container con `--rm` sparisce
a ogni uscita, ma il volume resta: le note sopravvivono (la cronologia della chat no).

Verificato il 2026-11-09:
- `docker compose build` termina senza errori;
- dal container la rete verso Open-Meteo risponde:
  `docker compose run --rm assistente python -c "import httpx; print(httpx.get('https://api.open-meteo.com/v1/forecast?latitude=46&longitude=13&current=temperature_2m', timeout=10).status_code)"`
  stampa `200`;
- con l'input passato via pipe, il modello ha chiamato `meteo_attuale` e `aggiungi_nota`:

  ```powershell
  "Che tempo fa a Udine?`nRicordami di comprare il pane`nesci" | docker compose run --rm -T assistente
  ```
- una seconda esecuzione con `"Elenca le mie note`nesci"` ha restituito la nota: il volume
  persiste tra un container e l'altro.

Il nome reale del volume è il prefisso del progetto più `note`: su questo PC `lab_llm_note`
(`docker volume ls` lo mostra).

**Per svuotare le note**, cancella il volume (a nessun container deve servire in quel momento):

```powershell
docker volume rm lab_llm_note
```

Alla prossima esecuzione Docker ne crea uno nuovo e vuoto. `docker compose down` **non** lo elimina
(servirebbe `-v`, da evitare se vuoi tenere le note).

In locale, senza Docker, le note stanno in `dati/note.sqlite3` dentro `lab_llm/`: per svuotarle basta
cancellare quel file con l'agente spento.
