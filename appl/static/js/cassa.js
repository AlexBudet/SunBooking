document.addEventListener('DOMContentLoaded', function () {

  // Funzione per capitalizzare nome/cognome (prima lettera maiuscola per ogni parola)
  function capitalizeName(name) {
    if (!name) return name || '';
    return String(name).toLowerCase().replace(/\b\w/g, l => l.toUpperCase());
  }
  window.capitalizeName = capitalizeName;  // Rendi globale se serve altrove

  // MEMORIZZA gli appointment_id originali portati in cassa (set globale)
  window.originalAppointmentIds = window.originalAppointmentIds || new Set();

  // Flag per modifiche (inizialmente false)
  window.hasModifications = false;

  if (window.SERVIZI_PRECOMPILATI && window.SERVIZI_PRECOMPILATI.length > 0) {
    localStorage.removeItem('scontrinoServizi');
  }

  // --- OPERATORE ---
  const operatorInput = document.getElementById('operatorSelectInput');
  const operatorDropdown = document.getElementById('operatorDropdown');
  const btnStampa = document.getElementById('btnStampaScontrino');
  const stampaLabel = document.getElementById('stampaLabel');
  if (btnStampa) {
    btnStampa.style.display = 'none';
    btnStampa.classList.remove('attivo');
  }
  if (stampaLabel) {
    stampaLabel.classList.add('d-none');
  }

  document.addEventListener('click', function (e) {
    if (
      operatorInput && operatorDropdown &&
      !operatorInput.contains(e.target) &&
      !operatorDropdown.contains(e.target)
    ) {
      operatorDropdown.style.display = 'none';
    }
  });

  // Mostra i servizi frequenti all'apertura della pagina
fetch('/cassa/api/services?frequenti=1')
  .then(res => res.json())
  .then(servizi => {
    const qNow = (document.getElementById('searchServiceInput')?.value || '').trim();
    if (qNow.length < 3) popolaPulsantiServizi(servizi);
  });

  operatorInput.addEventListener('click', function () {
    fetch('/cassa/api/operators')
      .then(res => res.json())
      .then(operators => {
        operatorDropdown.innerHTML = '';
        operators.forEach(op => {
          const item = document.createElement('button');
          item.type = 'button';
          item.className = 'dropdown-item';
          item.textContent = `${capitalizeName(op.nome)} ${capitalizeName(op.cognome)}`;
          item.dataset.operatorId = op.id;
          item.onclick = function () {
            operatorInput.value = `${capitalizeName(op.nome)} ${capitalizeName(op.cognome)}`;
            operatorInput.dataset.selectedOperator = op.id;
            operatorDropdown.style.display = 'none';
            // Forza trigger evento change per listener modifiche
            operatorInput.dispatchEvent(new Event('change'));
          };
          operatorDropdown.appendChild(item);
        });
        operatorDropdown.style.display = 'block';
      });
  });

  // --- RIPRISTINA SERVIZI DAL LOCALSTORAGE AL CARICAMENTO ---
  let serviziSalvati = JSON.parse(localStorage.getItem('scontrinoServizi') || '[]');
  serviziSalvati.forEach(servizio => aggiungiRigaServizio(servizio, false));

  // --- SERVIZI AUTOCOMPLETE ---
const serviceInput = document.getElementById('searchServiceInput');
let svcReqSeq = 0;  // token per accettare solo l’ultima risposta

serviceInput.addEventListener('input', function () {
  const q = serviceInput.value.trim();
  const mySeq = ++svcReqSeq;

  if (q.length < 3) {
    fetch('/cassa/api/services?frequenti=1')
      .then(res => res.json())
      .then(servizi => {
        if (mySeq !== svcReqSeq) return; // risposta superata da una più recente
        popolaPulsantiServizi(servizi);
      });
    return;
  }

  fetch(`/cassa/api/services?q=${encodeURIComponent(q)}`)
    .then(res => res.json())
    .then(services => {
      if (mySeq !== svcReqSeq) return; // risposta superata da una più recente
      if (!Array.isArray(services)) {
        alert(services.error || "Errore imprevisto");
        return;
      }
      popolaPulsantiServizi(services);
    });
});

  const clientInput = document.getElementById('clientSearchInputCassa');
  const clientDropdown = document.getElementById('clientDropdownCassa');

  clientInput.addEventListener('input', function () {
    // Se il valore è impostato programmaticamente, non eseguire il fetch
    if (window.settingClientProgrammatically) {
      window.settingClientProgrammatically = false;
      return;
    }
    
    const q = clientInput.value.trim().toLowerCase();
    if (q.length < 3) {  // Cambiato da < 2 a < 3 per popolare alla 3a lettera
      clientDropdown.style.display = 'none';
      return;
    }
    fetch(`/cassa/api/clients?q=${encodeURIComponent(q)}`)
      .then(res => res.json())
      .then(clients => {
        clientDropdown.innerHTML = '';
        if (!Array.isArray(clients)) return;
        clients.forEach(c => {
          const item = document.createElement('button');
          item.type = 'button';
          item.className = 'dropdown-item';
          item.textContent = `${capitalizeName(c.nome)} ${capitalizeName(c.cognome)}`;
          item.onclick = function () {
            clientInput.value = `${capitalizeName(c.nome)} ${capitalizeName(c.cognome)}`;
            clientInput.dataset.selectedClient = c.id;
            clientDropdown.style.display = 'none';
            // Forza trigger evento input per listener modifiche
            clientInput.dispatchEvent(new Event('input'));
          };
          clientDropdown.appendChild(item);
        });
        clientDropdown.style.display = clients.length ? 'block' : 'none';
      });
  });

  // Chiudi dropdown cliente se clicchi fuori
  document.addEventListener('click', function (e) {
    if (
      clientInput && clientDropdown &&
      !clientInput.contains(e.target) &&
      !clientDropdown.contains(e.target)
    ) {
      clientDropdown.style.display = 'none';
    }
  });

  // Esempio di fetch per "ultimi" servizi
  document.getElementById('btnUltimi').addEventListener('click', function () {
    fetch('/cassa/api/services?ultimi=1')
      .then(res => res.json())
      .then(servizi => popolaPulsantiServizi(servizi));
  });

  // fetch per "frequenti"
  document.getElementById('btnFrequenti').addEventListener('click', function () {
    fetch('/cassa/api/services?frequenti=1')
      .then(res => res.json())
      .then(servizi => popolaPulsantiServizi(servizi));
  });

  // fetch per Estetica
  document.getElementById('btnEstetica').addEventListener('click', function () {
    fetch('/cassa/api/services?categoria=Estetica')
      .then(res => res.json())
      .then(servizi => popolaPulsantiServizi(servizi));
  });

  // fetch per Solarium
  document.getElementById('btnSolarium').addEventListener('click', function () {
    fetch('/cassa/api/services?categoria=Solarium')
      .then(res => res.json())
      .then(servizi => popolaPulsantiServizi(servizi));
  });

  document.getElementById('btnProdotti').addEventListener('click', function () {
    fetch('/cassa/api/services?sottocategoria=Prodotti')
      .then(res => res.json())
      .then(servizi => popolaPulsantiServizi(servizi));
  });

  document.getElementById('payCashBtn').addEventListener('click', function () {
    aggiornaMetodoPagamentoGlobale('cash');
    aggiornaSubtotaliPagamenti();
    if (window.originalAppointmentIds && window.originalAppointmentIds.size > 0) {
    window.hasModifications = true;
    mostraPulsanteSalva();
  }
  });
  document.getElementById('payPosBtn').addEventListener('click', function () {
    aggiornaMetodoPagamentoGlobale('pos');
    aggiornaSubtotaliPagamenti();
    if (window.originalAppointmentIds && window.originalAppointmentIds.size > 0) {
    window.hasModifications = true;
    mostraPulsanteSalva();
  }
  });
  document.getElementById('payBankBtn').addEventListener('click', function () {
    aggiornaMetodoPagamentoGlobale('bank');
    aggiornaSubtotaliPagamenti();
    if (window.originalAppointmentIds && window.originalAppointmentIds.size > 0) {
    window.hasModifications = true;
    mostraPulsanteSalva();
    }
  });

  // Listener per il pulsante neumorfico stampa scontrino
let stampaLock = false;
document.getElementById('btnStampaScontrino').addEventListener('click', async () => {
  if (stampaLock) return;
  stampaLock = true;
  setTimeout(() => { stampaLock = false; }, 5000);
      if (!confermaAttiva) {
    alert('Devi prima confermare lo scontrino!');
    return;
  }
    const rows = document.querySelectorAll('.scontrino-row');
    if (rows.length === 0) {
      alert('Aggiungi almeno un servizio prima di generare lo scontrino!');
      return;
    }

    const voci_fiscali = [];
    let  voci_non_fiscali = [];

    rows.forEach(row => {
      const isGrigia = row.style.background === 'rgb(220, 220, 220)' || row.style.background === '#dcdcdc';
      const nome = row.querySelector('.flex-grow-1')?.textContent.trim() || '';
      const prezzo = parseFloat(row.querySelector('.scontrino-row-prezzo')?.value || '0');
      const sconto_riga = parseInt(row.querySelector('.scontrino-row-sconto')?.value || '0');
      const metodo = row.querySelector('select')?.value || 'cash';
      const servizio_id = row.dataset.servizioId || null;
      const appointment_id = row.dataset.appointmentId || null;
      const rata_id = row.dataset.rataId || null;
      const pacchetto_id = row.dataset.pacchettoId || null;
      const voce = {
        servizio_id,
        nome,
        prezzo,
        sconto_riga,
        tipo: 'service',
        metodo_pagamento: metodo,
        is_fiscale: !isGrigia
      };
      if (appointment_id) voce.appointment_id = appointment_id;
      if (rata_id) voce.rata_id = parseInt(rata_id);
      if (pacchetto_id) voce.pacchetto_id = parseInt(pacchetto_id);
      if (isGrigia) {
        voci_non_fiscali.push(voce);
      } else {
        voci_fiscali.push(voce);
      }
    });

    const cliente_id = document.getElementById('clientSearchInputCassa').dataset.selectedClient || null;
    const operatore_id = document.getElementById('operatorSelectInput').dataset.selectedOperator || null;
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');

    // Se ci sono voci fiscali, invia a RCH e salva Receipt fiscale
    if (voci_fiscali.length > 0) {
      function generaIdempotencyKey() {
        return ([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g, c =>
          (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16)
        );
      }
      const idempotencyKey = generaIdempotencyKey();
      const payloadFiscale = {
        voci: voci_fiscali,
        cliente_id,
        operatore_id,
        is_fiscale: true,
        idempotency_key: idempotencyKey
      };

      // Modal attesa/retry
function showPendingModal(key) {
  if (document.getElementById('rchPendingModal')) return;

  const wrap = document.createElement('div');
  wrap.id = 'rchPendingModal';

  const overlay = document.createElement('div');
  overlay.className = 'modal fade show';
  overlay.setAttribute('tabindex', '-1');
  overlay.setAttribute('role', 'dialog');
  overlay.setAttribute('aria-modal', 'true');
  overlay.style.display = 'block';
  overlay.style.background = 'rgba(0,0,0,0.5)';

  const dialog = document.createElement('div');
  dialog.className = 'modal-dialog modal-dialog-centered';

  const content = document.createElement('div');
  content.className = 'modal-content';

  const header = document.createElement('div');
  header.className = 'modal-header';
  const h5 = document.createElement('h5');
  h5.className = 'modal-title';
  h5.textContent = 'Attesa stampante fiscale';
  header.appendChild(h5);

  const body = document.createElement('div');
  body.className = 'modal-body';

  const p = document.createElement('p');
  p.textContent = 'La stampante è in attesa (es. cambio carta). Sostituire la carta o risolvere l\'errore e poi premi "Riprova".';
  body.appendChild(p);

  const flex = document.createElement('div');
  flex.className = 'd-flex align-items-center';
  flex.style.gap = '10px';

  const spinner = document.createElement('div');
  spinner.className = 'spinner-border text-primary';
  spinner.setAttribute('role', 'status');
  const vis = document.createElement('span');
  vis.className = 'visually-hidden';
  vis.textContent = '...';
  spinner.appendChild(vis);

  const msg = document.createElement('span');
  msg.id = 'rchPendingMsg';
  msg.textContent = 'In attesa...';

  flex.appendChild(spinner);
  flex.appendChild(msg);
  body.appendChild(flex);

  const footer = document.createElement('div');
  footer.className = 'modal-footer';

  const btnRetry = document.createElement('button');
  btnRetry.id = 'rchRetryBtn';
  btnRetry.type = 'button';
  btnRetry.className = 'btn btn-primary';
  btnRetry.textContent = 'Riprova';

  const btnCancel = document.createElement('button');
  btnCancel.id = 'rchCancelBtn';
  btnCancel.type = 'button';
  btnCancel.className = 'btn btn-secondary';
  btnCancel.textContent = 'Chiudi';

  footer.appendChild(btnRetry);
  footer.appendChild(btnCancel);

  content.appendChild(header);
  content.appendChild(body);
  content.appendChild(footer);
  dialog.appendChild(content);
  overlay.appendChild(dialog);
  wrap.appendChild(overlay);
  document.body.appendChild(wrap);

  let pollTimer = setInterval(async () => {
    try {
      const r = await fetch(`/cassa/rch-status?idempotency_key=${encodeURIComponent(key)}`);
      const d = await r.json();
      if (r.ok && d.done) {
        clearInterval(pollTimer);
        wrap.remove();
        fiscaleOkFinalize();
      }
    } catch (_) {}
  }, 3000);

  btnRetry.addEventListener('click', async () => {
    btnRetry.disabled = true;
    try {
      const rr = await fetch('/cassa/rch-retry', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(csrfToken ? { 'X-CSRFToken': csrfToken } : {})
        },
        body: JSON.stringify({ idempotency_key: key })
      });
      const dd = await rr.json();
      if (rr.ok && dd.results) {
        clearInterval(pollTimer);
        wrap.remove();
        fiscaleOkFinalize();
        return;
      }
      btnRetry.disabled = false;
      msg.textContent = 'Ancora in attesa della stampante...';
    } catch {
      btnRetry.disabled = false;
      msg.textContent = 'Errore rete. Riprova.';
    }
  });

  btnCancel.addEventListener('click', () => {
    clearInterval(pollTimer);
    wrap.remove();
  });
}
      async function fiscaleOkFinalize() {
    // Non fiscali (grigi) se presenti
    // Se ci sono voci non fiscali, salva Receipt non fiscale (NON invia a RCH)
    let nonFiscaleResponse = null;
    if (voci_non_fiscali.length > 0) {
      const payloadNonFiscale = {
        voci: voci_non_fiscali,
        cliente_id,
        operatore_id,
        is_fiscale: false
      };
      const res = await fetch('/cassa/send-to-rch', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(csrfToken ? { 'X-CSRFToken': csrfToken } : {})
        },
        body: JSON.stringify(payloadNonFiscale)
      });
      nonFiscaleResponse = await res.json();
    }

    alert('Pagamento registrato con successo!');

        // Aggiorna stati appuntamenti
        const csrf = document.querySelector('meta[name="csrf-token"]')?.content;
        const updatePromises = [];
        document.querySelectorAll('.scontrino-row').forEach(row => {
          const appointmentId = row.dataset.appointmentId;
          if (appointmentId) {
            updatePromises.push(
              fetch(`/calendar/update_status/${appointmentId}`, {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json',
                  ...(csrf ? { 'X-CSRFToken': csrf } : {})
                },
                body: JSON.stringify({ status: 2 })
              }).catch(()=>{})
            );
          }
        });
        if (window.originalAppointmentIds && window.originalAppointmentIds.size > 0) {
          window.originalAppointmentIds.forEach(appointmentId => {
            updatePromises.push(
              fetch(`/calendar/update_status/${appointmentId}`, {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json',
                  ...(csrf ? { 'X-CSRFToken': csrf } : {})
                },
                body: JSON.stringify({ status: 2 })
              }).catch(()=>{})
            );
          });
        }
        await Promise.allSettled(updatePromises);
        if (window.originalAppointmentIds && typeof window.originalAppointmentIds.clear === 'function') {
          window.originalAppointmentIds.clear();
        }
        resetScontrino(true);
        setTimeout(() => { window.location.href = '/cassa'; }, 150);
      }

      try {
        const res = await fetch('/cassa/send-to-rch', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(csrfToken ? { 'X-CSRFToken': csrfToken } : {})
          },
          body: JSON.stringify(payloadFiscale)
        });
        let data = null;
        try { data = await res.json(); } catch { data = null; }

        if (res.status === 202 && data && data.pending) {
          // Attesa stampante: mostra modal e interrompi flusso
          showPendingModal(idempotencyKey);
          return;
        }
        if (!res.ok) {
          alert((data && data.error) || 'Errore durante la stampa fiscale!');
          return;
        }

        // Successo immediato
        await fiscaleOkFinalize();
        return;
      } catch (err) {
        alert('Errore di rete durante la stampa fiscale.');
        return;
      }
    }

    // Se ci sono voci non fiscali, salva Receipt non fiscale (NON invia a RCH)
    let nonFiscaleResponse = null;  // <-- AGGIUNGI
    if (voci_non_fiscali.length > 0) {
      const payloadNonFiscale = {
        voci: voci_non_fiscali,
        cliente_id,
        operatore_id,
        is_fiscale: false
      };
      const res = await fetch('/cassa/send-to-rch', {  // <-- CATTURA res
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(csrfToken ? { 'X-CSRFToken': csrfToken } : {})
        },
        body: JSON.stringify(payloadNonFiscale)
      });
      nonFiscaleResponse = await res.json();  // <-- AGGIUNGI
    }

    alert('Pagamento registrato con successo!');

    // Aggiorna prima gli appointment delle righe effettive e poi quelli originali portati da calendar.
    // Raccogliamo le promise e le aspettiamo tutte (allSettled) prima di resettare e reload.
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content;
    const updatePromises = [];

    document.querySelectorAll('.scontrino-row').forEach(row => {
      const appointmentId = row.dataset.appointmentId;
      if (appointmentId) {
        updatePromises.push(
          fetch(`/calendar/update_status/${appointmentId}`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              ...(csrf ? { 'X-CSRFToken': csrf } : {})
            },
            body: JSON.stringify({ status: 2 })
          })
          .then(response => {
            if (!response.ok) throw new Error(`Errore update appointment ${appointmentId}`);
            return response.json();
          })
          .catch(err => console.error("Impossibile aggiornare lo stato:", err))
        );
      }
    });

    if (window.originalAppointmentIds && window.originalAppointmentIds.size > 0) {
      window.originalAppointmentIds.forEach(appointmentId => {
        updatePromises.push(
          fetch(`/calendar/update_status/${appointmentId}`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              ...(csrf ? { 'X-CSRFToken': csrf } : {})
            },
            body: JSON.stringify({ status: 2 })
          })
          .then(response => {
            if (!response.ok) throw new Error(`Errore update original appointment ${appointmentId}`);
            return response.json();
          })
          .catch(err => console.error("Impossibile aggiornare appointment originale:", err))
        );
      });
    }

    await Promise.allSettled(updatePromises);
    if (window.originalAppointmentIds && typeof window.originalAppointmentIds.clear === 'function') {
      window.originalAppointmentIds.clear();
    }
    // Svuota il pseudoscontrino subito (ma NON navigare immediatamente) per permettere repaint visibile.
    resetScontrino(true);
    // NUOVO: Se il pagamento non fiscale era una rata di pacchetto, redirect a pacchetto_detail
    if (nonFiscaleResponse && nonFiscaleResponse.redirect_to_pacchetto) {
      const url = `/pacchetti/detail/${nonFiscaleResponse.redirect_to_pacchetto}`;
      if (nonFiscaleResponse.rata_importo_modificato) {
        window.location.href = url + '?ricalcola_rate=1';
      } else {
        window.location.href = url;
      }
    } else {
      // Comportamento normale per tutti gli altri pagamenti non fiscali
      setTimeout(() => { window.location.href = '/cassa'; }, 150);
    }
  });
});

