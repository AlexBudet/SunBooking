/* Tastiera virtuale RCH - modal #modalTastieraRCH, aperto dalla Console
 * Sblocco RCH (solo admin/owner).
 *
 * Layout: tastiera 40 tasti del manuale operativo PRINT! F (cap. 1.5).
 * Quello della PRINT! 3.0 RT RCH lo pubblica solo dietro login: finche' non
 * lo abbiamo, il modello cambia solo i COMANDI disponibili (SRV e ">C").
 *
 * IMPORTANTE: un tasto NON simula la pressione fisica. Manda il comando di
 * protocollo equivalente (COMANDI RCH PRINT RT 3-0.txt, estratto del manuale
 * protocollo PRINT! 3.0 RT) tramite /cassa/rch-console/send-raw. Per questo:
 *  - i menu X/Z/PRG/SRV (scorrimento con REPARTO / PREZZO REPARTO, conferma
 *    con CONTANTI, uscita con STORNO) non si possono replicare: al loro posto
 *    c'e' "Funzione n" (=C n, e >C n sulla 3.0 RT);
 *  - uno scontrino chiuso da qui e' un documento fiscale vero, ma Tosca non lo
 *    registra (come succede con la tastiera fisica).
 *
 * Display RCH: quello che si digita (cifre, CL, SHIFT, X, PREZZO, messaggi)
 * viene scritto anche sul display della stampante con =D1 (riga 1) e =D2
 * (riga 2), in una sola richiesta. Dopo un comando vero (vendita, pagamento,
 * modalita') il display lo aggiorna la stampante da se'. Il significato di
 * =D1/=D2/=D3 nell'estratto del manuale non e' spiegato: se le righe finissero
 * nel posto sbagliato, si cambiano CMD_RIGA1/CMD_RIGA2 qui sotto.
 *
 * Tutte le richieste passano da UNA coda: la stampante non accetta comandi in
 * parallelo. Gli aggiornamenti del display si accorpano: se si digita veloce
 * parte solo l'ultimo stato.
 *
 * Inserimento numeri come sul registratore (manuale cap. 4.2): le cifre sono
 * centesimi, "5 0 00" = 50,00. La virgola serve per i decimali di quantita' e
 * percentuali (e, se usata, anche per un importo: "10,5" = 10,50).
 *
 * ANN-SCO. manda =K (chiude il documento in corso, come _rch_clear in
 * cassa.py) e MAI =k: sulla 3.0 RT =k annulla l'ULTIMO documento emesso
 * (incidente Biella 01/08/2026, vedi commento in cassa.py).
 */
