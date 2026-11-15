# Front-end: interfaccia di chat nel browser (lezione 6, step 8)

Data: 2026-11-15. Fonte: `materiali/LLM_Lez_6.pdf`, «Step 8 · Front-end: interfaccia di chat».
Parte dallo step 7 (back-end con PostgreSQL). Modalità autonoma: le scelte sono di Claude.

## 1. Problema
Serve un'interfaccia di chat utilizzabile da chi non conosce il progetto, che parli **solo con il
back-end**. Il contratto è il documento OpenAPI del back-end (`GET /openapi.json`): le chiamate si
scrivono da quella descrizione, senza indovinare gli endpoint.

## 2. Scelte
- **Tecnologia**: HTML, CSS e JavaScript senza framework né build (nessuna nuova dipendenza, niente
  Node in esercizio). Cartella `frontend/static/`: `index.html`, `stile.css`, `app.js`.
- **Servire i file in locale**: `python -m frontend` (solo libreria standard, `http.server`), porta
  `FRONTEND_PORTA` (default 8090) su `FRONTEND_ASCOLTO` (default 127.0.0.1).
- **Indirizzo del back-end da configurazione**: la pagina carica `/config.js`, generato dal server a
  partire da `FRONTEND_BACKEND_URL` (default `http://127.0.0.1:8080`):
  `window.CONFIGURAZIONE = {"backend": "..."}`. In Docker (step 9) lo stesso file lo genererà nginx.
- **CORS**: front-end (8090) e back-end (8080) sono origini diverse; il back-end abilita le origini di
  `BACKEND_ORIGINI` (separate da virgole, default `http://127.0.0.1:8090,http://localhost:8090`; vuota =
  nessuna). `crea_app` accetta già `origini_consentite`.

## 3. Interfaccia
- Colonna a sinistra: «+ Nuova chat», elenco delle chat (titolo, data dell'ultimo messaggio), la chat
  aperta evidenziata, pulsante di eliminazione con conferma. In alto lo stato (`GET /stato`): pallino
  verde «pronto» o rosso con il motivo (database o agente non raggiungibili).
- Area principale: messaggi in ordine (utente a destra, assistente a sinistra), sotto ogni risposta gli
  strumenti usati (`ora_corrente(fuso_orario=Asia/Tokyo)`, in rosso se `esito=errore`).
- Invio con il pulsante o Invio (Maiusc+Invio per andare a capo). Senza chat aperta, il primo invio crea la
  chat. **Attesa**: casella e pulsante disabilitati, la domanda compare subito e sotto «L'assistente sta
  rispondendo…» con il tempo trascorso (il modello locale può impiegare minuti).
- **Errori**: banner leggibile con il messaggio `errore` del back-end (o «Il back-end non è raggiungibile
  su …» se la rete fallisce); l'interfaccia non si blocca. Se l'invio fallisce la domanda non è stata
  salvata (step 7): viene tolta dalla vista e rimessa nella casella per riprovare.
- I testi si inseriscono con `textContent` (mai `innerHTML` con dati), a capo preservati.

## 4. Test
- Automatici: `frontend/__main__.py` (file statici, `config.js` dalla variabile, porta non valida);
  contratto: ogni chiamata `chiama("METODO", "/percorso")` di `app.js` esiste con quel metodo
  nell'OpenAPI del back-end; CORS del back-end con `BACKEND_ORIGINI`.
- Manuali nel browser (evidenze della slide): conversazione completa con uno strumento; chat ancora
  presente dopo il riavvio del back-end; agente spento → errore mostrato, interfaccia utilizzabile.

## 5. Non obiettivi
Streaming, markdown nelle risposte, autenticazione, rinomina delle chat, Docker (step 9).