// Funzione per aggiornare il totale
function aggiornaTotale() {
  let totaleScontrino = 0;
  let totaleComplessivo = 0;
  document.querySelectorAll('.scontrino-row').forEach(row => {
    const input = row.querySelector('.scontrino-row-prezzo');
    const prezzo = parseFloat(input.value) || 0;
    // Servizi in chiaro (non grigi)
    if (
      row.style.background !== 'rgb(220, 220, 220)' &&
      row.style.background !== '#dcdcdc'
    ) {
      totaleScontrino += prezzo;
    }
    // Tutti i servizi (anche grigi)
    totaleComplessivo += prezzo;
  });
  document.getElementById('totalAmount').textContent = `Scontrino: € ${totaleScontrino.toFixed(2)}`;
  document.getElementById('totalAmountAll').textContent = `Totale: € ${totaleComplessivo.toFixed(2)}`;
}

function getCurrentAppointmentIds() {
  const ids = new Set();
  document.querySelectorAll('.scontrino-row').forEach(row => {
    const id = row.dataset.appointmentId;
    if (id) ids.add(String(id));
  });
  return ids;
}

// NUOVA: Funzione per reset dello pseudoscontrino
function resetScontrino(keepData = false) {
  // Reset pulsante stampa scontrino
  const btnStampa = document.getElementById('btnStampaScontrino');
  const stampaLabel = document.getElementById('stampaLabel');
  if (btnStampa) {
    btnStampa.style.display = 'none';
    btnStampa.classList.remove('attivo');
  }
  if (stampaLabel) {
    stampaLabel.classList.add('d-none');
  }

  // Sblocca il container pseudoscontrino
  const container = document.querySelector('.card.neumorphic-card');
  if (container) {
    container.classList.remove('pseudoscontrino-bloccato');
  }

  // Rimuovi eventuale listener globale
  if (globalResetListener) {
    document.removeEventListener('click', globalResetListener, true);
    globalResetListener = null;
  }

  // Reset completo SEMPRE, anche dopo conferma
  confermaAttiva = false;

  document.getElementById('scontrinoRowsContainer').innerHTML = '';
  document.getElementById('scontrino-container').innerHTML = '';
  document.getElementById('totalAmount').textContent = 'Scontrino: € 0.00';
  document.getElementById('totalAmountAll').textContent = 'Totale: € 0.00';
  const anteprima = document.getElementById('anteprima-scontrino');
  if (anteprima) anteprima.remove();
  const stampaBtn = document.getElementById('stampa-scontrino-btn');
  if (stampaBtn) stampaBtn.remove();

  // Svuota anche i campi input cliente/operatore
  const clienteInput = document.getElementById('clientSearchInputCassa');
  if (clienteInput) {
    clienteInput.value = '';
    delete clienteInput.dataset.selectedClient;
  }
  const operatoreInput = document.getElementById('operatorSelectInput');
  if (operatoreInput) {
    operatoreInput.value = '';
    delete operatoreInput.dataset.selectedOperator;
  }

  // Svuota localStorage (aggiungi qui tutte le chiavi che usi)
  localStorage.removeItem('scontrinoServizi');
  localStorage.removeItem('scontrinoCliente');
  localStorage.removeItem('scontrinoOperatore');

  window.SERVIZI_PRECOMPILATI = [];

  document.getElementById('subtotaliPagamenti').innerHTML = '';
  document.getElementById('subtotaliPagamenti').style.display = 'none';

  // Nascondi pulsanti salva/reset
  const saveContainer = document.getElementById('saveModificheContainer');
  if (saveContainer) saveContainer.style.display = 'none';
  window.hasModifications = false;
  window.listenersAdded = false; // Reset flag listener
  window.appliedSavedModifications = false;

  // Pulisci anche la Set degli appointment_id per evitare chiavi sporche
  if (window.originalAppointmentIds && typeof window.originalAppointmentIds.clear === 'function') {
    window.originalAppointmentIds.clear();
  }

  if (!keepData) {
    window.location.href = '/cassa';
  }
}

