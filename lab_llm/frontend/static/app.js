// Interfaccia di chat (lezione 6, step 8): parla solo con il back-end.
// Contratto: l'OpenAPI del back-end (GET /openapi.json); l'indirizzo arriva da config.js.
"use strict";

const BACKEND = ((window.CONFIGURAZIONE || {}).backend || "").replace(/\/+$/, "");

const el = (id) => document.getElementById(id);
const stato = { chatAperta: null, inAttesa: false };

// --- chiamate al back-end -------------------------------------------------------------------

class ErroreApi extends Error {
  constructor(messaggio, dati = null) {
    super(messaggio);
    this.dati = dati;  // corpo della risposta d'errore, se c'è (per esempio /stato con 503)
  }
}

async function chiama(metodo, percorso, corpo) {
  let risposta;
  try {
    risposta = await fetch(BACKEND + percorso, {
      method: metodo,
      headers: corpo === undefined ? {} : { "Content-Type": "application/json" },
      body: corpo === undefined ? undefined : JSON.stringify(corpo),
    });
  } catch {
    throw new ErroreApi(`Il back-end non è raggiungibile su ${BACKEND || "questa pagina"}. Controlla che sia avviato.`);
  }
  if (risposta.status === 204) return null;
  let dati = null;
  try { dati = await risposta.json(); } catch { /* corpo non JSON */ }
  if (!risposta.ok) {
    const messaggio = (dati && dati.errore) || (dati && dati.detail && "Richiesta non valida.")
      || `Errore ${risposta.status} dal back-end.`;
    throw new ErroreApi(messaggio, dati);
  }
  return dati;
}

const api = {
  stato: () => chiama("GET", "/stato"),
  elenca: () => chiama("GET", "/chat"),
  crea: () => chiama("POST", "/chat", {}),
  leggi: (id) => chiama("GET", `/chat/${id}`),
  elimina: (id) => chiama("DELETE", `/chat/${id}`),
  invia: (id, testo) => chiama("POST", `/chat/${id}/messaggi`, { testo }),
};

// --- errori e stato -------------------------------------------------------------------------

function mostraErrore(testo) {
  el("errore-testo").textContent = testo;
  el("errore").hidden = false;
}

function nascondiErrore() {
  el("errore").hidden = true;
}

async function aggiornaStato() {
  const riga = el("stato");
  const testo = el("stato-testo");
  try {
    await api.stato();
    riga.className = "stato pronto";
    testo.textContent = "pronto";
    riga.title = "Back-end, database e agente raggiungibili";
  } catch (errore) {
    // /stato risponde 503 con il dettaglio: si dice che cosa manca.
    const dati = errore.dati;
    const mancanti = [];
    if (dati && dati.database && !dati.database.raggiungibile) mancanti.push("database");
    if (dati && dati.agente && !dati.agente.raggiungibile) mancanti.push("agente");
    if (dati && dati.agente && dati.agente.modello && !dati.agente.modello.raggiungibile) mancanti.push("modello");
    riga.className = "stato guasto";
    testo.textContent = dati ? `non pronto: ${mancanti.join(", ") || "?"} non raggiungibile` : "back-end non raggiungibile";
    riga.title = errore.message;
  }
}

// --- elenco delle chat ----------------------------------------------------------------------

const formatoData = new Intl.DateTimeFormat("it-IT", { dateStyle: "short", timeStyle: "short" });

async function aggiornaElenco() {
  const elenco = await api.elenca();
  const ul = el("elenco-chat");
  ul.replaceChildren(...elenco.map(vocePerChat));
  el("elenco-vuoto").hidden = elenco.length > 0;
}

function vocePerChat(chat) {
  const li = document.createElement("li");
  if (chat.id === stato.chatAperta) li.className = "aperta";

  const apri = document.createElement("button");
  apri.type = "button";
  apri.className = "apri";
  const titolo = document.createElement("strong");
  titolo.textContent = chat.titolo;
  const data = document.createElement("small");
  data.textContent = formatoData.format(new Date(chat.ultimo_messaggio_il));
  apri.append(titolo, data);
  apri.addEventListener("click", () => apriChat(chat.id));

  const elimina = document.createElement("button");
  elimina.type = "button";
  elimina.className = "elimina";
  elimina.textContent = "🗑";
  elimina.title = "Elimina la chat";
  elimina.setAttribute("aria-label", `Elimina la chat «${chat.titolo}»`);
  elimina.addEventListener("click", () => eliminaChat(chat));

  li.append(apri, elimina);
  return li;
}

// --- messaggi -------------------------------------------------------------------------------

function nodoMessaggio(messaggio) {
  const div = document.createElement("div");
  div.className = `messaggio ${messaggio.ruolo}`;
  const nuvola = document.createElement("div");
  nuvola.className = "nuvola";
  nuvola.textContent = messaggio.testo;
  div.append(nuvola);
  if (messaggio.strumenti && messaggio.strumenti.length) {
    const riga = document.createElement("div");
    riga.className = "strumenti";
    for (const s of messaggio.strumenti) {
      const etichetta = document.createElement("span");
      etichetta.className = s.esito === "errore" ? "strumento errore-strumento" : "strumento";
      const argomenti = Object.entries(s.argomenti || {}).map(([k, v]) => `${k}=${v}`).join(", ");
      etichetta.textContent = `${s.nome}(${argomenti})`;
      etichetta.title = s.esito === "errore" ? "lo strumento ha restituito un errore" : "strumento usato";
      riga.append(etichetta);
    }
    div.append(riga);
  }
  if (messaggio.creato_il) {
    const ora = document.createElement("span");
    ora.className = "ora";
    ora.textContent = formatoData.format(new Date(messaggio.creato_il));
    div.append(ora);
  }
  return div;
}

