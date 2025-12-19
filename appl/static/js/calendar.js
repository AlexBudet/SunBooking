(function(){
    const MOBILE_BP = 1200;
    const S_KEY = 'sun_touch_ui';
    const S_FORCED_FLAG = 'sun_touch_ui_forced';
    const S_PREV = 'sun_touch_ui_prev';

    // applica la classe e localStorage senza perdere il valore precedente
    function forceTouchOn() {
        try {
            // salva precedente solo la prima volta che forziamo
            if (!sessionStorage.getItem(S_FORCED_FLAG)) {
                sessionStorage.setItem(S_PREV, localStorage.getItem(S_KEY) ?? '');
            }
            sessionStorage.setItem(S_FORCED_FLAG, '1');
            localStorage.setItem(S_KEY, '1');        // mantiene compatibilità con codice esistente
            document.body.classList.add('touch-ui'); // immediato
            window.dispatchEvent(new CustomEvent('touchModeForced', { detail: { forced: true } }));
        } catch (e) { console.warn('forceTouchOn error', e); }
    }

    // rimuove il forcing e ripristina il valore salvato (lettura business)
    function restoreTouchSetting() {
        try {
            const prev = sessionStorage.getItem(S_PREV);
            // se prev === '1' o '0' / non vuoto, ripristina; altrimenti rimuovi key
            if (prev === '1') {
                localStorage.setItem(S_KEY, '1');
                document.body.classList.add('touch-ui');
            } else if (prev === '0') {
                localStorage.setItem(S_KEY, '0');
                document.body.classList.remove('touch-ui');
            } else {
                localStorage.removeItem(S_KEY);
                document.body.classList.toggle('touch-ui', false);
            }
            sessionStorage.removeItem(S_FORCED_FLAG);
            sessionStorage.removeItem(S_PREV);
            window.dispatchEvent(new CustomEvent('touchModeForced', { detail: { forced: false } }));
            // segnala al resto dell'app che deve rileggere l'impostazione business
            window.dispatchEvent(new Event('checkBusinessTouchSetting'));
        } catch (e) { console.warn('restoreTouchSetting error', e); }
    }

    function evaluate() {
        const w = window.innerWidth || document.documentElement.clientWidth;
        if (w < MOBILE_BP) forceTouchOn();
        else {
            // se era forzato, ripristina; altrimenti non intervenire (lascia business setting)
            if (sessionStorage.getItem(S_FORCED_FLAG)) restoreTouchSetting();
            // se non forzato, emit event so existing code re-reads business setting if needed
            else window.dispatchEvent(new Event('checkBusinessTouchSetting'));
        }
    }

    // debounce resize
    let t = null;
    function onResize() {
        clearTimeout(t);
        t = setTimeout(evaluate, 120);
    }

    // run as early as possible
    try {
        evaluate();
    } catch(e){ console.warn('responsive touch init failed', e); }

    window.addEventListener('resize', onResize, { passive: true });
    window.addEventListener('orientationchange', onResize);
    // also ensure after DOM ready (some code runs immediately relying on class)
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', evaluate, { once: true });
    } else {
        evaluate();
    }

    // expose helpers for debugging
    window.__forceTouchForViewport = evaluate;
    window.__forceTouchOn = forceTouchOn;
    window.__restoreTouchSetting = restoreTouchSetting;
})();

// appl/static/js/Calendar.js
(function() {
console.log("calendar.js caricato correttamente!"); // INSERIRE NELLA PRIMA RIGA DI calendar.js

// =============================================================
//   VARIABILI GLOBALI (NON RIMUOVERE)
// =============================================================
window.selectedOperatorId = null;
window.selectedAppointmentDate = selectedDate;
window.selectedClientId = null;
window.selectedClientName = "";
window.selectedClientIdNav = null;    // ID del cliente selezionato
window.selectedServicesArray = [];    // Array di servizi selezionati {id, name, duration}
window.selectedClientNameNav = "";    // Ora definito a livello globale
window.selectedServiceIdNav = null;   // Assicurati di definirlo se lo usi
window.selectedServiceNameNav = "";   // Ora definito a livello globale
window.selectedServiceDurationNav = 15;
window.handleClientSearchNav = handleClientSearchNav;
window.handleServiceSearchNav = handleServiceSearchNav;
window.pseudoBlocks = window.pseudoBlocks || [];
window.lastClickPosition = null;
window._lastBlocksCountPerCell = window._lastBlocksCountPerCell || new Map();
window.CLIENT_ID_BOOKING = null;

// (inserire qui) -> aggiungi variabile globale per il gap contiguo (minuti)
window.CONTIGUOUS_BLOCK_MAX_GAP_MINUTES = window.CONTIGUOUS_BLOCK_MAX_GAP_MINUTES ?? 30;

// === BLOCCO: LOCK CLICK ESTERNI MODAL CREAZIONE APPUNTAMENTO ===
function enableCreateApptModalLock(modalEl) {
  if (!modalEl || modalEl._createApptLockActive) return;
  const handler = (e) => {
    const t = e.target;
    // dentro il modal corrente → ok
    if (modalEl.contains(t)) return;
    // NUOVO: non bloccare i click dentro altri modal Bootstrap (es. AddClientModal)
    const otherModal = t.closest('.modal.show');
    if (otherModal && otherModal !== modalEl) return;

    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();
    showCreateApptOutsideClickWarning(modalEl);
  };
  ['click','mousedown','touchstart'].forEach(evt =>
    document.addEventListener(evt, handler, true)
  );
  modalEl._createApptLockHandler = handler;
  modalEl._createApptLockActive = true;
}

window.enableCreateApptModalClickLock = enableCreateApptModalLock;

function disableCreateApptModalLock(modalEl) {
  if (!modalEl || !modalEl._createApptLockActive) return;
  const h = modalEl._createApptLockHandler;
  ['click','mousedown','touchstart'].forEach(evt =>
    document.removeEventListener(evt, h, true)
  );
  delete modalEl._createApptLockHandler;
  modalEl._createApptLockActive = false;
}

window.disableCreateApptModalClickLock = disableCreateApptModalLock;

function showCreateApptOutsideClickWarning(modalEl) {
  const body = modalEl.querySelector('.modal-body');
  if (!body) return;
  let warn = body.querySelector('#createApptOutsideWarning');
  if (!warn) {
    warn = document.createElement('div');
    warn.id = 'createApptOutsideWarning';
    warn.className = 'alert alert-warning py-2 px-3 mb-2';
    warn.style.fontSize = '0.8rem';
    warn.style.userSelect = 'none';
    warn.style.zIndex = '5000';
    warn.textContent = "Occhio, click sulla cella disabilitato, l'ora di inizio è già stata impostata col click iniziale sulla cella!";
    body.prepend(warn);
  }
  warn.style.display = 'block';
  clearTimeout(warn._hideTimer);
  warn._hideTimer = setTimeout(() => { warn.style.display = 'none'; }, 2600);
}
// === FINE BLOCCO LOCK ===

function formatDateItalian(dateStr) {
  if (!dateStr || !/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) return dateStr; // Fallback se non yyyy-mm-dd
  const [year, month, day] = dateStr.split('-');
  const months = ['GEN', 'FEB', 'MAR', 'APR', 'MAG', 'GIU', 'LUG', 'AGO', 'SET', 'OTT', 'NOV', 'DIC'];
  return `${parseInt(day)} ${months[parseInt(month) - 1]} ${year}`;
}

window.formatDateItalian = formatDateItalian;

// Funzione per capitalizzare nome/cognome (prima lettera maiuscola per ogni parola)
function capitalizeName(name) {
  if (!name) return name;
  return name.toLowerCase().replace(/\b\w/g, l => l.toUpperCase());
}
window.capitalizeName = capitalizeName;  // Rendi globale se serve altrove

const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
fetch('/calendar/api/client-id-booking', {
  headers: { 'X-CSRFToken': csrfToken }
})
  .then(resp => resp.json())
  .then(data => { window.CLIENT_ID_BOOKING = data.client_id_booking; });

if (typeof window.clearCalendarHighlights !== 'function') {
  function clearCalendarHighlights() {
    document
      .querySelectorAll('.selectable-cell.highlight, .selectable-cell.highlight-side')
      .forEach(c => { c.classList.remove('highlight'); c.classList.remove('highlight-side'); });
  }
  window.clearCalendarHighlights = clearCalendarHighlights;
}

if (typeof window.applyHighlightToCell !== 'function') {
  let __lastMouseX = 0, __lastMouseY = 0;
  document.addEventListener('mousemove', function(e){
    __lastMouseX = e.clientX;
    __lastMouseY = e.clientY;
  }, { passive: true });

  function applyHighlightToCell(cell) {
    if (!cell) return;
    window.clearCalendarHighlights();

    // se esistono pseudo-blocchi, evidenzia intervallo basato sulla durata totale
    if (window.pseudoBlocks && Array.isArray(window.pseudoBlocks) && window.pseudoBlocks.length > 0) {
      let totalDuration = 0;
      if (selectedPseudoBlock) {
        const index = selectedPseudoBlock.getAttribute('data-index');
        if (index !== null && window.pseudoBlocks[index]) {
          totalDuration = parseInt(window.pseudoBlocks[index].duration || 0, 10) || 0;
        } else {
          totalDuration = window.pseudoBlocks.reduce((acc, blk) => acc + (parseInt(blk.duration || 0,10) || 0), 0);
        }
      } else {
        totalDuration = window.pseudoBlocks.reduce((acc, blk) => acc + (parseInt(blk.duration || 0,10) || 0), 0);
      }

      const startHour = parseInt(cell.getAttribute('data-hour'), 10) || 0;
      const startMinute = parseInt(cell.getAttribute('data-minute'), 10) || 0;
      const startTime = startHour * 60 + startMinute;
      const endTime = startTime + (totalDuration || 0);
      const operatorId = cell.getAttribute('data-operator-id');
      const date = cell.getAttribute('data-date');

      const cellsToHighlight = document.querySelectorAll(`.selectable-cell[data-operator-id="${operatorId}"][data-date="${date}"]`);
      cellsToHighlight.forEach(c => {
        const h = parseInt(c.getAttribute('data-hour'), 10) || 0;
        const m = parseInt(c.getAttribute('data-minute'), 10) || 0;
        const cellTime = h * 60 + m;
        if (cellTime >= startTime && cellTime < endTime) {
          c.classList.add('highlight');
        }
      });
    } else {
      // comportamento standard: evidenzia solo la cella
      cell.classList.add('highlight');
    }

    // Highlight laterale della riga (sempre)
    const row = cell.parentElement;
    if (row) {
      const cells = Array.from(row.querySelectorAll('.selectable-cell'));
      cells.forEach(c => {
        if (c !== cell && !c.classList.contains('calendar-closed')) {
          c.classList.add('highlight-side');
        }
      });
    }
  }
  window.applyHighlightToCell = applyHighlightToCell;

  function refreshHighlightForHover() {
    const el = document.elementFromPoint(__lastMouseX || 0, __lastMouseY || 0);
    const cell = el ? el.closest('.selectable-cell') : null;
    if (cell) applyHighlightToCell(cell);
    else window.clearCalendarHighlights();
  }
  window.refreshHighlightForHover = refreshHighlightForHover;

  // MutationObserver per aggiornare highlight quando cambiano pseudo-blocchi
  (function initPseudoBlocksObserver() {
    const container = document.getElementById('selectedServicesList');
    if (!container) return;
    const mo = new MutationObserver(() => {
      if (window.__pseudoRefreshTimeout) clearTimeout(window.__pseudoRefreshTimeout);
      window.__pseudoRefreshTimeout = setTimeout(() => {
        try { window.refreshHighlightForHover(); } catch (e) { /* ignore */ }
      }, 50);
    });
    mo.observe(container, { childList: true, attributes: true, subtree: false });
  })();
}

    // ============================================
    //   FUNZIONE PER IL MODAL DI AGGIUNTA CLIENTE 
    // ============================================
// funzione openAddClientModal
function openAddClientModal(callerId) {
    if (!window.bootstrap || !window.bootstrap.Modal) {
      console.error("Bootstrap o Modal non è definito. Assicurati che bootstrap.bundle.min.js sia caricato.");
      alert("Errore: Bootstrap non disponibile.");
      return;
    }
  
    const modalElement = document.getElementById('AddClientModal');
    if (!modalElement) {
      console.error("Elemento '#AddClientModal' non trovato nel DOM.");
      return;
    }

    const isNarrowViewport = window.matchMedia('(max-width: 1199.98px)').matches;
    if (isNarrowViewport) {
      const suspended = [];
      document.querySelectorAll('.modal.show').forEach(modalEl => {
        if (modalEl !== modalElement) {
          const instance = bootstrap.Modal.getInstance(modalEl);
          if (instance) {
            suspended.push(modalEl.id || '');
            instance.hide();
          }
        }
      });
      if (suspended.length) {
        modalElement.dataset.suspendedModals = suspended.join(',');
        if (!modalElement.dataset.resumeListenerAttachedMobile) {
          modalElement.addEventListener('hidden.bs.modal', function resumeSuspended(ev) {
            const current = ev.currentTarget;
            const ids = (current.dataset.suspendedModals || '').split(',').filter(Boolean);
            delete current.dataset.suspendedModals;
            ids.forEach(id => {
              const el = document.getElementById(id);
              if (!el) return;
              const inst = bootstrap.Modal.getOrCreateInstance(el, { focus: true });
              inst.show();
            });
          });
          modalElement.dataset.resumeListenerAttachedMobile = '1';
        }
      }
    } else {
      delete modalElement.dataset.suspendedModals;
    }
  
    const modal = isNarrowViewport
      ? bootstrap.Modal.getOrCreateInstance(modalElement, { focus: true })
      : new bootstrap.Modal(modalElement);
    const addClientForm = document.getElementById('AddClientForm');
    
    modalElement.dataset.caller = callerId;

    try {
      if (callerId === 'CreateAppointmentModal') {
        const input = document.getElementById('clientSearchInput');
        const results = document.getElementById('clientResults');
        if (input) {
          input.value = '';
          input.dispatchEvent(new Event('input', { bubbles: true }));
          input.dispatchEvent(new Event('change', { bubbles: true }));
        }
        if (results) {
          results.innerHTML = '';
          results.style.display = 'none';
        }
      } else if (callerId === 'navigator' || callerId === 'appointmentNavigator') {
        const inputNav = document.getElementById('clientSearchInputNav');
        const resultsNav = document.getElementById('clientResultsNav');
        if (inputNav) {
          inputNav.value = '';
          inputNav.dispatchEvent(new Event('input', { bubbles: true }));
          inputNav.dispatchEvent(new Event('change', { bubbles: true }));
        }
        if (resultsNav) {
          resultsNav.innerHTML = '';
          resultsNav.style.display = 'none';
        }
      }
    } catch (clearErr) {
      console.warn('openAddClientModal: clearing caller input failed', clearErr);
    }
  
    const btnCreateBlockOff = document.getElementById('btnCreateBlockOff');
    if (btnCreateBlockOff) {
        btnCreateBlockOff.style.display = 'none';
    }
    
    if (addClientForm) {
      addClientForm.reset();
      
      const newForm = addClientForm.cloneNode(true);
      addClientForm.parentNode.replaceChild(newForm, addClientForm);
      
      newForm.addEventListener('submit', function(event) {
        event.preventDefault();
        const formData = new FormData(newForm);
    
        let cliente_nome = formData.get('cliente_nome') || '';
        let cliente_cognome = formData.get('cliente_cognome') || '';
        let cliente_cellulare = formData.get('cliente_cellulare') || '';
        let cliente_sesso = formData.get('client_gender') || formData.get('cliente_sesso') || '';
    
        cliente_nome = cliente_nome.trim();
    
        if (!cliente_nome) {
            alert("Il campo Nome è obbligatorio");
            return;
        }
        if (!cliente_cognome.trim()) {
            alert("Il campo Cognome è obbligatorio");
            return;
        }
    
        if (!cliente_sesso) {
            console.log("Genere non specificato, utilizzo la logica di fallback");
            let nome_minuscolo = cliente_nome.toLowerCase();
            if (nome_minuscolo.endsWith('o')) {
                cliente_sesso = 'M';
                console.log("Imposto genere a M (nome finisce con o)");
            } else if (nome_minuscolo.endsWith('a')) {
                cliente_sesso = 'F';
                console.log("Imposto genere a F (nome finisce con a)");
            } else {
                cliente_sesso = '-';
                console.log("Impossibile dedurre il genere, imposto a -");
            }
        }
    
        const data = {
            cliente_nome: cliente_nome,
            cliente_cognome: cliente_cognome,
            cliente_cellulare: cliente_cellulare,
            cliente_sesso: cliente_sesso
        };
    
        console.log("Dati nuovo cliente mappati:", data);
    
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    
        fetch('/calendar/add-client', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify(data)
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => {
                    throw new Error(err.error || "Errore durante l'aggiunta del cliente");
                });
            }
            return response.json();
        })
        .then(client => {
            console.log("Cliente aggiunto:", client);
            const caller = modalElement.dataset.caller;
            if (caller === 'CreateAppointmentModal') {
                const clientSearchInput = document.getElementById('clientSearchInput');
                const clientIdInput = document.getElementById('client_id');
                if (clientSearchInput && clientIdInput) {
                    const fullName = `${client.cliente_nome || ''} ${client.cliente_cognome || ''}`.trim();
                    clientSearchInput.value = capitalizeName(fullName);
                    clientIdInput.value = client.cliente_id;
                    clientSearchInput.dispatchEvent(new Event('input', { bubbles: true }));
                    clientSearchInput.dispatchEvent(new Event('change', { bubbles: true }));
                    clientIdInput.dispatchEvent(new Event('input', { bubbles: true }));
                    clientIdInput.dispatchEvent(new Event('change', { bubbles: true }));
                    if (typeof loadServicesForModal === 'function') {
                      try { loadServicesForModal(); } catch(e){}
                    }
                }
            } else if (caller === 'navigator') {
                const clientSearchInputNav = document.getElementById('clientSearchInputNav');
                if (clientSearchInputNav) {
                    const fullName = `${client.cliente_nome || ''} ${client.cliente_cognome || ''}`.trim();
                    clientSearchInputNav.value = fullName;
                    window.selectedClientIdNav = client.cliente_id;
                    window.selectedClientNameNav = fullName;

                    // PATCH: Simula click per espandere il navigator e mostrare il campo servizi
                    try { clientSearchInputNav.click(); } catch(e) {}

                    clientSearchInputNav.dispatchEvent(new Event('input', { bubbles: true }));
                    clientSearchInputNav.dispatchEvent(new Event('change', { bubbles: true }));
                    if (typeof saveNavigatorState === 'function') {
                      try { saveNavigatorState(); } catch(e){}
                    }
                }
                const serviceInputNav = document.getElementById('serviceInputNav');
                const selectedServicesList = document.getElementById('selectedServicesList');
                if (serviceInputNav) {
                    // Assicurati che sia visibile
                    serviceInputNav.style.display = 'block';
                    serviceInputNav.focus();
                    setTimeout(() => {
                        loadFrequentServices();
                        const serviceResultsNav = document.getElementById('serviceResultsNav');
                        if (serviceResultsNav) {
                            serviceResultsNav.style.display = 'block';
                            serviceInputNav.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                        }
                    }, 100);
                }
                if (selectedServicesList) {
                    selectedServicesList.style.display = 'block'; // Assicura visibilità
                    selectedServicesList.style.border = '2px solid #28a745';
                    setTimeout(() => {
                        selectedServicesList.style.border = '1px dashed #ccc';
                    }, 1000);
                }
            } else if (caller === 'assignModal') {
                const editModalBody = document.querySelector('#EditAppointmentModal .modal-body');
                if (editModalBody) {
                    const clientSearchInput = editModalBody.querySelector('#clientSearchInput');
                    const clientIdInput = editModalBody.querySelector('#client_id');
                    const fullName = `${client.cliente_nome || ''} ${client.cliente_cognome || ''}`.trim();
                    if (clientSearchInput) clientSearchInput.value = fullName;
                    if (clientIdInput && (client.cliente_id ?? client.id) != null) clientIdInput.value = (client.cliente_id ?? client.id);
                    if (clientSearchInput) {
                      clientSearchInput.dispatchEvent(new Event('input', { bubbles: true }));
                      clientSearchInput.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                    if (clientIdInput) {
                      clientIdInput.dispatchEvent(new Event('input', { bubbles: true }));
                      clientIdInput.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                    try {
                      const editForm = editModalBody.querySelector('#EditAppointmentClientForm');
                      if (editForm) {
                        if (typeof editForm.requestSubmit === 'function') {
                          editForm.requestSubmit();
                        } else {
                          editForm.submit();
                        }
                      }
                    } catch (err) {
                      console.warn('Auto-submit EditAppointmentClientForm fallito:', err);
                    }
                }
            }
            const modalEl = document.getElementById('AddClientModal');
            const bsModal = bootstrap.Modal.getInstance(modalEl);
            if (bsModal) {
                bsModal.hide();
            }
        })
        .catch(error => {
            console.error("Errore:", error);
            alert(error.message);
        });
    });
    }
    
    modal.show();
}

// Assicurati che la funzione sia disponibile globalmente
window.openAddClientModal = openAddClientModal;

document.addEventListener('DOMContentLoaded', function() {
    const addClientForm = document.getElementById('AddClientForm');
    if (addClientForm) {
addClientForm.addEventListener('submit', function(event) {
    event.preventDefault();
    const originalData = new FormData(addClientForm);
    const formData = new FormData();
    formData.append('cliente_nome', originalData.get('client_name') || originalData.get('cliente_nome') || "");
    formData.append('cliente_cognome', originalData.get('client_surname') || originalData.get('cliente_cognome') || "");
    formData.append('cliente_cellulare', originalData.get('client_phone') || originalData.get('cliente_cellulare') || "");
    formData.append('cliente_sesso', originalData.get('client_gender') || originalData.get('cliente_sesso') || "-");

    fetch('/calendar/add-client', {
        method: 'POST',
        body: formData,
        credentials: 'same-origin'
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => { throw new Error(err.error || "Errore durante l'aggiunta del cliente"); });
        }
        return response.json();
    })
    .then(client => {
        // normalized values
        const clientId = client.cliente_id ?? client.id;
        const nome = (client.cliente_nome ?? client.name ?? "").toString().trim();
        const cognome = (client.cliente_cognome ?? client.surname ?? "").toString().trim();
        const fullName = `${nome} ${cognome}`.trim();

        // decide caller stored on modal
        const modalEl = document.getElementById('AddClientModal');
        const caller = modalEl && modalEl.dataset ? modalEl.dataset.caller : null;

        if (caller === 'CreateAppointmentModal') {
            const clientSearchInput = document.getElementById('clientSearchInput');
            const clientIdInput = document.getElementById('client_id');
            if (clientSearchInput) clientSearchInput.value = fullName;
            if (clientIdInput && clientId != null) clientIdInput.value = clientId;

        // dispatch + refresh modal services
        if (clientSearchInput) {
          clientSearchInput.dispatchEvent(new Event('input', { bubbles: true }));
          clientSearchInput.dispatchEvent(new Event('change', { bubbles: true }));
        }
        if (clientIdInput) {
          clientIdInput.dispatchEvent(new Event('input', { bubbles: true }));
          clientIdInput.dispatchEvent(new Event('change', { bubbles: true }));
        }
        if (typeof loadServicesForModal === 'function') {
          try { loadServicesForModal(); } catch(e){ /* ignore */ }
        }
            
            // refresh services for modal if function exists
            if (typeof loadServicesForModal === 'function') loadServicesForModal();
        } else if (caller === 'navigator') {
            const clientSearchInputNav = document.getElementById('clientSearchInputNav');
            if (clientSearchInputNav) clientSearchInputNav.value = fullName;
            window.selectedClientIdNav = clientId ?? null;
            window.selectedClientNameNav = fullName;

                    // dispatch + save navigator state
        if (clientSearchInputNav) {
          clientSearchInputNav.dispatchEvent(new Event('input', { bubbles: true }));
          clientSearchInputNav.dispatchEvent(new Event('change', { bubbles: true }));
        }
        if (typeof saveNavigatorState === 'function') {
          try { saveNavigatorState(); } catch(e){ /* ignore */ }
        }
            // expose navigator UI and focus service input
            const serviceInputNav = document.getElementById('serviceInputNav');
            const selectedServicesList = document.getElementById('selectedServicesList');
            if (serviceInputNav) {
                serviceInputNav.style.display = 'block';
                serviceInputNav.focus();
                // try to load last/frequent services for this client
                if (typeof loadLastServicesForClient === 'function' && clientId) {
                    loadLastServicesForClient(clientId);
                } else if (typeof loadFrequentServices === 'function') {
                    loadFrequentServices();
                }
            }
            if (selectedServicesList) {
                selectedServicesList.style.display = 'block';
                selectedServicesList.style.border = '2px solid #28a745';
                setTimeout(() => { selectedServicesList.style.border = '1px dashed #ccc'; }, 1000);
            }
            if (typeof saveNavigatorState === 'function') saveNavigatorState();
        } else if (caller === 'assignModal') {
            const editModalBody = document.querySelector('#EditAppointmentModal .modal-body');
            if (editModalBody) {
                const clientSearchInput = editModalBody.querySelector('#clientSearchInput');
                const clientIdInput = editModalBody.querySelector('#client_id');
                if (clientSearchInput) clientSearchInput.value = fullName;
                if (clientIdInput && clientId != null) clientIdInput.value = clientId;

                            //dispatch per assignModal
            if (clientSearchInput) {
              clientSearchInput.dispatchEvent(new Event('input', { bubbles: true }));
              clientSearchInput.dispatchEvent(new Event('change', { bubbles: true }));
            }
            if (clientIdInput) {
              clientIdInput.dispatchEvent(new Event('input', { bubbles: true }));
              clientIdInput.dispatchEvent(new Event('change', { bubbles: true }));
            }
            }
        }

        // close AddClientModal
        try {
            const bsModal = bootstrap.Modal.getInstance(modalEl);
            if (bsModal) bsModal.hide();
        } catch (e) { /* ignore */ }
    })
    .catch(error => {
        console.error("Errore aggiunta cliente:", error);
        alert(error.message || "Errore durante l'aggiunta del cliente");
    });
});
    }
  });
  
function arrangeBlocksInCell(cell) {
    if (!cell) return;

       // Ottieni info cella
    const cellHour = parseInt(cell.getAttribute('data-hour'), 10);
    const cellMinute = parseInt(cell.getAttribute('data-minute'), 10);
    const cellStart = cellHour * 60 + cellMinute;
    const cellEnd = cellStart + 15; // quarter di 15 minuti

    // Trova tutti i blocchi che OCCUPANO questa cella (anche se non partono qui)
    const blocks = Array.from(cell.parentNode.querySelectorAll('.appointment-block'))
        .filter(block => {
            const blockHour = parseInt(block.getAttribute('data-hour'), 10);
            const blockMinute = parseInt(block.getAttribute('data-minute'), 10);
            const blockStart = blockHour * 60 + blockMinute;
            const blockDuration = parseInt(block.getAttribute('data-duration'), 10) || 15;
            const blockEnd = blockStart + blockDuration;
            // Sovrapposizione: il blocco copre almeno in parte la cella
            return blockEnd > cellStart && blockStart < cellEnd &&
                   block.getAttribute('data-operator-id') === cell.getAttribute('data-operator-id');
        });
    
    if (blocks.length === 0) return;

    // Se c'è un solo blocco, occupa tutta la cella
    if (blocks.length === 1) {
        blocks[0].style.setProperty('width', '100%', 'important');
        blocks[0].style.setProperty('left', '0%', 'important');
        blocks[0].style.setProperty('z-index', '1', 'important');
        blocks[0].setAttribute('data-width', '100%');
        blocks[0].setAttribute('data-left', '0%');
        blocks[0].setAttribute('data-zindex', '1');
        return;
    }

    // Se ci sono due blocchi o più, tutti vanno al 50%
    for (let i = 0; i < blocks.length; i++) {
        blocks[i].style.setProperty('width', '50%', 'important');
        blocks[i].style.setProperty('left', (i === 0 ? '0%' : '50%'), 'important');
        blocks[i].style.setProperty('z-index', (i + 1).toString(), 'important');
        blocks[i].setAttribute('data-width', '50%');
        blocks[i].setAttribute('data-left', (i === 0 ? '0%' : '50%'));
        blocks[i].setAttribute('data-zindex', (i + 1).toString());
    }
}
  
  // Esponi la funzione globalmente
  window.arrangeBlocksInCell = arrangeBlocksInCell;

  // Funzione per alternare lo stato di selezione del pseudoblocco
function togglePseudoBlockSelection(event) {
  // Previeni la propagazione per non innescare il click della cella calendario
  event.stopPropagation();
  const pseudoBlock = event.currentTarget;
  if (pseudoBlock.classList.contains('selected')) {
      pseudoBlock.classList.remove('selected');
  } else {
      // Deseleziona eventuali altri pseudoblocchi selezionati
      document.querySelectorAll('.pseudo-block.selected').forEach(block => {
          block.classList.remove('selected');
      });
      pseudoBlock.classList.add('selected');
  }
}

// Inizializza i listener sui pseudoblocchi nel container
function initPseudoBlockSelection() {
  const container = document.getElementById('selectedServicesList');
  if (container) {
      container.querySelectorAll('.pseudo-block').forEach(block => {
          block.addEventListener('click', togglePseudoBlockSelection);
      });
  }
}
document.addEventListener('DOMContentLoaded', initPseudoBlockSelection);

  function fetchCalendarData() {
    const date = selectedDate;
    const operatorCells = document.querySelectorAll('.selectable-cell');
    const operatorIds = new Set();
    operatorCells.forEach(cell => operatorIds.add(cell.dataset.operatorId));

    // Converti operatorIds in array e crea le promises
    const promises = Array.from(operatorIds).map(operatorId => 
        fetch(`/calendar/api/operators/${operatorId}/shifts?date=${date}`)
            .then(response => response.json())
            .then(data => {
                if (data.error) throw new Error(data.error);
                updateCalendarDisplay(data, operatorId);
            })
    );

    // Aspetta il completamento di tutte le fetch
    Promise.all(promises)
        .then(() => {
            // Applica il ridimensionamento dopo il rendering
            arrangeBlocksInCell();
            // Ripristina i pseudo-blocchi
            restoreNavigatorState();
        })
        .catch(error => console.error("Errore fetch dati:", error));
}

window.fetchCalendarData = fetchCalendarData;

function updateCalendarDisplay(shiftData, operatorId) {
    if (closingDays.map(d => d.toLowerCase()).includes(new Date(selectedDate).toLocaleDateString('it-IT', {weekday:'long'}).toLowerCase())) return markUnavailable(0, 1440, operatorId);
    
    const cells = document.querySelectorAll(`.selectable-cell[data-operator-id="${operatorId}"]`);
    
    // Se non ci sono turni, applica gli orari di default da business_info
    if (!shiftData || shiftData.length === 0) {
        const openingTime = timeToMinutes(defaultOpeningTime); // Orario di apertura predefinito dal business_info
        const closingTime = timeToMinutes(defaultClosingTime); // Orario di chiusura predefinito dal business_info
    
        // Applica gli orari di default
        markUnavailable(0, openingTime, operatorId); // Grigio prima dell'apertura
        markUnavailable(closingTime, 1440, operatorId); // Grigio dopo la chiusura
        return;
    }

    // Ordina i turni per orario di inizio
    const sortedShifts = shiftData.sort((a, b) =>
        timeToMinutes(a.start_time) - timeToMinutes(b.start_time)
    );
    
    // Imposta gli intervalli di disponibilità
    let lastEndTime = 0; // Tiene traccia della fine dell'ultimo turno
    sortedShifts.forEach(shift => {
        const startTime = timeToMinutes(shift.start_time);
        const endTime = timeToMinutes(shift.end_time);

        // Prima dell'inizio del turno (grigio)
        markUnavailable(lastEndTime, startTime, operatorId);

        // Durante il turno (disponibile) - non facciamo nulla qui, le celle sono già disponibili di default

        // Dopo la fine del turno (grigio)
        markUnavailable(endTime, 1440, operatorId); // 1440 = 24 ore in minuti

        lastEndTime = endTime;
    });
}

function markUnavailable(startMin, endMin, operatorId) {
    document.querySelectorAll(`.selectable-cell[data-operator-id="${operatorId}"]`).forEach(cell => {
        const cellMin = parseInt(cell.dataset.hour) * 60 + parseInt(cell.dataset.minute);
        if (cellMin >= startMin && cellMin < endMin) {
            cell.classList.add('calendar-closed');
        }
    });
}

function timeToMinutes(timeStr) {
    const [h, m] = timeStr.split(':').map(Number);
    return h * 60 + m;
}

function showClientInfoModal(clientId) {
  if (!clientId) return;
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

  // crea modal se non esiste
  let modal = document.getElementById('ClientInfoModal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'ClientInfoModal';
    modal.className = 'modal fade';
    modal.tabIndex = -1;
    modal.setAttribute('role', 'dialog');

    const dialog = document.createElement('div');
    dialog.className = 'modal-dialog modal-lg';
    dialog.style.zIndex = '21000'; // alto z-index
    dialog.style.height = '90vh'; // Altezza 90% dello schermo
    dialog.setAttribute('role', 'document');

    const content = document.createElement('div');
    content.className = 'modal-content';
    content.style.maxHeight = '80vh';
    content.style.display = 'flex';
    content.style.flexDirection = 'column';

    // header
    const header = document.createElement('div');
    header.className = 'modal-header';
    const title = document.createElement('h5');
    title.className = 'modal-title';
    title.textContent = 'Info cliente';
    const btnClose = document.createElement('button');
    btnClose.type = 'button';
    btnClose.className = 'btn-close';
    btnClose.setAttribute('data-bs-dismiss', 'modal');
    btnClose.setAttribute('aria-label', 'Chiudi');
    header.appendChild(title);
    header.appendChild(btnClose);

    // body
    const body = document.createElement('div');
    body.className = 'modal-body';
 // Layout flessibile: lo scroll sarà SOLO nel container storico+prossimi
    body.style.display = 'flex';
    body.style.flexDirection = 'column';
    body.style.flex = '1 1 auto';
    body.style.minHeight = '0';
    body.style.overflow = 'hidden';
    body.style.flex = '1 1 auto'; 

    // footer
    const footer = document.createElement('div');
    footer.className = 'modal-footer';
    footer.style.padding = '0';
    footer.style.margin = '0';
    const closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'btn btn-secondary';
    closeBtn.setAttribute('data-bs-dismiss', 'modal');
    closeBtn.textContent = 'Chiudi';
    footer.appendChild(closeBtn);

    content.appendChild(header);
    content.appendChild(body);
    content.appendChild(footer);
    dialog.appendChild(content);
    modal.appendChild(dialog);
    document.body.appendChild(modal);
  }

  // popolamento sicuro: rimuove nodi precedenti
  const body = modal.querySelector('.modal-body');
  while (body.firstChild) body.removeChild(body.firstChild);

 // Reinforce layout anche se il modal esiste già
 const _dialog = modal.querySelector('.modal-dialog');
 if (_dialog) _dialog.style.height = '90vh';
 const _content = modal.querySelector('.modal-content');
 if (_content) _content.style.height = '88vh';
 body.style.display = 'flex';
 body.style.flexDirection = 'column';
 body.style.flex = '1 1 auto';
 body.style.minHeight = '0';
 body.style.overflow = 'hidden';

  // placeholder di caricamento
  const loading = document.createElement('div');
  loading.textContent = 'Caricamento dati...';
  body.appendChild(loading);

  // fetch anagrafica cliente
  fetch(`/settings/api/client_info/${encodeURIComponent(clientId)}`)
    .then(resp => resp.ok ? resp.json() : Promise.reject('client_info failed'))
    .then(cliente => {
      // pulizia e costruzione DOM sicuro
      while (body.firstChild) body.removeChild(body.firstChild);

      // Aggiorna l'header del modal: "Info Cliente NOME COGNOME"
      const nm = `${cliente.cliente_nome || ''}`.trim();
      const sn = `${cliente.cliente_cognome || ''}`.trim();
      const headerTitleEl = modal.querySelector('.modal-title');
      if (headerTitleEl) {
        // escape per sicurezza prima di inserire in innerHTML
        function escHtml(str) {
          return String(str || '').replace(/[&<>"'`]/g, ch =>
            ch === '&' ? '&amp;' :
            ch === '<' ? '&lt;' :
            ch === '>' ? '&gt;' :
            ch === '"' ? '&quot;' :
            ch === "'" ? '&#39;' : '&#96;'
          );
        }
        const fullName = `${nm} ${sn}`.trim();
        const nameEsc = escHtml(fullName).toUpperCase();
        headerTitleEl.innerHTML = 'INFO CLIENTE' + (nameEsc ? ' ' + `<strong>${nameEsc}</strong>` : '');
      }

      // CONTATTI + EDIT (GRID 2x2)
      const contactGrid = document.createElement('div');
      contactGrid.style.display = 'grid';
      contactGrid.style.gridTemplateColumns = '1fr 1fr';
      contactGrid.style.gap = '12px';
      contactGrid.style.alignItems = 'start';

      // Helper per creare cella (label + input + save)
      function makeField(labelText, inputType, initialValue, placeholder) {
        const wrap = document.createElement('div');
        wrap.style.display = 'flex';
        wrap.style.flexDirection = 'row';
        wrap.style.alignItems = 'center';
        wrap.style.gap = '8px';
        wrap.style.width = '100%';

        const label = document.createElement('div');
        label.textContent = labelText;
        label.style.minWidth = '70px';
        label.style.fontWeight = '600';
        label.style.textTransform = 'uppercase';
        label.style.fontSize = '0.85em';

        const input = document.createElement('input');
        input.type = inputType;
        input.value = initialValue || '';
        input.placeholder = placeholder || '';
        input.className = 'form-control';
        input.style.flex = '1 1 auto';
        input.style.minWidth = '0';

        const saveBtn = document.createElement('button');
        saveBtn.type = 'button';
        saveBtn.className = 'btn btn-sm btn-outline-primary';
        saveBtn.textContent = 'Salva';
        saveBtn.style.flex = '0 0 auto';

        wrap.appendChild(label);
        wrap.appendChild(input);
        wrap.appendChild(saveBtn);

        return { wrap, input, saveBtn };
      }

      // NOME / COGNOME row (left = NOME, right = COGNOME)
      const nameField = makeField('NOME', 'text', cliente.cliente_nome || '', 'Nome');
      const surnameField = makeField('COGNOME', 'text', cliente.cliente_cognome || '', 'Cognome');
      contactGrid.appendChild(nameField.wrap);
      contactGrid.appendChild(surnameField.wrap);

      // CELL / E-MAIL row (left = CELL, right = E-MAIL)
      const phoneField = makeField('CELL', 'text', cliente.cliente_cellulare || '', 'Cellulare');
      const emailField = makeField('E-MAIL', 'email', cliente.cliente_email || '', 'E-mail');
      contactGrid.appendChild(phoneField.wrap);
      contactGrid.appendChild(emailField.wrap);

      // Append allineato al body
      body.appendChild(contactGrid);

      // Funzione di update generica (usa endpoint unico /settings/api/update_client_info per nome/cognome,
      // esistenti per telefono/email)
        function updateNameSurname() {
        const payload = {
          client_id: clientId,
          cliente_nome: nameField.input.value.trim(),
          cliente_cognome: surnameField.input.value.trim()
        };
        nameField.saveBtn.textContent = '...'; surnameField.saveBtn.textContent = '...';
        fetch('/settings/api/update_client_info', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
          body: JSON.stringify(payload)
        })
        .then(r => {
          if (r.status === 404) throw { type: 'not_found' };
          if (!r.ok) return r.json().then(j => Promise.reject(j || 'update failed'));
          return r.json();
        })
        .then(j => {
          const success = !!(j && j.success);
          nameField.saveBtn.textContent = success ? 'Salvato!' : 'Errore';
          surnameField.saveBtn.textContent = success ? 'Salvato!' : 'Errore';

          // nuovo nome completo
          const newNm = payload.cliente_nome || nm;
          const newSn = payload.cliente_cognome || sn;
          const newFull = (`${newNm} ${newSn}`).trim();

          // PATCH: Aggiorna input Navigator e rilancia ricerca per aggiornare dropdown e onclick
          const navInput = document.getElementById('clientSearchInputNav');
          if (navInput) {
              // Aggiorna il testo nel campo di ricerca con il nuovo nome
              navInput.value = newFull;
              
              // Se il cliente era già selezionato, aggiorna anche la variabile globale
              if (String(window.selectedClientIdNav) === String(clientId)) {
                  window.selectedClientNameNav = newFull;
                  if (typeof saveNavigatorState === 'function') saveNavigatorState();
              }

              // Rilancia la ricerca per rigenerare il dropdown con i dati aggiornati (inclusi gli onclick)
              if (typeof window.handleClientSearchNav === 'function') {
                  window.handleClientSearchNav(newFull);
              }
          }

          // aggiorna header (MAIUSCOLO + GRASSETTO)
          if (headerTitleEl) {
            const esc = s => String(s || '').replace(/[&<>"'`]/g, ch =>
              ch === '&' ? '&amp;' :
              ch === '<' ? '&lt;' :
              ch === '>' ? '&gt;' :
              ch === '"' ? '&quot;' :
              ch === "'" ? '&#39;' : '&#96;'
            );
            headerTitleEl.innerHTML = 'INFO CLIENTE' + (newFull ? ' ' + `<strong>${esc(newFull).toUpperCase()}</strong>` : '');
          }

          // Aggiorna ISTANTANEAMENTE i risultati dei dropdown (se visibili)
          try {
            // container ids usati: clientResults (modal), clientResultsNav (navigator), possibile clientResults nel modal edit
            ['clientResults','clientResultsNav'].forEach(cid => {
              const container = document.getElementById(cid);
              if (!container) return;
              container.querySelectorAll('.dropdown-item').forEach(item => {
                if (String(item.dataset.clientId) === String(clientId)) {
                  const txt = item.querySelector('.dropdown-item-text');
                  if (txt) txt.textContent = newFull;
                  else item.childNodes.forEach(n => { if (n.nodeType === Node.TEXT_NODE) n.textContent = newFull; });
                }
              });
            });

            // Aggiorna anche i risultati che potrebbero essere dentro un modal (Create/Edit) usando selettori più generici
            document.querySelectorAll('.results-dropdown .dropdown-item').forEach(item => {
              if (String(item.dataset.clientId) === String(clientId)) {
                const txt = item.querySelector('.dropdown-item-text');
                if (txt) txt.textContent = newFull;
              }
            });

            // Aggiorna i blocchi appuntamento visibili (link nome cliente)
            document.querySelectorAll(`.appointment-block[data-client-id="${clientId}"]`).forEach(block => {
              block.setAttribute('data-client-nome', newNm);
              block.setAttribute('data-client-cognome', newSn);
              const link = block.querySelector('.appointment-content .client-name a');
              if (link) link.textContent = newFull;
            });

            // Rilancia le ricerche per aggiornare eventuali dropdown attivi (fallback: usa nuovoFull se input vuoto)
            const refreshIfPossible = (handler, inputEl) => {
              if (typeof handler !== 'function') return;
              if (!inputEl) { handler(newFull); return; }
              const q = (inputEl.value && inputEl.value.trim().length >= 1) ? inputEl.value.trim() : newFull;
              handler(q);
            };
            // Create/Edit modal inputs (possono essere presenti)
            refreshIfPossible(window.handleClientSearch, document.querySelector('#CreateAppointmentModal input#clientSearchInput'));
            refreshIfPossible(window.handleClientSearch, document.querySelector('#EditAppointmentModal input#clientSearchInput'));
            // navigator
            refreshIfPossible(window.handleClientSearchNav, document.getElementById('clientSearchInputNav'));
          } catch (refreshErr) {
            console.warn('refresh after name update failed', refreshErr);
          }

          setTimeout(() => { nameField.saveBtn.textContent = 'Salva'; surnameField.saveBtn.textContent = 'Salva'; }, 1200);
        })
        .catch(err => {
          console.error('update_client_info error', err);
          if (err && err.type === 'not_found') {
            alert('Impossibile salvare: endpoint update_client_info non trovato sul server.');
          } else {
            alert('Errore salvataggio nome/cognome. Controlla la console.');
          }
          nameField.saveBtn.textContent = 'Errore';
          surnameField.saveBtn.textContent = 'Errore';
          setTimeout(() => { nameField.saveBtn.textContent = 'Salva'; surnameField.saveBtn.textContent = 'Salva'; }, 1200);
        });
      }

      nameField.saveBtn.addEventListener('click', updateNameSurname);
      surnameField.saveBtn.addEventListener('click', updateNameSurname);

      // phone save (usa endpoint esistente)
      phoneField.saveBtn.addEventListener('click', () => {
        phoneField.saveBtn.textContent = '...';
        fetch('/settings/api/update_client_phone', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
          body: JSON.stringify({ client_id: clientId, phone: phoneField.input.value.trim() })
        })
        .then(r => r.ok ? r.json() : Promise.reject('phone update failed'))
        .then(j => { phoneField.saveBtn.textContent = j.success ? 'Salvato!' : 'Errore'; setTimeout(()=> phoneField.saveBtn.textContent='Salva',1200); })
        .catch(err => { console.error(err); phoneField.saveBtn.textContent = 'Errore'; setTimeout(()=> phoneField.saveBtn.textContent='Salva',1200); });
      });

      // email save (usa endpoint esistente)
      emailField.saveBtn.addEventListener('click', () => {
        emailField.saveBtn.textContent = '...';
        fetch('/settings/api/update_client_email', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
          body: JSON.stringify({ client_id: clientId, email: emailField.input.value.trim() })
        })
        .then(r => {
          if (!r.ok) return r.text().then(t => Promise.reject({status: r.status, body: t}));
          return r.json();
        })
        .then(j => { emailField.saveBtn.textContent = j.success ? 'Salvato!' : 'Errore'; setTimeout(()=> emailField.saveBtn.textContent='Salva',1200); })
        .catch(err => { console.error(err); emailField.saveBtn.textContent = 'Errore'; setTimeout(()=> emailField.saveBtn.textContent='Salva',1200); });
      });

      // Campo NOTE CLIENTE (centrato, sopra storico)
      const noteContainer = document.createElement('div');
      noteContainer.style.marginTop = '14px';
      noteContainer.style.textAlign = 'center';
      const noteLabel = document.createElement('label');
      noteLabel.setAttribute('for', 'clientNoteTextarea');
      noteLabel.textContent = 'NOTE CLIENTE';
      noteLabel.style.display = 'block';
      noteLabel.style.fontWeight = '600';       // come i titoli dei campi nella grid
      noteLabel.style.fontSize = '0.85em';      // stessa dimensione
      noteLabel.style.textTransform = 'uppercase';
      const noteTextarea = document.createElement('textarea');
      noteTextarea.id = 'clientNoteTextarea';
      noteTextarea.className = 'form-control';
      noteTextarea.rows = 3;
      noteTextarea.value = cliente.note || '';
      noteTextarea.style.width = '80%';
      noteTextarea.style.height = '80px';
      noteTextarea.style.maxHeight = '90px';
      noteTextarea.style.margin = '0 auto';  // Centra il textarea orizzontalmente
      const noteSaveBtn = document.createElement('button');
      noteSaveBtn.type = 'button';
      noteSaveBtn.className = 'btn btn-sm btn-outline-primary';
      noteSaveBtn.textContent = 'Salva';
      noteSaveBtn.style.marginTop = '2px';
      noteContainer.appendChild(noteLabel);
      noteContainer.appendChild(noteTextarea);
      noteContainer.appendChild(noteSaveBtn);
      body.appendChild(noteContainer);

      // note save (usa endpoint /settings/api/update_client_note)
      noteSaveBtn.addEventListener('click', () => {
        noteSaveBtn.textContent = '...';
        fetch('/settings/api/update_client_note', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
          body: JSON.stringify({ client_id: clientId, note: noteTextarea.value.trim() })
        })
        .then(r => r.ok ? r.json() : Promise.reject('note update failed'))
        .then(j => { noteSaveBtn.textContent = j.success ? 'Salvato!' : 'Errore'; setTimeout(()=> noteSaveBtn.textContent='Salva',1200); })
        .catch(err => { console.error(err); noteSaveBtn.textContent = 'Errore'; setTimeout(()=> noteSaveBtn.textContent='Salva',1200); });
      });

      const historyAndNextContainer = document.createElement('div');
      historyAndNextContainer.style.flex = '1 1 0';
      historyAndNextContainer.style.minHeight = '0';   // necessario per far funzionare lo scroll in flex
      historyAndNextContainer.style.overflowY = 'auto'; // unico scroll per entrambe le sezioni
      body.appendChild(historyAndNextContainer);

      // separatore tra dati cliente e storico
      const separator = document.createElement('hr');
      separator.style.margin = '14px 0';
      historyAndNextContainer.appendChild(separator);

      // storico cliente (fetch)
      const histContainer = document.createElement('div');
      histContainer.style.marginTop = '6px';
      // Rimuovi maxHeight e overflowY: ora gestito dal container padre
      historyAndNextContainer.appendChild(histContainer);

      const histTitle = document.createElement('div');
      histTitle.textContent = 'STORICO APPUNTAMENTI';
      histTitle.style.fontWeight = '700';
      histTitle.style.textTransform = 'uppercase';
      histTitle.style.marginBottom = '6px';
      histContainer.appendChild(histTitle);

      const histDivider = document.createElement('div');
      histDivider.style.height = '1px';
      histDivider.style.background = '#e0e0e0';
      histDivider.style.marginBottom = '8px';
      histContainer.appendChild(histDivider);

      const histContent = document.createElement('div');
      // garantisce spazio anche se vuoto
      histContent.style.minHeight = '1.2em';
      histContainer.appendChild(histContent);

      fetch(`/settings/api/client_history?q=${encodeURIComponent(clientId)}`)
        .then(r => r.ok ? r.json() : Promise.reject('history failed'))
        .then(storico => {
          histContent.innerHTML = '';
          if (!Array.isArray(storico) || storico.length === 0) {
            const em = document.createElement('em');
            em.textContent = 'Nessuna seduta nello storico';
            histContent.appendChild(em);
            return;
          }

          // raggruppa e crea tabelle come nello tooltip (DOM-safe)
          const groups = (function(arr){ /* reuse grouping logic inline */ 
            const now = new Date(); const weekAgo = new Date(now); weekAgo.setDate(now.getDate()-7);
            const monthAgo = new Date(now); monthAgo.setMonth(now.getMonth()-1);
            const sixMonthsAgo = new Date(now); sixMonthsAgo.setMonth(now.getMonth()-6);
            const G = { 'ULTIMA SETTIMANA':[], 'ULTIMO MESE':[], 'ULTIMI 6 MESI':[], 'MENO RECENTI':[] };
            arr.forEach(row => {
              let d = row.ora_inizio && row.ora_inizio.length>10 ? row.ora_inizio.substring(0,10) : row.ora_inizio;
              const dt = d ? new Date(d) : null;
              if (dt && dt >= weekAgo) G['ULTIMA SETTIMANA'].push(row);
              else if (dt && dt >= monthAgo) G['ULTIMO MESE'].push(row);
              else if (dt && dt >= sixMonthsAgo) G['ULTIMI 6 MESI'].push(row);
              else G['MENO RECENTI'].push(row);
            });
            return G;
          })(storico);

          const order = ['ULTIMA SETTIMANA','ULTIMO MESE','ULTIMI 6 MESI','MENO RECENTI'];
          order.forEach(label => {
            const group = groups[label];
            if (group && group.length) {
              const block = document.createElement('div');
              block.style.marginTop = '10px';
              const toggle = document.createElement('div');
              toggle.style.cursor = 'pointer';
              toggle.style.fontWeight = 'bold';
              toggle.style.color = '#333';
              toggle.style.userSelect = 'none';
              const iconSpan = document.createElement('span');
              iconSpan.textContent = label === 'ULTIMA SETTIMANA' ? '−' : '+';
              iconSpan.style.marginRight = '6px';
              toggle.appendChild(iconSpan);
              toggle.appendChild(document.createTextNode(' ' + String(label) + ' (' + String(group.length) + ' PASSAGGI)'));
              block.appendChild(toggle);

              const tableWrapper = document.createElement('div');
              tableWrapper.style.display = label === 'ULTIMA SETTIMANA' ? '' : 'none';
              tableWrapper.style.marginTop = '6px';

              const table = document.createElement('table');
              table.className = 'table table-sm table-bordered mb-0';
              table.style.fontSize = '0.93em';
              const thead = document.createElement('thead');
              const tr = document.createElement('tr');
              ['Data','Ora','Servizio','Durata','Operatore','Prezzo'].forEach(text => {
                const th = document.createElement('th');
                th.textContent = text;
                tr.appendChild(th);
              });
              thead.appendChild(tr);
              table.appendChild(thead);
              const tbody = document.createElement('tbody');

              group.forEach(row => {
                let dataStr = '';
                let oraStr = '';
                if (row.ora_inizio) {
                  const match = String(row.ora_inizio).match(/^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2})/);
                  if (match) { dataStr = match[1]; oraStr = match[2]; } else { oraStr = String(row.ora_inizio); }
                }
                const parts = oraStr ? oraStr.split(':') : ['', ''];
                const tr = document.createElement('tr');
                tr.className = 'clickable-row';
                tr.style.cursor = 'pointer';
                tr.setAttribute('data-date', dataStr);
                tr.setAttribute('data-hour', parts[0] || '');
                tr.setAttribute('data-minute', parts[1] || '');
                const tdData = document.createElement('td');
                tdData.textContent = (window.formatDateItalian && dataStr)
                  ? window.formatDateItalian(dataStr)
                  : dataStr;
                const tdOra = document.createElement('td'); tdOra.textContent = oraStr;
                const tdServ = document.createElement('td'); tdServ.textContent = row.servizio_tag || '';
                const tdDur = document.createElement('td'); tdDur.textContent = row.durata ? (row.durata + ' min') : '';
                const tdOp  = document.createElement('td'); tdOp.textContent = row.operatore || '';
                const tdCost= document.createElement('td'); tdCost.textContent = row.costo ? ('€' + row.costo) : '';
                tr.append(tdData, tdOra, tdServ, tdDur, tdOp, tdCost);
                tr.addEventListener('click', function() {
                  const d = this.getAttribute('data-date');
                  const h = this.getAttribute('data-hour');
                  const m = this.getAttribute('data-minute');
                  if (d && h && m) window.location.href = `/calendar?date=${d}&ora=${h}:${m}`;
                });
                tbody.appendChild(tr);
              });

              table.appendChild(tbody);
              tableWrapper.appendChild(table);
              block.appendChild(tableWrapper);

              toggle.addEventListener('click', function() {
                if (tableWrapper.style.display === 'none') {
                  tableWrapper.style.display = '';
                  iconSpan.textContent = '−';
                } else {
                  tableWrapper.style.display = 'none';
                  iconSpan.textContent = '+';
                }
              });

              histContent.appendChild(block);
            }
          });
        })
        .catch(err => {
          histContent.innerHTML = '';
          const em = document.createElement('em'); em.textContent = 'Errore caricamento storico';
          histContent.appendChild(em);
          console.error('client_history error', err);
        });

      // separatore per prossimi appuntamenti
      const separator2 = document.createElement('hr');
      separator2.style.margin = '14px 0';
      historyAndNextContainer.appendChild(separator2);

      // prossimi appuntamenti
      const nextContainer = document.createElement('div');
      nextContainer.style.marginTop = '6px';
      historyAndNextContainer.appendChild(nextContainer);

      const nextTitle = document.createElement('div');
      nextTitle.textContent = 'PROSSIMI APPUNTAMENTI';
      nextTitle.style.fontWeight = '700';
      nextTitle.style.textTransform = 'uppercase';
      nextTitle.style.marginBottom = '6px';
      nextContainer.appendChild(nextTitle);

      const nextDivider = document.createElement('div');
      nextDivider.style.height = '1px';
      nextDivider.style.background = '#e0e0e0';
      nextDivider.style.marginBottom = '8px';
      nextContainer.appendChild(nextDivider);

      const nextContent = document.createElement('div');
      nextContent.style.minHeight = '1.2em';
      nextContainer.appendChild(nextContent);

      fetch(`/calendar/api/next-appointments-for-client/${encodeURIComponent(clientId)}`)
        .then(r => r.ok ? r.json() : Promise.reject('next appointments failed'))
        .then(prossimi => {
          nextContent.innerHTML = '';
          if (!Array.isArray(prossimi) || prossimi.length === 0) {
            const em = document.createElement('em'); em.textContent = 'Nessuna seduta prenotata';
            nextContent.appendChild(em);
            return;
          }
          const table = document.createElement('table');
          table.className = 'table table-sm table-bordered mb-0';
          table.style.fontSize = '0.93em';
          const thead = document.createElement('thead');
          const trh = document.createElement('tr');
          ['Data','Ora','Servizio','Durata','Operatore','Prezzo'].forEach(txt=>{ const th=document.createElement('th'); th.textContent=txt; trh.appendChild(th); });
          thead.appendChild(trh); table.appendChild(thead);
          const tbody = document.createElement('tbody');

          prossimi.forEach(row => {
            let dataStr=''; let oraStr='';
            if (row.ora_inizio) { const m = String(row.ora_inizio).match(/^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2})/); if (m){dataStr=m[1]; oraStr=m[2];} else oraStr = row.ora_inizio; }
            const parts = oraStr ? oraStr.split(':') : ['',''];
            const tr = document.createElement('tr'); tr.style.cursor = 'pointer';
            const tdData=document.createElement('td');
            tdData.textContent = (window.formatDateItalian && dataStr)
              ? window.formatDateItalian(dataStr)
              : dataStr;
            const tdOra=document.createElement('td'); tdOra.textContent=oraStr;
            const tdServ=document.createElement('td'); tdServ.textContent=row.servizio_tag || '';
            const tdDur=document.createElement('td'); tdDur.textContent=row.durata? (row.durata+' min') : '';
            const tdOp=document.createElement('td'); tdOp.textContent=row.operatore || '';
            const tdCost=document.createElement('td'); tdCost.textContent=row.costo ? ('€' + row.costo) : '';
            tr.append(tdData, tdOra, tdServ, tdDur, tdOp, tdCost);
            tr.addEventListener('click', function() {
              const d = this.getAttribute('data-date'); const h = parts[0] || ''; const m = parts[1] || '';
              if (dataStr && parts[0]) window.location.href = `/calendar?date=${dataStr}&ora=${parts[0]}:${parts[1]}`;
            });
            tbody.appendChild(tr);
          });

          table.appendChild(tbody);
          nextContent.appendChild(table);
        })
        .catch(err => {
          nextContent.innerHTML = '';
          const em = document.createElement('em'); em.textContent = 'Errore caricamento prossimi appuntamenti';
          nextContent.appendChild(em);
          console.error('next appointments error', err);
        });

      // apri modal (già creato)
      try {
        const bs = bootstrap.Modal.getOrCreateInstance(modal);
        bs.show();
      } catch (e) {
        console.error('Bootstrap modal show failed', e);
      }
    })
    .catch(err => {
      while (body.firstChild) body.removeChild(body.firstChild);
      const em = document.createElement('em'); em.textContent = 'Errore caricamento dati cliente';
      body.appendChild(em);
      console.error('client_info fetch error:', err);
    });
}

window.showClientInfoModal = showClientInfoModal;

function handleClientSearch(query) {
  // fallback sicuro
   query = (query || '').toString().toLowerCase().trim();

  // trova il container risultati più appropriato:
  // - se il focus è sull'input #clientSearchInput dentro un modal, usa il clientResults di quel modal
  // - altrimenti fallback a #clientResults globale, poi #clientResultsNav
  let resultsContainer = null;
  try {
    const active = document.activeElement;
    if (active && active.id === 'clientSearchInput') {
      resultsContainer = active.closest('.modal')?.querySelector('#clientResults') || document.getElementById('clientResults');
    }
    if (!resultsContainer) {
      const modalShown = document.querySelector('#CreateAppointmentModal.show') || document.getElementById('CreateAppointmentModal');
      resultsContainer = modalShown?.querySelector('#clientResults') || document.getElementById('clientResults') || document.getElementById('clientResultsNav');
    }
  } catch (err) {
    console.warn('handleClientSearch: error finding results container', err);
    resultsContainer = document.getElementById('clientResults') || document.getElementById('clientResultsNav');
  }

  if (!resultsContainer) return;

  if (query.length < 3) {
    resultsContainer.innerHTML = '';
    resultsContainer.style.display = 'none';
    return;
  }

  fetch(`/calendar/api/search-clients/${encodeURIComponent(query)}`)
    .then(r => {
      if (!r.ok) throw new Error('Network response not ok: ' + r.status);
      return r.json();
    })
    .then(clients => {
      resultsContainer.innerHTML = '';

      if (!Array.isArray(clients) || clients.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'dropdown-item';
        empty.textContent = 'Nessun risultato';
        resultsContainer.appendChild(empty);
        resultsContainer.style.display = 'block';
        return;
      }

      clients.forEach(client => {
        const item = document.createElement('div');
        item.className = 'dropdown-item';
        item.style.display = 'flex';
        item.style.alignItems = 'center';
        item.style.gap = '8px';

        const id = String(client.id ?? '');
        const name = String(client.name ?? '');
        const phone = String(client.phone ?? '');

        // testo (left) — occupa lo spazio rimanente e tronca se troppo lungo
        const txt = document.createElement('span');
        txt.className = 'dropdown-item-text';
        txt.style.flex = '1 1 auto';
        txt.style.overflow = 'hidden';
        txt.style.textOverflow = 'ellipsis';
        txt.style.whiteSpace = 'nowrap';
        txt.textContent = phone ? `${capitalizeName(name)} - ${phone}` : capitalizeName(name);
        item.appendChild(txt);

        // dataset usati anche dall’hover
        item.dataset.clientId = id;
        item.dataset.clientName = name;

        // info button (right) — ferma la propagazione del click della riga
        const infoBtn = document.createElement('button');
        infoBtn.type = 'button';
        infoBtn.className = 'client-info-btn';
        infoBtn.title = 'Info cliente';
        infoBtn.setAttribute('aria-label', 'Info cliente');
        infoBtn.innerText = 'i';
        
        infoBtn.addEventListener('click', function(ev) {
          ev.stopPropagation();
          ev.preventDefault();
          try {
            // Chiama la funzione centrale che costruisce il modal in modo sicuro e completo
            showClientInfoModal(id);
          } catch (e) {
            console.error('showClientInfoModal error', e);
          }
        });

        item.appendChild(infoBtn);

        // click → selezione (riga)
        item.addEventListener('click', () => {
          if (typeof selectClient === 'function') {
            selectClient(id, name);
          } else {
            const input = document.querySelector('#clientSearchInput') || document.querySelector('#clientSearchInputNav');
            const idInput = document.querySelector('#client_id');
            if (input) input.value = name;
            if (idInput) idInput.value = id;
          }
          resultsContainer.innerHTML = '';
          resultsContainer.style.display = 'none';
        });

        resultsContainer.appendChild(item);
      });
      resultsContainer.style.display = 'block';
    })
    .catch(err => {
      console.error('handleClientSearch error:', err);
      resultsContainer.innerHTML = '';
      resultsContainer.style.display = 'none';
    });
}

function handleServiceSearch(query) {
    const resultsContainer = document.getElementById('serviceResults');

    if (query.length >= 3) {
        fetch(`/calendar/api/search-services/${encodeURIComponent(query)}`)
            .then(response => response.json())
            .then(services => {
resultsContainer.innerHTML = '';
services.forEach(service => {
  const item = document.createElement('div');
  item.className = 'dropdown-item';
  // Nessun HTML, solo testo
  item.textContent = `${service.name} - ${service.duration} min - €${service.price}`;
  item.addEventListener('click', () => {
    selectService(String(service.id), String(service.name), String(service.duration));
  });
  resultsContainer.appendChild(item);
});
resultsContainer.style.display = 'block';
            });
    } else {
        resultsContainer.innerHTML = '';
        resultsContainer.style.display = 'none';
    }
}

// Funzioni di selezione
function selectClient(clientId, fullName) {
  const modal = document.querySelector('.modal.show');
  const input = modal ? modal.querySelector('#clientSearchInput') : document.getElementById('clientSearchInput');
  const hidden = modal ? modal.querySelector('#client_id') : document.getElementById('client_id');
  const results = modal ? modal.querySelector('#clientResults') : document.getElementById('clientResults');
  if (input) input.value = fullName;
  if (hidden) hidden.value = clientId;
  if (results) results.style.display = 'none';
  // Ricarica i servizi suggeriti per il cliente selezionato
  if (typeof loadServicesForModal === 'function') loadServicesForModal();
}

function selectService(serviceId, serviceName, serviceDuration) {
  document.getElementById('serviceSearchInput').value = serviceName;
  document.getElementById('service_id').value = serviceId;
  document.getElementById('serviceResults').style.display = 'none';
  document.getElementById('duration').value = serviceDuration;

  // --- AGGIUNGI UN NUOVO PSEUDOBLOCCO (NON SOVRASCRIVERE) ---
  var pseudoContainer = document.getElementById('pseudoBlockContainer');
  if (!pseudoContainer) return;

  // === Colore: usa quello del primo pseudoblocco, oppure generane uno se è il primo ===
  let color;
  const firstBlock = pseudoContainer.querySelector('.pseudo-block');
  if (firstBlock) {
    color = firstBlock.style.borderColor || '#007bff';
  } else {
    color = getRandomColor();
    window.firstPseudoBlockColor = color;
  }

  var pseudoBlock = document.createElement('div');
  pseudoBlock.className = 'pseudo-block';
  pseudoBlock.style.position = 'relative';
pseudoBlock.innerHTML = '';                         // svuota
const strong = document.createElement('strong');
strong.textContent = String(serviceName);
pseudoBlock.appendChild(strong);
pseudoBlock.appendChild(document.createTextNode(' ' + String(serviceDuration) + ' min'));

  pseudoBlock.style.border = '2px solid ' + color;
  pseudoBlock.dataset.colore = color;

  pseudoBlock.dataset.service = serviceName;
  pseudoBlock.dataset.duration = serviceDuration;
  pseudoBlock.dataset.serviceId = serviceId; 

  // Pulsante X per eliminare il blocco
  var deleteBtn = document.createElement('button');
  deleteBtn.className = 'delete-btn';
  deleteBtn.textContent = 'X';
  deleteBtn.style.position = 'absolute';
  deleteBtn.style.top = '2px';
  deleteBtn.style.right = '2px';
  deleteBtn.style.background = 'transparent';
  deleteBtn.style.border = 'none';
  deleteBtn.style.color = '#ff0000';
  deleteBtn.style.fontWeight = 'bold';
  deleteBtn.style.cursor = 'pointer';
  deleteBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      pseudoBlock.remove();
      // Se non ci sono più pseudoblocchi, resetta il colore globale
      if (pseudoContainer.querySelectorAll('.pseudo-block').length === 0) {
        window.firstPseudoBlockColor = null;
      }
  });
  pseudoBlock.appendChild(deleteBtn);

  pseudoContainer.appendChild(pseudoBlock);

  document.getElementById('serviceSearchInput').value = '';
}

// =============================================================
//   MODAL PER GESTIONE TURNI (CALENDAR.HTML)
// =============================================================
function openShiftsModalCalendar(operatorId, operatorName, date) {
  console.log("Apro modal per operatore:", operatorId, operatorName, date);

  const modalEl = document.getElementById('OperatorShiftsModalCalendar');
  const modalBody = document.querySelector('#OperatorShiftsModalCalendar .modal-body');
  if (!modalEl || !modalBody) return;

  // Header e data-attribute
  document.getElementById('modalOperatorNameCalendar').textContent = operatorName;
  document.getElementById('modalSelectedDateCalendar').textContent = formatDateItalian(date);  // Formatta in gg MMM yyyy
  modalEl.setAttribute('data-operator-id', operatorId);
  modalEl.setAttribute('data-date', date);

  // Svuota e costruisci DOM del form
  modalBody.innerHTML = '';

  const form = document.createElement('form');
  form.id = 'shiftFormCalendar';
  form.setAttribute('autocomplete', 'off');

  // ===== 1a RIGA: Inizio turno [xx:xx]  Fine turno [xx:xx] =====
  const firstRow = document.createElement('div');
  firstRow.className = 'd-flex flex-wrap align-items-center gap-4 mb-3';

  // Inizio turno
  const startWrap = document.createElement('div');
  startWrap.className = 'd-flex align-items-center gap-3';
  const lblStart = document.createElement('label');
  lblStart.setAttribute('for', 'shiftStartTimeCalendar');
  lblStart.className = 'form-label mb-0 text-nowrap';
  lblStart.style.minWidth = '140px'; // più spazio al label
  lblStart.textContent = 'Inizio turno';
  const inpStart = document.createElement('input');
  inpStart.type = 'time';
  inpStart.id = 'shiftStartTimeCalendar';
  inpStart.className = 'form-control w-auto';
  inpStart.required = true;
  inpStart.step = 900; // 15 minuti
  inpStart.style.width = '130px';
  if (window.defaultOpeningTime) inpStart.placeholder = String(window.defaultOpeningTime);
  startWrap.appendChild(lblStart);
  startWrap.appendChild(inpStart);

  // Fine turno
  const endWrap = document.createElement('div');
  endWrap.className = 'd-flex align-items-center gap-3';
  const lblEnd = document.createElement('label');
  lblEnd.setAttribute('for', 'shiftEndTimeCalendar');
  lblEnd.className = 'form-label mb-0 text-nowrap';
  lblEnd.style.minWidth = '140px'; // più spazio al label
  lblEnd.textContent = 'Fine turno';
  const inpEnd = document.createElement('input');
  inpEnd.type = 'time';
  inpEnd.id = 'shiftEndTimeCalendar';
  inpEnd.className = 'form-control w-auto';
  inpEnd.required = true;
  inpEnd.step = 900; // 15 minuti
  inpEnd.style.width = '130px';
  if (window.defaultClosingTime) inpEnd.placeholder = String(window.defaultClosingTime);
  endWrap.appendChild(lblEnd);
  endWrap.appendChild(inpEnd);

  firstRow.appendChild(startWrap);
  firstRow.appendChild(endWrap);

  // ===== 2a RIGA: [Salva] [Giorno di riposo] (50/50) =====
  const secondRow = document.createElement('div');
  secondRow.className = 'd-flex gap-2 w-100';

  const btnSave = document.createElement('button');
  btnSave.type = 'button';
  btnSave.id = 'saveShiftCalendarBtn';
  btnSave.className = 'btn btn-primary';
  btnSave.textContent = 'Salva';
  btnSave.style.flex = '1 1 0';  // 50%

  const btnDayOff = document.createElement('button');
  btnDayOff.type = 'button';
  btnDayOff.id = 'dayOffCalendarBtn';
  btnDayOff.className = 'btn btn-outline-secondary';
  btnDayOff.textContent = 'Giorno di riposo';
  btnDayOff.style.flex = '1 1 0'; // 50%

  secondRow.appendChild(btnSave);
  secondRow.appendChild(btnDayOff);

  // Monta form
  form.appendChild(firstRow);
  form.appendChild(secondRow);
  modalBody.appendChild(form);

  // Adatta larghezza del modal al contenuto della prima riga
  const dialog = modalEl.querySelector('.modal-dialog');
  if (dialog) {
    // si adatta al contenuto (prima riga), ma non supera la viewport
    dialog.style.maxWidth = 'calc(100vw - 2rem)';
    dialog.style.width = 'max-content';  // o 'fit-content' se preferisci
  }

  // Precompila con ultimi valori usati (se presenti)
  const lastStart = localStorage.getItem('lastShiftStartTime');
  const lastEnd = localStorage.getItem('lastShiftEndTime');
  if (lastStart) inpStart.value = lastStart;
  if (lastEnd) inpEnd.value = lastEnd;

  // Listener (mantengono la tua logica esistente)
  btnSave.addEventListener('click', () => {
    if (typeof window.saveDailyShiftCalendar === 'function') {
      window.saveDailyShiftCalendar();
    }
  });
  btnDayOff.addEventListener('click', () => {
    if (typeof window.setDayOffCalendar === 'function') {
      window.setDayOffCalendar();
    }
  });

  // Mostra il modal
  const bsModal = bootstrap.Modal.getOrCreateInstance(modalEl);
  bsModal.show();
}

// Funzione per salvare il turno giornaliero (calendar.html)
function saveDailyShiftCalendar() {
    const operatorId = document.getElementById('OperatorShiftsModalCalendar').getAttribute('data-operator-id');
    const date = document.getElementById('OperatorShiftsModalCalendar').getAttribute('data-date');
    const startTime = document.getElementById('shiftStartTimeCalendar').value;
    const endTime = document.getElementById('shiftEndTimeCalendar').value;

    localStorage.setItem('lastShiftStartTime', startTime);
    localStorage.setItem('lastShiftEndTime', endTime);

    // Validazione base
    if (!startTime || !endTime) {
        alert('Inserisci ora di inizio e fine.');
        return;
    }

    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    fetch(`/calendar/api/operators/${operatorId}/shifts`, {
        method: 'POST',
        headers: { 
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
            date: date,
            startTime: startTime,
            endTime: endTime
        })
    })
    
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => { throw new Error(err.error || "Errore nel salvataggio") });
        }
        return response.json();
    })
    .then(data => {
        console.log('Turno salvato:', data);
        const modalEl = document.getElementById('OperatorShiftsModalCalendar');
        const bsModal = bootstrap.Modal.getInstance(modalEl);
        if (bsModal) {
            bsModal.hide();
        }
        fetchCalendarData(); // Ricarica i dati
        location.reload();
    })
    .catch(error => {
        console.error('Errore:', error);
        alert(error.message);
    });
}
window.saveDailyShiftCalendar = saveDailyShiftCalendar;

function setDayOffCalendar() {
    const operatorId = document.getElementById('OperatorShiftsModalCalendar').getAttribute('data-operator-id');
    const date = document.getElementById('OperatorShiftsModalCalendar').getAttribute('data-date');

    // Imposta ora di inizio e fine uguali per il giorno di riposo
    const startTime = "00:00";
    const endTime = "00:00";

    // Preleva il token CSRF dal meta tag
    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

    fetch(`/calendar/api/operators/${operatorId}/shifts`, {
        method: 'POST',
        headers: { 
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
            date: date,
            startTime: startTime,
            endTime: endTime
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Errore durante l\'impostazione del giorno di riposo.');
        }
        return response.json();
    })
    .then(data => {
        console.log('Giorno di riposo impostato:', data);
        const modalEl = document.getElementById('OperatorShiftsModalCalendar');
        const bsModal = bootstrap.Modal.getInstance(modalEl);
        if (bsModal) {
            bsModal.hide();
        }
        fetchCalendarData(); // Ricarica i dati
        location.reload(); // Ricarica la pagina dopo l'aggiornamento
    })
    .catch(error => {
        console.error('Errore:', error);
        alert('Errore durante l\'impostazione del giorno di riposo.');
    });
}

window.setDayOffCalendar = setDayOffCalendar;

// Aggiungi event listener ai link degli operatori nell'agenda
document.querySelectorAll('.operator-shift-link').forEach(link => {
    link.addEventListener('click', function (e) {
        e.preventDefault();
        const operatorId = this.dataset.operatorId;
        const operatorName = this.dataset.operatorName;
        const date = this.dataset.date;
        openShiftsModalCalendar(operatorId, operatorName, date);
    });
});

// =============================================================
//   CLICK SULLA CELLA → APRI PAGINA DI CREAZIONE APPUNTAMENTO
// =============================================================
function bindNoteToggle() {
    const btnToggleNote = document.getElementById('btnToggleNote');
    if (!btnToggleNote) return;
    btnToggleNote.addEventListener('click', function() {
        const appointmentModalEl = document.getElementById('CreateAppointmentModal');
        const offModalEl = document.getElementById('CreateOffBlockModal');
        if (appointmentModalEl) {
            const appointmentModal = bootstrap.Modal.getInstance(appointmentModalEl) || new bootstrap.Modal(appointmentModalEl);
            appointmentModalEl.addEventListener('hidden.bs.modal', function handler() {
                appointmentModalEl.removeEventListener('hidden.bs.modal', handler);
                const offModal = new bootstrap.Modal(offModalEl);
                offModal.show();
            });
            appointmentModal.hide();
        } else {
            const offModal = new bootstrap.Modal(offModalEl);
            offModal.show();
        }
    });
}

document.addEventListener('DOMContentLoaded', bindNoteToggle);

window._whatsappModalDisabledCache = null;

function fetchWhatsappModalDisabled() {
  // MOBILE: forza disabilitato
  if (window.matchMedia && window.matchMedia('(max-width: 1199.98px)').matches) {
    window._whatsappModalDisabledCache = true;
    return Promise.resolve(true);
  }

  const endpoint = window.apiWhatsappSettingUrl || '/settings/api/settings/whatsapp';
  if (window._whatsappModalDisabledCache !== null) {
    return Promise.resolve(window._whatsappModalDisabledCache);
  }
  return fetch(endpoint, { method: 'GET', credentials: 'same-origin' })
    .then(resp => {
      if (!resp.ok) {
        window._whatsappModalDisabledCache = false;
        return false;
      }
      return resp.json();
    })
    .then(json => {
      const disabled = !!(json && json.whatsapp_modal_disable);
      window._whatsappModalDisabledCache = disabled;
      return disabled;
    })
    .catch(() => {
      window._whatsappModalDisabledCache = false;
      return false;
    });
}

function chiediInvioWhatsappAuto() {
  // MOBILE: nessuna conferma, sempre false
  if (window.matchMedia && window.matchMedia('(max-width: 1199.98px)').matches) {
    return Promise.resolve(false);
  }

  return fetchWhatsappModalDisabled().then(isDisabled => {
    if (isDisabled) return false;

    return new Promise((resolve) => {
      const TRY_TIMEOUT = 300;
      const MAX_TRIES = 10;
      let tries = 0;

      function findModalBody() {
        return document.getElementById('CreateAppointmentModalBody') ||
               document.querySelector('#CreateAppointmentModal .modal-body') ||
               document.querySelector('#CreateAppointmentModalBody') ||
               document.querySelector('#CreateAppointmentModalBody .modal-body') ||
               null;
      }
      function waitForBody(cb) {
        const body = findModalBody();
        if (body) return cb(body);
        tries++;
        if (tries > MAX_TRIES) return cb(null);
        setTimeout(() => waitForBody(cb), TRY_TIMEOUT);
      }

      waitForBody(function(modalBody) {
        if (!modalBody) return resolve(false);

        const existing = document.getElementById('whatsappInlineConfirm');
        if (existing) existing.remove();

        const panel = document.createElement('div');
        panel.id = 'whatsappInlineConfirm';
        panel.setAttribute('role', 'region');
        panel.style.width = '100%';
        panel.style.boxSizing = 'border-box';
        panel.style.marginTop = '12px';
        panel.style.padding = '12px';
        panel.style.border = '1px solid rgba(0,0,0,0.08)';
        panel.style.borderRadius = '6px';
        panel.style.background = '#fff';
        panel.style.boxShadow = '0 6px 18px rgba(0,0,0,0.06)';
        panel.style.zIndex = '9999';
        panel.style.fontSize = '14px';
        panel.style.color = '#222';

        const txt = document.createElement('div');
        txt.style.marginBottom = '10px';
        txt.textContent = 'Vuoi inviare in automatico una conferma WhatsApp al cliente?';
        panel.appendChild(txt);

        const btnRow = document.createElement('div');
        btnRow.style.display = 'flex';
        btnRow.style.gap = '8px';
        btnRow.style.justifyContent = 'flex-end';

        const back = document.createElement('button');
        back.type = 'button';
        back.className = 'btn btn-link';
        back.textContent = 'INDIETRO';
        back.style.marginRight = 'auto';
        back.style.color = '#666';

        const no = document.createElement('button');
        no.type = 'button';
        no.className = 'btn btn-secondary';
        no.textContent = 'No, crea senza inviare';

        const yes = document.createElement('button');
        yes.type = 'button';
        yes.className = 'btn btn-success';
        yes.textContent = 'Sì, invia';

        btnRow.appendChild(back);
        btnRow.appendChild(no);
        btnRow.appendChild(yes);
        panel.appendChild(btnRow);

        const formEl = modalBody.querySelector('#CreateAppointmentForm') || modalBody.querySelector('form');
        if (formEl && formEl.parentNode) formEl.insertAdjacentElement('afterend', panel);
        else modalBody.appendChild(panel);

        setTimeout(() => yes.focus(), 50);

        function cleanup() {
          const p = document.getElementById('whatsappInlineConfirm');
            if (p && p.parentNode) p.parentNode.removeChild(p);
          const modalEl = document.getElementById('CreateAppointmentModal');
          if (modalEl) modalEl.removeEventListener('hidden.bs.modal', onModalHidden);
          document.removeEventListener('keydown', onKey);
        }
        function onModalHidden() { cleanup(); resolve(false); }
        function onKey(e) { if (e.key === 'Escape') { cleanup(); resolve(false); } }

        const modalEl = document.getElementById('CreateAppointmentModal');
        if (modalEl) modalEl.addEventListener('hidden.bs.modal', onModalHidden);
        document.addEventListener('keydown', onKey);

        yes.addEventListener('click', function() { cleanup(); resolve(true); });
        no.addEventListener('click', function() { cleanup(); resolve(false); });
        back.addEventListener('click', function(e) { e.preventDefault(); cleanup(); resolve('back'); });
      });
    });
  });
}

document.querySelectorAll('.selectable-cell').forEach(cell => {
  cell.addEventListener('click', function(e) {

    // BLOCCO: se la cella è chiusa non fare nulla
    if (cell.classList.contains('calendar-closed')) {
      e.stopPropagation();
      e.preventDefault();
      return;
    }

    // Ignora click che partono da bottoni popup o blocchi
    const t = e.target;
    if (t.closest('.btn-popup') || t.closest('.popup-buttons') || t.closest('.appointment-block')) {
      return;
    }
    // Se ci sono pseudo‑blocchi nel Navigator, il click viene gestito dal flusso Navigator:
    // non aprire il modal standard di creazione appuntamento.
    if (window.pseudoBlocks && Array.isArray(window.pseudoBlocks) && window.pseudoBlocks.length > 0) {
      e.stopImmediatePropagation();
      e.preventDefault();
      return;
    }

    window.lastClickPosition = e.clientY + window.scrollY;
    // Se il click è su un blocco esistente, non fare nulla
    if (e.target.closest('.appointment-block')) {
      e.stopPropagation();
      return;
    }

    // Raccogli i dati dalla cella
    const operatorId = cell.getAttribute('data-operator-id');
    const operatorName = cell.getAttribute('data-operator-name') || '';
    const hour = cell.getAttribute('data-hour');
    const minute = cell.getAttribute('data-minute');
    const date = cell.getAttribute('data-date') || selectedDate;
    const start_time = (hour !== '' && minute !== '') ? 
      ('0' + hour).slice(-2) + ':' + ('0' + minute).slice(-2) : '';

    // Prendi il template
// Prendi il template
const template = document.getElementById('create-appt-template').innerHTML;

// Sanifica qualunque stringa che finisce nell'HTML (text o attributi)
function escapeHtml(v) {
  return String(v).replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

// Sostituisci i placeholder con versioni escape
const html = template
  .replace(/{{operator_id}}/g, escapeHtml(operatorId))
  .replace(/{{operator_name}}/g, escapeHtml(operatorName))
  .replace(/{{date}}/g, escapeHtml(date))
  .replace(/{{start_time}}/g, escapeHtml(start_time))
  .replace(/{{hour}}/g, escapeHtml(hour))
  .replace(/{{minute}}/g, escapeHtml(minute));

// Inserisci il form nel contenitore
const modalBody = document.getElementById('CreateAppointmentModalBody');
modalBody.innerHTML = html;

// PATCH: valorizza esplicitamente campi ora e operatore nel DOM se presenti
setTimeout(function() {
  // Se hai elementi aggiuntivi da valorizzare, inserisci qui i loro ID
  const hourDisplay = document.getElementById('hour-display');
  if (hourDisplay) hourDisplay.textContent = start_time;
  const operatorDisplay = document.getElementById('operator-display');
  if (operatorDisplay) operatorDisplay.textContent = operatorName;
  // Eventuali input hidden aggiuntivi:
  const operatorIdInput = document.getElementById('appointmentOperatorId');
  if (operatorIdInput) operatorIdInput.value = operatorId;
  const operatorNameInput = document.getElementById('appointmentOperatorName');
  if (operatorNameInput) operatorNameInput.value = operatorName;
  const startTimeInput = document.getElementById('appointmentStartTime');
  if (startTimeInput) startTimeInput.value = start_time;
}, 50);

// Mostra il modal Bootstrap
const modalEl = document.getElementById('CreateAppointmentModal');
const bsModal = new bootstrap.Modal(modalEl);
bsModal.show();
    enableCreateApptModalLock(modalEl);
    modalEl.addEventListener('hidden.bs.modal', () => {
      disableCreateApptModalLock(modalEl);
      // pulizia eventuale warning
      const w = modalEl.querySelector('#createApptOutsideWarning');
      if (w) w.remove();
    }, { once: true });

    modalEl.addEventListener('hidePrevented.bs.modal', (ev) => {
      ev.preventDefault();
      showCreateApptOutsideClickWarning(modalEl);
    });

// Ricerca cliente nel modal (versione sicura)
const clientSearchInput = document.getElementById('clientSearchInput');
const clientResults = document.getElementById('clientResults');
if (clientSearchInput && clientResults && typeof window.handleClientSearch === 'function') {
  clientSearchInput.addEventListener('keyup', function () {
    window.handleClientSearch(this.value.trim());
  });
}

    // Listener per "Crea blocco OFF"
const btnCreateBlockOff = document.getElementById('btnCreateBlockOff');
if (btnCreateBlockOff) {
  btnCreateBlockOff.addEventListener('click', function() {
    document.getElementById('clientSearchInput').closest('.form-group').style.display = 'none';
    document.getElementById('serviceSearchInput').closest('.form-group').style.display = 'none';
    document.getElementById('client_id').value = "";
    document.getElementById('service_id').value = "";
    document.getElementById('divTitolo').style.display = 'block';
    document.getElementById('divDurata').style.display = 'block';
        // PATCH: imposta durata a 60 minuti
    const durataInput = document.getElementById('duration');
    if (durataInput) {
      durataInput.value = 60;
    }
    const submitBtn = document.querySelector('#CreateAppointmentForm button[type="submit"]');
    submitBtn.innerText = "Crea blocco OFF";
    submitBtn.classList.remove('btn-primary');
    submitBtn.classList.add('btn-warning');
    submitBtn.style.float = 'right';
    submitBtn.style.marginRight = '10px';
    btnCreateBlockOff.style.display = 'none'; // Nascondi il tasto giallo dopo il click
    const pseudoContainer = document.getElementById('pseudoBlockContainer');
if (pseudoContainer) pseudoContainer.style.display = 'none';
  });
}

    // Listener per il submit del form
    const submitForm = document.getElementById('CreateAppointmentForm');
    if (submitForm) {
      submitForm.addEventListener('submit', async function(event) {
        event.preventDefault();

        const formData = new FormData(submitForm);

        // Determina se è un blocco OFF leggendo i campi client_id / service_id (compatibile con form vuoto o "0")
        const clientIdRaw = formData.get('client_id');
        const serviceIdRaw = formData.get('service_id');
        const clientIdEmpty = clientIdRaw === null || clientIdRaw === '' || clientIdRaw === '0' || clientIdRaw === 'null';
        const serviceIdEmpty = serviceIdRaw === null || serviceIdRaw === '' || serviceIdRaw === '0' || serviceIdRaw === 'null';
        const isOffBlock = clientIdEmpty && serviceIdEmpty;

        // Se NON è blocco OFF, chiedi conferma per l'invio WhatsApp; se è OFF, salta sempre la richiesta
        let inviaWhatsapp = false;
        if (!isOffBlock) {
          try {
            // Gestione difensiva: la funzione può risolvere 'back' per tornare all'editing
            const risposta = await chiediInvioWhatsappAuto();
            if (risposta === 'back') {
              // Torna all'editing del modal: non creare l'appuntamento, non chiudere il modal
              return;
            }
            inviaWhatsapp = !!risposta;
          } catch (e) {
            console.warn('chiediInvioWhatsappAuto errore ignorato:', e);
            inviaWhatsapp = false;
          }
        } else {
          inviaWhatsapp = false;
        }

        const data = Object.fromEntries(formData.entries());

        data.appointment_date = data.appointment_date || data.date || selectedDate || window.selectedAppointmentDate;
        data.operator_id = data.operator_id || operatorId || submitForm.querySelector('[name="operator_id"]')?.value || '';
        data.start_time = data.start_time || start_time || submitForm.querySelector('[name="start_time"]')?.value || '';
        data.client_id = data.client_id || submitForm.querySelector('[name="client_id"]')?.value || '';
        data.service_id = data.service_id || submitForm.querySelector('[name="service_id"]')?.value || '';
        data.date = data.date || date || submitForm.querySelector('[name="date"]')?.value || '';
        data.hour = data.hour || hour || submitForm.querySelector('[name="hour"]')?.value || '';
        data.minute = data.minute || minute || submitForm.querySelector('[name="minute"]')?.value || '';
        data.duration = data.duration || 60;
        data.colore = data.colore || "#CCCCCC";
        data.colore_font = data.colore_font || "#222222";
        data.note = data.note || data.titolo || "";

        let clientId = data.client_id;
        let serviceId = data.service_id;
        clientId = (clientId === "" || clientId === "0" || clientId === null || clientId === undefined || clientId === "null") ? null : clientId;
        serviceId = (serviceId === "" || serviceId === "0" || serviceId === null || serviceId === undefined || serviceId === "null") ? null : serviceId;
        const note = data.note ? data.note.trim() : "";
        const isOffBlockFinal = (!clientId && !serviceId);

        if (isOffBlock) {
          clientId = "dummy";
          serviceId = "dummy";
          data.client_id = "dummy";
          data.service_id = "dummy";
        }

        if (!isOffBlock && !clientId) {
          alert("Seleziona o aggiungi un cliente!");
          return;
        }
        if (!isOffBlock && !serviceId) {
          alert("Seleziona un servizio!");
          return;
        }

        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        const pseudoContainer = document.getElementById('pseudoBlockContainer');
        if (pseudoContainer) {
          const pseudoblocks = [];
          Array.from(pseudoContainer.children).forEach(function(block) {
            pseudoblocks.push({
              serviceId: block.dataset.serviceId || block.getAttribute('data-service-id'),
              clientId: block.dataset.clientId || block.getAttribute('data-client-id'),
              duration: block.dataset.duration,
              start: block.dataset.start,
              colore: block.dataset.colore
            });
          });
          data.pseudoblocks = pseudoblocks;
        }

        fetch('/calendar/create', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
          },
          body: JSON.stringify(data)
        })
        .then(response => {
          if (!response.ok) {
            return response.json().then(err => {
              throw new Error(err.error || "Errore nel salvataggio dell'appuntamento");
            });
          }
          return response.json();
        })
        .then(appointment => {
            console.log("Risposta appointment:", appointment);
          if (appointment.start_time) {
            const [h, m] = appointment.start_time.split(':');
            sessionStorage.setItem('scrollToHour', parseInt(h, 10));
            sessionStorage.setItem('scrollToMinute', parseInt(m, 10));
          }
          if (appointment.id) {
            sessionStorage.setItem('scrollToAppointmentId', appointment.id);
          }
          const modalBody = document.getElementById('CreateAppointmentModalBody');
          if (modalBody) modalBody.style.display = 'none';

const doReload = () => {
  if (window.lastClickPosition !== undefined && window.lastClickPosition !== null) {
    sessionStorage.setItem('lastClickPosition', window.lastClickPosition);
  }
  location.reload();
};

// Se è stato chiesto l'invio WhatsApp, aspetta che finisca prima di ricaricare
if (inviaWhatsapp) {
  inviaWhatsappAutoSeRichiesto(appointment, data, csrfToken).finally(doReload);
}

setTimeout(doReload, 100);

        })
        .catch(error => {
          alert(error.message);
        });
      });
    }
  });
});

// =============================================================
//   DURATA DINAMICA PER <select id="service">
// =============================================================
const serviceSelect = document.getElementById('service');
if (serviceSelect) {
    serviceSelect.addEventListener('change', function () {
        const selectedServiceId = this.value;
        const selectedOption = Array.from(this.options)
            .find(o => o.value == selectedServiceId);

        const defaultDuration = selectedOption
            ? selectedOption.getAttribute('data-default-duration')
            : 30;

        const durationInput = document.getElementById('duration');
        durationInput.value = defaultDuration;
        durationInput.setAttribute('placeholder', `Durata suggerita: ${defaultDuration} minuti`);
    });
}

// =============================================================
//   5) DRAG-AND-DROP: UNA SOLA SEZIONE
// =============================================================
let customDragging = false;
let customDraggedBlock = null;
let customDragStartX = 0;
let customDragStartY = 0;
let customInitialLeft = 0;
let customInitialTop = 0;
let customOriginalParent = null;
// Flag per distinguere tra click e drag (se il movimento è superiore a una soglia, consideriamo che sia avvenuto un drag)
let wasDragged = false;
const DRAG_DISTANCE_THRESHOLD = 5; // in pixel
let dropOccurred = false;

/* =============================================================
   FUNZIONE NUOVA: Se in una cella rimane un SOLO blocco, riportalo a width 100%
============================================================= */

// Imposta il listener custom SOLO sul drag-handle di ogni blocco appuntamento
document.querySelectorAll('.appointment-block').forEach(block => {
    const TOUCH_UI = (() => { try { return localStorage.getItem('sun_touch_ui') === '1'; } catch(_) { return false; } })();
    // Disabilita il draggable nativo sul blocco
    block.removeAttribute('draggable');
    block.style.cursor = TOUCH_UI ? 'pointer' : 'default';
    
    // Click sul blocco:
    // - TOUCH: toggle dei popup con .active-popup
    // - DESKTOP: mantieni la logica attuale (hover), blocca il click “vuoto”
    block.addEventListener('click', function(e) {
      const isInteractive = (
        e.target.closest('a') ||
        e.target.closest('.popup-buttons') ||
        e.target.closest('.btn-popup') ||
        e.target.closest('.note-indicator') ||
        e.target.closest('.chain-button') ||
        e.target.closest('.off-block-title')
      );
      if (!isInteractive) {
        e.stopPropagation();
        e.preventDefault();
        e.stopImmediatePropagation();
      }
    }, true);
    
    // Trova l'elemento drag-handle all'interno del blocco
    const dragHandle = block.querySelector('.drag-handle');
    if (dragHandle) {
        dragHandle.style.cursor = 'grab'; // Indica la cliccabilità del drag-handle
        dragHandle.addEventListener('mousedown', function(e) {
          customDragging = true;
          // Se il blocco fa parte di un macro‑blocco, usiamo il contenitore del gruppo
          var macroBlock = block.closest('.macro-block');
          if (macroBlock) {
              // Segnaliamo che si tratta di un macroblocco
              macroBlock.dataset.isMacroBlock = "true";
              customDraggedBlock = macroBlock;
              // Imposta l'opacità a 0.5 solo sul macroblocco
              customDraggedBlock.style.opacity = "0.5";
          } else {
              customDraggedBlock = block;
          }
          customDraggedBlock.style.zIndex = '9999';
          wasDragged = false;
          customDragStartX = e.clientX;
          customDragStartY = e.clientY;
          customInitialLeft = parseFloat(window.getComputedStyle(customDraggedBlock).left) || 0;
          customInitialTop = parseFloat(window.getComputedStyle(customDraggedBlock).top) || 0;
          customDraggedBlock.__oldParent = block.parentNode;
              customDraggedBlock.__originalPosition = {
        left: customDraggedBlock.style.left,
        top: customDraggedBlock.style.top
    };
          e.stopPropagation();
          e.preventDefault();
      });
    }
});

/* =============================================================
   (OPZIONALE) EVENTO MOUSEMOVE PER SETTARE IL FLAG wasDragged
============================================================= */
document.addEventListener('mousemove', function(e) {
    if (!customDragging || !customDraggedBlock) return;
    const dx = e.clientX - customDragStartX;
    const dy = e.clientY - customDragStartY;
    if (Math.abs(dx) > DRAG_DISTANCE_THRESHOLD || Math.abs(dy) > DRAG_DISTANCE_THRESHOLD) {
        wasDragged = true;
    }
    // Aggiorno la posizione visiva del blocco
    customDraggedBlock.style.left = (customInitialLeft + dx) + 'px';
    customDraggedBlock.style.top = (customInitialTop + dy) + 'px';
});

/* =============================================================
   EVENTO MOUSEUP (DROP DEL BLOCCO) - NUOVO CODICE
============================================================= */
document.addEventListener('mouseup', async function(e) {
  if (!customDragging) return;
  customDragging = false;
  if (!wasDragged) return;

  // Nascondi temporaneamente l'elemento per individuare la cella sottostante
  customDraggedBlock.style.display = 'none';
  const dropTarget = document.elementFromPoint(e.clientX, e.clientY);
  customDraggedBlock.style.display = '';
  
  let newCell = dropTarget ? dropTarget.closest('.selectable-cell') : null;
  if (!newCell) {
      newCell = customDraggedBlock.__oldParent;
  }
  
  // Se la cella non è valida o è chiusa, annulla il drop
  if (!newCell || newCell.classList.contains('calendar-closed')) {
      revertToOldPosition(customDraggedBlock);
      customDraggedBlock = null;
      return;
  }

  const blocksInTargetCell = Array.from(newCell.querySelectorAll('.appointment-block'));
  const hasOffBlock = blocksInTargetCell.some(b =>
    !b.getAttribute('data-client-id') || b.getAttribute('data-client-id') === "dummy" || b.classList.contains('note-off')
  );
  const hasAppointment = blocksInTargetCell.some(b =>
    b.getAttribute('data-client-id') && b.getAttribute('data-client-id') !== "dummy" && !b.classList.contains('note-off')
  );

  if (
    (hasOffBlock && hasAppointment) ||
    (hasOffBlock && customDraggedBlock.getAttribute('data-client-id') && customDraggedBlock.getAttribute('data-client-id') !== "dummy") ||
    (hasAppointment && (!customDraggedBlock.getAttribute('data-client-id') || customDraggedBlock.getAttribute('data-client-id') === "dummy"))
  ) {
    await revertToOldPosition(customDraggedBlock);
    customDraggedBlock = null;
    return;
  }
  
const oldCell = customDraggedBlock.__oldParent;
const prevBlocks = oldCell ? oldCell.querySelectorAll('.appointment-block').length : 1;

// Sposta il blocco
newCell.appendChild(customDraggedBlock);
customDraggedBlock.style.left = '0px';
customDraggedBlock.style.top = '0px';

// Aggiorna gli attributi del blocco spostato
customDraggedBlock.setAttribute('data-hour', newCell.getAttribute('data-hour'));
customDraggedBlock.setAttribute('data-minute', newCell.getAttribute('data-minute'));

await saveDraggedBlockPosition(customDraggedBlock, newCell);
arrangeBlocksInCell(newCell);
if (oldCell) arrangeBlocksInCell(oldCell);

// DOPO lo spostamento: se la cella di partenza aveva 2 o 3 blocchi e ora ne ha 1 o 2, fai reload
if (oldCell) {
    setTimeout(() => {
        const nowBlocks = oldCell.querySelectorAll('.appointment-block').length;
        if (nowBlocks === prevBlocks - 1) {
            location.reload();
        }
    }, 50);
}
  
  // Se l'elemento trascinato è un macro-blocco, ripristina l'opacità a 1
  if (customDraggedBlock.dataset.isMacroBlock === "true") {
      customDraggedBlock.style.opacity = "1";
  }
  
  customDraggedBlock = null;
});

function onBlockMouseUp(e) {
    e.preventDefault();
    e.stopPropagation();

    if (!isDragging || !draggedBlock) return;

    if (lastCell) {
        // Verifica se il blocco era dimezzato (controllando la classe o lo stile)
        const wasHalfWidth = draggedBlock.classList.contains('half-width') || 
                           draggedBlock.style.width === '50%';

        // Controlla se la cella di destinazione è vuota
        const isCellEmpty = lastCell.children.length === 0;

        // Salva la posizione del blocco nella cella di destinazione
        const duration = parseInt(draggedBlock.getAttribute('data-duration'), 10) || 15;
        const hour = lastCell.getAttribute('data-hour');
        const minute = lastCell.getAttribute('data-minute');

        draggedBlock.setAttribute('data-operator-id', lastCell.getAttribute('data-operator-id'));
        draggedBlock.setAttribute('data-hour', hour);
        draggedBlock.setAttribute('data-minute', minute);

        // Se la cella è vuota e il blocco era dimezzato, ripristina width 100%
        if (isCellEmpty && wasHalfWidth) {
            draggedBlock.style.width = '100%';
            draggedBlock.classList.remove('half-width'); // se usi una classe
        }

        // Posiziona visivamente il blocco nella cella
        lastCell.appendChild(draggedBlock);

        // Salva la nuova posizione nel backend
        saveDraggedBlockPosition(draggedBlock, lastCell)
            .then(() => {
                console.log("Posizione salvata con successo.");
                location.reload(); // Ricarica la pagina per aggiornare il calendario
            })
            .catch(err => {
                console.error("Errore durante il salvataggio della posizione:", err);
                alert("Errore durante il salvataggio. Riprova.");
            });
    }

    // Reset degli stati
    resetDragState();
}

function openModifyPopup(appointmentId) {
  if (!appointmentId) return;
  // Recupera il blocco appuntamento dal DOM
  const block = document.querySelector(`.appointment-block[data-appointment-id="${appointmentId}"]`);
  if (!block) return;
  const clientNome = block.getAttribute('data-client-nome') || '';
  const clientCognome = block.getAttribute('data-client-cognome') || '';
  
  // NEW: auto-copia il cellulare dalle note per placeholder BOOKING/ONLINE (source=web)
  try {
    const src = (block.getAttribute('data-source') || '').trim().toLowerCase();
    if (src === 'web' && clientNome === 'BOOKING' && clientCognome === 'ONLINE') {
      const note = block.getAttribute('data-note') || '';
      // estrai cellulare come da backend: "Cellulare:" o "Telefono:"
      const m = String(note).match(/(?:Cellulare|Telefono)\s*:\s*([^\s,]+(?:\s+[^\s,]+)*)/i);
      if (m && m[1]) {
        let phone = m[1].replace(/\s+/g, '');
        if (phone.startsWith('+39')) phone = phone.slice(3);
        if (phone.startsWith('0')) phone = phone.slice(1);
        if (phone) {
          navigator.clipboard && navigator.clipboard.writeText(phone)
            .then(() => console.log('📋 Numero copiato in clipboard:', phone))
            .catch(err => console.warn('Clipboard copy failed:', err));
        }
      }
    }
  } catch (e) {
    console.warn('auto-copy phone failed', e);
  }

  // Preferisci il testo già renderizzato (decodificato) nel link del blocco
  const rawNameEl = block.querySelector('.appointment-content .client-name a');
  const rawName = rawNameEl ? rawNameEl.textContent.trim() : '';
  const currentClientName = (rawName || `${clientNome} ${clientCognome}`.replace(/&#39;/g, "'")).trim();
  const clientId = block.getAttribute('data-client-id') || '';
  const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

  // Recupera il template e sostituisci i placeholder (senza innerHTML)
  const modalBody = document.querySelector('#EditAppointmentModal .modal-body');
  // Pulizia precedente
  while (modalBody.firstChild) modalBody.removeChild(modalBody.firstChild);

  // Helper di escaping locale (sicuro)
  function _escapeHtml(v) {
    return String(v || '').replace(/[&<>"'`]/g, ch =>
      ch === '&' ? '&amp;' :
      ch === '<' ? '&lt;' :
      ch === '>' ? '&gt;' :
      ch === '"' ? '&quot;' :
      ch === "'" ? '&#39;' : '&#96;'
    );
  }
  const safeClient = _escapeHtml(currentClientName);

  // Costruisci il contenuto del modal usando DOM nativo (no innerHTML)
  const form = document.createElement('form');
  form.id = 'EditAppointmentClientForm';
  form.method = 'POST';
  form.action = `/calendar/edit/${appointmentId}`;

  // Hidden inputs
  const hiddenAppointmentId = document.createElement('input');
  hiddenAppointmentId.type = 'hidden';
  hiddenAppointmentId.id = 'appointmentId';
  hiddenAppointmentId.name = 'appointmentId';
  hiddenAppointmentId.value = String(appointmentId);
  form.appendChild(hiddenAppointmentId);

  const hiddenCsrf = document.createElement('input');
  hiddenCsrf.type = 'hidden';
  hiddenCsrf.name = 'csrf_token';
  hiddenCsrf.value = csrfToken;
  form.appendChild(hiddenCsrf);

  const hiddenClientId = document.createElement('input');
  hiddenClientId.type = 'hidden';
  hiddenClientId.id = 'client_id';
  hiddenClientId.name = 'client_id';
  hiddenClientId.value = '';
  form.appendChild(hiddenClientId);

  // Gruppo Cliente Attuale
  const groupCurrent = document.createElement('div');
  groupCurrent.className = 'form-group';

  const labelCurrent = document.createElement('label');
  labelCurrent.setAttribute('for', 'currentClient');
  labelCurrent.textContent = 'Cliente Attuale:';
  groupCurrent.appendChild(labelCurrent);

  const flexContainer = document.createElement('div');
  flexContainer.style.display = 'flex';
  flexContainer.style.alignItems = 'center';

  const inputCurrent = document.createElement('input');
  inputCurrent.type = 'text';
  inputCurrent.id = 'currentClient';
  inputCurrent.className = 'form-control';
  inputCurrent.value = currentClientName;
  inputCurrent.disabled = true;
  inputCurrent.style.flex = '1';
  inputCurrent.style.marginRight = '8px';
  inputCurrent.setAttribute('data-client-id', String(clientId));
  flexContainer.appendChild(inputCurrent);

  const infoBtn = document.createElement('button');
  infoBtn.type = 'button';
  infoBtn.className = 'client-info-btn';
  infoBtn.setAttribute('aria-label', 'Info cliente');
  infoBtn.title = 'Info cliente';
  infoBtn.id = 'infoClientBtn';
  infoBtn.textContent = 'i';
  flexContainer.appendChild(infoBtn);

  groupCurrent.appendChild(flexContainer);
  form.appendChild(groupCurrent);

  // Gruppo Nuovo Cliente
  const groupNew = document.createElement('div');
  groupNew.className = 'form-group';

  const labelNew = document.createElement('label');
  labelNew.setAttribute('for', 'clientSearchInput');
  labelNew.textContent = 'Nuovo cliente:';
  groupNew.appendChild(labelNew);

  const inputContainer = document.createElement('div');
  inputContainer.style.display = 'flex';
  inputContainer.style.alignItems = 'center';
  inputContainer.style.position = 'relative';

  const inputNew = document.createElement('input');
  inputNew.type = 'text';
  inputNew.id = 'clientSearchInput';
  inputNew.className = 'form-control';
  inputNew.placeholder = 'Nome, cognome o cellulare...';
  inputNew.autocomplete = 'off';
  inputNew.style.width = 'calc(100% - 40px)'; // Ristringe l'input per lasciare spazio al pulsante
  inputContainer.appendChild(inputNew);

  // Pulsante "+" per aggiungere nuovo cliente (posizionato fuori dal form, accanto all'input)
  const addBtn = document.createElement('button');
  addBtn.type = 'button';
  addBtn.className = 'btn btn-outline-success btn-add-client-square btn-add-client-nav';
  addBtn.setAttribute('aria-label', 'Aggiungi cliente');
  addBtn.title = 'Aggiungi cliente';
  addBtn.textContent = '+';
  addBtn.style.position = 'absolute';
  addBtn.style.right = '0';
  addBtn.style.top = '50%';
  addBtn.style.transform = 'translateY(-50%)';
  addBtn.addEventListener('click', function(ev) {
    ev.stopPropagation();
    ev.preventDefault();
    try {
      openAddClientModal('assignModal');
    } catch (e) {
      console.error('openAddClientModal error', e);
    }
  });
  inputContainer.appendChild(addBtn);

  groupNew.appendChild(inputContainer);

  const resultsDiv = document.createElement('div');
  resultsDiv.id = 'clientResults';
  resultsDiv.className = 'results-dropdown';
  groupNew.appendChild(resultsDiv);

  form.appendChild(groupNew);

  // Bottone Submit
  const submitBtn = document.createElement('button');
  submitBtn.type = 'submit';
  submitBtn.className = 'btn btn-primary';
  submitBtn.textContent = 'Assegna a Nuovo Cliente';
  form.appendChild(submitBtn);

  modalBody.appendChild(form);

  document.getElementById('EditAppointmentModalLabel').textContent = "Assegna ad Altro Cliente";

  // Mostra il modal
  const modal = new bootstrap.Modal(document.getElementById('EditAppointmentModal'));
  modal.show();

  try {
    // Gestione ricerca cliente (unica logica)
    const clientSearchInput = document.querySelector('#EditAppointmentModal input#clientSearchInput');
    if (clientSearchInput && typeof window.handleClientSearch === "function") {
      clientSearchInput.addEventListener('input', function() {
        window.handleClientSearch(this.value);
      });
    }

    // Event listener per il pulsante "i" (Info Cliente) - chiama showClientInfoModal come nelle altre parti
    const infoBtnElement = document.getElementById('infoClientBtn');
    if (infoBtnElement) {
      infoBtnElement.addEventListener('click', function(ev) {
        ev.stopPropagation();
        const clientId = document.getElementById('currentClient').getAttribute('data-client-id');
        if (clientId && typeof window.showClientInfoModal === 'function') {
          window.showClientInfoModal(clientId);
        }
      });
    }

    // Gestione submit form di modifica cliente (resta invariata)
    const formElement = document.getElementById('EditAppointmentClientForm');
    if (formElement) {
      formElement.addEventListener('submit', function(e) {
        e.preventDefault();
        const selectedClientId = document.querySelector('#EditAppointmentModal #client_id')?.value;
        if (!selectedClientId) { alert("Seleziona un cliente dalla lista."); return; }
        const fullName = (document.querySelector('#EditAppointmentModal input#clientSearchInput')?.value || '').trim();

        fetch(formElement.action, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
          body: JSON.stringify({ client_id: parseInt(selectedClientId, 10) })
        })
        .then(r => r.json())
        .then(() => {
          const baseBlock = document.querySelector(`.appointment-block[data-appointment-id="${appointmentId}"]`);
          // Se blocco web con booking_session_id, propaga a tutta la sessione; altrimenti usa i contigui
          let blocks = [];
          if (baseBlock) {
            const sessionId = baseBlock.getAttribute('data-booking_session_id');
            const src = (baseBlock.getAttribute('data-source') || '').toLowerCase();
            if (sessionId && src === 'web') {
              blocks = Array.from(document.querySelectorAll(`.appointment-block[data-booking_session_id="${sessionId}"]`));
            } else {
              blocks = (typeof getRelevantBlocks === 'function') ? getRelevantBlocks(baseBlock) : [baseBlock];
            }
          }
          const parts = fullName.split(' ');
          const nome = parts.shift() || '';
          const cognome = parts.join(' ').trim();

          const updates = [];
          blocks.forEach(b => {
            const id = b.getAttribute('data-appointment-id');
            // UI immediata
            b.setAttribute('data-client-id', String(selectedClientId));
            b.setAttribute('data-client-nome', nome);
            b.setAttribute('data-client-cognome', cognome);
            const link = b.querySelector('.appointment-content .client-name a');
            if (link) link.textContent = fullName || (nome + ' ' + cognome).trim();
            // Backend
            updates.push(fetch(`/calendar/edit/${id}`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
              body: JSON.stringify({ client_id: parseInt(selectedClientId, 10) })
            }).catch(() => {}));
          });

          // NEW: ricarica solo per blocchi web/booking_session
          const shouldReload = !!(baseBlock && (
            (baseBlock.getAttribute('data-source') || '').toLowerCase() === 'web' ||
            baseBlock.getAttribute('data-booking_session_id')
          ));

          return Promise.allSettled(updates);
        })
        .then((shouldReload) => {
          const bs = bootstrap.Modal.getInstance(document.getElementById('EditAppointmentModal'));
          if (bs) bs.hide();
          if (shouldReload) {
            setTimeout(() => location.reload(), 100);
          }
        })
        .catch(err => {
          console.error("Errore aggiornamento cliente:", err);
          alert("Errore durante l'aggiornamento.");
        });
      });
    }
  } catch (err) {
    console.error("Errore in openModifyPopup:", err);
  }
}
window.openModifyPopup = openModifyPopup;

// Funzione SEPARATA per i blocchi booking online
function propBookingBlocks(appointmentId, newClientId, newClientName) {
  const modified = document.querySelector(
    `.appointment-block[data-appointment-id="${appointmentId}"]`
  );
  if (!modified) return;

  // NUOVO: raggruppa tutti i blocchi della stessa sessione e propaga client+colore
  const sessionId = modified.getAttribute('data-booking_session_id');
  const blocks = sessionId
    ? Array.from(document.querySelectorAll(`.appointment-block[data-booking_session_id="${sessionId}"]`))
    : [modified];

  const baseColor = getRandomColor();
  const baseFont = computeFontColor(baseColor);
  const parts = newClientName.split(' ');
  const nome = parts.shift() || '';
  const cognome = parts.join(' ') || '';

  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');

  blocks.forEach(b => {
    // DOM
    b.setAttribute('data-client-id', String(newClientId));
    b.setAttribute('data-client-nome', nome);
    b.setAttribute('data-client-cognome', cognome);
    b.setAttribute('data-colore', baseColor);
    b.setAttribute('data-colore_font', baseFont);
    b.style.backgroundColor = baseColor;
    b.style.color = baseFont;
    const content = b.querySelector('.appointment-content');
    if (content) {
      content.style.color = baseFont;
      content.querySelectorAll('a').forEach(a => a.style.color = baseFont);
      const link = content.querySelector('.client-name a');
      if (link) link.innerText = newClientName;
    }
    // Backend
    const id = b.getAttribute('data-appointment-id');
    if (!id) return;
    const payload = {
      client_id: newClientId,
      // Persisti colore scelto per uniformità sessione
      colore: baseColor,
      colore_font: baseFont
    };
      const bId = b.getAttribute('data-appointment-id');
      if (bId) {
    fetch(`/calendar/edit/${id}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      },
      body: JSON.stringify(payload)
    }).catch(err => console.error(`Errore update blocco booking ${id}:`, err));
      }
  });
}

window.propBookingBlocks = propBookingBlocks;

// Funzione per il movimento del blocco durante il drag
function onBlockMouseMove(e) {
    if (!isDragging || !draggedBlock) return;

    const parentRect = draggedBlock.parentElement.getBoundingClientRect();

    // Aggiorna la posizione del blocco rispetto all'offset
    const newLeft = initialLeft + (e.clientX - dragStartX);
    const newTop = initialTop + (e.clientY - dragStartY);    

    // Limita il movimento del blocco all'interno del genitore
    const parentWidth = parentRect.width - draggedBlock.offsetWidth;
    const parentHeight = parentRect.height - draggedBlock.offsetHeight;

    draggedBlock.style.left = `${Math.max(0, Math.min(parentWidth, newLeft))}px`;
    draggedBlock.style.top = `${Math.max(0, Math.min(parentHeight, newTop))}px`;
}

function resetDragState() {
    isMouseDown = false;
    isDragging = false;
    draggedBlock = null;
    
    if (lastCell) {
        lastCell.classList.remove('highlight');
    }
    lastCell = null;

    document.removeEventListener('mousemove', onBlockMouseMove);
    document.removeEventListener('mouseup', onBlockMouseUp);
}


// =============================================================
//   Salvataggio posizione nel backend
// =============================================================
async function saveDraggedBlockPosition(block, cell) {
  const appointmentId = block.getAttribute('data-appointment-id');
  const operatorId = cell.getAttribute('data-operator-id');
  const hour = parseInt(cell.getAttribute('data-hour'), 10);
  const minute = parseInt(cell.getAttribute('data-minute'), 10);
  const newDate = cell.getAttribute('data-date') || selectedDate;
  
  // Formatta la data come stringa nel formato YYYY-MM-DD
  const newDateStr = new Date(newDate).toISOString().split('T')[0];
  
  // Verifica che tutti i parametri siano presenti e validi
  if (!appointmentId || !operatorId || isNaN(hour) || isNaN(minute) || !newDate) {
    console.warn("Parametri mancanti o non validi, skip update:", {
      appointmentId,
      operatorId,
      hour,
      minute,
      newDate: newDateStr
    });
    return; // Esce senza effettuare l'update
  }

  const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

  try {
    const resp = await fetch(`/calendar/update/${appointmentId}`, {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      },
      body: JSON.stringify({ operator_id: operatorId, hour, minute, date: newDateStr })
    });
    if (!resp.ok) {
      const errorText = await resp.text();
      console.warn("Errore update posizione:", errorText);
    } else {
      console.log("Posizione salvata con successo.");
    }
  } catch (err) {
    console.error("Errore salvataggio posizione:", err);
  }
}


// =============================================================
//   FUNZIONE PER IL CALCOLO DELLA DURATA DEI SERVIZI SU AGENDA
// =============================================================
// Funzione per ottenere il valore numerico della variabile CSS
function getQuarterPx() {
    const rootStyles = getComputedStyle(document.documentElement);
    const quarterPxValue = rootStyles.getPropertyValue('--quarter-px').trim();
    const quarterPx = parseInt(quarterPxValue, 10) || 60; // Default a 60 se non definito
    console.log(`QUARTER_PX: ${quarterPx}px`); // Debug
    return quarterPx;
}

window.getQuarterPx = getQuarterPx;

document.addEventListener('DOMContentLoaded', () => {
    const QUARTER_PX = getQuarterPx(); // Ottieni il valore dalla variabile CSS
    console.log(`Impostando QUARTER_PX a ${QUARTER_PX}px`); // Debug

    fetchCalendarData(); 

    let currentBlock  = null;
    let startY        = 0;
    let startHeight   = 0;

    function resizeBlock(e) {
      if (!currentBlock) return;
      currentBlock.classList.add('resizing');
  
      // Trova la cella contenitore
      const cell = currentBlock.parentElement;
      if (cell && cell.classList.contains('selectable-cell')) {
          cell.style.height = 'auto';
          cell.style.overflow = 'visible';
      }
  
      // Calcola la nuova altezza in pixel in base al movimento del mouse
      const deltaY = e.clientY - startY;
      let newHeight = startHeight + deltaY;
      // Imposta un minimo per evitare blocchi troppo piccoli
      const minHeight = 10;
      if (newHeight < minHeight) newHeight = minHeight;
  
      currentBlock.style.height = `${newHeight}px`;
  
      // Calcola la nuova durata in minuti in base all'altezza e aggiorna l'attributo
      const QUARTER_PX = getQuarterPx();
      const newDuration = Math.round(newHeight / QUARTER_PX * 15);
      currentBlock.setAttribute('data-duration', newDuration);
  }

  function stopResize() {
    if (!currentBlock) return;
    currentBlock.classList.remove('resizing');

    // Snap al multiplo di quarter più vicino
    const QUARTER_PX = getQuarterPx();
    let currentHeight = parseInt(currentBlock.style.height, 10);
    let quarters = Math.round(currentHeight / QUARTER_PX);
    if (quarters < 1) quarters = 1;
    const snappedHeight = quarters * QUARTER_PX;
    currentBlock.style.height = `${snappedHeight}px`;
    currentBlock.setAttribute('data-duration', quarters * 15);

    // Ripristina l'altezza della cella al valore di default (quarter)
    const cell = currentBlock.parentElement;
    if (cell && cell.classList.contains('selectable-cell')) {
        cell.style.height = '';
        cell.style.overflow = '';
    }

    const appointmentId = currentBlock.getAttribute('data-appointment-id');
    const newDuration = currentBlock.getAttribute('data-duration');

    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    fetch(`/calendar/adjust-duration/${appointmentId}`, {
        method: 'POST',
        headers: { 
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({ adjustment: parseInt(newDuration, 10) })
    }).then(response => {
        if (!response.ok) {
            console.error('Errore durante il salvataggio della durata.');
        } else {
            console.log(`Durata aggiornata: ${newDuration} minuti`);
        }
    }).catch(err => console.error('Errore di rete:', err));

    document.removeEventListener('mousemove', resizeBlock);
    document.removeEventListener('mouseup', stopResize);
    currentBlock = null;
}

    // Inizializza ogni blocco appuntamento
    document.querySelectorAll('.appointment-block').forEach(block => {
        const color = block.getAttribute('data-colore') || '#FFFFFF'; // Colore predefinito
        block.style.backgroundColor = color;
        const duration = parseInt(block.getAttribute('data-duration'), 10) || 15;
        const defaultHeight = (duration / 15) * QUARTER_PX;
        block.style.height = `${defaultHeight}px`;
        console.log(`Impostata altezza di ${defaultHeight}px per l'appuntamento ${block.getAttribute('data-appointment-id')}`);

        block.style.position = 'absolute';
        block.style.top = '0';
        block.style.left = '0';
        block.style.width = '100%';
        block.style.boxSizing = 'border-box';

        // [DOPO]: Consentiamo il drop su .selectable-cell
document.querySelectorAll('.selectable-cell').forEach(cell => {

    // dragover → deve fare event.preventDefault() per consentire il drop
    cell.addEventListener('dragover', function(event) {
        event.preventDefault();
        event.dataTransfer.dropEffect = 'move';
        cell.style.cursor = 'grabbing';
    });
    cell.addEventListener('dragleave', function() {
        cell.style.cursor = '';
    });

    // drop → recuperiamo i dati e spostiamo il blocco
    cell.addEventListener('drop', async function(event) {
        event.preventDefault();
    
        // Ottieni l'ID dell'appuntamento salvato in dataTransfer
        const appointmentId = event.dataTransfer.getData('appointmentId');
        if (!appointmentId) return;
    
        // Trova il blocco associato all'ID
        const draggedBlock = document.querySelector(`.appointment-block[data-appointment-id="${appointmentId}"]`);
        if (!draggedBlock) return;
    
        console.log("Blocco rilasciato in cella:", cell, "appointmentId:", appointmentId);
    
        // Aggiorna gli attributi del blocco in base alla cella target
        const hour = cell.getAttribute('data-hour');
        const minute = cell.getAttribute('data-minute');
        const operatorId = cell.getAttribute('data-operator-id');
    
        draggedBlock.setAttribute('data-operator-id', operatorId);
        draggedBlock.setAttribute('data-hour', hour);
        draggedBlock.setAttribute('data-minute', minute);
    
        // Appendi visivamente il blocco alla nuova cella e resetta la posizione interna
        cell.appendChild(draggedBlock);
        draggedBlock.style.left = '0px';
        draggedBlock.style.top = '0px';
    
        // Salva la nuova posizione (chiama la funzione che eventualmente aggiorna il backend)
        await saveDraggedBlockPosition(draggedBlock, cell);
    
        // Disposizione dei blocchi nella cella target
        arrangeBlocksInCell(cell);
      });
});
    });

    document.addEventListener('mousedown', function(e) {
      if (!e.target.classList.contains('resize-handle')) return;
      e.preventDefault();
      e.stopPropagation();

      currentBlock = e.target.parentElement;
      startY       = e.clientY;
      startHeight  = parseInt(window.getComputedStyle(currentBlock).height, 10);

      document.addEventListener('mousemove', resizeBlock);
      document.addEventListener('mouseup',   stopResize);
  });

    document.addEventListener('DOMContentLoaded', function () {
        const clientSearchInput = document.getElementById('clientSearchInput');
        const clientSearchResults = document.getElementById('clientSearchResults');
        const serviceSearchInput = document.getElementById('serviceSearchInput');
        const serviceSearchResults = document.getElementById('serviceSearchResults');

        // Funzione per gestire la ricerca dei clienti
        function clientHandleSearch(query) {
            if (query.length >= 3) {
                fetch(`/calendar/api/search-clients/${query}`)
                    .then((response) => response.json())
                    .then((data) => {
                        clientSearchResults.innerHTML = ''; // Pulisci risultati precedenti
                        if (data.length > 0) {
                            clientSearchResults.style.display = 'block';
                            data.forEach((client) => {
                                const resultItem = document.createElement('div');
                                resultItem.className = 'dropdown-item';
                                resultItem.textContent = `${client.name} (${client.phone || 'N/A'})`;
                                resultItem.dataset.clientId = client.id;
                                resultItem.addEventListener('click', function () {
                                    clientSearchInput.value = client.name;
                                    clientSearchResults.style.display = 'none';
                                    const clientSelect = document.getElementById('client');
                                    if (clientSelect) {
                                        clientSelect.value = client.id;
                                    }
                                });
                                clientSearchResults.appendChild(resultItem);
                            });
                        } else {
                            clientSearchResults.style.display = 'none';
                        }
                    })
                    .catch((error) =>
                        console.error('Errore durante la ricerca dei clienti:', error)
                    );
            } else {
                clientSearchResults.style.display = 'none';
            }
        }
    
        
        // Funzione per gestire la ricerca dei servizi
        function serviceHandleSearch(query) {
            if (query.length >= 3) {
                fetch(`/calendar/api/search-services/${query}`)
                    .then((response) => response.json())
                    .then((data) => {
                        serviceSearchResults.innerHTML = ''; // Pulisci risultati precedenti
                        if (data.length > 0) {
                            serviceSearchResults.style.display = 'block';
                            data.forEach((service) => {
                                const resultItem = document.createElement('div');
                                resultItem.className = 'dropdown-item';
                                resultItem.textContent = `${service.name} (${service.duration} min, €${service.price})`;
                                resultItem.dataset.serviceId = service.id;
                                resultItem.addEventListener('click', function () {
                                    serviceSearchInput.value = service.name;
                                    serviceSearchResults.style.display = 'none';
                                    const serviceSelect = document.getElementById('service');
                                    if (serviceSelect) {
                                        serviceSelect.value = service.id;
                                    }
                                });
                                serviceSearchResults.appendChild(resultItem);
                            });
                        } else {
                            serviceSearchResults.style.display = 'none';
                        }
                    })
                    .catch((error) =>
                        console.error('Errore durante la ricerca dei servizi:', error)
                    );
            } else {
                serviceSearchResults.style.display = 'none';
            }
        }
        
        // Event listeners per le ricerche
        clientSearchInput.addEventListener('keyup', function () {
            console.log('Keyup catturato', this.value);
            const query = this.value.trim();
            clientHandleSearch(query);
        });

        serviceSearchInput.addEventListener('keyup', function () {
            console.log('Keyup catturato', this.value);
            const query = this.value.trim();
            serviceHandleSearch(query);
        });
    });
});

window.handleClientSearch = handleClientSearch;
window.handleServiceSearch = handleServiceSearch;
window.selectClient = selectClient;
window.selectService = selectService;
window.saveDraggedBlockPosition = saveDraggedBlockPosition;
window.revertToOldPosition = revertToOldPosition;
window.openAddClientModal = openAddClientModal;
window.commonPseudoBlockColor = null;
})();

// Funzione per rimuovere un blocco appuntamento
function deleteAppointment(appointmentId) {
    if (!appointmentId) {
        console.error("ID appuntamento mancante");
        return;
    }
    if (!confirm("Confermi di voler eliminare l'appuntamento?")) {
        return;
    }

    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    const csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : '';

    return fetch(`/calendar/delete/${encodeURIComponent(appointmentId)}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        credentials: 'same-origin'
    })
    .then(async response => {
        if (response.ok) {
            // server ha cancellato correttamente
            return { success: true };
        }

        // Se 404 => consideriamo già rimosso sul server (idempotenza)
        if (response.status === 404) {
            console.warn(`Delete returned 404 for ${appointmentId} — treating as deleted.`);
            return { success: true, _warning: 'not_found' };
        }

        // Altri errori: prova a leggere body per dettaglio
        let body = '';
        try { body = await response.text(); } catch(e) { body = `HTTP ${response.status}`; }
        throw new Error(body || `HTTP ${response.status}`);
    })
    .then(result => {
        // Rimuovi sempre il blocco dal DOM (idempotente client-side)
        const block = document.querySelector(`.appointment-block[data-appointment-id="${appointmentId}"]`);
        if (block) {
            // dispose tooltip se presente
            block.querySelectorAll('[data-bs-toggle="tooltip"], .delete-appointment-block').forEach(el => {
                try {
                    const t = bootstrap?.Tooltip?.getInstance(el);
                    if (t && typeof t.dispose === 'function') t.dispose();
                } catch (e) { /* ignore */ }
            });
            // rimuovi note legate
            const notePopup = document.querySelector(`.note-popup[data-appointment-id="${appointmentId}"]`);
            if (notePopup) notePopup.remove();
            // rimuovi l'elemento
            block.remove();
            // aggiorna layout cella
            const parentCell = block.__oldParent || block.parentNode;
            if (parentCell) arrangeBlocksInCell(parentCell);
        } else {
            console.debug(`deleteAppointment: no DOM block for id ${appointmentId}`);
        }

        // mostra eventuale messaggio solo per errori reali
        if (result && result.success === false) {
            alert(result.error || 'Errore durante l\'eliminazione');
        }

        // Reload solo in modalità touch
        const TOUCH_UI = (() => { try { return localStorage.getItem('sun_touch_ui') === '1'; } catch(_) { return false; } })();
        if (TOUCH_UI) {
            setTimeout(() => location.reload(), 80);
        }
    })
    .catch(err => {
        console.error("Errore deleteAppointment:", err);
        // Non rimuovere il blocco in caso di errore diverso da 404: lascia il DOM consistente e segnala
        // (se vuoi, puoi forzare la rimozione per 404 già gestita sopra)
        alert(err.message || 'Errore durante l\'eliminazione');
        throw err; // rethrow per possibilità di await dal chiamante
    });
}
window.deleteAppointment = deleteAppointment;

async function inviaWhatsappAutoSeRichiesto(appointment, data, csrfToken) {
  let numero = (appointment && appointment.client_cellulare) ? appointment.client_cellulare : "";
  if (!numero && data && data.client_id) {
    try {
      const resp = await fetch(`/settings/api/client_info/${encodeURIComponent(data.client_id)}`);
      const info = await resp.json();
      numero = info?.cliente_cellulare || "";
    } catch (_) {}
  }

function normalizeForWbiz(raw) {
    if (!raw) return '';
    let s = String(raw).trim();

    // 1. Gestione prefissi internazionali espliciti (+ o 00)
    // Se inizia con +, togliamo il + e teniamo il resto (pulito da non-numeri)
    if (s.startsWith('+')) {
        return s.substring(1).replace(/\D/g, '');
    }
    // Se inizia con 00, togliamo 00 e teniamo il resto
    if (s.startsWith('00')) {
        return s.substring(2).replace(/\D/g, '');
    }

    // 2. Se non c'è prefisso esplicito, puliamo la stringa
    const digits = s.replace(/\D/g, '');
    if (!digits) return '';

    // Altrimenti... assumiamo che sia un numero nazionale italiano
    return digits;
}

numero = normalizeForWbiz(numero);
if (!numero) {
  console.warn("Nessun numero cliente disponibile dopo normalizzazione, WhatsApp non inviato");
  return;
}

  const payload = {
    numero: numero,
    messaggio: "",
    nome: (appointment && appointment.client_name) || (data && data.client_name) || "",
    client_id: (appointment && appointment.client_id) || (data && data.client_id) || "",
    data: (data && data.data) || (appointment && appointment.appointment_date) || (data && (data.appointment_date || data.date)) || "",
    ora: (data && data.ora) || (appointment && appointment.start_time) || (data && data.start_time) || ""
  };
  if (data && data.appointment_id) payload.appointment_id = data.appointment_id;
  if (data && Array.isArray(data.appointment_ids) && data.appointment_ids.length > 0) payload.appointment_ids = data.appointment_ids;
  if (data && ((Array.isArray(data.servizi) && data.servizi.length > 0) || (typeof data.servizi === 'string' && data.servizi.trim()))) {
    payload.servizi = data.servizi;
  }

  try {
    const resp = await fetch('/calendar/send-whatsapp-auto', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      },
      credentials: 'same-origin',
      keepalive: true, // evita "Failed to fetch" su reload/unload
      body: JSON.stringify(payload)
    });

    if (!resp.ok) {
      const t = await resp.text().catch(() => '');
      console.warn('send-whatsapp-auto non OK:', resp.status, t);
      return;
    }

    const ct = (resp.headers.get('content-type') || '').toLowerCase();
    if (ct.includes('application/json')) {
      const resJson = await resp.json().catch(() => ({}));
      if (resJson && resJson.error) {
        console.warn('Errore invio WhatsApp (JSON):', resJson.error);
      }
    }
    // Se non JSON (204/empty/text/html) lo consideriamo OK
  } catch (err) {
    // Tipico se la pagina ricarica: non mostrare alert all’utente
    console.warn('send-whatsapp-auto fetch error (ignoro):', err);
  }
}

// COPIA
document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.appointment-block .popup-buttons .btn-popup.copia')
  .forEach(button => {
    button.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      e.stopImmediatePropagation();
      const tooltipEl = document.querySelector('.tooltip');
      if (tooltipEl) {
        tooltipEl.remove();
      }
      this.removeAttribute('data-bs-original-title');
      this.removeAttribute('aria-describedby');
      // Recupera il blocco corrente

      // DOPO: solo blocco singolo, no contiguous
      const block = this.closest('.appointment-block');
      if (!block) return;

      // Escludi blocchi OFF
      const isOff = !block.getAttribute('data-client-id') || !block.getAttribute('data-service-id');
      if (isOff) {
        alert("Non puoi copiare un blocco OFF nel Navigator.");
        return;
      }

      // Limite 15 elementi nel Navigator
      window.pseudoBlocks = window.pseudoBlocks || [];
      if (window.pseudoBlocks.length >= 15) {
        alert("Limite massimo di 15 elementi nel Navigator raggiunto.");
        return;
      }

      copyAsNewPseudoBlock(block);
    });
  });
});
  
// SPOSTA/TAGLIA
(function bindCutMoveButtons() {
  function isTouchUI() {
    try { return localStorage.getItem('sun_touch_ui') === '1' || document.body.classList.contains('touch-ui'); }
    catch (_) { return document.body.classList.contains('touch-ui'); }
  }

  function hideAppointmentTooltipsAndPopups() {
    // Nascondi immediatamente i tooltip info (small e big)
    const small = document.getElementById('clientInfoPopup');
    if (small) { small.style.display = 'none'; }
    const big = document.getElementById('clientHistoryPopup');
    if (big) { big.style.display = 'none'; }

    // Chiudi eventuali popup Bootstrap residui
    document.querySelectorAll('.tooltip').forEach(t => { t.parentNode && t.parentNode.removeChild(t); });

    // Chiudi le barre popup e rimuovi active-popup (se disponibile la funzione globale di touch-ui)
    try { if (typeof window.closeAllPopups === 'function') window.closeAllPopups(); } catch (_) {}
  }

  function onCutClick(e) {
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();

    // In touch‑ui, chiudi subito qualsiasi tooltip/popup info
    if (isTouchUI()) hideAppointmentTooltipsAndPopups();

    // Rimuovi eventuale tooltip Bootstrap attaccato al pulsante
    const inst = (window.bootstrap && window.bootstrap.Tooltip) ? bootstrap.Tooltip.getInstance(this) : null;
    if (inst) { try { inst.dispose(); } catch(_) {} }
    this.removeAttribute('data-bs-original-title');
    this.removeAttribute('aria-describedby');

    // Rimuovi anche elementi tooltip residui dal DOM
    document.querySelectorAll('.tooltip').forEach(t => { t.parentNode && t.parentNode.removeChild(t); });

    // Recupera il blocco
    const block = this.closest('.appointment-block');
    if (!block) return;

    // Escludi blocchi OFF (senza client/service) come da logica esistente
    const isOff = !block.getAttribute('data-client-id') || !block.getAttribute('data-service-id');
    if (isOff) return;

    // Limite Navigator (15)
    window.pseudoBlocks = window.pseudoBlocks || [];
    if (window.pseudoBlocks.length >= 15) {
      alert('Hai già 15 elementi nel Navigator. Incolla o svuota prima di continuare.');
      return;
    }

    // Esegui operazione di taglio
    cutAsNewPseudoBlock(block);
  }

  // Bind diretto ai bottoni già presenti (.sposta e .taglia, se presente)
  document.querySelectorAll('.appointment-block .popup-buttons .btn-popup.sposta, .appointment-block .popup-buttons .btn-popup.taglia')
    .forEach(btn => {
      if (!btn._cutBound) {
        btn.addEventListener('click', onCutClick);
        btn._cutBound = true;
      }
    });

  // Delegato di sicurezza per elementi aggiunti dinamicamente
  document.addEventListener('click', function(e) {
    const btn = e.target.closest('.appointment-block .popup-buttons .btn-popup.sposta, .appointment-block .popup-buttons .btn-popup.taglia');
    if (!btn || btn._cutBoundDelegated) return;
    btn._cutBoundDelegated = true;
    onCutClick.call(btn, e);
  }, true);
})();

document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.btn-popup.pagamento').forEach(button => {
  button.addEventListener('click', function(e) {
    e.stopPropagation();
      const block = button.closest('.appointment-block');
      if (!block) return;

      // helper decodifica (fallback)
      const decodeHtml = (s) => { const t = document.createElement('textarea'); t.innerHTML = String(s || ''); return t.value; };

      const clientId = block.getAttribute('data-client-id');
      const operatorId = block.getAttribute('data-operator-id');
      const operatorName = button.closest('.appointment-block').closest('td').getAttribute('data-operator-name') || '';

      // PRIMA SCELTA: testo visibile nel blocco (già decodificato)
      const nameEl = block.querySelector('.appointment-content .client-name');
      const rawName = nameEl ? nameEl.textContent.trim() : '';
      // FALLBACK: data-* decodificati
      const clientNome = decodeHtml(block.getAttribute('data-client-nome') || '');
      const clientCognome = decodeHtml(block.getAttribute('data-client-cognome') || '');
      const clientName = rawName || `${clientNome} ${clientCognome}`.trim();

    // --- includi anche blocchi sovrapposti nella stessa cella con lo stesso cliente ---
    const cell = block.closest('.selectable-cell');
    let blocksInCell = [];
    if (cell) {
      blocksInCell = Array.from(cell.querySelectorAll('.appointment-block'))
        .filter(b => {
          // Confronta per clientId e per nome+cognome
          const bClientId = b.getAttribute('data-client-id');
          const bNome = b.getAttribute('data-client-nome');
          const bCognome = b.getAttribute('data-client-cognome');
          const bClientName = `${bNome || ''} ${bCognome || ''}`.trim();
          return (
            (bClientId && bClientId === clientId) ||
            (bClientName && bClientName === clientName)
          );
        });
    }

    // Unisci con i blocchi contigui classici
    const contiguousBlocks = getRelevantBlocks(block);
    const allBlocks = Array.from(new Set([...blocksInCell, ...contiguousBlocks]));

    // ESCLUDI I BLOCCI IN STATO 2 (già pagati)
    const servizi = allBlocks
      .filter(b => b.getAttribute('data-status') !== "2")
      .map(b => ({
        id: b.getAttribute('data-service-id'),
        appointment_id: b.getAttribute('data-appointment-id')
      }));

    // Costruisci la query string
      const params = new URLSearchParams();
      params.set('client_id', clientId);
      params.set('client_name', clientName);
      params.set('operator_id', operatorId);
      params.set('servizi', JSON.stringify(servizi));
      params.set('operator_name', operatorName);

    window.location.href = `/cassa?${params.toString()}`;
  });
});

    // Aggiunge l'event listener per il pulsante "nota" nei popup dei blocchi appuntamento
    document.querySelectorAll('.appointment-block .popup-buttons .btn-popup.nota').forEach(button => {
        button.addEventListener('click', function(e) {
            e.stopPropagation(); // Impedisce la propagazione del click
            const block = this.closest('.appointment-block');
            openNoteModal(block);
        });
    });

    // Aggiunge l'event listener per il pulsante "aggiungi-servizi" nei popup dei blocchi appuntamento
    document.querySelectorAll('.appointment-block .popup-buttons .btn-popup.aggiungi-servizi').forEach(button => {
        button.addEventListener('click', function(e) {
            e.stopPropagation(); // Impedisce la propagazione del click
            const block = this.closest('.appointment-block');
            openAddServicesModal(block);
        });
    });
});

document.addEventListener('DOMContentLoaded', function() {
  // In modalità touch non registriamo comportamenti hover
  const TOUCH_UI = (() => {
    try { return localStorage.getItem('sun_touch_ui') === '1'; }
    catch (_) { return false; }
  })();

  if (TOUCH_UI) {
    // Pulisci eventuali display inline residui impostati da altri handler
    document.querySelectorAll('.appointment-block .popup-buttons, .appointment-block .popup-buttons-bottom')
      .forEach(el => { el.style.display = ''; });
    return; // gestito da touch-ui.js via click (.active-popup)
  }

  // Desktop: hover apre/chiude i popup
  document.querySelectorAll('.appointment-block').forEach(block => {
    block.addEventListener('mouseenter', function() {
      if (block.hidePopupTimeout) {
        clearTimeout(block.hidePopupTimeout);
        block.hidePopupTimeout = null;
      }
      block.classList.add('active-popup');
    });
    block.addEventListener('mouseleave', function() {
      block.hidePopupTimeout = setTimeout(() => {
        block.classList.remove('active-popup');
        block.hidePopupTimeout = null;
      }, 200);
    });
  });

  document.querySelectorAll('.popup-buttons').forEach(popup => {
    popup.addEventListener('mouseenter', function() {
      const block = this.closest('.appointment-block');
      if (block.hidePopupTimeout) {
        clearTimeout(block.hidePopupTimeout);
        block.hidePopupTimeout = null;
      }
      block.classList.add('active-popup');
    });
    popup.addEventListener('mouseleave', function() {
      const block = this.closest('.appointment-block');
      block.hidePopupTimeout = setTimeout(() => {
        block.classList.remove('active-popup');
        block.hidePopupTimeout = null;
      }, 200);
    });
  });

  // Draggable solo desktop
  document.querySelectorAll('.appointment-block').forEach(block => {
    block.addEventListener('dragstart', function() { this.classList.add('dragging'); });
    block.addEventListener('dragend',   function() { this.classList.remove('dragging'); });
  });
});

document.addEventListener('DOMContentLoaded', function() {
  var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  const IS_TOUCH = (() => { try { return localStorage.getItem('sun_touch_ui') === '1'; } catch(_) { return false; } })();

  tooltipTriggerList.forEach(function(el) {
    // 1) Blocca SEMPRE (modalità default) i tooltip dei pulsanti dentro .popup-buttons
    if (!IS_TOUCH && el.closest('.popup-buttons')) {
      // Rimuove attributo per prevenire nuova inizializzazione
      el.removeAttribute('data-bs-toggle');
      el.setAttribute('data-tooltip-blocked', '1');
      return; // NON creare il tooltip
    }

    // 2) Inizializzazioni consentite
    if (el.closest('.client-name')) {
      new bootstrap.Tooltip(el, {
        placement: 'bottom',
        container: 'body',
        boundary: 'window'
      });
    } else if (el.classList.contains('my-spia') || el.classList.contains('no-show-button')) {
      new bootstrap.Tooltip(el, {
        placement: 'right',
        fallbackPlacements: ['left'],
        container: 'body',
        boundary: 'window'
      });
    } else if (el.classList.contains('whatsapp-btn')) {
      new bootstrap.Tooltip(el, {
        placement: 'top',
        container: 'body',
        boundary: 'window',
        fallbackPlacements: [],
        offset: [-46, 14]
      });
    } else {
      new bootstrap.Tooltip(el, { container: 'body' });
    }

    // 3) Logica pre‑esistente per il nome cliente (mantieni)
    if (el.closest('.client-name') && !IS_TOUCH) {
      el.addEventListener('mouseover', function() {
        const block = this.closest('.appointment-block');
        if (!block) return;
        const popupDiv = block.querySelector('.popup-buttons');
        if (popupDiv) popupDiv.style.display = 'none';
      });
      el.addEventListener('mouseout', function() {
        const block = this.closest('.appointment-block');
        if (!block) return;
        const popupDiv = block.querySelector('.popup-buttons');
        if (popupDiv) popupDiv.style.display = 'block';
      });
    }
  });
});

document.addEventListener('show.bs.tooltip', function(ev) {
  try {
    const trg = ev.target;
    const IS_TOUCH = document.body.classList.contains('touch-ui') ||
                     (localStorage.getItem('sun_touch_ui') === '1');
    if (!IS_TOUCH && trg.closest('.popup-buttons')) {
      // Annulla apertura del tooltip della top bar in modalità default
      ev.preventDefault();
      const inst = bootstrap.Tooltip.getInstance(trg);
      if (inst) inst.disable();
    }
  } catch(_) {}
}, true);

function openNoteModal(block) {
  const appointmentId = block.getAttribute('data-appointment-id') || "";
  const modalEl = document.getElementById('EditApptNoteModal');
  if (!modalEl) {
      console.error("Modal 'EditApptNoteModal' non trovato.");
      return;
  }
  modalEl.setAttribute('data-appointment-id', appointmentId);

  const existingNote = block.getAttribute('data-note') || '';
  const noteTextarea = modalEl.querySelector('#apptNote');
  if (!noteTextarea) {
      console.error("Textarea per la nota (#apptNote) non trovato.");
      return;
  }
  noteTextarea.value = existingNote;

  const bsModal = new bootstrap.Modal(modalEl);
  bsModal.show();
  console.log("Modal aperto");
}

document.addEventListener('DOMContentLoaded', function() {
    // Aggiunge l'event listener per il pulsante "nota" nei popup dei blocchi appuntamento
    document.querySelectorAll('.appointment-block .popup-buttons .btn-popup.nota').forEach(button => {
        button.addEventListener('click', function(e) {
            e.stopPropagation(); // Impedisce la propagazione del click
            const block = this.closest('.appointment-block');
            openNoteModal(block);
        });
    });
});

document.addEventListener('DOMContentLoaded', function () {
    var noteTooltipList = [].slice.call(document.querySelectorAll('.appt-note')); 
    noteTooltipList.forEach(function (tooltipTriggerEl) {
        new bootstrap.Tooltip(tooltipTriggerEl);
    });
});

document.addEventListener('DOMContentLoaded', function() {
    const saveNoteBtn = document.getElementById('saveNoteBtn');
    if (!saveNoteBtn) {
        console.error('Elemento saveNoteBtn non trovato');
        return;
    }
    saveNoteBtn.addEventListener('click', function() {
        const noteText = document.getElementById('apptNote').value;
        const modalEl = document.getElementById('EditApptNoteModal');
        const appointmentId = modalEl.getAttribute('data-appointment-id');
        console.log('Salva nota - appointmentId:', appointmentId, 'noteText:', noteText);
        
        const csrfMeta = document.querySelector('meta[name="csrf-token"]');
        if (!csrfMeta) {
            console.error('Meta tag CSRF non trovato');
            alert('Errore: CSRF token non trovato');
            return;
        }
        const csrfToken = csrfMeta.getAttribute('content');

        fetch(`/calendar/update_note/${appointmentId}`, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({ note: noteText })
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => { 
                    throw new Error(err.error || "Errore nel salvataggio della nota"); 
                });
            }
            return response.json();
        })
.then(data => {
    console.log('Nota salvata:', data);
    const bsModal = bootstrap.Modal.getInstance(modalEl);
    if (bsModal) {
        bsModal.hide();
    }

    // Aggiorna subito dataset + tooltip
    try { window.onAppointmentNoteSaved(appointmentId, noteText); } catch (_) {}

    // Se il blocco è in stato 2, evita il reload e lascia la UI aggiornata
    const block = document.querySelector(`.appointment-block[data-appointment-id="${appointmentId}"]`);
    const isStatus2 = block && String(block.getAttribute('data-status')) === '2';
    if (!isStatus2) {
        location.reload();
    }
})
        .catch(error => {
            console.error("Errore nel salvataggio della nota:", error);
            alert(error.message);
        });
    });
});

document.addEventListener("DOMContentLoaded", function() {
    var dateInput = document.getElementById('date');
    var dayOfWeekSpan = document.getElementById('dayOfWeek');

    function updateDayOfWeek() {
        if (dateInput.value) {
            var date = new Date(dateInput.value);
            var weekdayNames = ["DOM", "LUN", "MAR", "MER", "GIO", "VEN", "SAB"];
            dayOfWeekSpan.innerText = weekdayNames[date.getDay()];
        }
    }

    // Aggiorna il giorno della settimana al caricamento della pagina
    updateDayOfWeek();

    // Al cambio della data, aggiorna il giorno della settimana e reindirizza
    dateInput.addEventListener('change', function() {
        updateDayOfWeek();
        // Redirect alla pagina del calendario con la nuova data
        window.location.href = calendarHomeUrl + "?date=" + dateInput.value;
    });
});

document.addEventListener("DOMContentLoaded", function() {
    var dateInput = document.getElementById('date');
    var dayOfWeekSpan = document.getElementById('dayOfWeek');

    function updateDayOfWeek() {
        if (dateInput.value) {
            var date = new Date(dateInput.value);
            var weekdayNames = ["DOM", "LUN", "MAR", "MER", "GIO", "VEN", "SAB"];
            dayOfWeekSpan.innerText = weekdayNames[date.getDay()];
        }
    }

    // Aggiorna il giorno della settimana al caricamento della pagina
    updateDayOfWeek();
    // Aggiorna al cambio della data
    dateInput.addEventListener('change', updateDayOfWeek);
});

function changeAppointmentColor(block) {
  if (!block) return;

  var newColor = prompt("Inserisci il colore (codice HEX, es. #FF5733):", block.getAttribute("data-colore") || "#FFFFFF");
  if (newColor) {
      const appointmentId = block.getAttribute("data-appointment-id");
      const clientId = block.getAttribute('data-client-id');

      const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

      candidateBlocks.forEach(candidateBlock => {
          candidateBlock.style.backgroundColor = newColor;
          candidateBlock.setAttribute("data-colore", newColor);
          const fontColor = computeFontColor(newColor);
          candidateBlock.style.color = fontColor;
          candidateBlock.setAttribute("data-colore_font", fontColor);

          const content = candidateBlock.querySelector('.appointment-content');
          if (content) {
              content.style.color = fontColor;
              content.querySelectorAll('a').forEach(a => {
                  a.style.color = fontColor;
              });
          }

          const candidateAppointmentId = candidateBlock.getAttribute("data-appointment-id");
          fetch(`/calendar/update_color/${candidateAppointmentId}`, {
              method: "POST",
              headers: {
                  "Content-Type": "application/json",
                  "X-CSRFToken": csrfToken
              },
              body: JSON.stringify({ colore: newColor, colore_font: fontColor })
          })
          .then(response => {
              if (!response.ok) throw new Error("Errore nell'aggiornamento del colore");
              console.log("Colore aggiornato per appuntamento", candidateAppointmentId);
          })
          .catch(err => console.error(err));

          // Attiva la propagazione ai blocchi contigui immediati
          propagateColorToContiguousBlocks(candidateBlock);
      });
  }
}
  
  document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.btn-popup.colore').forEach(function(button) {
      button.addEventListener('click', function(e) {
        e.stopPropagation();
        const block = this.closest('.appointment-block');
        changeAppointmentColor(block);
      });
    });
  });
  
  // Applica il colore del font a tutti i blocchi appuntamento
  document.addEventListener("DOMContentLoaded", function() {
    document.querySelectorAll('.appointment-block').forEach(function(block) {
      var bgColor = block.getAttribute("data-colore") || "#ffffff";
      block.style.color = computeFontColor(bgColor);
    });
  });

// Variabile globale per tenere traccia del blocco appuntamento corrente per il colore
let currentColorBlock = null;

// Funzione per calcolare il colore del font in base al background (se il background è scuro, il font diventa bianco, altrimenti nero)
function computeFontColor(hex) {
    hex = hex.replace('#', '');
    if (hex.length === 3) {
        hex = hex.split('').map(c => c + c).join('');
    }
    const r = parseInt(hex.substring(0, 2), 16);
    const g = parseInt(hex.substring(2, 4), 16);
    const b = parseInt(hex.substring(4, 6), 16);
    const brightness = (r * 299 + g * 587 + b * 114) / 1000;
    return brightness > 204 ? "rgba(0, 0, 0, 0.7)" : "#ffffff";
}

// Funzione per aprire il modal per la selezione del colore
function openColorPickerModal(appointmentBlock) {
    currentColorBlock = appointmentBlock;
    // Imposta l'input per il colore di sfondo
    const currentBgColor = appointmentBlock.getAttribute('data-colore') || '#ffffff';
    document.getElementById('colorPickerInput').value = currentBgColor;
    
    // Verifica se il blocco ha già un colore del font memorizzato
    let storedFontColor = appointmentBlock.getAttribute('data-colore_font');
    // Se non è memorizzato, calcola il colore del font
    if (!storedFontColor) {
        storedFontColor = computeFontColor(currentBgColor);
    }
    // (Se avevi un display per il font, aggiornalo qui, altrimenti puoi rimuovere questo blocco)
    // Ad esempio, se esiste un elemento con id "computedFontColor":
    const computedFontElem = document.getElementById('computedFontColor');
    if (computedFontElem) {
        computedFontElem.innerText = storedFontColor;
    }
    
    // Apri il modal
    const colorPickerModal = new bootstrap.Modal(document.getElementById('ColorPickerModal'));
    colorPickerModal.show();
    
    // Focalizza il selettore del background
    setTimeout(() => {
      const bgInput = document.getElementById('colorPickerInput');
      bgInput.click();
      bgInput.blur();
    }, 500);
}

// Listener per il bottone "OK" del modal
document.addEventListener('DOMContentLoaded', function() {
  const saveColorBtn = document.getElementById('saveColorBtn');
  saveColorBtn.addEventListener('click', function() {
      const newBgColor = document.getElementById('colorPickerInput').value;
      // Calcola automaticamente il colore del font in base al background
      const newFontColor = computeFontColor(newBgColor);
      if (currentColorBlock) {
          // Ottieni l'ID del cliente dal blocco corrente
          const clientId = currentColorBlock.getAttribute('data-client-id');
        const sessionId = currentColorBlock.getAttribute('data-booking_session_id');
      const isBooking = (currentColorBlock.getAttribute('data-source') === 'web' || !!sessionId);

            const selector = isBooking && sessionId ? `[data-booking_session_id="${sessionId}"]` : `[data-client-id="${clientId}"]`;
      const candidateBlocks = Array.from(document.querySelectorAll(`.appointment-block${selector}`));

          // Aggiorna il colore di tutti i blocchi candidati
          candidateBlocks.forEach(candidateBlock => {
              candidateBlock.setAttribute('data-colore', newBgColor);
              candidateBlock.style.backgroundColor = newBgColor;
              candidateBlock.setAttribute('data-colore_font', newFontColor);
              candidateBlock.style.setProperty('color', newFontColor, 'important');

              // Aggiorna anche il colore del testo all'interno del blocco
              const content = candidateBlock.querySelector('.appointment-content');
              if (content) {
                  content.style.setProperty('color', newFontColor, 'important');
                  content.querySelectorAll('a').forEach(a => {
                      a.style.setProperty('color', newFontColor, 'important');
                  });
              }

    const deleteIcon = candidateBlock.querySelector('.delete-appointment-block i');
    if (deleteIcon) {
        deleteIcon.style.color = newFontColor;
    }

              // Invia la richiesta al backend per salvare i colori
              const appointmentId = candidateBlock.getAttribute('data-appointment-id');
              const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
              fetch(`/calendar/update_color/${appointmentId}`, {
                  method: "POST",
                  headers: {
                      "Content-Type": "application/json",
                      "X-CSRFToken": csrfToken
                  },
                  body: JSON.stringify({ colore: newBgColor, colore_font: newFontColor })
              })
              .then(response => {
                  if (!response.ok) throw new Error("Errore nell'aggiornamento dei colori");
                  console.log("Colori aggiornati per appuntamento", appointmentId);
              })
              .catch(err => console.error(err));
          });
      }
      // Nascondi il modal
      const modalEl = document.getElementById('ColorPickerModal');
      const colorPickerModal = bootstrap.Modal.getInstance(modalEl);
      if (colorPickerModal) {
          colorPickerModal.hide();
      }
  });
});

// Listener delegato per il pulsante colore: quando cliccato, apri il modal per il relativo blocco appuntamento
document.addEventListener('click', function(e) {
    const colorBtn = e.target.closest('.btn-popup.colore');
    if (colorBtn) {
        e.stopPropagation();
        const appointmentBlock = colorBtn.closest('.appointment-block');
        if (appointmentBlock) {
            openColorPickerModal(appointmentBlock);
        }
    }
}, true);

document.addEventListener("DOMContentLoaded", function() {
    document.querySelectorAll('.appointment-block').forEach(function(block) {
        const bgColor = block.getAttribute("data-colore") || "#ffffff";
        const fontColor = block.getAttribute("data-colore_font") || computeFontColor(bgColor);

        block.style.color = fontColor;

        const content = block.querySelector('.appointment-content');
        if (content) {
            content.style.color = fontColor;
            content.querySelectorAll('a').forEach(a => {
                a.style.color = fontColor;
            });
        }
    });
});

function computeFontColor(hexColor) {
    if (!hexColor) return "black";
    hexColor = hexColor.replace("#", "");
    if (hexColor.length < 6) return "black";

    const r = parseInt(hexColor.substring(0, 2), 16);
    const g = parseInt(hexColor.substring(2, 4), 16);
    const b = parseInt(hexColor.substring(4, 6), 16);

    const brightness = (r * 299 + g * 587 + b * 114) / 1000;
    return brightness > 204 ? "rgba(0, 0, 0, 0.7)" : "#ffffff";
}

function removePseudoBlock(index) {
  window.pseudoBlocks.splice(index, 1);
  renderPseudoBlocksList();
  saveNavigatorState();
  
  // Se non ci sono più pseudoblocchi, chiama clearNavigator()
  if (!window.pseudoBlocks || window.pseudoBlocks.length === 0) {
    // Qui possiamo chiamare clearNavigator() in modo sicuro
    // perché abbiamo già rimosso tutti i pseudoblocchi
    const clientSearchInputNav = document.getElementById('clientSearchInputNav');
    if (clientSearchInputNav) {
        clientSearchInputNav.value = "";
    }

    const serviceInputNav = document.getElementById('serviceInputNav');
    if (serviceInputNav) {
        serviceInputNav.value = "";
    }

    window.selectedClientIdNav = null;
    window.selectedClientNameNav = "";
  }
}

  function selectClientNav(clientId, fullName) {
    window.selectedClientIdNav = clientId;
    window.selectedClientNameNav = fullName;
    
    // chiudi dropdown
    const input = document.getElementById('clientSearchInputNav');
    const resultsContainer = document.getElementById('clientResultsNav');
    input.value = fullName;
    resultsContainer.style.display = 'none';
  
    saveNavigatorState();

    // Se esiste una logica di caricamento servizi, continua:
    loadLastServicesForClient(clientId);
  
    // Aggiorna (o crea) il pseudo-blocco se c’è già anche un service
    maybeShowPseudoBlock();
  }
  
function selectServiceNav(serviceId, serviceName, serviceDuration, serviceTag) {
  console.log("DEBUG: selectServiceNav called with serviceId:", serviceId);
  console.log("DEBUG: window.addServiceStatus at start:", window.addServiceStatus);
  if (!selectedClientIdNav) {
      alert("Seleziona prima un cliente");
      return;
  }
  const dur = parseInt(serviceDuration, 10) || 15;

  // Colore: prima quello del blocco sorgente (openAddServicesModal), poi quello comune; fallback random
  const color =
    window.originBlockColor ||
    window.commonPseudoBlockColor ||
    (window.pseudoBlocks[0] && window.pseudoBlocks[0].color) ||
    getRandomColor();

  // Calcola il font color dal background
  const fontColor = computeFontColor(color);

  // Assicurati che lo stato sia ereditato dal blocco originario (se addServiceStatus è definito)
  const inheritedStatus = window.addServiceStatus !== undefined ? window.addServiceStatus : 0;
  console.log("DEBUG: inheritedStatus calculated:", inheritedStatus);
  console.log("DEBUG: pseudoblock will have status:", inheritedStatus);

  // Aggiorna le variabili globali relative al servizio
  selectedServiceIdNav = serviceId;
  selectedServiceNameNav = serviceName;
  selectedServiceDurationNav = dur;

  // Aggiunge al vettore dei pseudo-blocchi anche il fontColor
  window.pseudoBlocks.push({
      clientId: selectedClientIdNav,
      clientName: selectedClientNameNav,
      serviceId: serviceId,
      serviceName: serviceName,
      tag: serviceTag,
      duration: dur,
      color: color,
      fontColor: fontColor,
      note: "",
      status: inheritedStatus
  });

  // Imposta il colore comune se non già presente
  if (!window.commonPseudoBlockColor) {
    window.commonPseudoBlockColor = color;
  }
  console.log("PseudoBlocks dopo push:", window.pseudoBlocks);

  saveNavigatorState();

  // Pulizia input
  const inputEl = document.getElementById('serviceInputNav');
  inputEl.value = '';
  const resultsContainer = document.getElementById('serviceResultsNav');
  resultsContainer.innerHTML = '';
  resultsContainer.style.display = 'none';

  renderPseudoBlocksList();
}

function maybeShowPseudoBlock() {
    const container = document.getElementById('selectedServicesList');
    if (window.pseudoBlocks && window.pseudoBlocks.length > 0) {
        container.style.display = 'block';
    } else {
        container.style.display = 'none';
    }
}

function handleClientSearchNav(query) {
  const resultsContainer = document.getElementById('clientResultsNav');
  const input = document.getElementById('clientSearchInputNav');
  if (!resultsContainer || !input) return;

  const clearResults = () => {
    resultsContainer.style.display = 'none';
    while (resultsContainer.firstChild) resultsContainer.removeChild(resultsContainer.firstChild);
  };

  // Normalizza la query a minuscolo per consistenza
  query = (query || '').toString().toLowerCase().trim();

  if (!query || query.length < 3) {
    clearResults();
    return;
  }

  fetch(`/calendar/api/search-clients/${encodeURIComponent(query)}`)
    .then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    })
    .then(clients => {
      clearResults();

      const ensureOverlay = () => {
        const parent = input.parentElement || input.closest('div');
        if (parent && window.getComputedStyle(parent).position === 'static') parent.style.position = 'relative';
        resultsContainer.style.position = 'absolute';
        resultsContainer.style.left = input.offsetLeft + 'px';
        resultsContainer.style.top = (input.offsetTop + input.offsetHeight) + 'px';
        resultsContainer.style.width = '100%';
        resultsContainer.style.zIndex = '2000';
        resultsContainer.style.maxHeight = '240px';
        resultsContainer.style.overflowY = 'auto';
      };

      if (!Array.isArray(clients) || clients.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'dropdown-item';
        empty.textContent = 'Nessun risultato';
        resultsContainer.appendChild(empty);
        ensureOverlay();
        resultsContainer.style.display = 'block';
        return;
      }

      clients.forEach(client => {
        const id = String(client.id ?? '');
        const name = String(client.name ?? '');
        const phone = String(client.phone ?? '');

        const item = document.createElement('div');
        item.className = 'dropdown-item';
        item.style.display = 'flex';
        item.style.alignItems = 'center';
        item.style.gap = '8px';
        item.style.boxSizing = 'border-box';

        const txt = document.createElement('span');
        txt.className = 'dropdown-item-text';
        txt.style.flex = '1 1 auto';
        txt.style.overflow = 'hidden';
        txt.style.textOverflow = 'ellipsis';
        txt.style.whiteSpace = 'nowrap';
        txt.textContent = phone ? `${capitalizeName(name)} - ${phone}` : capitalizeName(name);
        item.appendChild(txt);

        item.dataset.clientId = id;
        item.dataset.clientName = name;

        const infoBtn = document.createElement('button');
        infoBtn.type = 'button';
        infoBtn.className = 'client-info-btn';
        infoBtn.setAttribute('aria-label', 'Info cliente');
        infoBtn.title = 'Info cliente';
        infoBtn.textContent = 'i';
        infoBtn.addEventListener('click', function (ev) {
          ev.stopPropagation();
          ev.preventDefault();
          try { showClientInfoModal(id); } catch (e) { console.error('showClientInfoModal error', e); }
        });
        item.appendChild(infoBtn);

        item.addEventListener('click', () => {
          try {
            if (typeof selectClientNav === 'function') selectClientNav(id, phone ? `${capitalizeName(name)} - ${phone}` : capitalizeName(name));
            else {
              const inputNav = document.getElementById('clientSearchInputNav');
              if (inputNav) inputNav.value = phone ? `${capitalizeName(name)} - ${phone}` : capitalizeName(name);
            }
          } finally {
            clearResults();
          }
        });

        resultsContainer.appendChild(item);
      });

      ensureOverlay();
      resultsContainer.style.display = 'block';
    })
    .catch(err => {
      console.error('handleClientSearchNav error:', err);
      clearResults();
    });
}

function handleServiceSearchNav(query) {
  const resultsContainer = document.getElementById('serviceResultsNav');

  if (query.length < 3) {
    // Mantieni i risultati esistenti visibili se già presenti (stessa logica attuale)
    if (resultsContainer.childElementCount > 0) {
      resultsContainer.style.display = 'block';
    }
    return;
  }

  fetch(`/calendar/api/search-services/${encodeURIComponent(query)}`)
    .then(r => r.json())
    .then(services => {
      // Svuota contenitore
      resultsContainer.innerHTML = '';

      if (!Array.isArray(services) || services.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'dropdown-item';
        empty.textContent = 'Nessun risultato';
        resultsContainer.appendChild(empty);
        resultsContainer.style.display = 'block';
        return;
      }

      services.forEach(service => {
        const item = document.createElement('div');
        item.className = 'dropdown-item';

        const id = String(service.id);
        const name = (service.name ?? '').toString();
        const duration = (service.duration ?? '').toString();
        const price = (service.price ?? '').toString();
        const tag = (service.tag ?? '').toString();

        // Testo puro
        item.textContent = duration
          ? `${name} - ${duration} min - €${price}`
          : `${name}${price ? ' - €' + price : ''}`;

        // Listener sicuro (niente onclick inline)
        item.addEventListener('click', () => {
          // Mantiene la firma esistente
          selectServiceNav(id, name, duration, tag);
        });

        resultsContainer.appendChild(item);
      });

      resultsContainer.style.display = 'block';
    })
    .catch(err => {
      console.error(err);
      // In caso di errore, non toccare l’eventuale risultato precedente
    });
}

  // Carica ultimi 10 servizi di un dato cliente, oppure i 10 più frequenti
  function loadLastServicesForClient(clientId) {
    fetch(`/calendar/api/last-services-for-client/${clientId}`)
      .then(resp => resp.json())
      .then(services => {
        if (!Array.isArray(services) || services.length === 0) {
          // Se l'endpoint non ritorna nulla, carichiamo i “frequent”
          return loadFrequentServices();
        } else {
          // Se abbiamo trovato qualcosa, mostriamolo
          showServicesDropdownNav(services);
        }
      })
      .catch(err => console.error("Errore last-services:", err));
  }
  
  // Popola il <select> con la lista di servizi
  function populateServiceSelectNav(services) {
    const selectEl = document.getElementById('serviceInputNav');
    // Svuota il select, lasciando solo l'option di default
  selectEl.innerHTML = '';
  const opt = new Option('Seleziona un servizio...', '', true, true);
  opt.disabled = true;
  selectEl.appendChild(opt);
    // Aggiungi i servizi
    services.forEach(sv => {
      const opt = document.createElement('option');
      opt.value = sv.id;
      opt.textContent = `${sv.name} (${sv.duration} min)`;
      opt.setAttribute('data-duration', sv.duration);
      selectEl.appendChild(opt);
    });
  }

  function loadFrequentServices() {
    // Esempio: endpoint /calendar/api/top-frequent-or-latest-services
    const cid = window.selectedClientIdNav;
    const url = cid ? `/calendar/api/last-services-for-client/${cid}` : '/calendar/api/top-frequent-or-latest-services';
    fetch(url)
      .then(resp => resp.json())
      .then(services => {
        showServicesDropdownNav(services);
      })
      .catch(err => console.error(err));
  }

// Helper: formatta la distanza giorni (oggi/ieri/N gg) normalizzando a mezzanotte locale
function formatDaysSince(lastDateStr) {
  if (!lastDateStr) return '';
  const MS_PER_DAY = 24 * 60 * 60 * 1000;
  const todayStart = new Date();
  todayStart.setHours(0, 0, 0, 0);
  // Gestisce ISO "YYYY-MM-DD" o "YYYY-MM-DDTHH:MM..."
  const isoDate = String(lastDateStr).split('T')[0];
  const parts = isoDate.split('-');
  const lastStart = parts.length === 3 ? new Date(+parts[0], +parts[1] - 1, +parts[2]) : new Date(isoDate);
  lastStart.setHours(0, 0, 0, 0);

  const diffDays = Math.round((todayStart - lastStart) / MS_PER_DAY);
  if (diffDays === 0) return ' • oggi';
  if (diffDays === 1) return ' • ieri';
  if (diffDays > 1) return ` • ${String(diffDays).padStart(3, ' ')} gg`;
  return ''; // con filtro backend <= oggi non dovresti avere negativi
}
  
  // showServicesDropdownNav: scrive i risultati nel contenitore e li rende cliccabili
function showServicesDropdownNav(services) {
  const resultsContainer = document.getElementById('serviceResultsNav');
  if (!resultsContainer) return;
  resultsContainer.innerHTML = '';

  if (!Array.isArray(services) || services.length === 0) {
    const noResult = document.createElement('div');
    noResult.className = 'dropdown-item';
    noResult.textContent = 'Nessun risultato';
    resultsContainer.appendChild(noResult);
    resultsContainer.style.display = 'block';
    return;
  }

  const filteredServices = services.filter(sv => sv && sv.id && sv.name && sv.name.toLowerCase() !== 'off');

  if (filteredServices.length === 0) {
    const noResult = document.createElement('div');
    noResult.className = 'dropdown-item';
    noResult.textContent = 'Nessun risultato';
    resultsContainer.appendChild(noResult);
    resultsContainer.style.display = 'block';
    return;
  }

  filteredServices.forEach(sv => {
    const item = document.createElement('div');
    item.className = 'dropdown-item';

    const id = String(sv.id ?? '');
    const name = String(sv.name ?? '');
    const duration = String(sv.duration ?? '');
    const tag = String(sv.tag ?? '');
    const daysText = formatDaysSince(sv.last_date);

    item.textContent = (duration ? `${name} - ${duration} min` : name) + daysText;
    item.dataset.serviceId = id;
    item.dataset.serviceName = name;
    item.dataset.serviceDuration = duration;
    item.dataset.serviceTag = tag;

    item.addEventListener('click', () => {
      // chiama la funzione esistente in modo sicuro
      if (typeof selectServiceNav === 'function') {
        selectServiceNav(id, name, duration, tag);
      } else if (typeof selectService === 'function') {
        selectService(id, name, duration);
      }
      // pulizia dropdown
      resultsContainer.innerHTML = '';
      resultsContainer.style.display = 'none';
    });

    resultsContainer.appendChild(item);
  });

  resultsContainer.style.display = 'block';
}
  
  // renderSelectedServicesList: mostra i servizi selezionati nell'apposito div
  function renderSelectedServicesList() {
    const container = document.getElementById('selectedServicesList');
    container.innerHTML = '';
    
    selectedServicesArray.forEach((sv, idx) => {
      // Creo un container per la singola voce
      const row = document.createElement('div');
      row.style.display = 'flex';
      row.style.alignItems = 'center';
      row.style.justifyContent = 'space-between';
      row.style.marginBottom = '5px';
      row.setAttribute('data-idx', idx);
  
      // Drag handle (fittizio, serve styling se vuoi drag&drop verticale)
      const dragHandle = document.createElement('div');
      dragHandle.textContent = '::';
      dragHandle.style.cursor = 'grab';
      dragHandle.style.marginRight = '8px';
  
      // Nome servizio
      const nameSpan = document.createElement('span');
      nameSpan.textContent = sv.name;
  
      // Pulsante X
      const btnRemove = document.createElement('button');
      btnRemove.textContent = 'X';
      btnRemove.style.backgroundColor = 'transparent';
      btnRemove.style.border = 'none';
      btnRemove.style.color = 'red';
      btnRemove.style.cursor = 'pointer';
      btnRemove.addEventListener('click', () => {
        // Rimuovi da array e ri-render
        selectedServicesArray.splice(idx, 1);
        renderSelectedServicesList();
      });
  
      // Componi
      row.appendChild(dragHandle);
      row.appendChild(nameSpan);
      row.appendChild(btnRemove);
      container.appendChild(row);
    });
  }

function renderPseudoBlocksList() {
  const container = document.getElementById('selectedServicesList');
  if (!container) return;

  if (!Array.isArray(window.pseudoBlocks) || window.pseudoBlocks.length === 0) {
    container.style.display = 'none';
    // Rimuovi i dati dal localStorage
    localStorage.removeItem('selectedClientIdNav');
    localStorage.removeItem('selectedClientNameNav');
    localStorage.removeItem('pseudoBlocksData');
    // Nascondi il pulsante "Svuota"
    const clearNavigatorBtn = document.getElementById('clearNavigatorBtn');
    if (clearNavigatorBtn) clearNavigatorBtn.style.display = 'none';
    container.innerHTML = '';
    return;
  }

  if (!window.commonPseudoBlockColor && window.pseudoBlocks.length > 0) {
    window.commonPseudoBlockColor = window.pseudoBlocks[0].color;
  }
  const commonColor = window.commonPseudoBlockColor;

  // Svuota e ricostruisci via DOM (no innerHTML, no onclick inline)
  container.innerHTML = '';

  for (let i = 0; i < window.pseudoBlocks.length; i++) {
    const block = window.pseudoBlocks[i];
    if (!block.tag || !block.tag.trim()) {
      console.warn("ATTENZIONE: Il servizio selezionato non ha un tag definito (campo obbligatorio).", block);
    }

    const row = document.createElement('div');
    row.className = 'pseudo-block';
    row.dataset.index = String(i);
    if (block.note) row.setAttribute('data-note', String(block.note));

    // Stili inline identici all'HTML originale
    row.style.display = 'flex';
    row.style.justifyContent = 'space-between';
    row.style.alignItems = 'center';
    row.style.padding = '5px';
    row.style.border = `2px solid ${commonColor}`;
    row.style.marginBottom = '5px';

    // PATCH: Aggiungi listener per la selezione del pseudoblocco
    row.addEventListener('click', function(e) {
        e.stopPropagation();
        if (typeof handlePseudoBlockClick === 'function') {
            handlePseudoBlockClick(this);
        }
    });

    const left = document.createElement('div');

    // label (senza innerHTML)
    if (!block.clientId && !block.serviceId) {
      // BLOCCO OFF + anteprima nota
      const strong = document.createElement('strong');
      strong.textContent = 'BLOCCO OFF';
      left.appendChild(strong);

      if (block.note) {
        const preview = block.note.substring(0, 15) + (block.note.length > 15 ? '...' : '');
        if (preview) {
          left.appendChild(document.createTextNode(': ' + preview));
        }
      }
    } else {
      const strong = document.createElement('strong');
      strong.textContent = String(block.clientName || '');
      left.appendChild(strong);
      left.appendChild(document.createTextNode(' - '));
      const tagSpan = document.createElement('span');
      tagSpan.textContent = String(block.tag || '');
      left.appendChild(tagSpan);
    }

    const dur = document.createElement('span');
    dur.textContent = ` (${block.duration} min)`;
    left.appendChild(dur);

    // Pulsante rimozione (no onclick inline)
    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.textContent = 'X';
    removeBtn.style.marginRight = '15px';
    removeBtn.style.color = 'red';
    removeBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      if (typeof removePseudoBlock === 'function') {
        removePseudoBlock(i);
      }
    });

    row.appendChild(left);
    row.appendChild(removeBtn);

    container.appendChild(row);
  }

  container.style.display = 'block';

  // Mostra il pulsante "Svuota" se ci sono pseudoblocchi
  const clearNavigatorBtn = document.getElementById('clearNavigatorBtn');
  if (clearNavigatorBtn) {
    clearNavigatorBtn.style.display = 'inline-block';
  }
}

function getDragAfterElement(container, y) {
    const draggableElements = Array.from(container.querySelectorAll('.pseudo-block:not(.dragging)'));
    return draggableElements.reduce((closest, child) => {
        const box = child.getBoundingClientRect();
        const offset = y - box.top - box.height / 2;
        if (offset < 0 && offset > closest.offset) {
            return { offset, element: child };
        } else {
            return closest;
        }
    }, { offset: Number.NEGATIVE_INFINITY }).element;
}

function minutesToTime(minutes) {
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${("0" + hours).slice(-2)}:${("0" + mins).slice(-2)}`;
}

// Rimuove tutti gli highlight dalle celle calendario
function clearCalendarHighlights() {
  document
    .querySelectorAll('.selectable-cell.highlight, .selectable-cell.highlight-side')
    .forEach(c => { c.classList.remove('highlight'); c.classList.remove('highlight-side'); });
}
window.clearCalendarHighlights = clearCalendarHighlights;

function getRandomColor() {
    const letters = "0123456789ABCDEF";
    let color = "#";
    for (let i = 0; i < 6; i++) {
      color += letters[Math.floor(Math.random() * 16)];
    }
    return color;
  }

// Gestione backup "cut" dei blocchi: salva in localStorage per possibile restore
function _loadCutBlocks() {
  try {
    return JSON.parse(localStorage.getItem('cutBlocks') || '[]');
  } catch (e) {
    console.warn('cutBlocks parse error', e);
    return [];
  }
}
function _saveCutBlocks(arr) {
  try { localStorage.setItem('cutBlocks', JSON.stringify(arr)); } catch(e){ console.warn('save cutBlocks failed', e); }
}

// Salva backup del blocco tagliato (appende)
function saveCutBlockBackup(apptBackup) {
  const arr = _loadCutBlocks();
  arr.push(apptBackup);
  _saveCutBlocks(arr);
}

// Ricrea tutti i cutBlocks memorizzati (usato su "Svuota" o al load se necessario)
async function restoreCutBlocks() {
  const cutBlocks = _loadCutBlocks();
  if (!Array.isArray(cutBlocks) || cutBlocks.length === 0) return;
  const csrf = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
  const promises = cutBlocks.map(bkp => {
    // prepara payload compatibile con POST /calendar/create (singolo)
    const payload = {
      client_id: bkp.client_id ?? null,
      service_id: bkp.service_id ?? null,
      operator_id: bkp.operator_id ?? null,
      start_time: bkp.start_time_time || bkp.start_time || `${bkp.hour}:${bkp.minute}`,
      appointment_date: bkp.appointment_date || bkp.date,
      duration: bkp.duration || bkp._duration || bkp.duration_minutes,
      note: bkp.note || '',
      colore: bkp.colore || bkp.color || '',
      // opzionale: stato se disponibile
      status: (typeof bkp.status !== 'undefined') ? bkp.status : undefined
    };
    return fetch('/calendar/create', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        ...(csrf ? { 'X-CSRFToken': csrf } : {})
      },
      body: JSON.stringify(payload)
    }).then(async res => {
      if (!res.ok) {
        const t = await res.text().catch(()=>null);
        throw new Error(`restore failed ${res.status} ${t || ''}`);
      }
      return res.json();
    }).catch(err => {
      console.error('restoreCutBlocks: failed for', bkp, err);
      return { error: String(err) };
    });
  });

  await Promise.allSettled(promises);
  // Svuota il backup dopo tentativo di restore
  localStorage.removeItem('cutBlocks');
}

  // Inserisci questa funzione utility in alto nel file
function chiediInvioWhatsappNavigator() {
  return new Promise(resolve => {
    // Rimuovi eventuale popup precedente
    const existing = document.getElementById('whatsappNavigatorConfirm');
    if (existing) existing.remove();

    // Crea il popup
    const panel = document.createElement('div');
    panel.id = 'whatsappNavigatorConfirm';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-label', 'Conferma invio WhatsApp');
    panel.style.position = 'fixed';
    panel.style.top = '50%';
    panel.style.left = '50%';
    panel.style.transform = 'translate(-50%, -50%)';
    panel.style.background = '#fff';
    panel.style.boxShadow = '0 6px 18px rgba(0,0,0,0.12)';
    panel.style.border = '1px solid #ddd';
    panel.style.borderRadius = '8px';
    panel.style.zIndex = '99999';
    panel.style.padding = '24px';
    panel.style.minWidth = '320px';
    panel.style.maxWidth = '90vw';
    panel.style.fontSize = '16px';

    const txt = document.createElement('div');
    txt.style.marginBottom = '18px';
    txt.textContent = 'Vuoi inviare in automatico una conferma WhatsApp al cliente?';
    panel.appendChild(txt);

    const btnRow = document.createElement('div');
    btnRow.style.display = 'flex';
    btnRow.style.gap = '12px';
    btnRow.style.justifyContent = 'flex-end';

    const back = document.createElement('button');
    back.type = 'button';
    back.className = 'btn btn-link';
    back.textContent = 'INDIETRO';
    back.style.marginRight = 'auto';
    back.style.color = '#666';

    const no = document.createElement('button');
    no.type = 'button';
    no.className = 'btn btn-secondary';
    no.textContent = 'No, crea senza inviare';

    const yes = document.createElement('button');
    yes.type = 'button';
    yes.className = 'btn btn-success';
    yes.textContent = 'Sì, invia';

    btnRow.appendChild(back);
    btnRow.appendChild(no);
    btnRow.appendChild(yes);
    panel.appendChild(btnRow);

    document.body.appendChild(panel);
    setTimeout(() => yes.focus(), 50);

    function cleanup() {
      const p = document.getElementById('whatsappNavigatorConfirm');
      if (p && p.parentNode) p.parentNode.removeChild(p);
      document.removeEventListener('keydown', onKey);
    }
    function onKey(e) {
      if (e.key === 'Escape') {
        cleanup();
        resolve(false);
      }
    }
    document.addEventListener('keydown', onKey);

    yes.addEventListener('click', function() {
      cleanup();
      resolve(true);
    });
    no.addEventListener('click', function() {
      cleanup();
      resolve(false);
    });
    back.addEventListener('click', function(e) {
      e.stopPropagation();
      e.preventDefault();
      cleanup();
      resolve('back');
    });
  });
}

  document.querySelectorAll('.selectable-cell').forEach(cell => {
    cell.addEventListener('click', async function(e) {
      // Se il click proviene da popup/buttons o da un blocco, NON gestire il posizionamento da Navigator
      const t = e.target;
      if (t.closest('.btn-popup') || t.closest('.popup-buttons') || t.closest('.appointment-block')) {
        return;
      }

      // PATCH: Evita click multipli durante la creazione
      if (window.isCreatingAppointment) return;

      if (window.pseudoBlocks && window.pseudoBlocks.length > 0) {
        e.stopImmediatePropagation();
        e.preventDefault();
       // Disabilita subito gli highlight quando si piazzano pseudoblocchi
       if (typeof clearCalendarHighlights === 'function') clearCalendarHighlights();

        // Controllo specifico per cliente mancante
        if (window.pseudoBlocks.some(blk => !blk.clientId)) {
            alert("Seleziona o aggiungi un cliente!");
            return;
        }
        // Controllo per servizio mancante
        if (window.pseudoBlocks.some(blk => !blk.serviceId)) {
            alert("Parametri mancanti: assicurati di aver selezionato un servizio.");
            return;
        }

const blocksInCell = Array.from(cell.querySelectorAll('.appointment-block'));
const hasOffBlock = blocksInCell.some(b =>
  !b.getAttribute('data-client-id') || b.getAttribute('data-client-id') === "dummy" || b.classList.contains('note-off')
);
const hasAppointment = blocksInCell.some(b =>
  b.getAttribute('data-client-id') && b.getAttribute('data-client-id') !== "dummy" && !b.classList.contains('note-off')
);

if (
  (hasOffBlock && hasAppointment) ||
  (hasOffBlock && window.pseudoBlocks.some(blk => blk.clientId && blk.clientId !== "dummy")) ||
  (hasAppointment && window.pseudoBlocks.some(blk => !blk.clientId || blk.clientId === "dummy"))
) {
  alert("Non puoi sovrapporre un blocco OFF e un appuntamento nella stessa cella!");
  return;
}
if (blocksInCell.length >= 2) {
  alert("Non puoi inserire più di due appuntamenti nella stessa cella!");
  return;
}
            
            // PATCH: Blocca ulteriori click
            window.isCreatingAppointment = true;

            const operatorId = cell.getAttribute('data-operator-id');
            const hour = parseInt(cell.getAttribute('data-hour'), 10);
            const minute = parseInt(cell.getAttribute('data-minute'), 10);
            const date = cell.getAttribute('data-date') || window.selectedAppointmentDate || new Date().toISOString().slice(0,10);
            const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
            let startTimeInMin = hour * 60 + minute;
            if (!window.commonPseudoBlockColor && window.pseudoBlocks.length > 0) {
              window.commonPseudoBlockColor = window.pseudoBlocks[0].color;
            }
            const commonColor = window.commonPseudoBlockColor;
            
            // Se esiste un pseudo-blocco selezionato, crea solo quell'appuntamento
            if (selectedPseudoBlock) {
                const index = selectedPseudoBlock.getAttribute('data-index');
                const blk = window.pseudoBlocks[index];
                const startTimeStr = minutesToTime(startTimeInMin);
                const payload = {
                    client_id: blk.clientId,
                    service_id: blk.serviceId,
                    operator_id: operatorId,
                    appointment_date: date,
                    start_time: startTimeStr,
                    duration: blk.duration,
                    colore: commonColor,
                    note: blk.note || "",
                    status: blk.status || 0
                };

                

                fetch('/calendar/create', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
                    },
                    body: JSON.stringify(payload)
                })
                .then(resp => {
                    if (!resp.ok) {
                        return resp.json().then(err => {
                            throw new Error(err.error || "Errore creazione");
                        });
                    }
                    return resp.json();
                })
.then(async appointment => {
    console.log("Appuntamento creato per pseudo-blocco selezionato:", appointment);
    appointment.duration = appointment.duration || blk.duration;
    appointment.colore = appointment.colore || commonColor;
    appointment.colore_font = appointment.colore_font || computeFontColor(commonColor);
    appointment.note = appointment.note || blk.note || "";
    appointment.service_tag = appointment.service_tag || blk.tag || blk.serviceName;

    // Rimuovi subito il pseudoblocco consumato
    window.pseudoBlocks.splice(index, 1);
    if (selectedPseudoBlock) selectedPseudoBlock.classList.remove('selected');
    selectedPseudoBlock = null;
    renderPseudoBlocksList();
    if (typeof saveNavigatorState === 'function') { try { saveNavigatorState(); } catch(e) {} }

    // Crea il blocco nel calendario (solo una volta)
    const newBlock = createAppointmentBlockElement(appointment, operatorId, hour, minute);
    cell.appendChild(newBlock);
    arrangeBlocksInCell(cell);
    const noShowBtn = newBlock.querySelector('.no-show-button');
    if (noShowBtn) noShowBtn.style.display = 'none';

    // Assicura i campi (se la risposta non li riporta)
appointment.client_name = appointment.client_name || blk.clientName;
appointment.service_tag = appointment.service_tag || blk.tag || blk.serviceName;

// Inietta subito il contenuto (cliente + servizio) visibile prima del reload
(function injectImmediateContent() {
  const fontColor = '#FFFFFF'; // testo bianco richiesto
  let content = newBlock.querySelector('.appointment-content');
  if (!content) {
    content = document.createElement('div');
    content.className = 'appointment-content';
    newBlock.appendChild(content);
  }
  content.innerHTML = '';

  if (appointment.client_name) {
    const pClient = document.createElement('p');
    pClient.className = 'client-name';
    const a = document.createElement('a');
    a.href = '#';
    const apptId = Number(appointment.id) || null;
    a.textContent = String(appointment.client_name);
    a.style.color = fontColor;
    a.addEventListener('click', e => {
      e.preventDefault();
      if (apptId) openModifyPopup(apptId);
    });
    pClient.appendChild(a);
    content.appendChild(pClient);
  }

  if (appointment.service_tag) {
    const pService = document.createElement('p');
    const strong = document.createElement('strong');
    strong.textContent = String(appointment.service_tag);
    pService.appendChild(strong);
    pService.style.color = fontColor;
    content.appendChild(pService);
  }

  // Forza font bianco temporaneo senza cambiare il background esistente
  newBlock.style.color = fontColor;
  content.style.color = fontColor;
  content.querySelectorAll('a,strong').forEach(el => el.style.color = fontColor);
})();

    // Se restano pseudoblocchi: termina (niente WhatsApp, niente reload)
    if (window.pseudoBlocks.length > 0) {
        window.isCreatingAppointment = false; // PATCH: Sblocca il click per il prossimo blocco
        return;
    }

    // Ultimo pseudoblocco: chiedi WhatsApp e poi reload
    clearNavigator(false);
    const want = await chiediInvioWhatsappNavigator();
    if (want === true) {
        await inviaWhatsappAutoSeRichiesto(appointment, {
            client_id: blk.clientId,
            client_name: blk.clientName,
            data: date,
            ora: startTimeStr,
            servizi: blk.serviceName
        }, csrfToken);
        alert("Messaggio WhatsApp inviato!");
    }
    setTimeout(() => {
        if (window.lastClickPosition !== undefined && window.lastClickPosition !== null) {
            sessionStorage.setItem('lastClickPosition', window.lastClickPosition);
        }
        location.reload();
    }, 100);
  }).catch(err => {
      console.error(err);
      alert("Errore creazione: " + err.message);
      window.isCreatingAppointment = false; // PATCH: Sblocca click su errore
  });

            } else {
                // Se nessun pseudo-blocco è selezionato, esegue la creazione multipla (macro-blocco)
                const totalBlocks = window.pseudoBlocks.length;
                const totalDuration = window.pseudoBlocks.reduce((acc, b) => acc + b.duration, 0);
                const requests = window.pseudoBlocks.map(blk => {
                    const startTimeStr = minutesToTime(startTimeInMin);
                    startTimeInMin += blk.duration;
                    const payload = {
                        client_id: blk.clientId,
                        service_id: blk.serviceId,
                        operator_id: operatorId,
                        appointment_date: date,
                        start_time: startTimeStr,
                        duration: blk.duration,
                        colore: commonColor,
                        note: blk.note || "",
                        status: blk.status || 0
                    };
                    console.log("Invio pseudoblocchi:", window.pseudoBlocks);
                    return fetch('/calendar/create', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': csrfToken
                        },
                        body: JSON.stringify(payload)
                    })
                    .then(resp => {
                        if (!resp.ok) {
                            return resp.json().then(err => {
                                throw new Error(err.error || "Errore creazione multipla");
                            });
                        }
                        return resp.json();
                    });
                });
Promise.all(requests)
.then(async responses => {
  console.log("Appuntamenti creati dai pseudo-blocchi:", responses);

  const want = await chiediInvioWhatsappNavigator();
  if (want === true) {
    const servizi = window.pseudoBlocks.map(blk => blk.serviceName || blk.tag || "Servizio");
    const firstAppointment = responses[0];
    // Normalizza ora in formato HH:MM
    let oraMsg = '';
    if (typeof firstAppointment.start_time === 'string') {
      const m = firstAppointment.start_time.match(/(\d{2}:\d{2})/);
      oraMsg = m ? m[1] : '';
    }
    await inviaWhatsappAutoSeRichiesto(firstAppointment, {
      client_id: window.pseudoBlocks[0].clientId,
      client_name: window.pseudoBlocks[0].clientName,
      data: date,
      ora: oraMsg || (('0' + hour).slice(-2) + ':' + ('0' + minute).slice(-2)),
      servizi: servizi
    }, csrfToken);
    alert("Messaggio WhatsApp inviato!");
  }
    
    // Salva i dati dei pseudoBlocks prima di svuotare l'array
    const pseudoBlocksData = [...window.pseudoBlocks];
    console.log("pseudoBlocksData prima del ciclo:", pseudoBlocksData); // [1]
    window.pseudoBlocks = [];
    renderPseudoBlocksList();
    
    // Importante: salviamo la cella originale prima di modificarla
    const initialCell = cell;
    
    // Ordina le risposte in base all'orario di inizio
    responses.sort((a, b) => {
        const startTimeA = new Date(a.start_time).getTime();
        const startTimeB = new Date(b.start_time).getTime();
        return startTimeA - startTimeB;
    });

    // Per ogni risposta, troviamo la cella corretta in base all'orario restituito
    responses.forEach((appointment, index) => {
        console.log(`[${index}] Appuntamento start_time:`, appointment.start_time); // [2]
        // Ottieni l'ora e il minuto dall'orario di inizio dell'appuntamento
        const startTimeStr = appointment.start_time;
        // Converti in Date solo se è una stringa, altrimenti usa direttamente
        let appointmentHour, appointmentMinute;
        
        if (typeof startTimeStr === 'string') {
            // Se è una stringa nel formato "HH:MM" o contiene la data
            if (startTimeStr.includes('T') || startTimeStr.includes(' ')) {
                // Formato ISO o datetime standard
                const startTime = new Date(startTimeStr);
                appointmentHour = startTime.getHours();
                appointmentMinute = startTime.getMinutes();
            } else {
                // Formato "HH:MM"
                const parts = startTimeStr.split(':');
                appointmentHour = parseInt(parts[0], 10);
                appointmentMinute = parseInt(parts[1], 10);
            }
        } else {
            // Se per qualche motivo non è una stringa, usa l'ora della cella originale
            appointmentHour = parseInt(initialCell.getAttribute('data-hour'), 10);
            appointmentMinute = parseInt(initialCell.getAttribute('data-minute'), 10);
        }
        
        // Trova la cella corretta per questo appuntamento in base all'ora e ai minuti
        const targetCell = findCellAt(operatorId, appointmentHour, appointmentMinute);
        
        // IMPORTANTE: Forza il colore dal pseudo-blocco originale
        appointment.colore = commonColor;
        appointment.colore_font = computeFontColor(commonColor);
        
        // NUOVO: Abbina l'appuntamento con il suo pseudoblock originale utilizzando l'indice
        const originalPseudoBlock = pseudoBlocksData[index];
        if (originalPseudoBlock) {
            appointment.service_tag = originalPseudoBlock.tag || originalPseudoBlock.serviceName;
            appointment.service_name = originalPseudoBlock.serviceName;
            appointment.client_name = originalPseudoBlock.clientName;
        }
        
        if (targetCell) {
            // Crea il blocco con i dati corretti e aggiungilo alla cella appropriata
            const blockEl = createAppointmentBlockElement(appointment, operatorId, appointmentHour, appointmentMinute);
            console.log(`[${index}] Blocco creato:`, blockEl); // [3]
            
const blockColor = appointment.colore || commonColor;
const fontColor = appointment.colore_font || computeFontColor(blockColor);

blockEl.style.backgroundColor = blockColor;
blockEl.style.color = fontColor;
blockEl.setAttribute('data-colore', blockColor);
blockEl.setAttribute('data-colore_font', fontColor);
            
// Applica il colore anche al contenuto del blocco
const contentEl = blockEl.querySelector('.appointment-content');
if (contentEl) {
    contentEl.style.color = fontColor;
    const links = contentEl.querySelectorAll('a');
    links.forEach(link => link.style.color = fontColor);
                
// Sovrascriviamo immediatamente il contenuto HTML con i dati corretti senza iniezioni di html non sanificato
if (appointment.client_name && appointment.service_tag) {
    contentEl.innerHTML = '';

    const pClient = document.createElement('p');
    pClient.className = 'client-name';

    const a = document.createElement('a');
    a.href = '#';
    const apptId = Number(appointment.id) || null;
    a.addEventListener('click', function(e) {
      e.preventDefault();
      if (apptId) openModifyPopup(apptId);
    });
    a.style.color = computeFontColor(commonColor);
    a.textContent = String(appointment.client_name);

    pClient.appendChild(a);

    const pService = document.createElement('p');
    const strong = document.createElement('strong');
    strong.textContent = String(appointment.service_tag);
    pService.appendChild(strong);

    contentEl.appendChild(pClient);
    contentEl.appendChild(pService);
}
            }
            
            targetCell.appendChild(blockEl);
            // Organizza i blocchi nella cella dopo aver aggiunto quello nuovo
            arrangeBlocksInCell(targetCell);
            const noShowBtn = blockEl.querySelector('.no-show-button');
if (noShowBtn) noShowBtn.style.display = 'none';
        } else {
            console.warn(`Cella non trovata per orario ${appointmentHour}:${appointmentMinute}`);
            // Fallback: aggiunge comunque il blocco alla cella iniziale
            const blockEl = createAppointmentBlockElement(appointment, operatorId, appointmentHour, appointmentMinute);
            console.log(`[${index}] Blocco creato (fallback):`, blockEl); // [3]
            
            // Applica immediatamente i colori al blocco visivamente
            blockEl.style.backgroundColor = commonColor;
            blockEl.style.color = computeFontColor(commonColor);
            
            // Applica il colore anche al contenuto del blocco
            const contentEl = blockEl.querySelector('.appointment-content');
            if (contentEl) {
                contentEl.style.color = computeFontColor(commonColor);
                const links = contentEl.querySelectorAll('a');
                links.forEach(link => link.style.color = computeFontColor(commonColor));
                
                // NUOVO: Sovrascrive immediatamente il contenuto HTML con i dati corretti
if (appointment.client_name && appointment.service_tag) {
    contentEl.innerHTML = '';

    const pClient = document.createElement('p');
    pClient.className = 'client-name';

    const a = document.createElement('a');
    a.href = '#';
    const apptId = Number(appointment.id) || null;
    a.addEventListener('click', function(e) {
      e.preventDefault();
      if (apptId) openModifyPopup(apptId);
    });
    a.style.color = computeFontColor(commonColor);
    a.textContent = String(appointment.client_name);

    pClient.appendChild(a);

    const pService = document.createElement('p');
    const strong = document.createElement('strong');
    strong.textContent = String(appointment.service_tag);
    pService.appendChild(strong);

    contentEl.appendChild(pClient);
    contentEl.appendChild(pService);
}
            }
            
            initialCell.appendChild(blockEl);
            arrangeBlocksInCell(initialCell);
        }
    });
    
    // Svuota l'Appointment Navigator se non ci sono più pseudo-blocchi
    if (window.pseudoBlocks.length === 0) {
      clearNavigator(false);
  }

    // Aggiungiamo un reload ritardato per assicurarci che tutto venga visualizzato correttamente
    setTimeout(() => {
        location.reload();
    }, 500);
})
                .catch(err => {
                    console.error(err);
                    alert("Errore nella creazione multipla: " + err.message);
                    window.isCreatingAppointment = false;
                });
            }
        }
    }, true);
});

function createAppointmentBlockElement(appointment, operatorId, hour, minute) {
  const block = document.createElement('div');
  block.className = 'appointment-block';
  block.setAttribute('data-appointment-id', appointment.id);
  block.setAttribute('data-duration', appointment.duration);
  block.setAttribute('data-service-id', appointment.service_id);
  block.setAttribute('data-client-id', appointment.client_id);
  block.setAttribute('data-operator-id', operatorId);
  block.setAttribute('data-hour', hour);
  block.setAttribute('data-minute', minute);
  block.setAttribute('data-source', appointment.source || '');
  block.setAttribute('data-status', appointment.status || 0); 
  if (appointment.note) {
      block.setAttribute('data-note', appointment.note);
  }

  // PATCH: Salva il nome del servizio per recuperarlo correttamente nel Navigator (Cut/Paste)
  if (appointment.service_name) {
      block.setAttribute('data-service-name', appointment.service_name);
  }

  // --- LOGICA UNIFORME PER COLORE FONT SU SFONDI CHIARI ---
  let colore = appointment.colore;
  let coloreFont = appointment.colore_font;

if (colore) {
  coloreFont = computeFontColor(colore);
}

  block.setAttribute('data-colore', colore);
  block.setAttribute('data-colore_font', coloreFont);
  block.style.backgroundColor = colore || '';
  block.style.color = coloreFont;
  
  // Calcola l'altezza in base alla durata (ad es. 60 minuti = 4 quarter)
  const quarterHeight = getQuarterPx(); // Es. 60px per quarter
  const duration = parseInt(appointment.duration, 10) || 15;
  const heightPx = (duration / 15) * quarterHeight;
  block.style.height = `${heightPx}px`;
  
  // Posiziona il blocco in modo assoluto rispetto alla cella (la cella deve avere position: relative)
  block.style.position = 'absolute';
  block.style.left = '0px';
  block.style.top = '0px';
  
  // Imposta il colore di sfondo e il colore del font
  block.style.backgroundColor = appointment.colore || '';
  if (appointment.colore_font) {
      block.style.color = appointment.colore_font;
  }
  
  // Costruisci il contenuto del blocco
  const popupDiv = document.createElement('div');
  popupDiv.className = 'popup-buttons';
  block.appendChild(popupDiv);
  
  const dragHandle = document.createElement('div');
  dragHandle.className = 'drag-handle';
  block.appendChild(dragHandle);
  
  const contentDiv = document.createElement('div');
  contentDiv.className = 'appointment-content';
const isOffBlock = (
  !appointment.client_id || appointment.client_id === "dummy" || appointment.client_id == window.DUMMY_CLIENT_ID ||
  !appointment.service_id || appointment.service_id === "dummy" || appointment.service_id == window.DUMMY_SERVICE_ID
);

if (isOffBlock) {
  const p = document.createElement('p');
  p.style.textAlign = 'center';
  p.style.fontWeight = 'bold';
  p.style.fontSize = '18px';
  p.textContent = appointment.note || 'BLOCCO OFF';
  contentDiv.appendChild(p);
} else {
  // client name
  const pClient = document.createElement('p');
  pClient.className = 'client-name';
  if (appointment.client_name) {
    const a = document.createElement('a');
    a.href = '#';
    a.addEventListener('click', function(e){
      const TOUCH_UI = (() => { try { return localStorage.getItem('sun_touch_ui') === '1'; } catch(_) { return false; } })();
      if (TOUCH_UI) {
        const block = this.closest('.appointment-block');
        if (!block.classList.contains('active-popup')) {
          // do nothing, let block click handle
          return;
        }
      }
      e.preventDefault();
      openModifyPopup(appointment.id);
    });
    a.textContent = appointment.client_name;
    pClient.appendChild(a);
  }
  // service tag
  const pService = document.createElement('p');
  const strong = document.createElement('strong');
  strong.textContent = appointment.service_tag || appointment.servizio_tag || '';
  pService.appendChild(strong);

  contentDiv.appendChild(pClient);
  contentDiv.appendChild(pService);
}
  
  const spia = document.createElement('div');
  spia.className = 'my-spia';
  spia.setAttribute('title', 'cliente in istituto');
  block.appendChild(spia);
  
  const noShowBtn = document.createElement('button');
  noShowBtn.className = 'btn-popup no-show-button';
  noShowBtn.setAttribute('data-appointment-id', appointment.id);
  // crea l'icona in modo sicuro
  const xIcon = document.createElement('i');
  xIcon.className = 'bi bi-x';
  // svuota contenuto precedente e aggiungi l'icona
  noShowBtn.innerHTML = '';
  noShowBtn.appendChild(xIcon);
  block.appendChild(noShowBtn);

new bootstrap.Tooltip(noShowBtn, {
  placement: 'right',
  fallbackPlacements: ['left'],
  container: 'body',
  boundary: 'window'
});
  
  const resizeHandle = document.createElement('div');
  resizeHandle.className = 'resize-handle';
  block.appendChild(resizeHandle);
  
  if (!block.classList.contains('note-off')) {
    // Crea il pulsante cestino
    const bgColor = block.getAttribute('data-colore') || window.getComputedStyle(block).backgroundColor || '#fff';
    const iconColor = computeFontColor(bgColor);
    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'btn-popup delete-appointment-block';
    const delIcon = document.createElement('i');
    delIcon.className = 'bi bi-trash';
    delIcon.style.fontSize = '1.5em';
    delIcon.style.color = 'black';
    deleteBtn.innerHTML = '';
    deleteBtn.appendChild(delIcon);
    deleteBtn.style.position = 'absolute';
    deleteBtn.style.top = '4px';
    deleteBtn.style.left = '4px';
    deleteBtn.style.backgroundColor = 'transparent';

    // Gestione del click sul pulsante di elimina
    deleteBtn.addEventListener('click', function(e) {
        e.stopPropagation();
        const appointmentId = block.getAttribute('data-appointment-id');
        if (!appointmentId) return;
        deleteBtn.disabled = true;
        deleteAppointment(appointmentId)
          .then(() => {
            if (typeof fetchCalendarData === 'function') fetchCalendarData();
          })
          .catch(err => {
            console.error('Eliminazione fallita:', err);
            deleteBtn.disabled = false;
            alert('Eliminazione fallita: ' + (err.message || err));
          });
    });

    block.appendChild(deleteBtn);
}

  if (noShowBtn) {
    const blockHeight = block.offsetHeight || parseInt(block.style.height, 10) || 60;
    noShowBtn.style.height = `${blockHeight}px`;
    noShowBtn.style.lineHeight = `${blockHeight}px`;
    noShowBtn.style.fontSize = `${Math.max(16, Math.floor(blockHeight * 0.5))}px`;
    noShowBtn.style.display = 'flex';
    noShowBtn.style.alignItems = 'center';
    noShowBtn.style.justifyContent = 'center';
  }

  return block;
}


function updateAppointmentBlockStyles(block) {
  // Assumi che getQuarterPx() restituisca l'altezza di 15 minuti (ad esempio 60px)
  const QUARTER_PX = getQuarterPx();
  const duration = parseInt(block.getAttribute('data-duration'), 10) || 15;
  const heightPx = (duration / 15) * QUARTER_PX;
  block.style.height = `${heightPx}px`;
  
  // Imposta il colore di sfondo se definito
  const bgColor = block.getAttribute('data-colore') || '#FFFFFF';
  block.style.backgroundColor = bgColor;
  
  // Imposta il colore del font se definito
  const fontColor = block.getAttribute('data-colore_font');
  if (fontColor) {
      block.style.color = fontColor;
  }
}

document.addEventListener('DOMContentLoaded', () => {
    // Usa l'ID corretto per il campo "Cerca Cliente..."
    const clientSearchInput = document.getElementById('clientSearchInputNav');
    const serviceSearchInput = document.getElementById('serviceInputNav');
    const clientResults = document.getElementById('clientResultsNav');
    const serviceResults = document.getElementById('serviceResultsNav');
    const selectedServicesList = document.getElementById('selectedServicesList');
  
    // Nascondi tutti gli elementi tranne il campo "Cerca Cliente..."
    if (serviceSearchInput) serviceSearchInput.style.display = 'none';
    if (clientResults) clientResults.style.display = 'none';
    if (serviceResults) serviceResults.style.display = 'none';
    if (selectedServicesList) selectedServicesList.style.display = 'none';
  
    // Al primo click sul campo "Cerca Cliente...", mostra permanentemente gli altri elementi
    if (clientSearchInput) {
        const showNavigator = () => {
            if (serviceSearchInput) serviceSearchInput.style.display = 'block';
            if (clientResults) clientResults.style.display = 'block';
            if (serviceResults) serviceResults.style.display = 'block';
            if (selectedServicesList) selectedServicesList.style.display = 'block';
            clientSearchInput.removeEventListener('click', showNavigator);
        };
        clientSearchInput.addEventListener('click', showNavigator);
    }

  // === RIPRISTINA LO STATO DEL NAVIGATOR ===
  // Chiama restoreNavigatorState SOLO se non è già stato fatto dallo script inline
  if (typeof restoreNavigatorState === 'function' && !window.navigatorRestored) {
    restoreNavigatorState();
  }

  // Aggiungi listener per salvare automaticamente lo stato quando si digita nei campi
  if (clientSearchInputNav && typeof saveNavigatorState === 'function') {
    clientSearchInputNav.addEventListener('input', saveNavigatorState);
  }
  if (serviceInputNav && typeof saveNavigatorState === 'function') {
    serviceInputNav.addEventListener('input', saveNavigatorState);
  }
});
  
  async function revertToOldPosition(block) {
    if (!block || !block.__oldParent || !block.__originalPosition) return;
    // Rimuovi il blocco dalla cella corrente, se presente
    if (block.parentNode) {
        block.parentNode.removeChild(block);
    }
    // Riappendi il blocco nella cella originale
    block.__oldParent.appendChild(block);
    // Ripristina le coordinate originali
    block.style.left = block.__originalPosition.left;
    block.style.top = block.__originalPosition.top;
    // Aggiorna il backend con la posizione originale
    await saveDraggedBlockPosition(block, block.__oldParent);
}

async function saveBlockLayout(block, width, left, zIndex) {
    const appointmentId = block.getAttribute('data-appointment-id');
    if (!appointmentId) return; // Se non c'è ID, non fare nulla

    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    const payload = {
        widthValue: width,
        leftValue: left,
        zIndexValue: zIndex
    };

    try {
        const resp = await fetch(`/calendar/update_layout/${appointmentId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify(payload)
        });
        if (!resp.ok) {
            console.warn("Errore salvataggio layout");
        } else {
            console.log("Layout salvato per appuntamento:", appointmentId);
        }
    } catch (err) {
        console.error("Errore salvataggio layout:", err);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.selectable-cell').forEach(cell => {
        const blocks = cell.querySelectorAll('.appointment-block');
        if (blocks.length >= 2) {
            arrangeBlocksInCell(cell);
        }
    });
});

function openAddServicesModal(block) {
    // 1) Recupera gli attributi dal blocco
    const clientId = block.getAttribute("data-client-id") || "";
    const nome = block.getAttribute("data-client-nome") || "";
    const cognome = block.getAttribute("data-client-cognome") || "";

    // 2) Costruisce il nome completo
    const clientName = (nome + " " + cognome).trim();

    const originColor = block.getAttribute("data-colore") || "#FFFFFF";
    window.originBlockColor = originColor;

    // === NUOVO: Determina lo stato comune dei blocchi contigui ===
    // Usa la funzione esistente getRelevantBlocks per ottenere i blocchi contigui
    const groupBlocks = getRelevantBlocks(block);
    const statuses = groupBlocks.map(b => parseInt(b.getAttribute('data-status') || '0', 10));
    const commonStatus = statuses.every(s => s === 1) ? 1 : (statuses[0] || 0); // Se tutti 1, usa 1; altrimenti usa il primo (stato del blocco cliccato)
    console.log("DEBUG: block status:", block.getAttribute('data-status'));
    console.log("DEBUG: groupBlocks statuses:", groupBlocks.map(b => b.getAttribute('data-status')));
    console.log("DEBUG: commonStatus:", commonStatus);


    // Salva lo stato globale per i nuovi pseudoblocchi
    window.addServiceStatus = commonStatus;
    console.log("DEBUG: window.addServiceStatus set to:", window.addServiceStatus);
    // === FINE NUOVO CODICE ===

    // 3) Aggiorna le variabili globali
    window.selectedClientIdNav = clientId;
    window.selectedClientNameNav = clientName;

    // 4) Compila l’input “Cerca Cliente...” nel Navigator
    const clientInput = document.getElementById('clientSearchInputNav');
    if (clientInput) {
        clientInput.value = clientName;
    }

    // 5) Mostra immediatamente gli altri campi del Navigator
    const serviceInput = document.getElementById('serviceInputNav');
    const clientResults = document.getElementById('clientResultsNav');
    const serviceResults = document.getElementById('serviceResultsNav');
    const selectedServicesList = document.getElementById('selectedServicesList');
    if (serviceInput) serviceInput.style.display = 'block';
    if (clientResults) clientResults.style.display = 'block';
    if (serviceResults) serviceResults.style.display = 'block';
    if (selectedServicesList) selectedServicesList.style.display = 'block';

    // (Facoltativo) Aggiunge un riquadro in selectedServicesList
    if (selectedServicesList) {
        const div = document.createElement('div');
        div.textContent = "Nuovo Servizio per: " + clientName;
        selectedServicesList.appendChild(div);
    }
}

function updateBlockFontColor(block) {
    // Recupera il colore di sfondo del blocco
    const bgColor = block.getAttribute("data-colore") || "#FFFFFF";
    // Calcola il font color usando la regola (se il bg è chiaro, font scuro)
    const fontColor = computeFontColor(bgColor);
    // Salva il valore come attributo e lo applica in linea
    block.setAttribute("data-colore_font", fontColor);
    block.style.color = fontColor;
}

document.addEventListener('DOMContentLoaded', function() {
    document.addEventListener('click', function(e) {
        const noteIndicator = e.target.closest('.note-indicator');
        if (noteIndicator) {
            const block = noteIndicator.closest('.appointment-block');
            if (block) {
                openNoteModal(block);
            }
        }
    });
});

function loadServicesForModal() {
  const clientId = document.getElementById('client_id').value;

  // Funzione interna per caricare i servizi frequenti/recenti
  const loadFrequentServices = () => {
      fetch('/calendar/api/top-frequent-or-latest-services')
          .then(resp => resp.json())
          .then(services => {
              showServicesDropdownModal(services.slice(0, 10)); // Limita a 10
          })
          .catch(err => console.error("Errore caricamento servizi frequenti:", err));
  };

  if (clientId) {
      fetch(`/calendar/api/last-services-for-client/${clientId}`)
          .then(resp => resp.json())
          .then(services => {
              if (Array.isArray(services) && services.length > 0) {
                  showServicesDropdownModal(services.slice(0, 10)); // Mostra i primi 10 servizi del cliente
              } else {
                  loadFrequentServices(); // Fallback se non vengono trovati servizi per il cliente
              }
          })
          .catch(err => {
              console.error("Errore caricamento servizi cliente:", err);
              loadFrequentServices(); // Fallback in caso di errore
          });
  } else {
      loadFrequentServices(); // Nessun cliente valido, carica i servizi frequenti
  }
}

function showServicesDropdownModal(services) {
  const resultsContainer = document.getElementById('serviceResults');
  if (!resultsContainer) return;
  resultsContainer.innerHTML = '';

  if (!Array.isArray(services) || services.length === 0) {
    const noResult = document.createElement('div');
    noResult.className = 'dropdown-item';
    noResult.textContent = 'Nessun risultato';
    resultsContainer.appendChild(noResult);
    resultsContainer.style.display = 'block';
    return;
  }

  services.forEach(service => {
    const item = document.createElement('div');
    item.className = 'dropdown-item';
    const id = String(service.id ?? '');
    const name = String(service.name ?? '');
    const duration = String(service.duration ?? '');
    const daysText = formatDaysSince(service.last_date);

    item.textContent = (duration ? `${name} - ${duration} min` : `${name}`) + daysText;
    item.dataset.serviceId = id;
    item.dataset.serviceName = name;
    item.dataset.serviceDuration = duration;

    item.addEventListener('click', () => {
      // chiama la funzione di selezione corretta (modal)
      selectService(String(id), String(name), String(duration));
      resultsContainer.innerHTML = '';
      resultsContainer.style.display = 'none';
    });

    resultsContainer.appendChild(item);
  });

  resultsContainer.style.display = 'block';
}

// Funzione per gestire la ricerca servizi nel modal
function handleServiceSearchModal(query) {
  const resultsContainer = document.getElementById('serviceResults');
  if (query.length < 3) {
      // Mantieni i risultati iniziali per 1 o 2 caratteri
      if (resultsContainer.innerHTML.trim() !== '') {
          resultsContainer.style.display = 'block';
      }
      return;
  }
  fetch(`/calendar/api/search-services/${encodeURIComponent(query)}`)
      .then(response => response.json())
      .then(services => {
          if (!Array.isArray(services) || services.length === 0) {
              const div = document.createElement('div');
div.className = 'dropdown-item';
div.textContent = someVar; // safe
resultsContainer.appendChild(div);
          } else {
// versione sicura
resultsContainer.innerHTML = '';
services.slice(0, 10).forEach(service => {
  console.log("Service object:", service); // conserva il log

  const item = document.createElement('div');
  item.className = 'dropdown-item';

  const id       = String(service.id ?? '');
  const name     = String(service.name ?? '');
  const duration = String(service.duration ?? '');

  // testo puro
  item.textContent = duration
    ? `${name} - ${duration} min`
    : `${name}`;

  // click handler al posto di onclick inline
  item.addEventListener('click', () => {
    selectService(id, name, duration);
    resultsContainer.innerHTML = '';
    resultsContainer.style.display = 'none';
  });

  resultsContainer.appendChild(item);
});
resultsContainer.style.display = 'block';

          }
          resultsContainer.style.display = 'block';
      })
      .catch(err => console.error("Errore ricerca servizi:", err));
}

document.addEventListener('click', function(event) {
  const serviceInput = document.getElementById('serviceSearchInput');
  const serviceResults = document.getElementById('serviceResults');
  // Se il click NON è né sull'input né sul dropdown
  if (
      serviceInput &&
      serviceResults &&
      !serviceInput.contains(event.target) &&
      !serviceResults.contains(event.target)
  ) {
      serviceInput.value = '';
      serviceResults.innerHTML = '';
      serviceResults.style.display = 'none';
  }
});

// Esponi le funzioni globalmente
window.loadServicesForModal = loadServicesForModal;
window.handleServiceSearchModal = handleServiceSearchModal;

// ===============================
// EVENT HANDLER PER IL CLICK SULLA SPIA (Cliente in istituto)
// Toggle tra stato 0 e 1 (e, se in stato 3, torna a 0)
// ===============================
document.addEventListener('click', function(e) {
  const mySpiaElement = e.target.closest('.my-spia');
  if (!mySpiaElement) return;
  
  e.stopPropagation();

const baseBlock = mySpiaElement.closest('.appointment-block');
if (!baseBlock) return;

// PATCH: includi anche blocchi nella stessa cella con lo stesso cliente
const cell = baseBlock.closest('.selectable-cell');
let blocksInCell = [];
if (cell) {
  const clientId = baseBlock.getAttribute('data-client-id');
  const clientNome = baseBlock.getAttribute('data-client-nome');
  const clientCognome = baseBlock.getAttribute('data-client-cognome');
  const clientName = `${clientNome} ${clientCognome}`.trim();
  blocksInCell = Array.from(cell.querySelectorAll('.appointment-block')).filter(b => {
    const bClientId = b.getAttribute('data-client-id');
    const bNome = b.getAttribute('data-client-nome');
    const bCognome = b.getAttribute('data-client-cognome');
    const bClientName = `${bNome || ''} ${bCognome || ''}`.trim();
    return (bClientId && bClientId === clientId) || (bClientName && bClientName === clientName);
  });
}

// Unisci con i blocchi contigui classici
const contiguousBlocks = getRelevantBlocks(baseBlock);
const groupBlocks = Array.from(new Set([...blocksInCell, ...contiguousBlocks]));

  // Verifica che la data selezionata sia quella odierna
  let now = new Date();
  const todayStr = now.toISOString().slice(0, 10);
  if (typeof selectedDate !== 'undefined' && selectedDate !== todayStr) {
    alert("ATTENZIONE! Operazione non concessa. Spostare appuntamento sulla data di oggi per selezionare appuntamento in istituto");
    return;
  }
  
  // Per ciascun blocco del gruppo, aggiorna lo stato
  groupBlocks.forEach(block => {
    let currentStatus = parseInt(block.getAttribute('data-status') || '0', 10);
    let newStatus = (currentStatus !== 1) ? 1 : 0;
    
    const tooltips = {
      0: "Segna cliente arrivato",
      1: "CLIENTE IN ISTITUTO",
      2: "Pagato",
      3: "Non arrivato"
    };
    
    const appointmentId = block.getAttribute('data-appointment-id');
    if (!appointmentId) return;
    
    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    
    // Aggiorna il backend per questo blocco
    fetch(`/calendar/update_status/${appointmentId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      },
      body: JSON.stringify({ status: newStatus })
    })
    .then(response => response.json())
    .then(data => {
      console.log("my-spia aggiornato per block:", appointmentId, data);
      block.setAttribute('data-status', newStatus);
      
      // Aggiorna la spia interna al blocco
      const spia = block.querySelector('.my-spia');
      if (spia) {
        spia.setAttribute('data-status', newStatus);
        sessionStorage.setItem(`app_status_${appointmentId}`, newStatus);
        if (newStatus === 1) {
          spia.classList.add('active');
          spia.classList.remove('blink');
        } else {
          spia.classList.remove('active');
          spia.classList.remove('blink');
        }
        spia.setAttribute('data-bs-original-title', tooltips[newStatus]);

        try {
          // dispose eventuale istanza precedente in modo sicuro
          const existingTooltip = (bootstrap && bootstrap.Tooltip) ? bootstrap.Tooltip.getInstance(spia) : null;
          if (existingTooltip && typeof existingTooltip.dispose === 'function') {
            existingTooltip.dispose();
          }
          // crea nuova istanza tooltip solo se l'elemento è ancora in DOM
          if (document.contains(spia) && bootstrap && bootstrap.Tooltip) {
            new bootstrap.Tooltip(spia, {
              placement: 'right',
              fallbackPlacements: ['left'],
              container: 'body',
              boundary: 'window'
            });
          }
        } catch (ttErr) {
          // Non interrompere la logica principale se bootstrap genera errori
          console.warn('Tooltip init/dispose error (ignored):', ttErr);
        }
        
        // Listener per nascondere/mostrare i popup al mouseover/mouseout
        spia.addEventListener('mouseover', function() {
          const popupDiv = block.querySelector('.popup-buttons');
          if (popupDiv) {
            popupDiv.style.display = 'none';
          }
        });
        spia.addEventListener('mouseout', function() {
          const popupDiv = block.querySelector('.popup-buttons');
          if (popupDiv) {
            popupDiv.style.display = 'block';
          }
        });
      }
      
      updateBlinkForBlock(block);
      
      // Se il blocco passa da stato 3 a 1, ricarica la pagina (se richiesto)
      if (currentStatus === 3 && newStatus === 1) {
        location.reload();
      }
    })
    .catch(error => {
      console.error("Errore nell'aggiornamento di my-spia per block:", error);
      const spia = block.querySelector('.my-spia');
      if (spia) {
        spia.setAttribute('data-bs-original-title', tooltips[currentStatus]);
        const existingTooltip = bootstrap.Tooltip.getInstance(spia);
        if (existingTooltip) {
          existingTooltip.dispose();
        }
        new bootstrap.Tooltip(spia, {
          placement: 'right',
          fallbackPlacements: ['left'],
          container: 'body',
          boundary: 'window'
        });
      }
    });
  });
}, true);

  
  // ===============================
  // EVENT HANDLER PER IL CLICK SUL TASTO NO-SHOW (Cliente non arrivato)
  // Ciclo: se il blocco è in stato 1 o 3, il primo click lo resetta a 0; se già a 0, il click successivo lo porta a stato 3.
  // In questo caso, l'unica modifica grafica è che il blocco diventa completamente nero e puntinato.
  // ===============================
function getRelevantBlocks(baseBlock) {
  const allBlocks = Array.from(document.querySelectorAll('.appointment-block'));
  const baseClientId = baseBlock.getAttribute('data-client-id') || '';
  const baseDate = baseBlock.getAttribute('data-date') || selectedDate;
  const baseSource = (baseBlock.getAttribute('data-source') || '').toString().trim().toLowerCase();
  const baseBookingSessionId = baseBlock.getAttribute('data-booking_session_id') || '';
  const baseNome = (baseBlock.getAttribute('data-client-nome') || '').toString().trim().toLowerCase();
  const baseCognome = (baseBlock.getAttribute('data-client-cognome') || '').toString().trim().toLowerCase();

  // Se è chiaramente un placeholder booking-online generico, non propagare
  if (baseSource === 'web' && baseNome === 'booking' && baseCognome === 'online') {
    return [baseBlock];
  }

  // Gap massimo in minuti (globale)
  const MAX_GAP = Number(window.CONTIGUOUS_BLOCK_MAX_GAP_MINUTES || 30);

  // Costruiamo la lista candidati:
  // - preferiamo match su client_id
  // - altrimenti match su nome+cognome (normalize lowercase)
  // - includiamo anche blocchi con lo stesso booking_session_id (anche se client_id missing)
  const candidates = allBlocks.filter(b => {
    const bDate = b.getAttribute('data-date') || selectedDate || '';
    if (String(bDate) !== String(baseDate)) return false;

    // escludi placeholder booking genericamente vuoti
    const bNome = (b.getAttribute('data-client-nome') || '').toString().trim().toLowerCase();
    const bCognome = (b.getAttribute('data-client-cognome') || '').toString().trim().toLowerCase();
    if (b.getAttribute('data-source') === 'web' && bNome === 'booking' && bCognome === 'online') return false;

    const bClientId = b.getAttribute('data-client-id') || '';
    const bBookingSession = b.getAttribute('data-booking_session_id') || '';

    // match preferenziale su client_id
    if (baseClientId && bClientId && String(baseClientId) === String(bClientId)) return true;

    // stessa booking_session_id → includi (copre gruppi già associati)
    if (baseBookingSessionId && bBookingSession && String(baseBookingSessionId) === String(bBookingSession)) return true;

    // fallback: match su nome+cognome (utile per web booking con booking_session diversi)
    if (baseNome && baseCognome && bNome === baseNome && bCognome === baseCognome) return true;

    return false;
  });

  if (candidates.length === 0) return [baseBlock];

  // Ordina per orario di inizio
  candidates.sort((a, b) => getBlockStartTime(a) - getBlockStartTime(b));

  // Trova l'indice del baseBlock nella lista candidati (se non presente, aggiungilo)
  let idx = candidates.indexOf(baseBlock);
  if (idx === -1) {
    // Find insertion index by start time
    const baseStart = getBlockStartTime(baseBlock);
    idx = 0;
    while (idx < candidates.length && getBlockStartTime(candidates[idx]) <= baseStart) idx++;
    candidates.splice(idx, 0, baseBlock);
  }

  // Costruisci il gruppo intorno al baseBlock usando MAX_GAP (transitivo)
  const group = [baseBlock];

  // verso l'alto
  for (let i = idx - 1; i >= 0; i--) {
    const prev = candidates[i];
    const cur = group[0];
    const gap = getBlockStartTime(cur) - getBlockEndTime(prev);
    // PATCH: Rimosso check gap >= -MAX_GAP per permettere sovrapposizioni ampie (es. appuntamenti contemporanei)
    if (gap <= MAX_GAP) group.unshift(prev);
    else break;
  }
  // verso il basso
  for (let i = idx + 1; i < candidates.length; i++) {
    const next = candidates[i];
    const cur = group[group.length - 1];
    const gap = getBlockStartTime(next) - getBlockEndTime(cur);
    // PATCH: Rimosso check gap >= -MAX_GAP per permettere sovrapposizioni ampie
    if (gap <= MAX_GAP) group.push(next);
    else break;
  }

  // Rimuovi eventuali duplicati e restituisci
  const unique = Array.from(new Set(group));

  // PROPAGAZIONE COLORE: applica il colore del blocco di origine a tutti i blocchi contigui trovati
  try {
    const originColor = baseBlock.getAttribute('data-colore') || '';
    const originFont = baseBlock.getAttribute('data-colore_font') || (originColor ? computeFontColor(originColor) : '');
    if (originColor) {
      unique.forEach(b => {
        b.setAttribute('data-colore', originColor);
        if (originFont) b.setAttribute('data-colore_font', originFont);
        b.style.backgroundColor = originColor;
        if (originFont) {
          b.style.color = originFont;
          const content = b.querySelector('.appointment-content');
          if (content) {
            content.style.color = originFont;
            content.querySelectorAll('a').forEach(a => a.style.color = originFont);
          }
        }
      });
    }
  } catch (err) {
    console.warn('getRelevantBlocks: color propagation failed', err);
  }

  return unique.length ? unique : [baseBlock];
}

function getContiguousClientBlocks(block) {
  console.log("🔍 DEBUG: getContiguousClientBlocks called for block:", block.getAttribute('data-appointment-id'));
  const clientId = block.getAttribute('data-client-id');
  const date = block.getAttribute('data-date') || selectedDate;
  if (!clientId) {
    console.log("⚠️ DEBUG: No clientId, returning [block]");
    return [block];
  }

  // Prendi tutti i blocchi dello stesso cliente e data, escludendo "cliente booking" con source=web
  const allBlocks = Array.from(document.querySelectorAll('.appointment-block'))
    .filter(b =>
      b.getAttribute('data-client-id') === clientId &&
      (b.getAttribute('data-date') || selectedDate) === date &&
      !(
        b.getAttribute('data-client-nome') === 'cliente' &&
        b.getAttribute('data-client-cognome') === 'booking' &&
        b.getAttribute('data-source') === 'web'
      )
    );
  console.log("📋 DEBUG: Filtered blocks:", allBlocks.map(b => b.getAttribute('data-appointment-id')));

  // Ordina per orario di inizio
  allBlocks.sort((a, b) => getBlockStartTime(a) - getBlockStartTime(b));

  // Trova il gruppo contiguo che include il blocco di partenza
  const idx = allBlocks.indexOf(block);
  if (idx === -1) return [block];

    // Gap massimo in minuti (globale, impostabile): default da window.CONTIGUOUS_BLOCK_MAX_GAP_MINUTES
  const MAX_GAP = Number(window.CONTIGUOUS_BLOCK_MAX_GAP_MINUTES || 30);

  let group = [block];
  // Verso l'alto: includi prev se la distanza tra end(prev) e start(curr) <= MAX_GAP
  for (let i = idx - 1; i >= 0; i--) {
    const prev = allBlocks[i];
    const curr = group[0];
    const gap = getBlockStartTime(curr) - getBlockEndTime(prev);
    if (gap <= MAX_GAP && gap >= -MAX_GAP) { // tolleranza anche per sovrapposizioni negative
      group.unshift(prev);
    } else {
      break;
    }
  }

  // Verso il basso: includi next se la distanza tra start(next) e end(curr) <= MAX_GAP
  for (let i = idx + 1; i < allBlocks.length; i++) {
    const next = allBlocks[i];
    const curr = group[group.length - 1];
    const gap = getBlockStartTime(next) - getBlockEndTime(curr);
    if (gap <= MAX_GAP && gap >= -MAX_GAP) {
      group.push(next);
    } else {
      break;
    }
  }

    console.log("📋 DEBUG: Final group (MAX_GAP=" + MAX_GAP + "):", group.map(b => b.getAttribute('data-appointment-id')));
  return group;
}

  document.addEventListener('click', function(e) {
    const noShowBtn = e.target.closest('.no-show-button');
    if (!noShowBtn) return;
  
    e.stopPropagation();
  
const baseBlock = noShowBtn.closest('.appointment-block');
if (!baseBlock) return;

// PATCH: includi anche blocchi nella stessa cella con lo stesso cliente
const cell = baseBlock.closest('.selectable-cell');
let blocksInCell = [];
if (cell) {
  const clientId = baseBlock.getAttribute('data-client-id');
  const clientNome = baseBlock.getAttribute('data-client-nome');
  const clientCognome = baseBlock.getAttribute('data-client-cognome');
  const clientName = `${clientNome} ${clientCognome}`.trim();
  blocksInCell = Array.from(cell.querySelectorAll('.appointment-block')).filter(b => {
    const bClientId = b.getAttribute('data-client-id');
    const bNome = b.getAttribute('data-client-nome');
    const bCognome = b.getAttribute('data-client-cognome');
    const bClientName = `${bNome || ''} ${bCognome || ''}`.trim();
    return (bClientId && bClientId === clientId) || (bClientName && bClientName === clientName);
  });
}

const contiguousBlocks = getRelevantBlocks(baseBlock);
const groupBlocks = Array.from(new Set([...blocksInCell, ...contiguousBlocks]));
  
    // Definisce lo stato target: se lo stato corrente è 0 passa a 3 (non arrivato), altrimenti torna a 0
    const currentStatus = parseInt(baseBlock.getAttribute('data-status') || '0', 10);
    const targetStatus = (currentStatus === 0) ? 3 : 0;
  
    const tooltips = {
      0: "Cliente non ancora arrivato",
      1: "Cliente in istituto",
      2: "Pagato",
      3: "Non arrivato"
    };
  
    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
  
    groupBlocks.forEach(function(block) {
      const appointmentId = block.getAttribute('data-appointment-id');
      if (!appointmentId) return;
  
      // Aggiorna lo stile del blocco in base al target
      if (targetStatus === 3) {
        if (!block.getAttribute('data-original-color')) {
          block.setAttribute('data-original-color', window.getComputedStyle(block).backgroundColor);
        }
        block.style.backgroundColor = '#000';
        block.style.backgroundImage = 'radial-gradient(#555 1px, transparent 1px)';
        block.style.backgroundSize = '5px 5px';
        block.style.color = '#fff';
        const content = block.querySelector('.appointment-content');
        if (content) {
          content.style.color = '#fff';
          content.querySelectorAll('a').forEach(a => a.style.color = '#fff');
        }
      } else {
  const originalColor = block.getAttribute('data-original-color') || '';
  block.style.backgroundColor = originalColor;
  block.style.backgroundImage = '';
  block.style.backgroundSize = '';

  // PATCH: ripristina il colore del font originale
  const coloreFont = block.getAttribute('data-colore_font') || computeFontColor(originalColor) || '#222';
  block.style.color = coloreFont;

  // Ripristina anche il colore del testo interno (contenuto e link)
  const content = block.querySelector('.appointment-content');
  if (content) {
    content.style.color = coloreFont;
    content.querySelectorAll('a').forEach(a => a.style.color = coloreFont);
  }
}
  
      // Invia la richiesta per aggiornare lo stato nel backend
const bgColor = block.getAttribute('data-colore') || window.getComputedStyle(block).backgroundColor || "#fff";
const fontColor = block.getAttribute('data-colore_font') || window.getComputedStyle(block).color || "#000";

fetch(`/calendar/update_status/${appointmentId}`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRFToken': csrfToken
  },
  body: JSON.stringify({
    status: targetStatus,
    colore: bgColor,
    colore_font: fontColor
  })
})
.then(response => response.json())
.then(data => {
  console.log("Aggiornamento no-show per id:", appointmentId, data);
  block.setAttribute('data-status', targetStatus);
  const spia = block.querySelector('.my-spia');
  if (spia) {
    spia.setAttribute('data-status', targetStatus);
    spia.setAttribute('data-bs-original-title', tooltips[targetStatus]);
    const existingTooltip = bootstrap.Tooltip.getInstance(spia);
    if (existingTooltip) existingTooltip.dispose();
    new bootstrap.Tooltip(spia, {
      placement: 'right',
      fallbackPlacements: ['left'],
      container: 'body',
      boundary: 'window'
    });
  }
})
.catch(error => {
  console.error("Errore aggiornamento no-show per id:", appointmentId, error);
});
    });
  
    // Nascondi il tooltip dopo il click
    const tooltipInstance = bootstrap.Tooltip.getInstance(noShowBtn);
    if (tooltipInstance) tooltipInstance.hide();
  
  }, true);
  
  // ===============================
  // FUNZIONE PER AGGIORNARE IL COMPORTAMENTO (ACTIVE/BLINK) DELLA SPIA PER UN BLOCCO
  // ===============================
function updateBlinkForBlock(block) {
    const spia = block.querySelector('.my-spia');
    if (!spia) return;

    let now = new Date();
    const todayStr = now.toISOString().slice(0, 10);

    // Se selectedDate è definito e non è oggi, rimuovi ogni effetto.
    if (typeof selectedDate !== 'undefined' && selectedDate !== todayStr) {
        spia.classList.remove('active');
        spia.classList.remove('blink');
        return;
    }

    // Trova tutti i blocchi contigui per questo cliente e questa data
    const clientId = block.getAttribute('data-client-id');
    const date = block.getAttribute('data-date') || selectedDate;
    const allBlocks = Array.from(document.querySelectorAll('.appointment-block'))
        .filter(b => b.getAttribute('data-client-id') === clientId && (b.getAttribute('data-date') || selectedDate) === date);

    // Ordina per orario di inizio
    allBlocks.sort((a, b) => getBlockStartTime(a) - getBlockStartTime(b));

    // Trova il gruppo contiguo a cui appartiene il blocco corrente
    let group = [];
    let found = false;
    for (let i = 0; i < allBlocks.length; i++) {
        if (allBlocks[i] === block) found = true;
        if (group.length === 0) group.push(allBlocks[i]);
        else {
            const prev = group[group.length - 1];
            const prevEnd = getBlockEndTime(prev);
            const currStart = getBlockStartTime(allBlocks[i]);
            if (currStart === prevEnd) {
                group.push(allBlocks[i]);
            } else if (allBlocks[i] === block) {
                // Se il blocco corrente non è contiguo a quelli precedenti, inizia un nuovo gruppo
                group = [allBlocks[i]];
            }
        }
        if (found && (i === allBlocks.length - 1 || getBlockStartTime(allBlocks[i + 1]) !== getBlockEndTime(allBlocks[i]))) {
            break;
        }
    }

    // Calcola l'intervallo totale del gruppo
    const groupStart = Math.min(...group.map(getBlockStartTime));
    const groupEnd = Math.max(...group.map(getBlockEndTime));
    const blockStatus = parseInt(block.getAttribute('data-status') || '0', 10);

    // Logica spia su tutto il gruppo
    if (blockStatus === 0) {
        spia.classList.remove('active');
        spia.classList.remove('blink');
        const originalColor = block.getAttribute('data-original-color');
        if (originalColor) {
            block.style.backgroundColor = originalColor;
            block.style.backgroundImage = '';
            block.style.backgroundSize = '';
        }
    } else if (blockStatus === 1) {
        // Se ora è PRIMA della fine del gruppo → spia attiva, altrimenti blinking
        const nowMinutes = now.getHours() * 60 + now.getMinutes();
        if (nowMinutes < groupEnd) {
            spia.classList.add('active');
            spia.classList.remove('blink');
        } else {
            spia.classList.remove('active');
            spia.classList.add('blink');
        }
    } else if (blockStatus === 3) {
        spia.classList.remove('active');
        spia.classList.remove('blink');
    } else {
        spia.classList.remove('active');
        spia.classList.remove('blink');
    }
}
  
  // ===============================
  // AGGIORNAMENTO PERIODICO DEI BLOCCI (ogni secondo)
  // ===============================
  setInterval(function() {
    document.querySelectorAll('.appointment-block').forEach(block => {
      updateBlinkForBlock(block);
    });
  }, 200);

// ===============================
// EVENT HANDLER PER IL CLICK SUL BOTTONE "NO-SHOW" (Cliente non arrivato)
// ===============================
document.addEventListener('click', function(e) {
  const noShowButton = e.target.closest('.no-show-button');
  if (!noShowButton) return;

  e.stopPropagation();

  const clickedBlock = noShowButton.closest('.appointment-block');
  if (!clickedBlock) return;

  // Prendi tutti i blocchi contigui per il no-show
  const blocksToUpdate = getRelevantBlocks(clickedBlock);

  const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

  blocksToUpdate.forEach(appointmentBlock => {
    const appointmentId = appointmentBlock.getAttribute('data-appointment-id');
    if (!appointmentId) return;

    let currentStatus = parseInt(appointmentBlock.getAttribute('data-status') || '0', 10);
    let newStatus = currentStatus === 3 ? 0 : 3;

    const tooltips = {
      0: "Cliente non ancora arrivato",
      1: "Cliente in istituto",
      2: "Pagato",
      3: "Non arrivato"
    };

    const spia = appointmentBlock.querySelector('.my-spia');

    if (newStatus === 3) {
      if (!appointmentBlock.getAttribute('data-original-color')) {
        appointmentBlock.setAttribute('data-original-color', window.getComputedStyle(appointmentBlock).backgroundColor);
      }
      appointmentBlock.style.backgroundColor = '#000';
      appointmentBlock.style.backgroundImage = 'radial-gradient(#555 1px, transparent 1px)';
      appointmentBlock.style.backgroundSize = '5px 5px';
      appointmentBlock.style.color = '#fff';
      if (spia) {
        spia.classList.remove('active', 'blink');
        spia.setAttribute('data-status', newStatus);
        spia.setAttribute('data-bs-original-title', tooltips[newStatus]);
        spia.style.zIndex = '9999';
      }
    } else if (newStatus === 0) {
      const savedColor = appointmentBlock.getAttribute('data-original-color');
      appointmentBlock.style.backgroundColor = savedColor ? savedColor : '';
      appointmentBlock.style.backgroundImage = '';
      appointmentBlock.style.backgroundSize = '';
      appointmentBlock.style.color = '';
      if (spia) {
        spia.classList.remove('active', 'blink');
        spia.setAttribute('data-status', newStatus);
        spia.setAttribute('data-bs-original-title', tooltips[newStatus]);
        spia.style.zIndex = '9999';
      }
    }

    // Aggiorna lo stato sul backend per ogni blocco
    fetch(`/calendar/update_status/${appointmentId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      },
      body: JSON.stringify({ status: newStatus })
    })
    .then(response => response.json())
    .then(data => {
      console.log("no-show aggiornato per blocco:", appointmentId, data);
      appointmentBlock.setAttribute('data-status', newStatus);
      if (spia) spia.setAttribute('data-status', newStatus);
      sessionStorage.setItem(`app_status_${appointmentId}`, newStatus);
      updateBlinkForBlock(appointmentBlock);
    })
    .catch(error => {
      console.error("Errore aggiornamento (no-show) per blocco:", appointmentId, error);
      if (spia) spia.setAttribute('title', tooltips[currentStatus]);
    });
  });
}, true);

// ===============================
// AL CARICAMENTO DELLA PAGINA: APPLICA GLI STILI CORRETTI BASATI SULLO STATO
// ===============================
document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.appointment-block').forEach(function(block) {
      const appointmentId = block.getAttribute('data-appointment-id');
      if (!appointmentId) return;
      
let status = parseInt(block.getAttribute('data-status') || '0');
if (status !== 2 && status !== 3) { // Solo se non già pagato o no-show
  const appStatusKey = `app_status_${appointmentId}`;
  const savedStatus = sessionStorage.getItem(appStatusKey);
  if (savedStatus && parseInt(savedStatus) > status) {
    status = parseInt(savedStatus);
  }
}
block.setAttribute('data-status', status);
      
      // Imposta lo stato per la spia
      const mySpia = block.querySelector('.my-spia');
      if (mySpia) {
          if (status === 1) {
              mySpia.classList.add('active');
          } else {
              mySpia.classList.remove('active');
          }
          
          const tooltips = {
              0: "Segna cliente in istituto",
              1: "CLIENTE IN ISTITUTO",
              2: "Pagato",
              3: "Non arrivato"
          };
          // Usa l'attributo data-bs-original-title per Bootstrap Tooltip
          mySpia.setAttribute('data-bs-original-title', tooltips[status] || tooltips[0]);
          // Se esiste già un'istanza, la rimuove
          const existingTooltip = bootstrap.Tooltip.getInstance(mySpia);
          if(existingTooltip) {
              existingTooltip.dispose();
          }
          // Crea il tooltip con container: 'body'
          new bootstrap.Tooltip(mySpia, {
            placement: 'right',
            fallbackPlacements: ['left'],
            container: 'body',
            boundary: 'window'
        });
          mySpia.setAttribute('data-status', status);
          
      }
      const __TOUCH_UI = (() => { try { return localStorage.getItem('sun_touch_ui') === '1'; } catch(_) { return false; } })();
      if (!__TOUCH_UI) {
        mySpia.addEventListener('mouseover', function() {
          const popupDiv = block.querySelector('.popup-buttons');
          if (popupDiv) popupDiv.style.display = 'none';
        });
        mySpia.addEventListener('mouseout', function() {
          const popupDiv = block.querySelector('.popup-buttons');
          if (popupDiv) popupDiv.style.display = 'block';
        });
      }
        // Applica gli stili per lo stato no-show (3)
        if (status === 3) {
            // Controlla se esiste un colore originale salvato in sessionStorage
            const originalColorKey = `app_original_color_${appointmentId}`;
            const savedOriginalColor = sessionStorage.getItem(originalColorKey);
            
            // Salva il colore originale se non è già salvato
            if (!block.hasAttribute('data-original-color')) {
                if (savedOriginalColor) {
                    block.setAttribute('data-original-color', savedOriginalColor);
                } else {
                    block.setAttribute('data-original-color', block.style.backgroundColor || '');
                }
            }
            
            // Applica lo stile no-show
            block.style.backgroundColor = '#000';
            block.style.backgroundImage = 'radial-gradient(#555 1px, transparent 1px)';
            block.style.backgroundSize = '5px 5px';
            block.style.color = 'white';
            
            // Applica il colore al testo interno
            const textElements = block.querySelectorAll('.appointment-content, .appointment-content a');
            textElements.forEach(el => {
                el.style.color = 'white';
            });
            
            // Configura il pulsante no-show
            const noShowButton = block.querySelector('.no-show-button');
            if (noShowButton) {
                noShowButton.setAttribute('data-status', '3');
                noShowButton.style.color = 'white';
                noShowButton.style.opacity = '1';
                noShowButton.setAttribute('title', 'NON ARRIVATO');
            }
        }
    });
});

function setNoShow(appointmentId) {
  // Trova il blocco base corrispondente all'appointmentId
  const baseBlock = document.querySelector(`.appointment-block[data-appointment-id="${appointmentId}"]`);
  if (!baseBlock) return;
  
  // Recupera tutti i blocchi del medesimo macro‑blocco
  const groupBlocks = getRelevantBlocks(baseBlock);

  // Calcola lo stato target in base allo stato del blocco base:
  // se è 0 (non ancora arrivato) allora diventerà 3 (non arrivato); altrimenti, tornerà a 0
  let baseStatus = parseInt(baseBlock.getAttribute('data-status') || '0', 10);
  const targetStatus = (baseStatus === 0) ? 3 : 0;
  
  // Definisci i tooltip corrispondenti
  const tooltips = {
    0: "Cliente non ancora arrivato",
    1: "Cliente in istituto",
    2: "Pagato",
    3: "Non arrivato"
  };
  
  // Recupera il CSRF token
  const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
  
  // Per ogni blocco del gruppo, aggiorna l'aspetto e invia la richiesta al backend
  groupBlocks.forEach(function(block) {
    const id = block.getAttribute('data-appointment-id');
    if (!id) return;
    
    if (targetStatus === 3) {
      // Se impostiamo NO-SHOW, salva il colore originale se non già salvato
      if (!block.getAttribute('data-original-color')) {
        block.setAttribute('data-original-color', window.getComputedStyle(block).backgroundColor);
      }
      block.style.backgroundColor = '#000';
      block.style.backgroundImage = 'radial-gradient(#555 1px, transparent 1px)';
      block.style.backgroundSize = '5px 5px';
      block.style.color = '#fff';
      
      const spia = block.querySelector('.my-spia');
      if (spia) {
        spia.classList.remove('active');
        spia.classList.remove('blink');
        spia.setAttribute('data-status', targetStatus);
        spia.setAttribute('data-bs-original-title', tooltips[targetStatus]);
        spia.style.zIndex = '9999';
      }
      const noShowBtn = block.querySelector('.no-show-button');
      if (noShowBtn) {
        noShowBtn.style.zIndex = '10000';
      }
      const popupDiv = block.querySelector('.popup-buttons');
      if (popupDiv) {
        popupDiv.style.display = 'none';
      }
    } else { // targetStatus === 0, ripristino
      const savedColor = block.getAttribute('data-original-color');
      block.style.backgroundColor = savedColor ? savedColor : '';
      block.style.backgroundImage = '';
      block.style.backgroundSize = '';
      block.style.color = '';
      const content = block.querySelector('.appointment-content');
      if (content) {
        content.style.color = '';
        content.querySelectorAll('a').forEach(a => a.style.color = '');
      }
    }
    
    // Invia la richiesta per aggiornare lo stato del blocco
    fetch(`/calendar/update_status/${id}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      },
      body: JSON.stringify({ status: targetStatus })
    })
    .then(response => response.json())
    .then(data => {
      console.log("no-show aggiornato per block:", id, data);
      block.setAttribute('data-status', targetStatus);
      const spia = block.querySelector('.my-spia');
      if (spia) {
        spia.setAttribute('data-status', targetStatus);
      }
      sessionStorage.setItem(`app_status_${id}`, targetStatus);
      updateBlinkForBlock(block);
    })
    .catch(error => {
      console.error("Errore nell'aggiornamento di no-show per block:", error);
      const spia = block.querySelector('.my-spia');
      if (spia) {
        spia.setAttribute('title', tooltips[baseStatus]);
      }
    });
  });
}

// Funzione per aggiornare lo stato delle spie in base all'orario
function updateMySpiaStatus() {
    const now = new Date();
    const currentMinutes = now.getHours() * 60 + now.getMinutes();
    
    document.querySelectorAll('.appointment-block').forEach(block => {
        // Salta i blocchi che hanno status=3 (non arrivato)
        const blockStatus = parseInt(block.getAttribute('data-status') || '0');
        if (blockStatus === 3) return;
        
        const mySpia = block.querySelector('.my-spia');
        if (!mySpia) return;
        
        // Calcola l'orario dell'appuntamento e la sua fine
        const hour = parseInt(block.getAttribute('data-hour'), 10) || 0;
        const minute = parseInt(block.getAttribute('data-minute'), 10) || 0;
        const duration = parseInt(block.getAttribute('data-duration'), 10) || 30;
        
        const appointmentStartTime = hour * 60 + minute;
        const appointmentEndTime = appointmentStartTime + duration;
        
        // Se lo stato è 1 (cliente arrivato)
        if (blockStatus === 1) {
            mySpia.classList.add('active');
            
            // Se l'appuntamento è nel futuro o in corso, deve lampeggiare
            if (appointmentEndTime > currentMinutes) {
                mySpia.classList.add('blink');
                mySpia.style.opacity = '1'; // Assicurati che sia visibile
            } else {
                // Altrimenti resta accesa ma non lampeggia
                mySpia.classList.remove('blink');
                mySpia.style.opacity = '1'; // Assicurati che sia visibile
            }
        }
        // Se lo stato è 0 (normale) ma l'appuntamento è imminente o in corso
        else if (blockStatus === 0) {
            // Se l'appuntamento è imminente (entro 15 minuti) o in corso, aggiungi blinking
            if ((appointmentStartTime <= currentMinutes && appointmentEndTime > currentMinutes) ||
                (appointmentStartTime > currentMinutes && appointmentStartTime - currentMinutes <= 15)) {
                mySpia.classList.add('blink');
                mySpia.style.opacity = '1'; // Assicurati che sia visibile
            } else {
                mySpia.classList.remove('blink');
                mySpia.style.opacity = ''; // Ripristina l'opacità predefinita
            }
        }
    });
}

// Esegui quando il DOM è pronto e aggiorna regolarmente
document.addEventListener('DOMContentLoaded', function() {
    // Esegui subito l'aggiornamento delle spie
    updateMySpiaStatus();
    
    // E poi ogni minuto
    setInterval(updateMySpiaStatus, 60000);
});
  
// Aggiungi highlight alle celle selezionabili al passaggio del mouse
document.querySelectorAll('.selectable-cell:not(.calendar-closed)').forEach(cell => {
  cell.addEventListener('mouseenter', (e) => {
    // usa la funzione helper per applicare l'highlight (gestisce pseudo‑blocchi)
    if (typeof window.applyHighlightToCell === 'function') {
      window.applyHighlightToCell(cell);
    } else {
      // fallback minimo
      cell.classList.add('highlight');
      const row = cell.parentElement;
      if (row) {
        const cells = Array.from(row.querySelectorAll('.selectable-cell'));
        cells.forEach(c => { if (c !== cell && !c.classList.contains('calendar-closed')) c.classList.add('highlight-side'); });
      }
    }
  });

  cell.addEventListener('mouseleave', (e) => {
    if (typeof window.clearCalendarHighlights === 'function') {
      window.clearCalendarHighlights();
    } else {
      const operatorId = cell.getAttribute('data-operator-id');
      const date = cell.getAttribute('data-date');
      const cellsToUnhighlight = document.querySelectorAll(`.selectable-cell[data-operator-id="${operatorId}"][data-date="${date}"]`);
      cellsToUnhighlight.forEach(c => c.classList.remove('highlight'));
      const row = cell.parentElement;
      if (row) row.querySelectorAll('.highlight-side').forEach(c => c.classList.remove('highlight-side'));
    }
  });
});

// Delegato: mostra l'highlight sopra i blocchi esistenti (escludendo .note-off)
document.addEventListener('mouseenter', function(e) {
  // FIX: Verifica che e.target sia un elemento valido e supporti .closest
  if (!e.target || typeof e.target.closest !== 'function') return;

  const blk = e.target.closest('.appointment-block:not(.note-off)');
  if (!blk) return;

  // Rimuovi highlight-side dalla riga (come era prima)
  const cell = blk.closest('.selectable-cell');
  if (cell && cell.parentElement) {
    cell.parentElement.querySelectorAll('.highlight-side').forEach(c => c.classList.remove('highlight-side'));
  }

  // Applica l'highlight alla cella sottostante in modo che l'utente veda la destinazione (usa la funzione esistente)
  if (typeof applyHighlightToCell === 'function' && cell) {
    applyHighlightToCell(cell);
  }
}, true);

document.addEventListener('mouseleave', function(e) {
  // FIX: Verifica che e.target sia un elemento valido e supporti .closest
  if (!e.target || typeof e.target.closest !== 'function') return;

  const blk = e.target.closest('.appointment-block:not(.note-off)');

  if (!blk) return;
  // Rimuovi tutti gli highlight quando il mouse esce dal blocco
  if (typeof clearCalendarHighlights === 'function') {
    clearCalendarHighlights();
  }
}, true);

document.addEventListener('click', function(e) {
  try {
    if (e && e._fromPseudoRedirect) return; // evento sintetico: non reindirizzare
  } catch(_) {}

  if (!window.pseudoBlocks || !Array.isArray(window.pseudoBlocks) || window.pseudoBlocks.length === 0) return;

  const clickedBlock = e.target.closest('.appointment-block:not(.note-off)');
  if (!clickedBlock) return;

  const targetCell = clickedBlock.closest('.selectable-cell');
  if (!targetCell) return;

  // Previeni che i gestori sul blocco ricevano l'evento originale
  // stopImmediatePropagation per sicurezza (evita altri handler in cattura/same-target)
  e.preventDefault();
  e.stopImmediatePropagation();

  // Dispatch di un click sintetico sulla cella (con flag per evitare loop)
  const ev = new MouseEvent('click', { bubbles: true, cancelable: true, view: window });
  try {
    // Aggiungiamo un flag non enumerabile sull'evento per riconoscerlo nelle nostre listener
    Object.defineProperty(ev, '_fromPseudoRedirect', { value: true, configurable: true, writable: false });
  } catch(_) {
    // In ambienti strani, fallback: assegna direttamente (potrebbe non essere consentito in alcuni browser)
    try { ev._fromPseudoRedirect = true; } catch(_) {}
  }
  targetCell.dispatchEvent(ev);
}, true);

// =============================================================
//   FUNZIONALITÀ CHAIN BUTTON (MACRO-BLOCCHI)
// =============================================================

let activeMacroBlockParent = null;
let macroBlockCandidates = [];
let linkedBlocks = [];
let isDragging = false;
let startX, startY;
let draggedBlocks = [];
let blockInitialPositions = [];
let targetCell = null;

// Mappa degli ID degli appuntamenti ai loro macro-blocchi
const macroBlockMap = new Map();

function moveBlocksToTarget() {
  if (!targetCell || !activeMacroBlockParent) return;

  const targetOperatorId = targetCell.getAttribute('data-operator-id');
  const targetHour = parseInt(targetCell.getAttribute('data-hour'), 10);
  const targetMinute = parseInt(targetCell.getAttribute('data-minute'), 10);
  const targetDate = targetCell.getAttribute('data-date') || selectedDate;

  const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

  const parentOriginalMinutes = parseInt(activeMacroBlockParent.getAttribute('data-hour'), 10) * 60 +
                                parseInt(activeMacroBlockParent.getAttribute('data-minute'), 10);

  const targetStartMinutes = targetHour * 60 + targetMinute;

  const savePromises = [];

  draggedBlocks.forEach((block) => {
    const blockOriginalHour = parseInt(block.getAttribute('data-hour'), 10);
    const blockOriginalMinute = parseInt(block.getAttribute('data-minute'), 10);
    const originalMinutes = blockOriginalHour * 60 + blockOriginalMinute;
    const offsetFromParent = originalMinutes - parentOriginalMinutes;

    const newTotalMinutes = targetStartMinutes + offsetFromParent;
    const newHour = Math.floor(newTotalMinutes / 60);
    const newMinute = newTotalMinutes % 60;

    const appointmentId = block.getAttribute('data-appointment-id');
    if (!appointmentId) {
      console.error("Errore: Blocco senza ID");
      revertToOriginalPositions();
      throw new Error("Blocco senza ID");
    }

    const savePromise = fetch(`/calendar/update/${appointmentId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      },
      body: JSON.stringify({
        operator_id: targetOperatorId,
        hour: newHour,
        minute: newMinute,
        date: targetDate
      })
    }).then(response => {
      if (!response.ok) {
        return response.text().then(text => {
          throw new Error(`Errore nel salvataggio blocco ${appointmentId}: ${text}`);
        });
      }
      return response.json();
    }).then(data => {
      console.log(`Blocco ${appointmentId} salvato correttamente:`, data);
      return data;
    });

    savePromises.push(savePromise);
  });

  Promise.all(savePromises)
  .then(results => {
    console.log("Tutti i blocchi salvati correttamente:", results);

    // Riorganizza tutte le celle coinvolte
    const updatedCells = new Set();
    draggedBlocks.forEach(block => {
      const hour = block.getAttribute('data-hour');
      const minute = block.getAttribute('data-minute');
      const cell = findCellAt(targetOperatorId, hour, minute);
      if (cell) updatedCells.add(cell);
    });

    updatedCells.forEach(cell => arrangeBlocksInCell(cell));

    setTimeout(() => {
      const chainBtn = activeMacroBlockParent.querySelector('.chain-button');
      if (chainBtn) {
        chainBtn.classList.add('active');
      }
    }, 300);

    // NUOVO: Aggiorna i dati per evitare problemi visivi (se persistono problemi visivi ricarica dopo un breve timeout)
    setTimeout(() => location.reload(), 500);
  })
  .catch(error => {
    console.error("Errore durante lo spostamento dei blocchi:", error);
    alert("Errore durante il salvataggio. La pagina verrà ricaricata.");
    setTimeout(() => location.reload(), 1000);
  });
}



document.addEventListener('DOMContentLoaded', function() {

  // Intercetta i click sulla navigazione calendario (frecce e bottone Oggi)
  document.querySelectorAll('.calendar-navigation .arrow-nav, .calendar-navigation .btn-today').forEach(link => {
    link.addEventListener('click', function(event) {
      if (isDragging || (draggedBlocks && draggedBlocks.length > 0)) {
        event.preventDefault();
      }
    });
  });

});

/**
 * Restituisce l'orario di fine del blocco in minuti.
 */
function getBlockEndTime(block) {
  const startTime = getBlockStartTime(block);
  const duration = parseInt(block.getAttribute('data-duration'), 10) || 15;
  return startTime + duration;
}

/**
 * Restituisce l'orario di inizio del blocco in minuti.
 */
function getBlockStartTime(block) {
  const hour = parseInt(block.getAttribute('data-hour'), 10) || 0;
  const minute = parseInt(block.getAttribute('data-minute'), 10) || 0;
  return hour * 60 + minute;
}

document.addEventListener('DOMContentLoaded', function() {
  // Seleziona tutti i blocchi appuntamento non OFF
  const appointmentBlocks = Array.from(document.querySelectorAll('.appointment-block:not(.note-off)'));
  const blocksByClient = {};

  // Raggruppa i blocchi per client id (escludendo quelli null)
appointmentBlocks.forEach(block => {
    const clientId = block.getAttribute('data-client-id');
    if (!clientId) return; // Escludi blocchi OFF/PAUSA (clientId null/undefined/vuoto)
    if (!blocksByClient[clientId]) {
        blocksByClient[clientId] = [];
    }
    blocksByClient[clientId].push(block);
});
});

function transformToPseudoBlock(block) {
  // Marca il blocco come pseudo-blocco senza alterarne lo stile
  // Invece di aggiungere una classe che potrebbe influire sul CSS, utilizziamo un attributo dati
  block.setAttribute('data-pseudo', 'true');
}

function findCellAt(operatorId, hour, minute) {
 return document.querySelector(
   `.selectable-cell[data-operator-id="${operatorId}"][data-hour="${hour}"][data-minute="${minute}"]`
 );
}

function isColorDark(hexColor) {
  const hex = hexColor.replace('#', '');
  const r = parseInt(hex.substr(0,2), 16);
  const g = parseInt(hex.substr(2,2), 16);
  const b = parseInt(hex.substr(4,2), 16);
  const luminosity = (r * 299 + g * 587 + b * 114) / 1000;
  return luminosity < 128;
}

// Applica automaticamente la classe in base alla luminosità dello sfondo
// Verifica che appointment sia definito e abbia una proprietà color
if (typeof appointment !== 'undefined' && appointment.color) {
  if (isColorDark(appointment.color)) {
    block.classList.add('dark-bg');
  } else {
    block.classList.add('light-bg');
  }
}

// Variabile globale per tenere traccia del pseudoblocco attualmente selezionato
let selectedPseudoBlock = null;

// Funzione per gestire il click su un pseudoblocco
function handlePseudoBlockClick(pseudoBlock) {
    // Se il pseudoblocco cliccato è già selezionato, deselezionalo
    if (selectedPseudoBlock === pseudoBlock) {
        pseudoBlock.classList.remove('selected');
        selectedPseudoBlock = null;
        console.log("Pseudoblocco deselezionato.");
    } else {
        // Deseleziona il precedente pseudoblocco selezionato, se esiste
        if (selectedPseudoBlock) {
            selectedPseudoBlock.classList.remove('selected');
        }
        // Seleziona il nuovo pseudoblocco
        pseudoBlock.classList.add('selected');
        selectedPseudoBlock = pseudoBlock;
        console.log("Pseudoblocco selezionato:", pseudoBlock);
    }
}

document.addEventListener('DOMContentLoaded', () => {
  const pseudoBlocksContainer = document.getElementById('selectedServicesList');
  if (pseudoBlocksContainer) {
      pseudoBlocksContainer.addEventListener('click', (e) => {
          const pseudoBlock = e.target.closest('.pseudo-block');
          if (pseudoBlock) {
              handlePseudoBlockClick(pseudoBlock);
          }
      });
  } else {
      console.warn("Elemento con id 'selectedServicesList' non trovato.");
  }
});

window.clearNavigator = async function clearNavigator(confirmRestore = true) {
  // Se esistono cutBlocks backup, gestiscili SOLO se confermato (default true)
  try {
    const cutBlocks = (typeof _loadCutBlocks === 'function') ? _loadCutBlocks() : JSON.parse(localStorage.getItem('cutBlocks') || '[]');
    if (Array.isArray(cutBlocks) && cutBlocks.length > 0) {
      if (confirmRestore) {
        // chiedo conferma all'utente
        if (confirm('Sono presenti blocchi tagliati non ancora ripristinati. Vuoi ripristinarli ora?')) {
          await restoreCutBlocks();
        } else {
          // l'utente rifiuta: manteniamo il backup per futuri tentativi
        }
      } else {
        // Chiamata programmatica (es. creazione da pseudoblocco): NON chiedere e NON ripristinare.
        // Rimuoviamo il backup perché l'intenzione è "consumare" i pseudoblocchi (cut -> create)
        try { localStorage.removeItem('cutBlocks'); } catch (e) { /* ignore */ }
      }
    }
  } catch (e) {
    console.warn('restoreCutBlocks/clearNavigator check failed', e);
  }

  // Reset dei dati navigator visivi e persistenti
  window.selectedClientIdNav = null;
  window.selectedClientNameNav = "";
  window.pseudoBlocks = [];

  const clientSearchInputNav = document.getElementById('clientSearchInputNav');
  if (clientSearchInputNav) {
      clientSearchInputNav.value = "";
  }

  const serviceInputNav = document.getElementById('serviceInputNav');
  if (serviceInputNav) {
      serviceInputNav.value = "";
  }

  const clearNavigatorBtn = document.getElementById('clearNavigatorBtn');
  if (clearNavigatorBtn) {
      clearNavigatorBtn.style.display = 'none';
  }

  // Rimuovi i dati dal localStorage relativi SOLO al navigator
  try {
    localStorage.removeItem('selectedClientIdNav');
    localStorage.removeItem('selectedClientNameNav');
    localStorage.removeItem('pseudoBlocksData');
    // NOTA: cutBlocks già rimossi sopra quando confirmRestore === false
  } catch (e) {
    console.warn('clearNavigator localStorage cleanup failed', e);
  }

  // Aggiorna l'interfaccia utente rimuovendo i pseudoblocchi
  const container = document.getElementById('selectedServicesList');
  if (container) {
      container.innerHTML = '';
      container.style.display = 'none';
  }

  // Persist state pulito
  try { saveNavigatorState(); } catch(e) { /* ignore */ }

  // NEW: ricarica SOLO quando lo svuotamento è manuale (tasto "Svuota")
  if (confirmRestore) {
    setTimeout(() => location.reload(), 50);
  }
}

window.addCutSourceHighlight = addCutSourceHighlight;
window.clearCutSourceHighlights = clearCutSourceHighlights;

// NEW: Helper per applicare highlight da dati grezzi (utile per restore)
function addCutSourceHighlightFromData(opId, date, startHour, startMinute, duration, width, left) {
  const startTotal = parseInt(startHour, 10) * 60 + parseInt(startMinute, 10);
  const endTotal = startTotal + parseInt(duration || '15', 10);

  // Cerca celle corrispondenti nel DOM (che hanno data-date corretto)
  const cells = document.querySelectorAll(`.selectable-cell[data-operator-id="${opId}"][data-date="${date}"]`);
  cells.forEach(cell => {
    const ch = parseInt(cell.getAttribute('data-hour'), 10);
    const cm = parseInt(cell.getAttribute('data-minute'), 10);
    if (isNaN(ch) || isNaN(cm)) return;
    const cellStart = ch * 60 + cm;
    
    if (cellStart >= startTotal && cellStart < endTotal) {
      addCutSourceHighlight(cell);
      
      // Handle overlay
      if (width && width !== '100%') {
        cell.style.position = 'relative';
        let ov = cell.querySelector('.cut-source-overlay');
        if (!ov) {
          ov = document.createElement('div');
          ov.className = 'cut-source-overlay';
          ov.style.position = 'absolute';
          ov.style.inset = '0 0 0 0';
          ov.style.pointerEvents = 'none';
          ov.style.boxSizing = 'border-box';
          ov.style.zIndex = '0';
          ov.style.border = 'none';
          cell.appendChild(ov);
        }
        ov.style.width = width;
        ov.style.left = left || '0%';
      }
    }
  });
}

// NEW: evidenzia tutte le celle coperte dal blocco (durata > 15 min)
function addCutSourceHighlightRange(block) {
  if (!block) return;
  const opId = block.getAttribute('data-operator-id');
  const date = block.getAttribute('data-date') || window.selectedAppointmentDate || (typeof selectedDate !== 'undefined' ? selectedDate : '');
  const startHour = block.getAttribute('data-hour');
  const startMinute = block.getAttribute('data-minute');
  const duration = block.getAttribute('data-duration');
  const width = block.getAttribute('data-width') || block.style.width || '100%';
  const left = block.getAttribute('data-left') || block.style.left || '0%';
  
  addCutSourceHighlightFromData(opId, date, startHour, startMinute, duration, width, left);
}

function cutAsNewPseudoBlock(block) {
  if (!block) return;
  const appointmentId = block.getAttribute('data-appointment-id');
  if (!appointmentId) {
    console.error("ID appuntamento mancante");
    return;
  }

  // Evidenzia tutte le celle coperte dal blocco
  try { addCutSourceHighlightRange(block); } catch (_) {}

  const backup = {
    appointment_id: String(appointmentId),
    client_id: block.getAttribute('data-client-id') || null,
    client_name: block.getAttribute('data-client-nome') || block.querySelector('.appointment-content .client-name a')?.textContent || '',
    service_id: block.getAttribute('data-service-id') || null,
    service_name: block.getAttribute('data-service-name') || block.querySelector('.appointment-content p:nth-child(2) strong')?.textContent || '',
    duration: parseInt(block.getAttribute('data-duration') || '15', 10),
    operator_id: block.getAttribute('data-operator-id') || null,
    hour: block.getAttribute('data-hour') || null,
    minute: block.getAttribute('data-minute') || null,
    appointment_date: block.getAttribute('data-date') || (typeof selectedDate !== 'undefined' ? selectedDate : ''),
    note: block.getAttribute('data-note') || '',
    colore: block.getAttribute('data-colore') || '',
    colore_font: block.getAttribute('data-colore_font') || '',
    status: parseInt(block.getAttribute('data-status') || '0', 10),
    // SAVE WIDTH/LEFT for highlight restore
    width: block.getAttribute('data-width') || block.style.width || '100%',
    left: block.getAttribute('data-left') || block.style.left || '0%'
  };
    copyAsNewPseudoBlock(block);
}

function restoreCutHighlights() {
  try {
    const cutBlocks = _loadCutBlocks();
    if (Array.isArray(cutBlocks)) {
      cutBlocks.forEach(bkp => {
        addCutSourceHighlightFromData(
          bkp.operator_id,
          bkp.appointment_date,
          bkp.hour,
          bkp.minute,
          bkp.duration,
          bkp.width,
          bkp.left
        );
      });
    }
  } catch(e) { console.warn('restoreCutHighlights failed', e); }
}

document.addEventListener('DOMContentLoaded', function() {
  restoreCutHighlights();
});

function copyAsNewPseudoBlock(block) {
  if (!block) return;
  
  // Ottieni i dati dell'appuntamento
  const clientId = block.getAttribute('data-client-id');
  const clientName = block.querySelector('.appointment-content .client-name a')?.textContent || "Cliente".trim();
  const serviceId = block.getAttribute('data-service-id');
  const serviceName = block.getAttribute('data-service-name') || block.querySelector('.appointment-content p:nth-child(2) strong')?.textContent || "Servizio";
  const duration = parseInt(block.getAttribute('data-duration'), 10) || 15;
  const color = block.getAttribute('data-colore') || '#FFFFFF';
  const note = block.getAttribute('data-note') || '';
  console.log("Nota estratta:", note);
  
  // Se si tratta di un blocco OFF (clientId e serviceId null/undefined/"")
  if (!clientId && !serviceId) {
    // RIMOSSO: controllo duplicati su note OFF
    // Crea sempre un nuovo pseudo-blocco OFF
    window.pseudoBlocks.unshift({
      clientId: null,
      clientName: "BLOCCO OFF",
      serviceId: null,
      serviceName: "Blocco OFF",
      tag: "OFF",
      duration: duration,
      color: color,
      fontColor: computeFontColor(color),
      note: note
    });
    window.commonPseudoBlockColor = color;
    renderPseudoBlocksList();
    saveNavigatorState();
    alert("Blocco OFF copiato nell'Appointment Navigator!");
    return;
  }

  // Ottieni il tag del servizio (importante per la visualizzazione)
  let serviceTag = serviceName;
  const fullServiceText = block.querySelector('.appointment-content p:nth-child(2) strong')?.textContent;
  if (fullServiceText && fullServiceText.includes(' - ')) {
    serviceTag = fullServiceText.split(' - ')[0].trim();
  }

  // Crea SEMPRE il nuovo pseudo-blocco (consenti duplicati)
  const newPseudoBlock = {
    clientId: clientId,
    clientName: clientName,
    serviceId: serviceId,
    serviceName: serviceName,
    tag: serviceTag,
    duration: duration,
    color: color,
    fontColor: computeFontColor(color),
    note: note
  };
  window.pseudoBlocks.unshift(newPseudoBlock);
  window.commonPseudoBlockColor = color;

  // SELEZIONA il cliente nel Navigator (necessario per aggiungere nuovi servizi)
  try {
    window.selectedClientIdNav = clientId || null;
    window.selectedClientNameNav = clientName || "";
  } catch(_) {}

  renderPseudoBlocksList();
  saveNavigatorState();

  const clientSearchInput = document.getElementById('clientSearchInputNav');
  const serviceSearchInput = document.getElementById('serviceInputNav');
  const clientResults = document.getElementById('clientResultsNav');
  const serviceResults = document.getElementById('serviceResultsNav');
  const selectedServicesList = document.getElementById('selectedServicesList');
  if (serviceSearchInput) serviceSearchInput.style.display = 'block';
  if (clientResults) clientResults.style.display = 'block';
  if (serviceResults) serviceResults.style.display = 'block';
  if (selectedServicesList) selectedServicesList.style.display = 'block';
  if (clientSearchInput) clientSearchInput.value = clientName.trim();
}

function addCutSourceHighlight(cell) {
  if (!cell || !cell.classList) return;
  cell.classList.add('cut-source');
  window.__cutSourceCellsSet = window.__cutSourceCellsSet || new Set();
  window.__cutSourceCellsSet.add(cell);
}
function clearCutSourceHighlights() {
  try {
    document.querySelectorAll('.selectable-cell.cut-source').forEach(c => c.classList.remove('cut-source'));
    if (window.__cutSourceCellsSet && typeof window.__cutSourceCellsSet.clear === 'function') {
      window.__cutSourceCellsSet.clear();
    }
  } catch (_) {}
}
window.addCutSourceHighlight = addCutSourceHighlight;
window.clearCutSourceHighlights = clearCutSourceHighlights;

// NEW: evidenzia tutte le celle coperte dal blocco (durata > 15 min)
function addCutSourceHighlightRange(block) {
  if (!block) return;
  const opId = block.getAttribute('data-operator-id');
  const date = block.getAttribute('data-date') || window.selectedAppointmentDate || selectedDate;
  const startHour = parseInt(block.getAttribute('data-hour'), 10);
  const startMinute = parseInt(block.getAttribute('data-minute'), 10);
  const duration = parseInt(block.getAttribute('data-duration') || '15', 10);
  if (isNaN(startHour) || isNaN(startMinute) || isNaN(duration)) return;

  const startTotal = startHour * 60 + startMinute;
  const endTotal = startTotal + duration;

  const cells = document.querySelectorAll(`.selectable-cell[data-operator-id="${opId}"][data-date="${date}"]`);
  cells.forEach(cell => {
    const ch = parseInt(cell.getAttribute('data-hour'), 10);
    const cm = parseInt(cell.getAttribute('data-minute'), 10);
    if (isNaN(ch) || isNaN(cm)) return;
    const cellStart = ch * 60 + cm;
    // ogni cella rappresenta un quarter [cellStart, cellStart+15)
    if (cellStart >= startTotal && cellStart < endTotal) {
      addCutSourceHighlight(cell);
      // Se il blocco è dimezzato (width 50%) replica la larghezza sull’highlight
      const w = block.getAttribute('data-width') || block.style.width || '100%';
      const l = block.getAttribute('data-left') || block.style.left || '0%';
      if (w && w !== '100%') {
        cell.style.position = 'relative';
        if (!cell.querySelector('.cut-source-overlay')) {
          const ov = document.createElement('div');
          ov.className = 'cut-source-overlay';
          ov.style.position = 'absolute';
          ov.style.inset = '0 0 0 0';
          ov.style.pointerEvents = 'none';
          ov.style.boxSizing = 'border-box';
          ov.style.width = w;
          ov.style.left = l;
          ov.style.right = 'auto';
          ov.style.zIndex = '0';      // sotto al puntatore
          ov.style.border = 'none';   // rimuove bordo arancione
          cell.appendChild(ov);
        } else {
          const ov = cell.querySelector('.cut-source-overlay');
          ov.style.width = w;
          ov.style.left = l;
          ov.style.zIndex = '0';
          ov.style.border = 'none';
        }
      }
    }
  });
}

function cutAsNewPseudoBlock(block) {
  if (!block) return;
  const appointmentId = block.getAttribute('data-appointment-id');
  if (!appointmentId) {
    console.error("ID appuntamento mancante");
    return;
  }

  // Evidenzia tutte le celle coperte dal blocco
  try { addCutSourceHighlightRange(block); } catch (_) {}

  const backup = {
    appointment_id: String(appointmentId),
    client_id: block.getAttribute('data-client-id') || null,
    client_name: block.getAttribute('data-client-nome') || block.querySelector('.appointment-content .client-name a')?.textContent || '',
    service_id: block.getAttribute('data-service-id') || null,
    service_name: block.getAttribute('data-service-name') || block.querySelector('.appointment-content p:nth-child(2) strong')?.textContent || '',
    duration: parseInt(block.getAttribute('data-duration') || '15', 10),
    operator_id: block.getAttribute('data-operator-id') || null,
    hour: block.getAttribute('data-hour') || null,
    minute: block.getAttribute('data-minute') || null,
    appointment_date: block.getAttribute('data-date') || selectedDate,
    note: block.getAttribute('data-note') || '',
    colore: block.getAttribute('data-colore') || '',
    colore_font: block.getAttribute('data-colore_font') || '',
    status: parseInt(block.getAttribute('data-status') || '0', 10)
  };

  copyAsNewPseudoBlock(block);

  try {
    if (!Array.isArray(window.pseudoBlocks)) window.pseudoBlocks = [];
    if (window.pseudoBlocks.length > 0) {
      const pseudo = window.pseudoBlocks[0];
      pseudo._origin_appointment_id = String(appointmentId);
      pseudo._origin_backup = backup;
      try { saveNavigatorState(); } catch (e) {}
    }
  } catch (e) {
    console.warn('cutAsNewPseudoBlock: non è stato possibile marcare il pseudoblocco con origin_backup', e);
  }

  try {
    if (typeof saveCutBlockBackup === 'function') {
      saveCutBlockBackup(backup);
    } else {
      const arr = JSON.parse(localStorage.getItem('cutBlocks') || '[]');
      arr.push(backup);
      localStorage.setItem('cutBlocks', JSON.stringify(arr));
    }
  } catch (e) {
    console.warn('cutAsNewPseudoBlock: failed to persist backup', e);
  }

  const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
  fetch(`/calendar/delete/${appointmentId}`, {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken
    }
  })
  .then(response => {
    if (response.ok) {
      block.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(elem => {
        const tooltipInstance = bootstrap.Tooltip.getInstance(elem);
        if (tooltipInstance) tooltipInstance.dispose();
      });
      const notePopup = document.querySelector(`.note-popup[data-appointment-id="${appointmentId}"]`);
      if (notePopup) notePopup.remove();
      block.remove();
      arrangeBlocksInCell(block.parentNode);
      saveNavigatorState();
    } else {
      return response.text().then(text => { 
        throw new Error(text || "Errore durante l'eliminazione");
      });
    }
  })
  .catch(error => {
    console.error("Errore:", error);
    alert(error.message);
  });
}

function copyAndPasteBlockOff() {
  // Aggiungi un gestore di eventi a tutti i blocchi OFF esistenti
  document.querySelectorAll('.appointment-block.note-off').forEach(block => {
    // Aggiungi un pulsante di copia direttamente nei blocchi OFF
    const copyBtn = document.createElement('button');
    copyBtn.className = 'btn-popup copy-off-block';
    const icon = document.createElement('i');
    icon.className = 'bi bi-files';
    icon.style.fontSize = '1.5em';
    icon.style.color = 'black';
    copyBtn.appendChild(icon);
    copyBtn.title = 'Copia blocco OFF';
    copyBtn.style.position = 'absolute';
    copyBtn.style.top = '4px';
    copyBtn.style.right = '4px';
    copyBtn.style.backgroundColor = 'transparent';
    
    // Evita duplicati
    if (!block.querySelector('.copy-off-block')) {
      block.appendChild(copyBtn);
    }
    
    // Gestore per il click sul pulsante di copia
    copyBtn.addEventListener('click', function(e) {
      e.stopPropagation();
      // Salva i dati del blocco OFF in localStorage
      const note = block.getAttribute('data-note') || '';
      const duration = block.getAttribute('data-duration') || '15';
      const color = block.getAttribute('data-colore') || '#FFFFFF';
      const offBlockData = {
        type: 'OFF_BLOCK',
        note: note,
        duration: duration,
        color: color
      };
      localStorage.setItem('copiedOffBlock', JSON.stringify(offBlockData));
      document.body.classList.add('paste-off-block-mode');
      // Feedback visivo
      let msg = document.createElement('div');
      msg.textContent = 'blocco OFF copiato';
      msg.style.position = 'fixed';
      msg.style.top = '60px';
      msg.style.left = '50%';
      msg.style.transform = 'translateX(-50%)';
      msg.style.background = '#222';
      msg.style.color = '#fff';
      msg.style.padding = '10px 24px';
      msg.style.borderRadius = '8px';
      msg.style.zIndex = '99999';
      document.body.appendChild(msg);
      setTimeout(() => msg.remove(), 400);
    });
  });
  
  // Gestisci il click sulle celle per incollare il blocco OFF
  document.querySelectorAll('.selectable-cell').forEach(cell => {
    cell.addEventListener('click', function(e) {
      
    // Verifica se siamo in modalità incolla blocco OFF
    if (document.body.classList.contains('paste-off-block-mode')) {
      e.stopPropagation(); // Impedisci altri handler
      e.preventDefault();

      // Recupera i dati del blocco OFF
      const offBlockDataStr = localStorage.getItem('copiedOffBlock');
      if (!offBlockDataStr) {
        document.body.classList.remove('paste-off-block-mode');
        return;
      }

      const offBlockData = JSON.parse(offBlockDataStr);

      // Verifica che sia effettivamente un blocco OFF
      if (offBlockData.type !== 'OFF_BLOCK') {
        document.body.classList.remove('paste-off-block-mode');
        return;
      }
        
        // Raccogli i dati necessari per creare il nuovo blocco OFF
        const operatorId = cell.getAttribute('data-operator-id');
        const hour = cell.getAttribute('data-hour');
        const minute = cell.getAttribute('data-minute');
        const date = cell.getAttribute('data-date') || selectedDate;
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        
        
      // Prepara i dati per la richiesta
      const payload = {
        client_id: null,
        service_id: null,
        operator_id: operatorId,
        appointment_date: date,
        start_time: `${hour}:${minute}`,
        duration: offBlockData.duration,
        colore: offBlockData.color,
        note: offBlockData.note,
        titolo: offBlockData.note
      };

      // Invia la richiesta per creare il nuovo blocco OFF
      fetch('/calendar/create', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify(payload)
      })
      .then(resp => {
        if (!resp.ok) {
          return resp.json().then(err => {
            throw new Error(err.error || "Errore nella creazione del blocco OFF");
          });
        }
        return resp.json();
      })
      .then(appointment => {
        console.log("Blocco OFF creato:", appointment);
        document.body.classList.remove('paste-off-block-mode');
        location.reload();
      })
      .catch(err => {
        console.error(err);
        alert("Errore nella creazione del blocco OFF: " + err.message);
        document.body.classList.remove('paste-off-block-mode');
      });
    }
  }, true);
});
}

// Chiama la funzione all'avvio per inizializzare i comportamenti
document.addEventListener('DOMContentLoaded', copyAndPasteBlockOff);

// Aggiungi osservatore per inizializzare i pulsanti anche sui blocchi aggiunti dinamicamente
const offBlockObserver = new MutationObserver((mutations) => {
  mutations.forEach(mutation => {
    if (mutation.addedNodes && mutation.addedNodes.length > 0) {
      mutation.addedNodes.forEach(node => {
        if (node.nodeType === 1 && node.classList && node.classList.contains('note-off')) {
          copyAndPasteBlockOff();
        }
      });
    }
  });
});

// Osserva le modifiche al DOM dopo che è stato caricato
document.addEventListener('DOMContentLoaded', () => {
  offBlockObserver.observe(document.body, {
    childList: true,
    subtree: true
  });
});

document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.appointment-block.note-off').forEach(block => {
    if (!block.querySelector('.delete-off-block')) {
      const deleteBtn = document.createElement('button');
      deleteBtn.className = 'btn-popup delete-off-block';
      const icon = document.createElement('i');
      icon.className = 'bi bi-trash';
      icon.style.fontSize = '1.5em';
      icon.style.color = 'black';
      deleteBtn.appendChild(icon);
      deleteBtn.title = 'Elimina blocco OFF';
      deleteBtn.style.position = 'absolute';
      deleteBtn.style.top = '5px';
      deleteBtn.style.left = '4px';
      deleteBtn.style.backgroundColor = 'transparent'
      
      // Aggiungi il pulsante al blocco OFF
      block.appendChild(deleteBtn);
      
      // Gestione del click sul pulsante di elimina
      deleteBtn.addEventListener('click', function(e) {
        e.stopPropagation();
        
        // Se il blocco ha un ID, elimina anche dal database
        const appointmentId = block.getAttribute('data-appointment-id');
        deleteBtn.disabled = true;
        if (appointmentId) {
          deleteAppointment(appointmentId)
            .then(() => {
              // aggiorna i dati dal server senza mostrare reload visibile
              if (typeof fetchCalendarData === 'function') fetchCalendarData();
            })
            .catch(err => {
              console.error('Eliminazione blocco OFF fallita:', err);
              deleteBtn.disabled = false;
              alert('Eliminazione fallita: ' + (err.message || err));
            });
        }
        
        // Rimuovi il blocco dagli pseudo-blocchi, se presente
if (window.pseudoBlocks && Array.isArray(window.pseudoBlocks)) {
  const index = window.pseudoBlocks.findIndex(pb =>
    !pb.clientId && !pb.serviceId &&
    pb.note === (block.getAttribute('data-note') || "")
  );
  if (index !== -1) {
    window.pseudoBlocks.splice(index, 1);
    renderPseudoBlocksList();
  }
}
        
        // Rimuovi il blocco dal DOM
        if (!appointmentId) {
          block.remove();
        }
      });
    }
  });
});

document.addEventListener('DOMContentLoaded', function() {
  // Per ogni blocco OFF, aggiungi l'elemento titolo se non esiste già
  document.querySelectorAll('.appointment-block.note-off').forEach(block => {
    try {
      const fullText = String(block.getAttribute('data-note') || block.getAttribute('data-titolo') || 'BLOCCO OFF');
      const MAX_CHARS = 12;
      const displayText = fullText.length > MAX_CHARS ? (fullText.slice(0, MAX_CHARS) + '...') : fullText;

      let titleEl = block.querySelector('.off-block-title');
      if (!titleEl) {
        titleEl = document.createElement('span');
        titleEl.className = 'off-block-title';
        block.appendChild(titleEl);
      }

      // Testo visualizzato (troncato)
      titleEl.textContent = displayText;
      // Conserva il testo completo per modal/tooltip/debug
      titleEl.setAttribute('data-full-note', fullText);
      titleEl.setAttribute('title', fullText);

      // Stili per forzare ellipsis e centro, compatibili con layout esistente
      titleEl.style.position = 'absolute';
      titleEl.style.top = '50%';
      titleEl.style.left = '50%';
      titleEl.style.transform = 'translate(-50%, -50%)';
      titleEl.style.fontSize = '20px';
      titleEl.style.fontWeight = 'bold';
      titleEl.style.color = '#474646';
      titleEl.style.textAlign = 'center';
      titleEl.style.textShadow = '1px 1px 2px rgba(17,16,16,0.2)';
      titleEl.style.cursor = 'pointer';
      titleEl.style.zIndex = '1000';
      titleEl.style.pointerEvents = 'auto';

      // IMPORTANT: constraints per evitare overflow del testo oltre i bordi del blocco
      titleEl.style.whiteSpace = 'nowrap';
      titleEl.style.overflow = 'hidden';
      titleEl.style.textOverflow = 'ellipsis';
      // lascia un piccolo padding interno e limita la larghezza al contenitore
      titleEl.style.maxWidth = 'calc(100% - 12px)';
      titleEl.style.display = 'inline-block';
      titleEl.style.boxSizing = 'border-box';
      titleEl.style.padding = '0 2px';

      // Click sul titolo -> apre il modal con la nota completa
      // rimuovo listener duplicati prima di aggiungerne uno nuovo
      titleEl.removeEventListener('click', titleEl._offClickHandler);
      titleEl._offClickHandler = function (e) {
        e.stopPropagation();
        openNoteModal(block);
      };
      titleEl.addEventListener('click', titleEl._offClickHandler, true);

    } catch (err) {
      // Non bloccare l'esecuzione in caso di errore su un singolo blocco
      console.warn('init off-block-title failed for block', block, err);
    }
  });
});

function saveNavigatorState() {
  try {
    const selId = window.selectedClientIdNav ?? null;
    const selName = window.selectedClientNameNav ?? "";
    const pseudoBlocksData = JSON.stringify(window.pseudoBlocks || []);
    const clientSearchValue = document.getElementById('clientSearchInputNav')?.value || "";
    const serviceSearchValue = document.getElementById('serviceInputNav')?.value || "";

    // Salva sempre i campi, anche se pseudoBlocks è vuoto
    localStorage.setItem('selectedClientIdNav', selId === null ? '' : String(selId));
    localStorage.setItem('selectedClientNameNav', selName);
    localStorage.setItem('pseudoBlocksData', pseudoBlocksData);
    localStorage.setItem('clientSearchInputNav', clientSearchValue);
    localStorage.setItem('serviceInputNav', serviceSearchValue);
  } catch (e) {
    console.warn('saveNavigatorState failed', e);
  }
}

function restoreNavigatorState() {
  try {
    const rawSelId = localStorage.getItem('selectedClientIdNav') || '';
    const rawSelName = localStorage.getItem('selectedClientNameNav') || '';
    const rawPseudo = localStorage.getItem('pseudoBlocksData') || '[]';
    const clientSearchValue = localStorage.getItem('clientSearchInputNav') || '';
    const serviceSearchValue = localStorage.getItem('serviceInputNav') || '';

    // Ripristina selected client (id o null) e nome selezionato
    window.selectedClientIdNav = rawSelId === '' ? null : rawSelId;
    window.selectedClientNameNav = rawSelName || '';

    // Ripristina i campi input visivi: preferisci nome selezionato, altrimenti il valore digitato
    const clientInput = document.getElementById('clientSearchInputNav');
    if (clientInput) {
      if (window.selectedClientIdNav) {
        // Se cliente selezionato, usa solo il nome (senza cellulare) per evitare problemi di ricerca
        const fullName = window.selectedClientNameNav || '';
        const nameOnly = fullName.split(' - ')[0] || fullName;
        clientInput.value = nameOnly;
      } else {
        clientInput.value = clientSearchValue || '';
      }
    }
    const serviceInput = document.getElementById('serviceInputNav');
    if (serviceInput) serviceInput.value = serviceSearchValue || '';

    // Ripristina solo i pseudoBlocks salvati; NON creare client-only per default
    let parsed = [];
    try { parsed = JSON.parse(rawPseudo); } catch (e) { parsed = []; console.warn('restoreNavigatorState: bad pseudoBlocksData', e); }
    window.pseudoBlocks = Array.isArray(parsed) ? parsed : [];

    // Evita di aprire il dropdown client se c'è un cliente selezionato (previene "Nessun risultato" stuck)
    const clientResults = document.getElementById('clientResultsNav');
    if (clientResults) { clientResults.innerHTML = ''; clientResults.style.display = 'none'; }

    // Se c'è un cliente selezionato, mantienilo e prepara subito il campo servizi:
    if (window.selectedClientIdNav) {
      // mostra il campo servizio
      if (serviceInput) {
        serviceInput.style.display = 'block';
      }

      // PATCH: Focus e caricamento servizi SOLO se NON ci sono già pseudoblocchi
      if (!window.pseudoBlocks || window.pseudoBlocks.length === 0) {
        // Il focus farà scattare l'onfocus HTML (loadFrequentServices), ma noi carichiamo anche quelli specifici
        if (serviceInput) { try { serviceInput.focus(); } catch (e) {} }

        // carica i servizi per il cliente (preferisci last-services)
        try {
          if (typeof loadLastServicesForClient === 'function') {
            loadLastServicesForClient(window.selectedClientIdNav);
          } else if (typeof loadFrequentServices === 'function') {
            loadFrequentServices();
          }
        } catch (e) {
          console.warn('restoreNavigatorState: load services failed', e);
          if (typeof loadFrequentServices === 'function') loadFrequentServices();
        }

        // mostra contenitori servizi se presenti
        const serviceResults = document.getElementById('serviceResultsNav');
        if (serviceResults) serviceResults.style.display = 'block';
      }

      const selectedServicesList = document.getElementById('selectedServicesList');
      if (selectedServicesList && window.pseudoBlocks && window.pseudoBlocks.length > 0) selectedServicesList.style.display = 'block';
    } else {

      // Nessun cliente selezionato: se c'è testo digitato, valuta se riaprire il client dropdown
      if (clientInput && clientInput.value && clientInput.value.trim()) {
        const q = clientInput.value.trim();

        // Se ci sono pseudoblocchi originati da "taglia", NON aprire il popup risultati:
        const hasCutOrigin = Array.isArray(window.pseudoBlocks) &&
                             window.pseudoBlocks.some(pb => pb && (pb._origin_appointment_id || pb._origin_backup));

        if (q.length >= 3 && !hasCutOrigin) {
          // comportamento normale: ricerca e mostra risultati
          try { handleClientSearchNav(q); } catch (e) { console.warn('handleClientSearchNav missing', e); }
        } else {
          // Non aprire il dropdown quando il valore proviene da un cut; altrimenti mostra hint per <3 char
          if (!hasCutOrigin) {
            if (clientResults) {
              clientResults.innerHTML = '';
              const hint = document.createElement('div');
              hint.className = 'dropdown-item text-muted';
              hint.textContent = 'Digita almeno 3 caratteri per cercare...';
              clientResults.appendChild(hint);
              clientResults.style.display = 'block';
            }
          } else {
            // nascondi eventuale popup residuo quando il valore è stato ripristinato da un taglio
            if (clientResults) {
              clientResults.innerHTML = '';
              clientResults.style.display = 'none';
            }
          }
        }
      }
    }

    // Render dei pseudoBlocks solo se ce ne sono
    try { renderPseudoBlocksList(); } catch (e) { /* ignore */ }

        try {
      const cutBlocks = (typeof _loadCutBlocks === 'function') ? _loadCutBlocks() : JSON.parse(localStorage.getItem('cutBlocks') || '[]');
      const pseudo = Array.isArray(window.pseudoBlocks) ? window.pseudoBlocks : [];
      if (pseudo.length === 0 && Array.isArray(cutBlocks) && cutBlocks.length > 0) {
        console.log(`restoreNavigatorState: ${cutBlocks.length} cutBlocks trovati, avvio restoreCutBlocks() in background.`);
        // Non await: operazione in background, restoreCutBlocks rimuoverà cutBlocks se andata a buon fine
        if (typeof restoreCutBlocks === 'function') {
          restoreCutBlocks().catch(err => console.error('restoreCutBlocks failed', err));
        } else {
          // fallback: lascia il record per il futuro
          console.warn('restoreCutBlocks non definita');
        }
      }
    } catch (e) {
      console.warn('restoreNavigatorState cutBlocks check failed', e);
    }

    // Non sovrascrivere persisted state: salva di nuovo per assicurare coerenza
    try { saveNavigatorState(); } catch (e) { /* ignore */ }
  } catch (e) {
    console.warn('restoreNavigatorState failed', e);
  }
}

function rgbToHex(rgb) {
  const result = rgb.match(/\d+/g);
  if (!result || result.length < 3) return "#ffffff";
  return "#" + result.slice(0, 3).map(x => {
      const hex = parseInt(x).toString(16);
      return hex.length === 1 ? "0" + hex : hex;
  }).join('');
}

document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.appointment-block:not(.note-off)').forEach(block => {
    let deleteBtn = block.querySelector('.delete-appointment-block');
    const rawBgColor = block.getAttribute('data-colore') || window.getComputedStyle(block).backgroundColor || '#fff';
    const bgColor = rawBgColor.startsWith('#') ? rawBgColor : rgbToHex(rawBgColor);
    const iconColor = computeFontColor(bgColor);

    if (!deleteBtn) {
      deleteBtn = document.createElement('button');
      deleteBtn.className = 'btn-popup delete-appointment-block';
      deleteBtn.style.position = 'absolute';
      deleteBtn.style.top = '7px';
      deleteBtn.style.left = '4px';
      deleteBtn.style.backgroundColor = 'transparent';
      block.appendChild(deleteBtn);
    }

    const delIcon = document.createElement('i');
    delIcon.className = 'bi bi-trash';
    delIcon.style.fontSize = '1.5em';
    delIcon.style.color = iconColor;
    // rimuove contenuto precedente e aggiunge l'icona
    deleteBtn.innerHTML = '';
    deleteBtn.appendChild(delIcon);

    deleteBtn.onmouseenter = function() {
      const popupBtns = block.querySelector('.popup-buttons');
      if (popupBtns) popupBtns.style.display = 'none';
    };
    deleteBtn.onmouseleave = function() {
      const popupBtns = block.querySelector('.popup-buttons');
      if (popupBtns) popupBtns.style.display = '';
    };

    deleteBtn.onclick = function(e) {
      e.stopPropagation();
      const appointmentId = block.getAttribute('data-appointment-id');
      if (appointmentId) {
        deleteAppointment(appointmentId);
      }
    };
  });
});

// ===============================
// AUTOCLOSE APPOINTMENT NAVIGATOR DOPO 10 SECONDI DI INATTIVITÀ
// ===============================

// Funzione per "contrarre" il navigator: mostra solo il campo "Cerca Cliente"
function collapseAppointmentNavigator() {
  const serviceInput = document.getElementById('serviceInputNav');
  const clientResults = document.getElementById('clientResultsNav');
  const serviceResults = document.getElementById('serviceResultsNav');
  const selectedServicesList = document.getElementById('selectedServicesList');
  if (serviceInput) serviceInput.style.display = 'none';
  if (clientResults) clientResults.style.display = 'none';
  if (serviceResults) serviceResults.style.display = 'none';
  if (selectedServicesList) selectedServicesList.style.display = 'none';
}

// Chiudi il navigator anche cliccando fuori, se i campi sono vuoti
document.addEventListener('mousedown', function(event) {
  const nav = document.getElementById('appointmentNavigator');
  if (!nav) return;
  // Se il click è fuori dal navigator
  if (!nav.contains(event.target)) {
    const clientInput = document.getElementById('clientSearchInputNav');
    const serviceInput = document.getElementById('serviceInputNav');
    const pseudoBlocks = window.pseudoBlocks || [];
    if (
      clientInput && serviceInput &&
      clientInput.value.trim() === '' &&
      serviceInput.value.trim() === '' &&
      pseudoBlocks.length === 0
    ) {
      collapseAppointmentNavigator();
    }
  }
});

// Funzione per espandere il navigator (mostra tutti i campi)
function expandAppointmentNavigator() {
  const serviceInput = document.getElementById('serviceInputNav');
  const clientResults = document.getElementById('clientResultsNav');
  const serviceResults = document.getElementById('serviceResultsNav');
  const selectedServicesList = document.getElementById('selectedServicesList');
  if (serviceInput) serviceInput.style.display = 'block';
  if (clientResults) clientResults.style.display = 'block';
  if (serviceResults) serviceResults.style.display = 'block';
  if (selectedServicesList) selectedServicesList.style.display = 'block';
}

// Timer globale
let navigatorTimeout = null;

// Reset del timer e chiusura se i campi sono vuoti
function resetNavigatorTimeout() {
  clearTimeout(navigatorTimeout);
  navigatorTimeout = setTimeout(() => {
      const clientInput = document.getElementById('clientSearchInputNav');
      const serviceInput = document.getElementById('serviceInputNav');
      const pseudoBlocks = window.pseudoBlocks || [];
      if (
          clientInput && serviceInput &&
          clientInput.value.trim() === '' &&
          serviceInput.value.trim() === '' &&
          pseudoBlocks.length === 0
      ) {
          collapseAppointmentNavigator();
      }
  }, 10000);
}

// Espansione navigator e attacco dei listener per il reset del timer
function openAppointmentNavigator() {
  expandAppointmentNavigator();
  resetNavigatorTimeout();
  const nav = document.getElementById('appointmentNavigator');
  if (nav && !nav.dataset.listenersAdded) {
      nav.addEventListener('mousemove', resetNavigatorTimeout);
      nav.addEventListener('keydown', resetNavigatorTimeout);
      nav.addEventListener('mousedown', resetNavigatorTimeout);
      nav.addEventListener('touchstart', resetNavigatorTimeout);
      nav.dataset.listenersAdded = "true";
  }
}

// All'avvio pagina: mostra solo il campo cliente
document.addEventListener('DOMContentLoaded', collapseAppointmentNavigator);

// Al click sul campo "Cerca Cliente..." espandi il navigator e attiva autoclose
document.addEventListener('DOMContentLoaded', function() {
  const clientSearchInput = document.getElementById('clientSearchInputNav');
  if (clientSearchInput) {
      clientSearchInput.addEventListener('click', openAppointmentNavigator);
      clientSearchInput.addEventListener('input', resetNavigatorTimeout);
  }


      // NEW: se l'utente svuota manualmente il campo, rimuovi la selezione persistente
      clientSearchInput.addEventListener('input', function () {
        try {
          const v = (this.value || '').toString().trim();

          // Se campo vuoto -> rimuovi la selezione persistente e salva lo stato
          if (v === '') {
            if (window.selectedClientIdNav || window.selectedClientNameNav) {
              window.selectedClientIdNav = null;
              window.selectedClientNameNav = '';
              try {
                localStorage.removeItem('selectedClientIdNav');
                localStorage.removeItem('selectedClientNameNav');
                localStorage.setItem('clientSearchInputNav', '');
                if (typeof saveNavigatorState === 'function') saveNavigatorState();
              } catch (err) { console.warn('clear persisted client failed', err); }
            }
            // anche nascondi risultati se visibili
            const res = document.getElementById('clientResultsNav');
            if (res) { res.innerHTML = ''; res.style.display = 'none'; }
            return;
          }

          // Se l'utente sta digitando qualcosa che NON corrisponde al client selezionato,
          // invalida la selezione precedente per evitare ripopolamento dopo refresh.
          const selectedName = (window.selectedClientNameNav || '').toString().split(' - ')[0] || '';
          if (window.selectedClientIdNav && selectedName && v !== selectedName) {
            window.selectedClientIdNav = null;
            window.selectedClientNameNav = '';
            try {
              localStorage.removeItem('selectedClientIdNav');
              localStorage.removeItem('selectedClientNameNav');
              if (typeof saveNavigatorState === 'function') saveNavigatorState();
            } catch (err) { console.warn('invalidate persisted client failed', err); }
          }

          // aggiorna il clientSearchInputNav persistente (consistenza)
          try { localStorage.setItem('clientSearchInputNav', v); } catch(e){/*ignore*/}

        } catch (e) {
          console.warn('clientSearchInputNav input handler error', e);
        }
      }, true);
      
  const serviceInput = document.getElementById('serviceInputNav');
  if (serviceInput) {
      serviceInput.addEventListener('input', resetNavigatorTimeout);
  }
  const nav = document.getElementById('appointmentNavigator');
  if (nav) {
      nav.addEventListener('mousemove', resetNavigatorTimeout);
      nav.addEventListener('keydown', resetNavigatorTimeout);
      nav.addEventListener('mousedown', resetNavigatorTimeout);
      nav.addEventListener('touchstart', resetNavigatorTimeout);
  }
});

// Nascondi il campo cerca cliente quando si apre il modal "Aggiungi Cliente"
document.addEventListener('DOMContentLoaded', function() {
  var addClientModal = document.getElementById('AddClientModal');
  var clientSearchInputContainer = document.getElementById('clientSearchInputContainer');
  if (addClientModal && clientSearchInputContainer) {
      addClientModal.addEventListener('show.bs.modal', function () {
          clientSearchInputContainer.style.visibility = 'hidden';
      });
      addClientModal.addEventListener('hidden.bs.modal', function () {
          clientSearchInputContainer.style.visibility = 'visible';
      });
  }
});

document.addEventListener('shown.bs.tooltip', function (event) {
  const trigger = event.target;
  if (trigger.classList.contains('btn-popup')) {
    // Bootstrap inserisce il tooltip in fondo al body
    const tooltips = document.querySelectorAll('.tooltip.show');
    tooltips.forEach(tooltip => {
      if (tooltip && (tooltip.classList.contains('bs-tooltip-top') || tooltip.classList.contains('bs-tooltip-bottom'))) {
        // Usa getBoundingClientRect per ottenere la posizione attuale
        const currentTop = parseInt(tooltip.style.top || window.getComputedStyle(tooltip).top || 0, 10);
        tooltip.style.top = (currentTop + 5) + 'px'; // Sposta 5px più in basso
      }
    });
  }
});

function procediAlPagamentoDaBlocchi(selectedBlocks) {
  if (!Array.isArray(selectedBlocks) || selectedBlocks.length === 0) return;

  const decodeHtml = (s) => { const t = document.createElement('textarea'); t.innerHTML = String(s || ''); return t.value; };

  const first = selectedBlocks[0];
  const clientId = first.dataset.clientId || '';
  const operatorId = first.dataset.operatorId || '';

  // PRIMA SCELTA: testo visibile nel blocco (già decodificato)
  const nameEl = first.querySelector('.appointment-content .client-name');
  const rawName = nameEl ? nameEl.textContent.trim() : '';
  // FALLBACK: data-* decodificati
  const clientNome = decodeHtml(first.dataset.clientNome || '');
  const clientCognome = decodeHtml(first.dataset.clientCognome || '');
  const clientName = rawName || `${clientNome} ${clientCognome}`.trim();

  const servizi = selectedBlocks
    .filter(b => b.getAttribute('data-status') !== "2")
    .map(block => {
      return {
        id: block.dataset.serviceId,
        nome: block.dataset.serviceName || '',
        prezzo: block.dataset.servicePrice || '',
        appointment_id: block.dataset.appointmentId
      };
    });

  const params = new URLSearchParams();
  params.set('servizi', JSON.stringify(servizi));
  if (clientId) params.set('client_id', clientId);
  if (clientName) params.set('client_name', clientName);
  if (operatorId) params.set('operator_id', operatorId);

  window.location.href = `/cassa?${params.toString()}`;
}

document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.appointment-block').forEach(function(block) {
    const status = parseInt(block.getAttribute('data-status') || '0', 10);
    if (status === 2) {
      block.classList.add('status-2');
      block.style.color = '';
      const content = block.querySelector('.appointment-content');
      if (content) content.style.color = '';
      // Rendi il cestino bianco
      const deleteBtn = block.querySelector('.delete-appointment-block i');
if (deleteBtn) {
  deleteBtn.style.setProperty('color', '#fff', 'important');
}
    }
  });
});

function aggiornaStatoAppuntamenti(ids) {
  fetch('/api/appointment_status', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids: ids })
  })
  .then(res => res.json())
  .then(data => {
    if (data.success) {
      data.appointments.forEach(app => {
        const blocco = document.querySelector('.appointment-block[data-appointment-id="' + app.id + '"]');
        if (blocco) {
          // Aggiorna la classe in base allo stato
          blocco.classList.remove('lampeggia', 'default', 'pagato', 'non_arrivato');
          if (app.stato == 1) {
            blocco.classList.add('lampeggia');
          } else if (app.stato == 0) {
            blocco.classList.add('default');
          } else if (app.stato == 2) {
            blocco.classList.add('pagato');
          } else if (app.stato == 3) {
            blocco.classList.add('non_arrivato');
          }
        }
      });
    }
  });
}

document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.btn-popup.whatsapp-btn').forEach(function(btn) {
    btn.addEventListener('click', async function(e) {
      e.stopPropagation();

      // FONTE UNICA: blocco genitore del bottone
      const block = btn.closest('.appointment-block');
      // Prendi i dati dal bottone come fallback
      let nome = btn.getAttribute('data-client-nome') || '';
      let cellulare = btn.getAttribute('data-client-cellulare') || '';
      let data = btn.getAttribute('data-date') || '';
      let hour = btn.getAttribute('data-hour') || '';
      let minute = btn.getAttribute('data-minute') || '';
      hour = hour.toString().padStart(2, '0');
      minute = minute.toString().padStart(2, '0');
      let ora = (hour && minute) ? `${hour}:${minute}` : '';

      // Ricava sempre appointmentId dal bottone o dal blocco
      let appointmentId = btn.getAttribute('data-appointment-id') || (block ? block.getAttribute('data-appointment-id') : '') || '';

      // Gruppo contiguo e normalizzazione orario di partenza
      let groupBlocks = [];
      if (block) {
        groupBlocks = (typeof getRelevantBlocks === 'function') ? getRelevantBlocks(block) : [block];
        if (groupBlocks.length > 0) {
          groupBlocks.sort((a, b) => {
            const aStart = (parseInt(a.getAttribute('data-hour'), 10) || 0) * 60 + (parseInt(a.getAttribute('data-minute'), 10) || 0);
            const bStart = (parseInt(b.getAttribute('data-hour'), 10) || 0) * 60 + (parseInt(b.getAttribute('data-minute'), 10) || 0);
            return aStart - bStart;
          });
          const parentBlock = groupBlocks[0];
          data = parentBlock.getAttribute('data-date') || data;
          hour = (parentBlock.getAttribute('data-hour') || hour || '').toString().padStart(2, '0');
          minute = (parentBlock.getAttribute('data-minute') || minute || '').toString().padStart(2, '0');
          ora = (hour && minute) ? `${hour}:${minute}` : '';
          // Se mancava l'id sul bottone, usa quello del parent
          if (!appointmentId) appointmentId = parentBlock.getAttribute('data-appointment-id') || '';
        }
      }

      let servizi_text = '';
      try {
        if (block) {
          // id appuntamenti dal gruppo (ordinati)
          const blocksForServices = (groupBlocks.length ? groupBlocks : [block]);
          const appointmentIds = Array.from(new Set(blocksForServices.map(b => b.getAttribute('data-appointment-id')).filter(Boolean)));
          const idsCsv = appointmentIds.join(',');

          // mappa appointmentId -> serviceId (estrai sempre data-service-id se presente)
          const apptToService = {};
          appointmentIds.forEach(id => {
            const b = document.querySelector(`.appointment-block[data-appointment-id="${id}"]`);
            if (b) {
              const svcId = b.getAttribute('data-service-id') || b.dataset?.serviceId || b.getAttribute('data-service') || '';
              if (svcId) apptToService[id] = String(svcId);
            }
          });

          // 1) Prova backend client_info (se clientId + appointment_ids)
          const clientId = block.getAttribute('data-client-id') || btn.getAttribute('data-client-id') || '';
          if (clientId && idsCsv) {
            try {
              const resp = await fetch(`/settings/api/client_info/${encodeURIComponent(clientId)}?appointment_ids=${encodeURIComponent(idsCsv)}`, { credentials: 'same-origin' });
              if (resp.ok) {
                const json = await resp.json();
                if (json && typeof json.servizi === 'string' && json.servizi.trim()) {
                  servizi_text = json.servizi.trim();
                }
              } else {
                console.warn('client_info fetch failed', resp.status, resp.statusText);
              }
            } catch (err) {
              console.warn('client_info fetch error', err);
            }
          }

          // 2) Se backend non ha fornito servizi, prova a ottenere nomi servizi via service_id dal backend
          if (!servizi_text && Object.keys(apptToService).length > 0) {
            try {
              const uniqueSvcIds = Array.from(new Set(Object.values(apptToService))).filter(Boolean);
              if (uniqueSvcIds.length) {
                const resp2 = await fetch(`/settings/api/services_by_ids?ids=${encodeURIComponent(uniqueSvcIds.join(','))}`, { credentials: 'same-origin' });
                if (resp2.ok) {
                  const json2 = await resp2.json();
                  const servicesMap = (json2 && json2.services) ? json2.services : {};
                  // ricostruisci labels nell'ordine degli appointmentIds
                  const labels = [];
                  appointmentIds.forEach(id => {
                    const sid = apptToService[id];
                    if (sid && servicesMap[sid]) {
                      const svcObj = servicesMap[sid];
                      const nome = (svcObj.nome || "").trim();
                      const tag = (svcObj.tag || "").trim();
                      if (nome) labels.push(nome);
                      else if (tag) labels.push(tag);
                    }
                  });
const ordered = labels.filter(Boolean);
if (ordered.length) servizi_text = ordered.map(s => `• ${s}`).join('\n');
                } else {
                  console.warn('services_by_ids fetch failed', resp2.status, resp2.statusText);
                }
              }
            } catch (err) {
              console.warn('services_by_ids fetch error', err);
            }
          }

          // 3) Ultima risorsa: estrai dai blocchi DOM i testi visibili (se ancora vuoto)
          if (!servizi_text) {
            const labels = [];
            appointmentIds.forEach(id => {
              const b = document.querySelector(`.appointment-block[data-appointment-id="${id}"]`);
              if (!b) return;
              // cerca campi visibili/attributi che più probabilmente contengono il nome completo
              const candidates = [
                b.dataset?.serviceName, b.dataset?.servizioNome, b.dataset?.servizio_nome, b.getAttribute('data-service-name'),
                b.getAttribute('data-service-nome'), b.getAttribute('data-service'), b.getAttribute('data-service-tag')
              ];
              let text = candidates.find(c => c && String(c).trim());
              if (!text) {
                const sel = b.querySelector('.service-name, .service-label, .appointment-content p strong, .appointment-content .service');
                if (sel && sel.textContent) text = sel.textContent.trim();
              }
              if (text) labels.push(String(text).trim());
            });
            const uniq2 = Array.from(new Set(labels.filter(Boolean)));
            if (uniq2.length) servizi_text = uniq2.map(s => `• ${s}`).join('\n');
          }
        }
      } catch (err) {
        console.warn('errore costruzione servizi_text:', err);
        servizi_text = '';
      }
  
      if (!cellulare) {
        alert('Numero di cellulare non disponibile per questo cliente.');
        return;
      }

      // Normalizzazione numero per WhatsApp:
      // - Inizia con '+': non modificare
      // - Inizia con '3': aggiungi '+39' davanti
      // - Inizia con cifra diversa da '3' e senza '+': aggiungi '+'
      // Poi per wa.me rimuovi solo il '+' dal path
      (function() {
        cellulare = String(cellulare || '').trim().replace(/\s+/g, '');
      })();
      let numeroNorm;
      if (cellulare.startsWith('+')) {
        numeroNorm = cellulare;
      } else if (/^\d/.test(cellulare)) {
        if (cellulare.startsWith('3')) {
          numeroNorm = '+39' + cellulare;
        } else {
          numeroNorm = '+' + cellulare;
        }
      } else {
        // Fallback: se non inizia con + o cifra, usa com'è
        numeroNorm = cellulare;
      }

      const nomeFmt = (typeof window.capitalizeName === 'function') ? capitalizeName(nome) : (nome || "");
      let testo = (window.whatsappMessageTemplate || "Buongiorno, ecco un memo per il tuo appuntamento del {{data}} alle ore {{ora}}. Ci vediamo presto! Sun Booking")
        .replace("{{nome}}", nomeFmt)
        .replace("{{data}}", data)
        .replace("{{ora}}", ora)
        .replace("{{servizi}}", servizi_text ? ("\n" + servizi_text + "\n") : "");

      const url = `https://wa.me/${numeroNorm.replace(/^\+/, '')}?text=${encodeURIComponent(testo)}`;

      // Copia negli appunti (best effort)
      if (navigator.clipboard && window.isSecureContext) {
        try { await navigator.clipboard.writeText(testo); } catch (_) {}
      } else {
        const temp = document.createElement('textarea');
        temp.value = testo; document.body.appendChild(temp); temp.select();
        try { document.execCommand('copy'); } catch (_) {}
        document.body.removeChild(temp);
      }

      window.open(url, '_blank');
    });
  });
});

function scrollToHourMinute(hour, minute) {
  const h = parseInt(hour, 10);
  const m = parseInt(minute, 10);
  if (isNaN(h) || isNaN(m)) return;

  // 1) Cella precisa (selectable-cell) per quell'ora/minuto
  let cell = document.querySelector(`.selectable-cell[data-hour="${h}"][data-minute="${m}"]`);

  // 2) Se non trovata e minuto non zero, prova comunque l'ora (hour-cell) per avere un riferimento
  if (!cell && m !== 0) {
    cell = document.querySelector(`td.hour-cell[data-hour="${h}"]`);
  }

  // 3) Fallback finale: qualsiasi cella per quell'ora
  if (!cell) {
    cell = document.querySelector(`.selectable-cell[data-hour="${h}"]`) ||
           document.querySelector(`td[data-hour="${h}"]`);
  }

  if (!cell) return;

  // Centra la cella (retry per layout ancora in stabilizzazione)
  let attempts = 0;
  const maxAttempts = 5;
  function center() {
    attempts++;
    const rect = cell.getBoundingClientRect();
    const targetY = rect.top + window.scrollY - (window.innerHeight / 2) + (rect.height / 2);
    window.scrollTo({ top: Math.max(0, targetY), behavior: 'auto' });

    // Verifica centratura entro tolleranza
    const newRect = cell.getBoundingClientRect();
    const delta = Math.abs((newRect.top + newRect.height / 2) - (window.innerHeight / 2));
    if (delta > 6 && attempts < maxAttempts) {
      setTimeout(center, attempts < 3 ? 80 : 160);
    }
  }
  center();

  // Flash visivo leggero
  try {
    cell.style.transition = 'background-color 0.5s';
    const old = cell.style.backgroundColor;
    cell.style.backgroundColor = '#fff8aa';
    setTimeout(() => { cell.style.backgroundColor = old; }, 700);
  } catch(_) {}
}
window.scrollToHourMinute = scrollToHourMinute;

document.addEventListener('DOMContentLoaded', function() {
  let hour = sessionStorage.getItem('scrollToHour');
  let minute = sessionStorage.getItem('scrollToMinute');

  // Se non presenti in sessionStorage, prova parametro ?ora=HH:MM
  if ((hour === null || minute === null) && typeof URLSearchParams === 'function') {
    try {
      const params = new URLSearchParams(window.location.search);
      const ora = params.get('ora'); // formato HH:MM
      if (ora && /^\d{1,2}:\d{2}$/.test(ora)) {
        const parts = ora.split(':');
        hour = parts[0];
        minute = parts[1];
      }
    } catch(_) {}
  }

  if (hour !== null && minute !== null) {
    // Consuma e rimuovi subito (evita doppio scroll)
    try {
      sessionStorage.removeItem('scrollToHour');
      sessionStorage.removeItem('scrollToMinute');
    } catch(_) {}

    // Posticipa leggermente per assicurare che le altezze dei quarter siano applicate
    setTimeout(() => {
      scrollToHourMinute(hour, minute);
    }, 90);
  }
});

document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.appointment-block').forEach(function(block) {
    block.addEventListener('mouseenter', function() {
      // Trova la cella contenitore
      const cell = block.closest('td.selectable-cell');
      if (!cell) return;
      // Conta i blocchi nella cella
      const blocksInCell = cell.querySelectorAll('.appointment-block');
      if (blocksInCell.length === 1) {
        // Solo se è l'unico blocco nella cella
        block.style.zIndex = 9999;
        const popups = block.querySelectorAll('.popup-buttons, .btn-popup.whatsapp-btn');
        popups.forEach(p => p.style.zIndex = 10000);
      }
    });
    block.addEventListener('mouseleave', function() {
      // Trova la cella contenitore
      const cell = block.closest('td.selectable-cell');
      if (!cell) return;
      const blocksInCell = cell.querySelectorAll('.appointment-block');
      if (blocksInCell.length === 1) {
        block.style.zIndex = '';
        const popups = block.querySelectorAll('.popup-buttons, .btn-popup.whatsapp-btn');
        popups.forEach(p => p.style.zIndex = '');
      }
    });
  });
});

document.addEventListener('shown.bs.tooltip', function (e) {
  if (e.target.classList.contains('whatsapp-btn')) {
    const tooltipId = e.target.getAttribute('aria-describedby');
    if (tooltipId) {
      const tooltipEl = document.getElementById(tooltipId);
      if (tooltipEl) tooltipEl.classList.add('tooltip-whatsapp');
    }
  }
});

      // Logica modal appuntamenti via booking online
document.addEventListener('DOMContentLoaded', function() {
  const btnWeb = document.getElementById('btnWebInformatica');
  if (btnWeb) {
    btnWeb.addEventListener('click', function() {
      // Imposta la data di oggi come default
      const today = new Date().toISOString().slice(0,10);
      document.getElementById('webApptDate').value = today;
      loadWebAppointments(today, "");
      const modal = new bootstrap.Modal(document.getElementById('WebAppointmentsModal'));
      modal.show();
    });
  }
  
  // Date navigator — SAFE handlers (non sovrascrivono risultati di ricerca)
  (function(){
    const prevBtn = document.getElementById('webApptPrev');
    const nextBtn = document.getElementById('webApptNext');
    const dateInput = document.getElementById('webApptDate');
    const searchInput = document.getElementById('webApptSearch');

    function getISODateNoTZ(raw) {
      const r = raw ? raw : new Date().toISOString().slice(0,10);
      return new Date(r + 'T12:00:00');
    }

    if (prevBtn) {
      prevBtn.onclick = function() {
        if (searchInput && searchInput.value.trim().length > 0) return;
        const raw = (dateInput && dateInput.value) ? dateInput.value : new Date().toISOString().slice(0,10);
        const d = getISODateNoTZ(raw);
        d.setDate(d.getDate() - 1);
        if (dateInput) dateInput.value = d.toISOString().slice(0,10);
        if (!(searchInput && searchInput.value.trim().length > 0)) loadWebAppointments(dateInput.value, '');
      };
    }

    if (nextBtn) {
      nextBtn.onclick = function() {
        if (searchInput && searchInput.value.trim().length > 0) return;
        const raw = (dateInput && dateInput.value) ? dateInput.value : new Date().toISOString().slice(0,10);
        const d = getISODateNoTZ(raw);
        d.setDate(d.getDate() + 1);
        if (dateInput) dateInput.value = d.toISOString().slice(0,10);
        if (!(searchInput && searchInput.value.trim().length > 0)) loadWebAppointments(dateInput.value, '');
      };
    }

    if (dateInput) {
      dateInput.onchange = function() {
        if (searchInput && searchInput.value.trim().length > 0) return;
        loadWebAppointments(this.value, '');
      };
    }

    // Single controlled oninput for search (debounced). If >=3 chars -> search fetch only.
    if (searchInput) {
      if (!window._webApptSearchDebounce) window._webApptSearchDebounce = null;
      searchInput.oninput = function() {
        const v = (this.value || '').toString();
        const dateEl = dateInput;

        // visual behaviour: store and disable date when >=3
        if (v.trim().length >= 3) {
          if (dateEl && dateEl.dataset._storedDate === undefined) dateEl.dataset._storedDate = dateEl.value || '';
          if (dateEl) {
            dateEl.value = '';
            dateEl.disabled = true;
            dateEl.style.background = '#efefef';
            dateEl.style.color = '#666';
          }
        } else {
          if (dateEl) {
            if (dateEl.dataset._storedDate !== undefined) {
              dateEl.value = dateEl.dataset._storedDate || '';
              delete dateEl.dataset._storedDate;
            }
            dateEl.disabled = false;
            dateEl.style.background = '';
            dateEl.style.color = '';
          }
        }

        // debounce fetches
        if (window._webApptSearchDebounce) clearTimeout(window._webApptSearchDebounce);
        window._webApptSearchDebounce = setTimeout(function() {
          // if user typed >=3 chars -> perform search fetch (search only)
          if (v.trim().length >= 3) {
            loadWebAppointments('', v.trim());
            return;
          }
          // if field emptied -> fetch by date
          if (!v.trim()) {
            const dateVal = (dateEl && dateEl.value) ? dateEl.value : new Date().toISOString().slice(0,10);
            loadWebAppointments(dateVal, '');
            return;
          }
          // 1-2 chars -> do nothing (avoid accidental overwrite)
        }, 220);
      };
    }
  }());
});

// =============================================================
//   FUNZIONE PRINCIPALE: CARICA E MOSTRA GLI APPUNTAMENTI ONLINE
// =============================================================
// Questa funzione gestisce il caricamento dei dati dal backend, il rendering della tabella nel modal,
// e la gestione degli errori. Viene chiamata quando si apre il modal o si cambia data/ricerca.
function loadWebAppointments(date, search) {
  // Controllo se CLIENT_ID_BOOKING è disponibile (necessario per il matching clienti)
  if (!window.CLIENT_ID_BOOKING) {
    // Se non è pronto, ritenta dopo 100ms (evita errori iniziali)
    setTimeout(() => loadWebAppointments(date, search), 100);
    return;
  }

  // Costruzione dei parametri per la richiesta GET al backend
  const params = new URLSearchParams();
  // Sempre inviare `search` se presente (ricerca globale). Solo se search è vuoto inviare la date.
  if (search && String(search).trim().length > 0) {
    params.append('search', String(search).trim());
  } else {
    params.append('date', date);
  }

  // Fetch dei dati dal backend (endpoint per appuntamenti online)
  fetch(`/calendar/api/online-appointments-by-booking-date?${params.toString()}`)
    .then(resp => {
      // Controllo se la risposta è OK (status 200-299), altrimenti lancia errore
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      return resp.json(); // Converte la risposta in JSON
    })
    .then(data => {
      // Trova il tbody della tabella nel modal
      const tbody = document.querySelector('#webApptTable tbody');
      if (!tbody) return; // Se non esiste, esci (evita errori)

      // Svuota la tabella per ricaricarla con nuovi dati
      tbody.innerHTML = '';

      // Assicura che i dati siano un array (fallback a array vuoto)
      const arr = Array.isArray(data) ? data : [];

      // Se non ci sono risultati, mostra un messaggio
      if (arr.length === 0) {
        const tr = document.createElement('tr');
        const td = document.createElement('td');
        td.colSpan = 5; // Spazia su tutte le colonne
        td.textContent = 'Nessun risultato';
        tr.appendChild(td);
        tbody.appendChild(tr);
      } else {
        // Per ogni sessione (appuntamento raggruppato), crea una riga nella tabella
        arr.forEach(session => {
          const tr = document.createElement('tr');

// Colonna 1: Data di booking (centrata)
const tdBooking = document.createElement('td');
tdBooking.style.textAlign = 'center';
const bookingDateStr = (session?.data_booking ?? '').toString().split(' ')[0];  // Prendi solo la parte data
tdBooking.textContent = formatDateItalian(bookingDateStr);
tr.appendChild(tdBooking);

// Colonna 2: Cliente (nome cognome - cellulare)
const tdCliente = document.createElement('td');
const nome = (session?.nome ?? '').toString();
const cognome = (session?.cognome ?? '').toString();
const cell = (session?.cellulare ?? '').toString();
tdCliente.textContent = `${nome}${nome && cognome ? ' ' : ''}${cognome}${cell ? ' - ' + cell : ''}`;
tr.appendChild(tdCliente);

// Colonna 3: Match cliente (mostra se c'è un match con clienti esistenti)
const tdMatch = document.createElement('td');
tdMatch.style.textAlign = 'center';  // Aggiungi centramento se necessario
const matchCliente = !!session?.match_cliente;  
tdMatch.textContent = matchCliente ? 'Sì' : 'No';  // O lascia vuoto se non hai dati
tr.appendChild(tdMatch);

          // Colonna 4: Bottone associa / stato (logica per mostrare ❓, 🟢 o niente)
          const tdBtn = document.createElement('td');
          tdBtn.style.textAlign = 'center';
          tdBtn.style.verticalAlign = 'middle';
          tdBtn.style.minWidth = '40px';
          tdBtn.style.height = '20px';

          const matchClienteId = session?.match_cliente_id ?? null;
          const clientId = session?.client_id ?? null;
          // identifica placeholder: backend flag OR dummy id OR nome/cognome "cliente"/"booking"
          const isPlaceholder =
            !!session?.placeholder_exists ||
            String(clientId) === String(window.CLIENT_ID_BOOKING ?? '') ||
            ((String(session?.nome || '').toLowerCase() === 'cliente') && (String(session?.cognome || '').toLowerCase() === 'booking'));

          // Vero se la sessione è già associata al client matchato
          const isAssociatedToMatchedClient = matchClienteId && String(clientId ?? '') === String(matchClienteId);

          if (matchCliente && isPlaceholder) {
            // Mostra ❓ solo quando esiste un match e il blocco è ancora placeholder/booking
            const btn = document.createElement('button');
            btn.className = 'btn btn-link btn-associa';
            btn.type = 'button';
            btn.title = 'Associa';
            if (Array.isArray(session?.ids) && session.ids[0] != null) {
              btn.dataset.appointmentId = String(session.ids[0]);
            }
            // NEW: porta tutti gli appuntamenti della sessione
            if (Array.isArray(session?.ids) && session.ids.length > 0) {
              btn.dataset.appointmentIds = session.ids.join(',');
            }
            if (matchClienteId) btn.dataset.matchClienteId = String(matchClienteId);
            btn.dataset.clientNome = (session.nome || '');
            btn.dataset.clientCognome = (session.cognome || '');
            btn.dataset.clientCellulare = (session.cellulare || '');
            const icon = document.createElement('span');
            icon.textContent = '❓';
            icon.style.color = '#d32f2f';
            icon.style.fontSize = '1.6em';
            btn.appendChild(icon);
            tdBtn.appendChild(btn);
          } else if (matchCliente && isAssociatedToMatchedClient) {
            // Mostra 🟢 se c'è un match e l'appuntamento è già associato al client trovato
            const span = document.createElement('span');
            span.textContent = '🟢';
            span.style.color = '#388e3c';
            tdBtn.appendChild(span);
          } else {
            // Niente (spazio vuoto)
          }
          tr.appendChild(tdBtn);

// Colonna 5: Data appuntamento (centrata) - Estrai solo la data (senza orario)
const tdAppt = document.createElement('td');
tdAppt.style.textAlign = 'center';
const apptDateStr = (session?.data_appuntamento ?? '').toString().split(' ')[0];  // Prendi solo la parte data
const apptTimeStr = (session?.data_appuntamento ?? '').toString().split(' ')[1] || '';  // Prendi l'orario
const [apptHour, apptMinute] = apptTimeStr.split(':');

// Salva i valori originali negli attributi data-* per il click handler
tdAppt.dataset.date = apptDateStr;
tdAppt.dataset.hour = apptHour || '';
tdAppt.dataset.minute = apptMinute || '';

// Mostra il testo formattato
tdAppt.textContent = formatDateItalian(apptDateStr);
tr.appendChild(tdAppt);

if (tdAppt.textContent.trim()) {
  // Rende cliccabile e aggiunge tooltip
  tdAppt.style.cursor = 'pointer';
  tdAppt.title = "Vai all'appuntamento";
  tdAppt.addEventListener('click', function () {
    // Usa gli attributi data-* invece di parsare il testo
    const dateStr = tdAppt.dataset.date;
    const hour = tdAppt.dataset.hour;
    const minute = tdAppt.dataset.minute;

    if (dateStr && hour && minute) {
      // Chiude il modal corrente
      const modalEl = document.getElementById('WebAppointmentsModal');
      if (modalEl) {
        const bsModal = bootstrap.Modal.getInstance(modalEl);
        if (bsModal) bsModal.hide();
      }

      // Salva in sessionStorage per scroll automatico
      sessionStorage.setItem('scrollToHour', hour);
      sessionStorage.setItem('scrollToMinute', minute);

      // Naviga al calendario con i parametri
      window.location.href = `/calendar?date=${dateStr}&ora=${hour}:${minute}`;
    }
  });
}

          tr.appendChild(tdAppt);
          tbody.appendChild(tr);
        });
      }

      // =============================================================
      //   BINDING DEI CLICK PER I BOTTONI "ASSOCIA"
      // =============================================================
      // Trova il token CSRF per le richieste POST
      const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');

// Normalizza nomi con apostrofi e capitalizzazione nella Web Booking Table
(function normalizeWebBookingNames() {
  const tbody = document.querySelector('#webApptTable tbody');
  if (!tbody) return;

  const decodeHtml = (s) => {
    const t = document.createElement('textarea');
    t.innerHTML = String(s || '');
    return t.value;
  };
  const capAll = (s) => {
    const v = String(s || '').trim();
    if (typeof window.capitalizeName === 'function') {
      return window.capitalizeName(v);
    }
    return v.toLowerCase().replace(/\b\p{L}/gu, m => m.toUpperCase());
  };

  tbody.querySelectorAll('tr').forEach(tr => {
    // Colonna 2 = CLIENTE PRENOTATO
    const cellClient = tr.children[1];
    if (cellClient) {
      const raw = cellClient.textContent;
      cellClient.textContent = capAll(decodeHtml(raw));
    }
    // Colonna 3 = MATCH CLIENTE
    const cellMatch = tr.children[2];
    if (cellMatch) {
      const raw = cellMatch.textContent;
      cellMatch.textContent = capAll(decodeHtml(raw));
    }
  });
})();

      // Per ogni bottone "Associa", aggiungi listener per la richiesta al backend
      document.querySelectorAll('.btn-associa').forEach(btn => {
        btn.addEventListener('click', async function () {
          // Conferma associazione
          if (!window.confirm('Vuoi associare questo appuntamento al cliente selezionato?')) return;

          // Estrai dati dal dataset del bottone
          const appointmentId = btn.dataset.appointmentId;
          const matchClienteId = btn.dataset.matchClienteId || null;
          const nome = btn.dataset.clientNome || '';
          const cognome = btn.dataset.clientCognome || '';
          const cellulare = btn.dataset.clientCellulare || '';

          const payload = matchClienteId ? {
            appointment_id: appointmentId,
            client_id: matchClienteId
          } : {
            appointment_id: appointmentId,
            nome,
            cognome,
            cellulare
          };

          fetch('/calendar/api/associa-cliente-booking', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': csrfToken
            },
            body: JSON.stringify(payload)
          })
          .then(resp => resp.json())
          .then(async data => {
            if (data.success) {
              // Chiama funzione globale per aggiornare i blocchi booking (se esiste)
              if (typeof propBookingBlocks === 'function') {
                propBookingBlocks(appointmentId, data.new_client_id, `${nome} ${cognome}`);
              }

              // --- NEW: cerca altri blocchi web dello stesso cliente entro 30min e applica stesso colore ---
              try {
                const originId = String(appointmentId);
                const clientIdToMatch = data.new_client_id || matchClienteId || null;
                const dateToMatch = data.appointment_date || data.date || document.getElementById('webApptDate')?.value || selectedDate;
                const originBlock = document.querySelector(`.appointment-block[data-appointment-id="${originId}"]`);
                const originColor = originBlock?.getAttribute('data-colore') || '';
                const originFont = originBlock?.getAttribute('data-colore_font') || (originColor ? computeFontColor(originColor) : '');

                if (clientIdToMatch && originColor) {
                  const MAX_GAP = Number(window.CONTIGUOUS_BLOCK_MAX_GAP_MINUTES || 30);
                  const candidates = Array.from(document.querySelectorAll(`.appointment-block[data-source="web"][data-client-id="${clientIdToMatch}"][data-date="${dateToMatch}"]`));
                  candidates.forEach(b => {
                    if (b.getAttribute('data-appointment-id') === originId) return;
                    const gap = Math.abs(getBlockStartTime(b) - getBlockStartTime(originBlock || b));
                    if (gap <= MAX_GAP) {
                      // Applica DOM
                      b.setAttribute('data-colore', originColor);
                      if (originFont) b.setAttribute('data-colore_font', originFont);
                      b.style.backgroundColor = originColor;
                      if (originFont) {
                        b.style.setProperty('color', originFont, 'important');
                        const content = b.querySelector('.appointment-content');
                        if (content) {
                          content.style.setProperty('color', originFont, 'important');
                          content.querySelectorAll('a').forEach(a => a.style.setProperty('color', originFont, 'important'));
                        }
                      }
                      // Persisti cambiamento colore lato server (best-effort, non blocchiamo)
                      const bid = b.getAttribute('data-appointment-id');
                      if (bid) {
                        fetch(`/calendar/update_color/${bid}`, {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                          body: JSON.stringify({ colore: originColor, colore_font: originFont })
                        }).catch(err => console.warn('update_color failed for', bid, err));
                      }
                    }
                  });
                }
              } catch (err) {
                console.warn('propagate booking color failed', err);
              }

// Sostituisci il bottone con 🟢
const green = document.createElement('span');
green.textContent = '🟢';
green.style.color = '#388e3c';
btn.replaceWith(green);

// Spegni l'icona di notifica (se presente)
const btnWeb = document.getElementById('btnWebInformatica');
if (btnWeb) {
  btnWeb.style.boxShadow = '';
  btnWeb.style.background = '';
}

// Mostra il pannello WhatsApp e invia se confermato
try {
  // Estrai gli ID della sessione dal bottone (servono al backend per calcolare i servizi)
  const idsCsv = btn.dataset.appointmentIds || '';
  const idsArr = idsCsv ? idsCsv.split(',').map(s => s.trim()).filter(Boolean) : [];

  // Normalizza ora (HH:MM) da risposta server o fallback hour/minute
  const hhmm = (v) => {
    const m = String(v || '').match(/(\d{2}:\d{2})/);
    return m ? m[1] : '';
  };
  let oraMsg = hhmm(data.start_time);
  if (!oraMsg) {
    const hh = (data.hour ?? '').toString().padStart(2, '0');
    const mm = (data.minute ?? '').toString().padStart(2, '0');
    if (hh && mm) oraMsg = `${hh}:${mm}`;
  }

  const whatsappData = {
    client_id: data.new_client_id || matchClienteId || null,
    client_name: `${nome} ${cognome}`.trim(),
    data: data.appointment_date || data.date || '',
    ora: oraMsg || '',
    appointment_id: btn.dataset.appointmentId || (idsArr[0] || null),
    appointment_ids: idsArr
  };

  if (typeof chiediInvioWhatsappAuto === 'function' && typeof inviaWhatsappAutoSeRichiesto === 'function') {
    let sendResult = false;
    try { sendResult = await chiediInvioWhatsappAuto(); } catch { sendResult = false; }
    if (sendResult === true) {
      await inviaWhatsappAutoSeRichiesto(null, whatsappData, csrfToken);
      alert('Messaggio WhatsApp inviato!');
    } else if (sendResult !== 'back' && typeof chiediInvioWhatsappNavigator === 'function') {
      const navSend = await chiediInvioWhatsappNavigator();
      if (navSend === true) {
        await inviaWhatsappAutoSeRichiesto(null, whatsappData, csrfToken);
        alert('Messaggio WhatsApp inviato!');
      }
    }
  } else if (typeof chiediInvioWhatsappNavigator === 'function' && typeof inviaWhatsappAutoSeRichiesto === 'function') {
    const navSend = await chiediInvioWhatsappNavigator();
    if (navSend === true) {
      await inviaWhatsappAutoSeRichiesto(null, whatsappData, csrfToken);
      alert('Messaggio WhatsApp inviato!');
    }
  }
} catch (whErr) {
  console.warn('Errore flusso WhatsApp dopo associazione:', whErr);
}

            } else {
              // Mostra errore
              alert(data.error || 'Errore nell\'associazione');
            }
          });
        });
      });
    })
    .catch(err => {
      // =============================================================
      //   GESTIONE ERRORI: MOSTRA MESSAGGIO IN TABELLA
      // =============================================================
      // In caso di errore (es. rete, backend), svuota la tabella e mostra errore
      const tbody = document.querySelector('#webApptTable tbody');
      if (!tbody) return;
      tbody.innerHTML = '';
      const tr = document.createElement('tr');
      const td = document.createElement('td');
      td.colSpan = 5;
      td.textContent = `Errore caricamento: ${err.message}`;
      tr.appendChild(td);
      tbody.appendChild(tr);
      console.error('loadWebAppointments error:', err); // Log per debug
    });
}

// =============================================================
//   GESTIONE MODAL E NOTIFICHE WEB APPOINTMENTS
// =============================================================
document.addEventListener('DOMContentLoaded', function() {
  const btnWeb = document.getElementById('btnWebInformatica'); // Bottone per aprire il modal
  const MODAL_ID = 'WebAppointmentsModal'; // ID del modal
  const STORAGE_KEY = 'lastSeenOnlineBookingId'; // Chiave per localStorage

  // Funzioni helper per l'icona di notifica
  function illuminaIcona() {
    if (btnWeb) btnWeb.style.background = '#fff696ff'; // Colore giallo per notifica
  }
  function spegniIcona() {
    if (btnWeb) {
      btnWeb.style.boxShadow = '';
      btnWeb.style.background = '';
    }
  }

  // =============================================================
  //   FUNZIONE: CONTROLLA NUOVE PRENOTAZIONI ONLINE
  // =============================================================
  // Chiama il backend per vedere se ci sono nuove prenotazioni e illumina l'icona se necessario
  function checkNuovePrenotazioni() {
    fetch('/calendar/api/last-online-booking')
      .then(r => r.json())
      .then(data => {
        if (!data.id) return spegniIcona(); // Se no ID, spegni
        const lastSeen = localStorage.getItem(STORAGE_KEY);

        // Se non c'è lastSeen, inizializzalo senza illuminare
        if (!lastSeen) {
          localStorage.setItem(STORAGE_KEY, String(data.id));
          return spegniIcona();
        }

        // Confronto sicuro (numerico o stringa)
        const current = Number(data.id);
        const prev = Number(lastSeen);
        if (!isNaN(current) && !isNaN(prev)) {
          if (current > prev) {
            illuminaIcona(); // Nuove prenotazioni
          } else {
            spegniIcona();
          }
        } else {
          if (String(data.id) !== String(lastSeen)) {
            illuminaIcona();
          } else {
            spegniIcona();
          }
        }
      });
  }

  // Controlla subito e ogni 30 secondi
  checkNuovePrenotazioni();
  setInterval(checkNuovePrenotazioni, 30000);

  // =============================================================
  //   EVENT LISTENER: APRI MODAL E RESET NOTIFICA
  // =============================================================
  if (btnWeb) {
    btnWeb.addEventListener('click', function() {
      // Quando si apre il modal, salva l'ultimo ID visto e spegni l'icona
      fetch('/calendar/api/last-online-booking')
        .then(r => r.json())
        .then(data => {
          if (data.id) localStorage.setItem(STORAGE_KEY, data.id);
          spegniIcona();
        });
    });
  }

  // =============================================================
  //   EVENT LISTENER: CHIUSURA MODAL
  // =============================================================
  const modalEl = document.getElementById(MODAL_ID);
  if (modalEl) {
    modalEl.addEventListener('hidden.bs.modal', spegniIcona); // Spegni quando si chiude
  }
  // Se vuoi spegnere anche quando il modal viene chiuso:
  document.getElementById(MODAL_ID).addEventListener('hidden.bs.modal', spegniIcona);
});

document.getElementById('EditAppointmentModal').addEventListener('shown.bs.modal', function () {
  // Blocca lo scroll automatico
  setTimeout(() => {
    window.scrollTo({ top: window.scrollY, behavior: 'instant' });
    // Focus solo dopo apertura
    const input = document.querySelector('#EditAppointmentModal input#clientSearchInput');
    if (input) input.focus();
  }, 0);
});

// --- 1. Intercetta il click sulle righe dello storico cliente ---
document.addEventListener('DOMContentLoaded', function() {
  // Storico cliente da popup risultati ricerca (modal crea/edit)
  document.addEventListener('click', function(e) {
    const row = e.target.closest('.clickable-row');
    if (row && row.dataset.date && row.dataset.hour && row.dataset.minute) {
      // Salva la posizione oraria in sessionStorage
      sessionStorage.setItem('scrollToDate', row.dataset.date);
      sessionStorage.setItem('scrollToHour', row.dataset.hour);
      sessionStorage.setItem('scrollToMinute', row.dataset.minute);
      // Vai alla pagina calendario
      window.location.href = `/calendar?date=${row.dataset.date}&ora=${row.dataset.hour}:${row.dataset.minute}`;
    }
  });
});

// --- 2. Scroll automatico dopo il reload della pagina ---
document.addEventListener('DOMContentLoaded', function() {
  const scrollDate = sessionStorage.getItem('scrollToDate');
  const scrollHour = sessionStorage.getItem('scrollToHour');
  const scrollMinute = sessionStorage.getItem('scrollToMinute');
  // Solo se la data corrisponde a quella visualizzata
  if (scrollDate && scrollHour && scrollMinute) {
    const currentDate = document.getElementById('date')?.value;
    if (currentDate === scrollDate) {
      // Trova la cella oraria corrispondente
      const cell = document.querySelector(
        `.selectable-cell[data-hour="${scrollHour}"][data-minute="${scrollMinute}"]`
      );
      if (cell) {
        // Scrolla la cella al centro della viewport
        cell.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
    // Pulisci la memoria
    sessionStorage.removeItem('scrollToDate');
    sessionStorage.removeItem('scrollToHour');
    sessionStorage.removeItem('scrollToMinute');
  }
});

document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.client-info-link').forEach(link => {
    link.addEventListener('click', function(e){
      const TOUCH_UI = (() => { try { return localStorage.getItem('sun_touch_ui') === '1'; } catch(_) { return false; } })();
      const block = this.closest('.appointment-block');
      if (!block) return;

      if (TOUCH_UI) {
        // Modalità touch-ui: primo click attiva popup, secondo apre modal
        if (!block.classList.contains('active-popup')) {
          e.preventDefault();
          // toggle popups
          if (typeof setActivePopupAndTooltip === 'function') {
            setActivePopupAndTooltip(block);
          } else {
            block.classList.add('active-popup');
          }
          return;
        }
        // Popup attivi: apri modal
      } else {
        // Modalità default: apri sempre modal
      }

      // Apri modal (comune a entrambe le modalità quando permesso)
      e.preventDefault();
      const apptId = block.getAttribute('data-appointment-id');
      if (apptId && typeof openModifyPopup === 'function') {
        openModifyPopup(apptId);
      }
    }, true); // capture per priorità
  });
});

document.addEventListener('click', function(e){
  const c = e.target.closest('.selectable-cell.calendar-closed');
  if (c) {
    e.stopImmediatePropagation();
    e.preventDefault();
  }
}, true);

// Aggiorna dataset + tooltip dopo il salvataggio nota
window.onAppointmentNoteSaved = function (appointmentId, noteText) {
  try {
    const id = String(appointmentId || '').trim();
    const block = document.querySelector(`.appointment-block[data-appointment-id="${id}"]`);
    if (!block) return;

    // Aggiorna dataset/attributo usato dal tooltip
    block.dataset.note = noteText || '';
    block.setAttribute('data-note', noteText || '');

    // Se esiste il setter del tooltip, richiamalo per forzare il refresh
    if (typeof window.setActivePopupAndTooltip === 'function') {
      window.setActivePopupAndTooltip(block);
    } else {
      // Fallback: aggiorna subito l’elemento del tooltip se visibile
      const tip = document.getElementById('clientInfoPopup');
      if (tip && tip.style.display !== 'none') {
        const el =
          tip.querySelector('.tooltip-note') ||
          tip.querySelector('[data-role="note"]') ||
          tip.querySelector('.note') ||
          null;
        if (el) el.textContent = noteText || '';
      }
    }
  } catch (_) {}
};

// Listener delegato per eliminazione: desktop large (no touch-ui)
document.addEventListener('click', function(e) {
  const delBtn = e.target.closest('.appointment-block .delete-icon, .appointment-block .icon-trash, .appointment-block .popup-buttons .btn-popup.delete-appointment-block');
  if (!delBtn) return;

  // Esci in touch-ui
  try {
    if (localStorage.getItem('sun_touch_ui') === '1' || document.body.classList.contains('touch-ui')) return;
  } catch(_) {
    if (document.body.classList.contains('touch-ui')) return;
  }

  // Solo schermi larghi
  if (!window.matchMedia || !window.matchMedia('(min-width: 1201px)').matches) return;

  e.preventDefault();
  e.stopPropagation();
  e.stopImmediatePropagation();

  const block = delBtn.closest('.appointment-block');
  const id = delBtn.getAttribute('data-appointment-id') || (block && block.getAttribute('data-appointment-id'));
  if (!id) return;

  if (typeof window.deleteAppointment === 'function') {
    window.deleteAppointment(id);
  }
}, true);

document.addEventListener('DOMContentLoaded', function() {
  const inp = document.getElementById('mobileCalDate');
  if (!inp) return;
  inp.addEventListener('change', function() {
    const v = (this.value || '').trim();
    if (!v) return;
    const base = (typeof calendarHomeUrl === 'string') ? calendarHomeUrl : '/calendar';
    window.location.href = base + '?date=' + encodeURIComponent(v);
  });
});

document.addEventListener('DOMContentLoaded', function() {
  const mobileInput = document.getElementById('mobileCalDate');
  if (!mobileInput) return;

  function redirectIfValid(val) {
    if (!val) return;
    const base = (typeof calendarHomeUrl === 'string') ? calendarHomeUrl : '/calendar';
    window.location.href = base + '?date=' + encodeURIComponent(val);
  }

  // Cambia data → redirect
  mobileInput.addEventListener('change', function() {
    redirectIfValid(this.value.trim());
  });

  // Unico handler (click). Niente pointerdown/keydown.
  mobileInput.addEventListener('click', function() {
    // Se il browser gestisce nativamente il picker, lascia fare (eviti doppio popup)
    if (typeof mobileInput.showPicker === 'function') {
      try { mobileInput.showPicker(); } catch(_) {}
      return;
    }
    // Fallback flatpickr solo se assente showPicker
    if (typeof flatpickr === 'function' && !mobileInput._flatpickr) {
      mobileInput._flatpickr = flatpickr(mobileInput, {
        dateFormat: 'Y-m-d',
        defaultDate: mobileInput.value || '{{ selected_date_str }}',
        locale: 'it',
        onChange: function(_, dateStr){ redirectIfValid(dateStr); }
      });
    }
    if (mobileInput._flatpickr) {
      try { mobileInput._flatpickr.open(); } catch(_) {}
    }
  });
});

/* PATCH: Disabilita auto‑WhatsApp su mobile (<1200px) */
(function disableAutoWhatsAppOnSmallScreens(){
  function isSmall() {
    return window.matchMedia && window.matchMedia('(max-width: 1199.98px)').matches;
  }
  if (!isSmall()) return;

  // Forza disabilitazione globale (creazione appuntamento / navigator / spostamento)
  window.fetchWhatsappModalDisabled = function(){ return Promise.resolve(true); };
  window.chiediInvioWhatsappAuto = function(){ return Promise.resolve(false); };
  window.inviaWhatsappAutoSeRichiesto = function(){ return Promise.resolve(); };
  window.chiediInvioWhatsappNavigator = function(){ return Promise.resolve(false); };

  // Flag di stato (se qualche altra parte del codice vuole sapere)
  window.__WHATSAPP_AUTO_DISABLED_MOBILE = true;
})();

// =============================================================
//   INDICATORE VISUALE DROP SU BLOCCO APPUNTAMENTO
// =============================================================
document.addEventListener('mouseenter', function(e) {
    // Verifica che il target sia valido
    if (!e.target || typeof e.target.closest !== 'function') return;

    // PATCH: In modalità touch-ui, l'indicatore di drop non serve (no hover) e causa problemi grafici
    if (document.body.classList.contains('touch-ui')) return;
    
    // Verifica se c'è uno pseudoblocco nel navigator (operazione di cut/copy/new in corso)
    if (!window.pseudoBlocks || window.pseudoBlocks.length === 0) return;

    // Trova il blocco appuntamento
    const block = e.target.closest('.appointment-block');
    
    // Se non è un blocco, oppure è un blocco OFF (note-off), ignora
    if (!block || block.classList.contains('note-off')) return;
    
    // Se ha già l'indicatore, ignora
    if (block.querySelector('.appointment-drop-arrow')) return;

    // Crea l'indicatore
    const arrow = document.createElement('div');
    arrow.className = 'appointment-drop-arrow';
    arrow.innerHTML = '<i class="bi bi-arrow-down"></i>';
    
    block.appendChild(arrow);
}, true); // Use capture per intercettare prima

document.addEventListener('mouseleave', function(e) {
    if (!e.target || typeof e.target.closest !== 'function') return;
    
    const block = e.target.closest('.appointment-block');
    if (!block) return;

    const arrow = block.querySelector('.appointment-drop-arrow');
    if (arrow) {
        arrow.remove();
    }
}, true);

// =============================================================
//   GESTIONE BADGE NOTIFICHE WEB
// =============================================================
function checkPendingWebAppointments() {
    fetch('/calendar/api/web-appointments/count-pending')
        .then(r => r.json())
        .then(data => {
            const badge = document.getElementById('webApptBadge');
            if (!badge) return;

            const count = data.count || 0;
            if (count > 0) {
                badge.textContent = count > 99 ? '99+' : count;
                badge.style.display = 'inline-block';
                
                // Opzionale: animazione pulsazione se il numero cambia o è > 0
                badge.classList.add('animate__animated', 'animate__pulse'); 
            } else {
                badge.style.display = 'none';
            }
        })
        .catch(err => console.warn('Check web pending failed', err));
}

// Avvia il controllo al caricamento e poi ogni minuto
document.addEventListener('DOMContentLoaded', function() {
    checkPendingWebAppointments();
    setInterval(checkPendingWebAppointments, 60000);
});