function mostraPulsanteSalva() {
  const container = document.getElementById('saveModificheContainer');
  const saveBtn = document.getElementById('btnSaveModifiche');
  const resetBtn = document.getElementById('btnResetModifiche');

  const hasApplied = window.appliedSavedModifications === true;
  const canSave = !!(window.hasModifications && window.originalAppointmentIds && window.originalAppointmentIds.size > 0);
  const showContainer = hasApplied || canSave;

  if (container) container.style.display = showContainer ? 'block' : 'none';
  if (saveBtn)  saveBtn.style.display  = canSave ? 'inline-block' : 'none';
  if (resetBtn) resetBtn.style.display = hasApplied ? 'inline-block' : 'none';
}

function aggiungiRigaServizio(servizio, salva = true) {
  const container = document.getElementById('scontrinoRowsContainer');

  // Inizializza flag listener una sola volta
  if (typeof window.listenersAdded === 'undefined') {
    window.listenersAdded = false;
  }

  const row = document.createElement('div');
  row.dataset.appointmentId = servizio.appointment_id || '';
  row.dataset.rataId = servizio.rata_id || '';
  row.dataset.pacchettoId = servizio.pacchetto_id || '';
  row.className = 'd-flex align-items-center border scontrino-row mb-1';
  row.style.background = '#fff';
  row.dataset.servizioId = servizio.id || '';

  // Se la riga proviene da un appuntamento del calendar, memorizza l'id originale
  if (servizio.appointment_id) {
    window.originalAppointmentIds = window.originalAppointmentIds || new Set();
    window.originalAppointmentIds.add(String(servizio.appointment_id));
    window.appliedSavedModifications = false;
  }

  // Salva in localStorage solo se richiesto
  if (salva) {
    let servizi = JSON.parse(localStorage.getItem('scontrinoServizi') || '[]');
    if (!servizi.some(s => s.id === servizio.id)) {
      servizi.push(servizio);
      localStorage.setItem('scontrinoServizi', JSON.stringify(servizi));
    }
  }

  // Spazio vuoto cliccabile per selezione
  const selectBox = document.createElement('div');
  selectBox.style.width = '32px';
  selectBox.style.height = '32px';
  selectBox.style.cursor = 'pointer';
  row.appendChild(selectBox);

  // Nome servizio
  const nome = document.createElement('div');
  nome.className = 'flex-grow-1 px-2';
  nome.textContent = servizio.nome;
  row.appendChild(nome);

  // Prezzo editabile
  const prezzoOriginale = parseFloat(servizio.prezzo || 0);
  const prezzo = document.createElement('input');
  prezzo.type = 'number';
  prezzo.min = '0';
  prezzo.step = '0.01';
  prezzo.value = isNaN(prezzoOriginale) ? '0.00' : prezzoOriginale.toFixed(2);
  prezzo.className = 'form-control scontrino-row-prezzo';
  prezzo.name = 'prezzo[]';
  prezzo.style.width = '95px';
  prezzo.style.marginRight = '8px';
  row.appendChild(prezzo);

  // Simbolo euro
  const euro = document.createElement('span');
  euro.textContent = '€';
  euro.style.marginRight = '8px';
  row.appendChild(euro);

  // Sconto percentuale
  const sconto = document.createElement('input');
  sconto.type = 'number';
  sconto.min = '0';
  sconto.max = '100';
  sconto.step = '1';
  sconto.value = '0';
  sconto.className = 'form-control scontrino-row-sconto';
  sconto.style.width = '70px';
  sconto.style.display = 'inline';
  sconto.style.marginRight = '4px';
  row.appendChild(sconto);

  const percent = document.createElement('span');
  percent.textContent = '%';
  percent.style.marginRight = '12px';
  row.appendChild(percent);

  // Select metodo pagamento
  const selectPay = document.createElement('select');
  selectPay.className = 'form-select form-select-sm mx-1';
  selectPay.name = 'metodo_pagamento[]';
  selectPay.style.width = '90px';
  [
    { value: 'pos', label: 'POS', icon: 'bi-calculator' },
    { value: 'cash', label: 'Cash', icon: 'bi-cash' },
    { value: 'bank', label: 'Bank', icon: 'bi-bank' }
  ].forEach(opt => {
    const option = document.createElement('option');
    option.value = opt.value;
    option.textContent = String(opt.label);
    selectPay.appendChild(option);
  });
  selectPay.value = 'pos';
  row.appendChild(selectPay);

  // Icona metodo pagamento selezionato
  const payIcon = document.createElement('i');
  payIcon.className = 'bi bi-calculator ms-2';
  row.appendChild(payIcon);

  // Tasto cancella
  const delBtn = document.createElement('button');
  delBtn.type = 'button';
  delBtn.className = 'btn btn-link text-danger ms-2';
  const xIcon = document.createElement('i');
  xIcon.className = 'bi bi-x-lg';
  delBtn.appendChild(xIcon);
  delBtn.onclick = function () {
    const apptId = row.dataset.appointmentId || '';
    row.remove();
    aggiornaTotale();
    aggiornaSubtotaliPagamenti();

    // Aggiorna storage servizi manuali
    let servizi = JSON.parse(localStorage.getItem('scontrinoServizi') || '[]');
    servizi = servizi.filter(s => s.id !== servizio.id);
    localStorage.setItem('scontrinoServizi', JSON.stringify(servizi));

    if (window.originalAppointmentIds && window.originalAppointmentIds.size > 0) {
      window.hasModifications = true;
      mostraPulsanteSalva();
    }
  };
  row.appendChild(delBtn);

  // Sincronizzazione prezzo <-> sconto
  prezzo.addEventListener('input', function () {
    const nuovoPrezzo = parseFloat(prezzo.value) || 0;
    let scontoPerc = 0;
    if (prezzoOriginale > 0) {
      scontoPerc = Math.round((1 - nuovoPrezzo / prezzoOriginale) * 100);
      if (scontoPerc < 0) scontoPerc = 0;
      if (scontoPerc > 100) scontoPerc = 100;
    }
    sconto.value = scontoPerc;
    aggiornaTotale();
    aggiornaSubtotaliPagamenti();
  });

  sconto.addEventListener('input', function () {
    let scontoPerc = parseInt(sconto.value) || 0;
    if (scontoPerc < 0) scontoPerc = 0;
    if (scontoPerc > 100) scontoPerc = 100;
    prezzo.value = (prezzoOriginale * (1 - scontoPerc / 100)).toFixed(2);
    aggiornaTotale();
    aggiornaSubtotaliPagamenti();
  });

  // Cambia icona al cambio select
  selectPay.addEventListener('change', function () {
    if (selectPay.value === 'pos') payIcon.className = 'bi bi-calculator ms-2';
    else if (selectPay.value === 'cash') payIcon.className = 'bi bi-cash ms-2';
    else if (selectPay.value === 'bank') payIcon.className = 'bi bi-bank ms-2';

    // Se NON è cash, la riga torna bianca subito
    if (selectPay.value !== 'cash') {
      row.style.background = '#fff';
    }
    aggiornaSubtotaliPagamenti();
  });

  // Selezione grigia solo se cash (non per Prodotti)
  selectBox.onclick = function () {
    if (servizio.sottocategoria && String(servizio.sottocategoria).toLowerCase() === 'prodotti') {
      return;
    }
    if (selectPay.value === 'cash') {
      if (row.style.background === 'rgb(220, 220, 220)' || row.style.background === '#dcdcdc') {
        row.style.background = '#fff';
      } else {
        row.style.background = '#dcdcdc';
      }
      aggiornaTotale();
    }
  };

  // Aggiungi la riga al container
  container.appendChild(row);
  aggiornaTotale();
  aggiornaSubtotaliPagamenti();

  // Se stiamo gestendo blocchi da calendar, l'aggiunta di una riga extra è una modifica
  if (!servizio.appointment_id && window.originalAppointmentIds && window.originalAppointmentIds.size > 0) {
    window.hasModifications = true;
    mostraPulsanteSalva();
  }

  // Aggiunta richiesta: listener che abilitano il pulsante Salva quando ci sono blocchi da calendar
  if (window.originalAppointmentIds && window.originalAppointmentIds.size > 0) {
    prezzo.addEventListener('input', () => {
      window.hasModifications = true;
      mostraPulsanteSalva();
    });
    selectPay.addEventListener('change', () => {
      window.hasModifications = true;
      mostraPulsanteSalva();
    });

    // Aggiungi una sola volta i listener per operatore e cliente
    if (!window.listenersAdded) {
      const operatorInput = document.getElementById('operatorSelectInput');
      const clientInput = document.getElementById('clientSearchInputCassa');
      if (operatorInput) {
        operatorInput.addEventListener('change', () => {
          window.hasModifications = true;
          mostraPulsanteSalva();
        });
      }
      if (clientInput) {
        clientInput.addEventListener('input', () => {
          window.hasModifications = true;
          mostraPulsanteSalva();
        });
      }
      window.listenersAdded = true;
    }
  }
}