function mostraMessaggi(messaggi) {
  const area = el("messaggi");
  if (!messaggi.length) {
    area.replaceChildren(el("benvenuto") || creaBenvenuto());
    return;
  }
  area.replaceChildren(...messaggi.map(nodoMessaggio));
  area.scrollTop = area.scrollHeight;
}

const testoBenvenuto = el("benvenuto").textContent;
function creaBenvenuto() {
  const p = document.createElement("p");
  p.id = "benvenuto";
  p.className = "benvenuto";
  p.textContent = testoBenvenuto;
  return p;
}

async function apriChat(id) {
  if (stato.inAttesa) return;
  nascondiErrore();
  try {
    const chat = await api.leggi(id);
    stato.chatAperta = chat.id;
    el("titolo-chat").textContent = chat.titolo;
    mostraMessaggi(chat.messaggi);
    await aggiornaElenco();
    el("testo").focus();
  } catch (errore) {
    mostraErrore(errore.message);
  }
}

function nuovaChat() {
  if (stato.inAttesa) return;
  nascondiErrore();
  stato.chatAperta = null;  // la chat si crea al primo invio
  el("titolo-chat").textContent = "Nuova chat";
  mostraMessaggi([]);
  aggiornaElenco().catch((errore) => mostraErrore(errore.message));
  el("testo").focus();
}

async function eliminaChat(chat) {
  if (stato.inAttesa) return;
  if (!window.confirm(`Eliminare la chat «${chat.titolo}» e tutti i suoi messaggi?`)) return;
  nascondiErrore();
  try {
    await api.elimina(chat.id);
    if (chat.id === stato.chatAperta) nuovaChat();
    else await aggiornaElenco();
  } catch (errore) {
    mostraErrore(errore.message);
  }
}

// --- invio con stato di attesa --------------------------------------------------------------

function impostaAttesa(attiva) {
  stato.inAttesa = attiva;
  el("testo").disabled = attiva;
  el("invia").disabled = attiva;
  el("nuova-chat").disabled = attiva;
  el("invia").textContent = attiva ? "Attendi…" : "Invia";
}

function nodoAttesa() {
  const div = nodoMessaggio({ ruolo: "assistente", testo: "L'assistente sta rispondendo…" });
  div.classList.add("attesa");
  const inizio = Date.now();
  const nuvola = div.querySelector(".nuvola");
  const timer = setInterval(() => {
    const secondi = Math.round((Date.now() - inizio) / 1000);
    nuvola.textContent = `L'assistente sta rispondendo… (${secondi} s)`;
  }, 1000);
  return { div, ferma: () => clearInterval(timer) };
}

async function invia(evento) {
  evento.preventDefault();
  const casella = el("testo");
  const testo = casella.value.trim();
  if (!testo || stato.inAttesa) return;
  nascondiErrore();
  impostaAttesa(true);
  casella.value = "";

  const area = el("messaggi");
  if (el("benvenuto")) area.replaceChildren();
  const domanda = nodoMessaggio({ ruolo: "utente", testo });
  const attesa = nodoAttesa();
  area.append(domanda, attesa.div);
  area.scrollTop = area.scrollHeight;

  try {
    if (stato.chatAperta === null) {
      const chat = await api.crea();
      stato.chatAperta = chat.id;
      await aggiornaElenco();
    }
    await api.invia(stato.chatAperta, testo);
    attesa.ferma();
    const chat = await api.leggi(stato.chatAperta);
    el("titolo-chat").textContent = chat.titolo;
    mostraMessaggi(chat.messaggi);
    await aggiornaElenco();
  } catch (errore) {
    // La domanda non è stata salvata (il back-end salva solo a risposta ricevuta): la si rimette nella casella.
    attesa.ferma();
    domanda.remove();
    attesa.div.remove();
    if (!area.children.length) area.replaceChildren(creaBenvenuto());
    casella.value = testo;
    mostraErrore(errore.message);
    aggiornaStato();
  } finally {
    impostaAttesa(false);
    casella.focus();
  }
}

// --- avvio ----------------------------------------------------------------------------------

el("composizione").addEventListener("submit", invia);
el("testo").addEventListener("keydown", (evento) => {
  if (evento.key === "Enter" && !evento.shiftKey) {
    evento.preventDefault();
    el("composizione").requestSubmit();
  }
});
el("nuova-chat").addEventListener("click", nuovaChat);
el("errore-chiudi").addEventListener("click", nascondiErrore);

aggiornaStato();
setInterval(aggiornaStato, 30000);
aggiornaElenco().catch((errore) => mostraErrore(errore.message));