(function () {
  'use strict';

  var root = document.getElementById('rchTastiera');
  if (!root) return;

  var CMD_RIGA1 = '=D1';
  var CMD_RIGA2 = '=D2';
  var LARGHEZZA_DISPLAY = 20;

  var sendUrl = root.dataset.sendUrl;
  var csrfMeta = document.querySelector('meta[name="csrf-token"]');
  var csrf = csrfMeta ? (csrfMeta.getAttribute('content') || '') : '';
  var logBox = document.getElementById('rchLogContainer');
  var riga1 = document.getElementById('rchTkRiga1');
  var riga2 = document.getElementById('rchTkRiga2');
  var selModello = document.getElementById('rchTkModello');
  var chkSpecchio = document.getElementById('rchTkSpecchio');
  var statoSpecchio = document.getElementById('rchTkSpecchioStato');
  var modalTk = document.getElementById('modalTastieraRCH');
  var modalConsole = document.getElementById('modalConsoleRCH');
  var btnApri = document.getElementById('btnRchApriTastiera');

  var MODI = ['LOCK', 'REG', 'X', 'Z', 'PRG', 'SRV'];
  // La modalita' della stampante non si legge da protocollo: la tastiera la
  // conosce solo dopo numero + CHIAVE. Finche' non la sa, il display dice cosa
  // fare invece di "MODO ?", che non spiegava niente (e finiva anche sulla RCH).
  // Solo ASCII e max 20 caratteri: va anche sul display della stampante.
  var MODO_IGNOTO = 'PREMI 1 + CHIAVE';
  var st = { buf: '', qty: null, prezzo: null, shift: false, modo: null, msg: null, busy: false, inviato: false };

  // Stesso formato di rchLog() della console, cosi' "Copia" porta tutto insieme.
  function log(testo, tipo) {
    if (!logBox) return;
    var ts = new Date().toLocaleTimeString();
    var prefix = tipo === 'error' ? '❌' : tipo === 'success' ? '✅' : 'ℹ️';
    logBox.textContent += '\n[' + ts + '] ' + prefix + ' ' + testo;
    logBox.scrollTop = logBox.scrollHeight;
  }

  function isRT() { return selModello.value === 'rch_print_rt'; }

  function applicaModello() {
    root.classList.toggle('rch-tk-f', !isRT());
  }

  // "5000" -> "5000" (50,00 €) ; "10,5" -> "1050"
  function centesimi(s) {
    if (!s) return null;
    if (s.indexOf(',') >= 0) {
      var p = s.split(',');
      var interi = parseInt(p[0] || '0', 10) || 0;
      var dec = parseInt(((p[1] || '') + '00').slice(0, 2), 10) || 0;
      return String(interi * 100 + dec);
    }
    return String(parseInt(s, 10) || 0);
  }

  function euro(cent) {
    var n = parseInt(cent, 10) || 0;
    return (n / 100).toFixed(2).replace('.', ',');
  }

  // quantita' e percentuali: virgola -> punto, come vuole il protocollo (=%/*12.15)
  function decimale(s) { return s ? s.replace(',', '.') : null; }

  // Protocollo: solo ASCII 20h-7Fh, ")" si raddoppia dentro (descrizione).
  function testoProtocollo(t, max) {
    return String(t || '').replace(/[^\x20-\x7E]/g, '').slice(0, max).replace(/\)/g, '))');
  }

  function azzera() { st.buf = ''; st.qty = null; st.prezzo = null; }

  function inREG() { return st.modo === null || st.modo === 1; }

  function mostra() {
    var r1 = st.modo === null ? MODO_IGNOTO : MODI[st.modo];
    if (st.shift) r1 += '  SHIFT';
    if (st.qty) r1 += '  ' + st.qty.replace('.', ',') + 'X';
    if (st.prezzo) r1 += '  PR.REP ' + euro(st.prezzo);
    riga1.textContent = st.msg || r1;
    riga1.classList.toggle('rch-tk-msg', !!st.msg);

    var r2;
    if (st.buf.indexOf(',') >= 0) r2 = st.buf;
    else if (inREG()) r2 = euro(st.buf || '0');
    else r2 = st.buf || '0';
    riga2.textContent = r2;

    root.querySelector('.rch-tk-grid').classList.toggle('rch-tk-shift', st.shift);
  }

  // Un tasto rifiutato butta via quanto digitato: altrimenti le cifre restano
  // nel buffer e si attaccano a quelle digitate dopo ("500" + "906").
  function bloccatoFuoriREG(tipo) {
    if (st.modo === 0) { azzera(); st.msg = 'BLOCCATA: 1 + CHIAVE'; return true; }
    if (inREG()) return false;
    azzera();
    if (tipo === 'menu') st.msg = 'Menu: usa Funzione n';
    else if (tipo === 'esci') st.msg = 'Per uscire: 1 + CHIAVE';
    else st.msg = 'Solo in REG: 1 + CHIAVE';
    return true;
  }

  // ---- Coda unica verso la stampante -------------------------------------
  var coda = Promise.resolve();
  function inCoda(fn) {
    var p = coda.then(fn);
    coda = p.catch(function () {});
    return p;
  }

  async function post(comandi) {
    var headers = { 'Content-Type': 'application/json' };
    if (csrf) headers['X-CSRFToken'] = csrf;
    var corpo = comandi.length === 1 ? { command: comandi[0] } : { commands: comandi };
    var resp = await fetch(sendUrl, { method: 'POST', headers: headers, body: JSON.stringify(corpo) });
    return resp.json();
  }

  function invia(cmd) {
    st.inviato = true;
    if (st.busy) return Promise.resolve(null);
    st.busy = true;
    root.classList.add('rch-tk-busy');
    log('Tastiera: ' + cmd + '...');
    return inCoda(async function () {
      try {
        var data = await post([cmd]);
        log('Tastiera ' + cmd + ':\n' + JSON.stringify(data, null, 2), data.success ? 'success' : 'error');
        if (data.success) {
          st.msg = 'OK  ' + (data.command_sent || cmd);
        } else {
          var codice = data.error_code !== null && data.error_code !== undefined ? data.error_code : (data.error || '?');
          st.msg = 'ERR ' + codice + '  ' + (data.command_sent || cmd);
        }
        return data;
      } catch (e) {
        log('Tastiera ' + cmd + ': errore ' + e.message, 'error');
        st.msg = 'ERRORE DI RETE';
        return null;
      } finally {
        st.busy = false;
        root.classList.remove('rch-tk-busy');
        mostra();
      }
    });
  }

  // ---- Display RCH ---------------------------------------------------------
  var specchio = { testo: null, accodato: false, esito: null };

  function aggiornaStatoSpecchio(ok, data) {
    var esito = ok ? 'ok' : 'err';
    if (ok) {
      statoSpecchio.textContent = 'display RCH: aggiornato';
      statoSpecchio.className = 'text-success';
    } else {
      var codice = data && data.error_code !== null && data.error_code !== undefined ? data.error_code : ((data && data.error) || '?');
      statoSpecchio.textContent = 'display RCH: errore ' + codice;
      statoSpecchio.className = 'text-danger';
    }
    // Nel log solo i cambi di stato, non un rigo per ogni cifra digitata.
    if (esito !== specchio.esito) {
      log('Display RCH ' + (ok ? 'OK' : 'ERRORE') + ':\n' + JSON.stringify(data, null, 2), ok ? 'success' : 'error');
      specchio.esito = esito;
    }
  }

  function specchiaDisplay() {
    if (!chkSpecchio || !chkSpecchio.checked) return;
    var r1 = riga1.textContent.slice(0, LARGHEZZA_DISPLAY);
    var r2 = riga2.textContent.slice(-LARGHEZZA_DISPLAY);
    while (r2.length < LARGHEZZA_DISPLAY) r2 = ' ' + r2;   // a destra, come gli importi sul display
    specchio.testo = [r1, r2];
    if (specchio.accodato) return;   // la richiesta in coda prendera' il testo piu' recente
    specchio.accodato = true;
    inCoda(async function () {
      specchio.accodato = false;
      var t = specchio.testo;
      specchio.testo = null;
      if (!t) return;
      var comandi = [
        CMD_RIGA1 + '/(' + testoProtocollo(t[0], LARGHEZZA_DISPLAY) + ')',
        CMD_RIGA2 + '/(' + testoProtocollo(t[1], LARGHEZZA_DISPLAY) + ')'
      ];
      try {
        var data = await post(comandi);
        aggiornaStatoSpecchio(!!data.success, data);
      } catch (e) {
        aggiornaStatoSpecchio(false, { error: e.message });
      }
    });
  }

  // ---- Tasti ---------------------------------------------------------------
  async function pagamento(n) {
    if (bloccatoFuoriREG(n === '1' ? 'menu' : '')) return;
    var cmd = '=T' + n + (st.buf ? '/$' + centesimi(st.buf) : '');
    azzera();
    await invia(cmd);
  }

  async function funzione(prefisso) {
    if (!/^\d{1,4}$/.test(st.buf)) { st.buf = ''; st.msg = 'Digita il numero funzione'; return; }
    if (prefisso === '>' && !isRT()) { st.buf = ''; st.msg = '>C solo su 3.0 RT'; return; }
    var n = parseInt(st.buf, 10);
    st.buf = '';  // anche se poi si annulla la conferma
    var cmd = prefisso + 'C' + n;
    var modoTxt = st.modo === null ? 'modalità non nota' : 'modalità ' + MODI[st.modo];
    var ok = window.confirm(
      'Invio ' + cmd + ' alla stampante (' + modoTxt + ').\n\n' +
      'In Z e SRV alcune funzioni sono operazioni fiscali vere ' +
      '(es. =C10 in Z = chiusura giornaliera). Procedo?'
    );
    if (!ok) return;
    var data = await invia(cmd);
    if (data && data.success && prefisso === '=' && n <= 5) st.modo = n;
  }

  async function premi(k, el) {
    if (st.busy) return;
    st.msg = null;
    st.inviato = false;
    var shift = st.shift;
    // Manuale PRINT! F (1.5.1): SHIFT si azzera alla fine di una sequenza o
    // con un tasto funzione, NON con le cifre (SHIFT, 1 5 0, SCONTO = MAGG.).
    var cifra = /^(\d|00|,)$/.test(k);
    if (k !== 'SHIFT' && !cifra) st.shift = false;

    switch (k) {
      case '0': case '1': case '2': case '3': case '4':
      case '5': case '6': case '7': case '8': case '9': case '00':
        if (st.buf.length < 12) st.buf += k;
        break;

      case ',':
        if (st.buf.indexOf(',') < 0) st.buf += (st.buf ? ',' : '0,');
        break;

      case 'CL':
        if (st.buf || st.qty || st.prezzo) azzera();
        else st.msg = 'Sblocco stampante: Invia CL';
        break;

      case 'SHIFT':
        st.shift = !st.shift;
        break;

      case 'X': {
        if (!st.buf) { st.msg = "ORA: solo sul display RCH"; break; }
        var q = decimale(st.buf);
        st.buf = '';
        if (!/^\d{1,4}(\.\d{1,3})?$/.test(q) || parseFloat(q) <= 0) { st.msg = 'Quantità non valida'; break; }
        st.qty = q;
        break;
      }

      case 'CHIAVE': {
        var max = isRT() ? 5 : 4;
        if (!/^\d$/.test(st.buf) || parseInt(st.buf, 10) > max) {
          st.buf = '';
          st.msg = 'Digita 0-' + max + ' + CHIAVE';
          break;
        }
        var m = parseInt(st.buf, 10);
        azzera();
        var d = await invia('=C' + m);
        if (d && d.success) st.modo = m;
        break;
      }

      case 'R': {
        if (bloccatoFuoriREG('')) break;
        var cmdR = '=R' + el.dataset.rep;
        if (st.buf) cmdR += '/$' + centesimi(st.buf);
        if (st.qty) cmdR += '/*' + st.qty;
        azzera();
        await invia(cmdR);
        break;
      }

      case 'PREZZO':
        if (bloccatoFuoriREG('menu')) break;
        if (!st.buf) { st.msg = 'Importo + PREZZO REPARTO'; break; }
        st.prezzo = centesimi(st.buf);
        st.buf = '';
        st.msg = 'Ora n. reparto + REPARTO';
        break;

      case 'REP': {
        if (bloccatoFuoriREG('menu')) break;
        if (!/^\d{1,3}$/.test(st.buf) || parseInt(st.buf, 10) < 1) { st.buf = ''; st.msg = 'N. reparto + REPARTO'; break; }
        var cmdRep = '=R' + parseInt(st.buf, 10);
        if (st.prezzo) cmdRep += '/$' + st.prezzo;
        if (st.qty) cmdRep += '/*' + st.qty;
        azzera();
        await invia(cmdRep);
        break;
      }

      case 'STORNO':
        if (shift) { st.msg = 'RESO: da Registro Scontrini'; break; }
        if (bloccatoFuoriREG('esci')) break;
        await invia('=s');
        break;

      case 'ANNULLO':
        if (shift) {
          if (window.confirm('Annullo lo scontrino in corso (=K)?')) { azzera(); await invia('=K'); }
          break;
        }
        if (bloccatoFuoriREG('')) break;
        await invia('=a');
        break;

      case 'COD': {
        if (bloccatoFuoriREG('')) break;
        if (shift) {
          var t = window.prompt('Riga di testo da stampare (max 25 caratteri):', '');
          if (t === null || !t.trim()) break;
          await invia('="/?A/(' + testoProtocollo(t.trim(), 25) + ')');
        } else {
          var cf = window.prompt('Codice fiscale o partita IVA del cliente:', '');
          if (cf === null) break;
          cf = cf.replace(/\s+/g, '').toUpperCase();
          if (!/^[A-Z0-9]{11,16}$/.test(cf)) { st.msg = 'Codice fiscale non valido'; break; }
          await invia('="/?C/(' + cf + ')');
        }
        break;
      }

      case 'OPERATORE':
        if (bloccatoFuoriREG('')) break;
        if (!/^\d{1,2}$/.test(st.buf) || parseInt(st.buf, 10) < 1) { st.buf = ''; st.msg = 'N. operatore + OPERATORE'; break; }
        var op = parseInt(st.buf, 10);
        st.buf = '';
        await invia('=O' + op);
        break;

      case 'ASSEGNI':
        if (shift) { st.msg = 'PAG. DIV.: non disponibile'; break; }
        await pagamento('3');
        break;

      case 'CORR':
        await pagamento(shift ? '4' : '2');
        break;

      case 'CONTANTI':
        await pagamento('1');
        break;

      case 'SCONTO': {
        if (bloccatoFuoriREG('')) break;
        if (!st.buf) { st.msg = 'Importo + ' + (shift ? 'MAGG.' : 'SCONTO'); break; }
        var c = centesimi(st.buf);
        st.buf = '';
        await invia((shift ? '=V+/$' : '=V-/$') + c);
        break;
      }

      case 'PERC': {
        if (bloccatoFuoriREG('')) break;
        if (!st.buf) { st.msg = 'Percentuale + ' + (shift ? '+%' : '-%'); break; }
        var p = decimale(st.buf);
        st.buf = '';
        if (!/^\d{1,2}(\.\d{1,2})?$/.test(p) || parseFloat(p) <= 0) { st.msg = 'Percentuale non valida'; break; }
        await invia((shift ? '=%+/*' : '=%-/*') + p);
        break;
      }

      case 'SUBTOT':
        if (bloccatoFuoriREG('')) break;
        await invia('=S');
        break;

      case 'FUNZ_EQ':
        await funzione('=');
        break;

      case 'FUNZ_GT':
        await funzione('>');
        break;
    }
    mostra();
    // Dopo un comando vero il display lo aggiorna la stampante da se'; qui si
    // scrive solo quello che sulla RCH non arriverebbe (digitazione e messaggi).
    if (!st.inviato) specchiaDisplay();
  }

  root.addEventListener('click', function (ev) {
    var el = ev.target.closest('[data-k]');
    if (!el || !root.contains(el)) return;
    ev.preventDefault();
    premi(el.dataset.k, el);
  });

  selModello.addEventListener('change', function () {
    applicaModello();
    mostra();
  });

  if (chkSpecchio) {
    chkSpecchio.addEventListener('change', function () {
      if (!chkSpecchio.checked) { statoSpecchio.textContent = ''; specchio.esito = null; }
    });
  }

  // Ad ogni lettura di Stato Stampante: modello dal server; la modalita' torna
  // "?" perche' i pulsanti della console (CL, Reset, comando manuale) la
  // cambiano senza passare di qui.
  document.addEventListener('rch-status', function (ev) {
    var data = ev.detail || {};
    if (data.printer_model === 'rch_print_f' || data.printer_model === 'rch_print_rt') {
      selModello.value = data.printer_model;
      applicaModello();
    }
    st.modo = null;
    st.msg = null;
    mostra();
  });

  // ---- Apertura / chiusura del modal ---------------------------------------
  // base.html carica Bootstrap DOPO il contenuto della pagina: quando questo
  // file viene eseguito window.bootstrap non c'e' ancora, quindi si aggancia
  // tutto a DOMContentLoaded.
  var tooltips = [];
  var riapriConsole = false;

  function agganciaModal() {
    if (!window.bootstrap) return;
    // Tooltip Bootstrap: la console inizializza solo i suoi, questi li fa qui.
    if (bootstrap.Tooltip) {
      root.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
        tooltips.push(bootstrap.Tooltip.getOrCreateInstance(el));
      });
    }
    if (!btnApri || !modalTk || !bootstrap.Modal) return;
    btnApri.addEventListener('click', function () {
      var mTk = bootstrap.Modal.getOrCreateInstance(modalTk);
      if (modalConsole && modalConsole.classList.contains('show')) {
        riapriConsole = true;
        modalConsole.addEventListener('hidden.bs.modal', function () { mTk.show(); }, { once: true });
        bootstrap.Modal.getOrCreateInstance(modalConsole).hide();
      } else {
        mTk.show();
      }
    });

    modalTk.addEventListener('shown.bs.modal', function () {
      st.msg = null;
      mostra();
    });

    modalTk.addEventListener('hide.bs.modal', function () {
      tooltips.forEach(function (t) { t.hide(); });
    });

    // Chiusa la tastiera si torna alla console, dove c'e' il log da copiare.
    modalTk.addEventListener('hidden.bs.modal', function () {
      if (!riapriConsole || !modalConsole) return;
      riapriConsole = false;
      bootstrap.Modal.getOrCreateInstance(modalConsole).show();
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', agganciaModal);
  else agganciaModal();

  applicaModello();
  mostra();
})();