// Cambia metodo pagamento globale
function aggiornaMetodoPagamentoGlobale(tipo) {
  document.querySelectorAll('#scontrinoRowsContainer .scontrino-row').forEach(row => {
    const select = row.querySelector('select');
    const icon = row.querySelector('i');
    // Aggiorna il metodo di pagamento
    if (select) {
      select.value = tipo;
      // Aggiorna icona
      if (icon) {
        if (tipo === 'pos') icon.className = 'bi bi-calculator ms-2';
        else if (tipo === 'cash') icon.className = 'bi bi-cash ms-2';
        else if (tipo === 'bank') icon.className = 'bi bi-bank ms-2';
      }
    }
    // Se il metodo NON è cash, la riga torna bianca
    if (tipo !== 'cash') {
      row.style.background = '#fff';
    }
  });
  aggiornaSubtotaliPagamenti();
}

// Popola i pulsanti dei servizi
function popolaPulsantiServizi(servizi) {
  if (!Array.isArray(servizi)) {
    // Se servizi è un oggetto, prova a convertirlo in array
    if (servizi && typeof servizi === 'object') {
      servizi = Object.values(servizi);
    } else {
      console.error("popolaPulsantiServizi: dati non validi", servizi);
      return;
    }
  }
  const container = document.getElementById('serviceButtonsContainer');
  container.innerHTML = '';
  servizi.forEach(servizio => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'service-btn-custom tooltip-parent';

    if (servizio.categoria === 'Solarium') {
      btn.classList.add('service-btn-solarium');
    } else if (servizio.categoria === 'Estetica') {
      btn.classList.add('service-btn-estetica');
    }

    if (
      servizio.sottocategoria &&
      servizio.sottocategoria.toLowerCase() === 'prodotti'
    ) {
      btn.classList.add('service-btn-prodotti');
    }

    btn.textContent = servizio.tag;

    // Tooltip custom
    const tooltip = document.createElement('span');
    tooltip.className = 'custom-tooltip';
    tooltip.textContent = servizio.nome;
    btn.appendChild(tooltip);

    btn.onclick = () => {
      aggiungiRigaServizio(servizio);
      btn.blur();
    };
    container.appendChild(btn);
  });
}

// Definisci la variabile fuori, così è globale nello scope del file
let globalResetListener = window.globalResetListener || null;
let confermaAttiva = window.confermaAttiva || false;

document.getElementById('confermaBtn').addEventListener('click', (e) => {
  e.preventDefault();
  const confermaBtn = document.getElementById('confermaBtn');
  const btnStampa = document.getElementById('btnStampaScontrino');
  const stampaLabel = document.getElementById('stampaLabel');
  const btnLotteria = document.getElementById('btnLotteria');
  const container = document.querySelector('.card.neumorphic-card');
  const btnAnnulla = document.getElementById('reset-scontrino'); // NEW

  // Se siamo già in stato confermato, torna all'editing (INDIETRO)
  if (confermaAttiva) {
    confermaAttiva = false;
  if (btnAnnulla) btnAnnulla.classList.remove('d-none'); // SHOW ANNULLA
    confermaBtn.textContent = 'CONFERMA';
    if (btnStampa) {
      btnStampa.style.display = 'none';
      btnStampa.classList.remove('attivo');
      btnStampa.disabled = true;
    }
    if (stampaLabel) stampaLabel.classList.add('d-none');
    if (btnLotteria) btnLotteria.classList.add('d-none');
    if (container) container.classList.remove('pseudoscontrino-bloccato');
    if (btnAnnulla) btnAnnulla.classList.remove('d-none');
    confermaBtn.textContent = 'CONFERMA';

    if (globalResetListener) {
      document.removeEventListener('click', globalResetListener, true);
      globalResetListener = null;
    }
    return;
  }

  // Primo click: entra in stato confermato
  const rows = document.querySelectorAll('.scontrino-row');
  if (rows.length === 0) {
    alert('Aggiungi almeno un servizio prima di generare lo scontrino!');
    return;
  }
  if (btnStampa) {
    btnStampa.style.display = 'flex';
    btnStampa.classList.add('attivo');
    btnStampa.disabled = false;
  }
  if (stampaLabel) stampaLabel.classList.remove('d-none');
  if (container) container.classList.add('pseudoscontrino-bloccato');
  confermaAttiva = true;
  confermaBtn.textContent = 'INDIETRO';
    if (btnAnnulla) btnAnnulla.classList.add('d-none'); // HIDE ANNULLA qui

  // Click esterno: torna in editing (senza resettare lo scontrino)
  globalResetListener = function(e) {
    const lotteriaBtn   = document.getElementById('btnLotteria');
    const modalLotteria = document.getElementById('modalLotteria');
    if (
      !btnStampa.contains(e.target) &&
      !confermaBtn.contains(e.target) &&
      !(lotteriaBtn   && lotteriaBtn.contains(e.target)) &&
      !(modalLotteria && modalLotteria.contains(e.target))
    ) {
      confermaAttiva = false;
      if (btnStampa) {
        btnStampa.style.display = 'none';
        btnStampa.classList.remove('attivo');
        btnStampa.disabled = true;
      }
      if (stampaLabel) stampaLabel.classList.add('d-none');
      if (lotteriaBtn) lotteriaBtn.classList.add('d-none');
      if (container) container.classList.remove('pseudoscontrino-bloccato');
      if (btnAnnulla) btnAnnulla.classList.remove('d-none'); // SHOW ANNULLA
      confermaBtn.textContent = 'CONFERMA';
      document.removeEventListener('click', globalResetListener, true);
      globalResetListener = null;
    }
  };
  document.addEventListener('click', globalResetListener, true);
});

document.getElementById('reset-scontrino').addEventListener('click', () => {
  // Reset pulsante stampa scontrino
  resetScontrino(false);
});

// Funzione per mostrare i subtotali pagamenti se ci sono più tipi
function aggiornaSubtotaliPagamenti() {
  const rows = document.querySelectorAll('.scontrino-row');
  let subtotali = { pos: 0, cash: 0, bank: 0 };
  rows.forEach(row => {
    const prezzo = parseFloat(row.querySelector('.scontrino-row-prezzo')?.value || '0');
    const metodo = row.querySelector('select')?.value || 'cash';
    if (subtotali.hasOwnProperty(metodo)) {
      subtotali[metodo] += prezzo;
    }
  });
  const tipiPresenti = Object.entries(subtotali).filter(([k, v]) => v > 0);
  const subtotaliDiv = document.getElementById('subtotaliPagamenti');
  subtotaliDiv.innerHTML = '';
  if (tipiPresenti.length > 1) {
    if (subtotali.pos > 0) {
      const div = document.createElement('div');
      div.appendChild(document.createTextNode('- subtotale POS: '));
      const b = document.createElement('b');
      b.textContent = `€ ${subtotali.pos.toFixed(2)}`;
      div.appendChild(b);
      subtotaliDiv.appendChild(div);
    }
    if (subtotali.cash > 0) {
      const div = document.createElement('div');
      div.appendChild(document.createTextNode('- subtotale CASH: '));
      const b = document.createElement('b');
      b.textContent = `€ ${subtotali.cash.toFixed(2)}`;
      div.appendChild(b);
      subtotaliDiv.appendChild(div);
    }
    if (subtotali.bank > 0) {
      const div = document.createElement('div');
      div.appendChild(document.createTextNode('- subtotale BANK: '));
      const b = document.createElement('b');
      b.textContent = `€ ${subtotali.bank.toFixed(2)}`;
      div.appendChild(b);
      subtotaliDiv.appendChild(div);
    }
    subtotaliDiv.style.display = '';
  } else {
    subtotaliDiv.style.display = 'none';
  }
}

// Helper
function parseJSONSafe(s) { try { return JSON.parse(s); } catch { return null; } }

// Funzione per salvare modifiche pseudoscontrino in localStorage
async function salvaModifichePseudoscontrino() {
  // Prima proviamo a leggere gli appointment_id dalle righe correnti;
  // se sono stati rimossi tutti, usiamo il set originale portato da Calendar.
  let idsSet = getCurrentAppointmentIds();
  if (!idsSet || idsSet.size === 0) {
    idsSet = window.originalAppointmentIds || new Set();
  }
  if (!idsSet || idsSet.size === 0) return;  // nessun gruppo di riferimento: esci

  const appointmentIds = Array.from(idsSet).map(String).sort();
  const groupKey = `pseudoscontrino_modifiche_group_${appointmentIds.join('_')}`;

  const operatore = document.getElementById('operatorSelectInput').dataset.selectedOperator || '';
  const cliente = {
    nome: document.getElementById('clientSearchInputCassa').value || '',
    id: document.getElementById('clientSearchInputCassa').dataset.selectedClient || ''
  };

  // Snapshot completo delle righe correnti (rispecchia eliminazioni/aggiunte)
  const servizi = [];
  document.querySelectorAll('.scontrino-row').forEach(row => {
    const servizioId = row.dataset.servizioId;
    const prezzo = parseFloat(row.querySelector('.scontrino-row-prezzo')?.value || '0');
    const metodo = row.querySelector('select')?.value || 'cash';
    servizi.push({ servizioId, prezzo, metodo });
  });

  const payload = {
    ts: Date.now(),
    appointmentIds,
    operatore,
    cliente,
    servizi
  };

  // Salva la chiave di gruppo
  localStorage.setItem(groupKey, JSON.stringify(payload));
  // Salva anche per ogni appointment una chiave per-id (fallback restore)
  appointmentIds.forEach(id => {
    localStorage.setItem(`pseudoscontrino_modifiche_for_${id}`, JSON.stringify(payload));
  });

  // Stato e applicazione immediata (serve a MOSTRARE il tasto Reset subito)
  window.appliedSavedModifications = false;
  window.hasModifications = false;
  await ripristinaModifichePseudoscontrino(); // setta appliedSavedModifications=true e mostra Reset
  mostraPulsanteSalva();

  alert("Modifiche all'appuntamento salvate, quando procederai di nuovo al pagamento saranno applicate queste modifiche");
}

// Funzione per ripristinare modifiche salvate automaticamente
async function ripristinaModifichePseudoscontrino() {
  let idsSet = getCurrentAppointmentIds();
  if (!idsSet || idsSet.size === 0) idsSet = window.originalAppointmentIds || new Set();
  if (!idsSet || idsSet.size === 0) return;

  const currentIds = Array.from(idsSet).map(String);
  const sorted = currentIds.slice().sort();
  const groupKey = `pseudoscontrino_modifiche_group_${sorted.join('_')}`;

  let modifiche = parseJSONSafe(localStorage.getItem(groupKey));
  if (!modifiche) {
    const candidates = [];
    currentIds.forEach(id => {
      const p = parseJSONSafe(localStorage.getItem(`pseudoscontrino_modifiche_for_${id}`));
      if (p) candidates.push(p);
    });
    if (candidates.length > 0) {
      const containsAll = candidates.filter(p =>
        Array.isArray(p.appointmentIds) &&
        currentIds.every(id => p.appointmentIds.includes(String(id)))
      );
      const pickFrom = containsAll.length ? containsAll : candidates;
      pickFrom.sort((a, b) => (b.ts || 0) - (a.ts || 0));
      modifiche = pickFrom[0] || null;
    }
  }
  if (!modifiche) return;

  if (modifiche.operatore) {
    document.getElementById('operatorSelectInput').dataset.selectedOperator = modifiche.operatore;
    try {
      const ops = await fetch('/cassa/api/operators').then(r => r.json());
      const op = Array.isArray(ops) ? ops.find(o => o.id == modifiche.operatore) : null;
      if (op) document.getElementById('operatorSelectInput').value = `${op.nome} ${op.cognome}`;
    } catch {}
  }
  if (modifiche.cliente) {
    document.getElementById('clientSearchInputCassa').value = modifiche.cliente.nome || '';
    document.getElementById('clientSearchInputCassa').dataset.selectedClient = modifiche.cliente.id || '';
  }

  const savedIds = new Set((modifiche.servizi || []).map(s => String(s.servizioId)));
  document.querySelectorAll('.scontrino-row').forEach(row => {
    const sid = String(row.dataset.servizioId || '');
    const apptId = row.dataset.appointmentId || '';
    if (apptId && !savedIds.has(sid)) row.remove();
  });

  const addPromises = [];
  (modifiche.servizi || []).forEach(sv => {
    const sid = String(sv.servizioId);
    if (!document.querySelector(`.scontrino-row[data-servizio-id="${sid}"]`)) {
      const p = fetch(`/cassa/api/services?id=${encodeURIComponent(sid)}`)
        .then(r => r.json())
        .then(data => {
          const d = Array.isArray(data) && data[0] ? data[0] : null;
          if (!d) return;
          aggiungiRigaServizio({
            id: d.id,
            nome: d.nome,
            prezzo: d.prezzo,
            tag: d.tag,
            sottocategoria: d.sottocategoria
          }, false);
        })
        .catch(() => {});
      addPromises.push(p);
    }
  });
  await Promise.allSettled(addPromises);

  (modifiche.servizi || []).forEach(sv => {
    const row = document.querySelector(`.scontrino-row[data-servizio-id="${sv.servizioId}"]`);
    if (!row) return;
    const prezzoInput = row.querySelector('.scontrino-row-prezzo');
    if (prezzoInput) prezzoInput.value = Number(sv.prezzo || 0).toFixed(2);
    const sel = row.querySelector('select');
    if (sel) sel.value = sv.metodo || 'cash';
  });

  aggiornaTotale();
  aggiornaSubtotaliPagamenti();

  // Segnala che stai mostrando dati ripristinati: container visibile + Reset visibile
  window.appliedSavedModifications = true;
  window.hasModifications = false;
  mostraPulsanteSalva();

  // Flash nel container (fallback se il container non esiste)
  const host = document.getElementById('saveModificheContainer') || document.getElementById('scontrinoRowsContainer');
  if (host) {
    let flash = document.getElementById('flashModifiche');
    if (!flash) {
      flash = document.createElement('div');
      flash.id = 'flashModifiche';
      flash.style.marginTop = '8px';
      flash.style.fontSize = '0.95em';
      flash.style.padding = '6px 10px';
      flash.style.borderRadius = '6px';
      flash.style.background = '#e7f5ff';
      flash.style.color = '#0b7285';
      flash.style.display = 'inline-block';
      flash.style.marginLeft = '10px';
      host.appendChild(flash);
    }
    flash.textContent = 'modifiche salvate applicate';
    clearTimeout(window._flashModificheTimer);
    window._flashModificheTimer = setTimeout(() => {
      const el = document.getElementById('flashModifiche');
      if (el) el.remove();
    }, 2500);
  }

  return true;
}

// Ricostruisce lo pseudoscontrino leggendo i dati “veri” dei blocchi dal calendar (senza reload)
async function ricreaDaCalendarSenzaReload(appointmentIds) {
  const ids = (appointmentIds || []).map(String).filter(Boolean);
  if (!ids.length) return;

  const res = await fetch('/cassa/api/myspia/dettagli', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || ''
    },
    body: JSON.stringify({ ids })
  });
  const data = await res.json();
  if (!data || !data.success) return;

  // Svuota e repopola con i servizi originali dal calendar
  const rowsC = document.getElementById('scontrinoRowsContainer');
  if (rowsC) rowsC.innerHTML = '';
  window.originalAppointmentIds = new Set();

  const apptIds = [];
  (data.appuntamenti || []).forEach(servizio => {
    const apptId =
      servizio.appointment_id ||
      servizio.appointmentId ||
      servizio.app_id ||
      servizio.appId ||
      servizio.appIdStr ||
      servizio.appt_id ||
      null;
    if (apptId) apptIds.push(String(apptId));
    aggiungiRigaServizio({
      id: servizio.id,
      nome: servizio.nome,
      prezzo: servizio.prezzo,
      tag: servizio.tag,
      sottocategoria: servizio.sottocategoria,
      appointment_id: apptId
    }, false);
  });
  window.lastPseudoscontrinoAppointmentIds = apptIds.filter(Boolean);

  // Reimposta cliente e operatore come da calendar
  if (data.cliente_nome) {
    const input = document.getElementById('clientSearchInputCassa');
    if (input) {
      window.settingClientProgrammatically = true;
      input.value = (data.cliente_nome || '') + ' ' + (data.cliente_cognome || '');
      input.dataset.selectedClient = data.cliente_id || '';
      input.dispatchEvent(new Event('input'));
    }
  }
  if (data.operatore_nome) {
    const op = document.getElementById('operatorSelectInput');
    if (op) {
      op.value = data.operatore_nome || '';
      op.dataset.selectedOperator = data.operatore_id || '';
      op.dispatchEvent(new Event('change'));
    }
  }

  aggiornaTotale();
  aggiornaSubtotaliPagamenti();

  // Stato UI post-reset (niente modifiche applicate)
  window.appliedSavedModifications = false;
  window.hasModifications = false;
  mostraPulsanteSalva();
}

function resetModifichePseudoscontrino(opts = {}) {
  const { skipRebuild = false, silent = false } = opts;

  // Prendi gli appointment correnti dal DOM, fallback alla Set globale
  let idsSet = getCurrentAppointmentIds();
  if (!idsSet || idsSet.size === 0) idsSet = window.originalAppointmentIds || new Set();
  const appointmentIds = Array.from(idsSet).map(String).sort();

  if (appointmentIds.length === 0) {
    if (!silent) alert('Nessun appuntamento da ripristinare');
    return;
  }

  // Rimuovi tutte le chiavi usate dal ripristino (nuove) + legacy
  const groupKey = `pseudoscontrino_modifiche_group_${appointmentIds.join('_')}`;
  localStorage.removeItem(groupKey);
  appointmentIds.forEach(id => {
    localStorage.removeItem(`pseudoscontrino_modifiche_for_${id}`);
  });
  const legacyKey = `pseudoscontrino_modifiche_${appointmentIds.join('_')}`;
  localStorage.removeItem(legacyKey);

  // Rimuovi lo stato "edited" dal My‑Spia per questi appuntamenti
  try { if (typeof window.unmarkEditedIds === 'function') window.unmarkEditedIds(appointmentIds); } catch(_) {}
  const mySpia = document.getElementById('mySpiaListContainer');
  if (mySpia && mySpia.classList.contains('open') && typeof window.caricaAppuntamentiMySpia === 'function') {
    try { window.caricaAppuntamentiMySpia(); } catch(_) {}
  }

  // Se richiesto, non toccare il DOM dello pseudoscontrino (niente svuotamento/ricostruzione)
  if (skipRebuild) {
    if (!silent) alert('Ripristinato ai valori originali');
    return;
  }

  // Ricrea dai dati del calendar (senza reload)
  ricreaDaCalendarSenzaReload(appointmentIds)
    .then(() => { if (!silent) alert('Ripristinato ai valori originali'); })
    .catch(() => { if (!silent) alert('Ripristino completato (parziale).'); });
}

// Ricostruisce lo pseudoscontrino dai servizi originali passati dal backend (senza reload)
function ripristinaOriginaleSenzaReload() {
  try {
    const orig = Array.isArray(window.SERVIZI_PRECOMPILATI) ? window.SERVIZI_PRECOMPILATI : [];
    const rowsC = document.getElementById('scontrinoRowsContainer');
    if (!rowsC) return;

    // Sostituisci le righe con quelle originali
    rowsC.innerHTML = '';
    orig.forEach(s => aggiungiRigaServizio(s, false));

    aggiornaTotale();
    aggiornaSubtotaliPagamenti();

    // Flags e UI
    window.appliedSavedModifications = false;
    window.hasModifications = false;
    mostraPulsanteSalva();
  } catch (_) {}
}

// Listener per icona dischetto
document.addEventListener('DOMContentLoaded', function() {
  const btnSave = document.getElementById('btnSaveModifiche');
  if (btnSave) {
    btnSave.addEventListener('click', async function(e) {
      e.preventDefault();
      await salvaModifichePseudoscontrino();
    });
  }
  const btnReset = document.getElementById('btnResetModifiche');
  if (btnReset) {
    btnReset.addEventListener('click', function(e) {
      e.preventDefault();
      // Importante: non svuotare il DOM dello pseudoscontrino prima del reload
      resetModifichePseudoscontrino({ skipRebuild: true, silent: true });
      setTimeout(() => { location.reload(); }, 120);
    });
  }
});