document.addEventListener('DOMContentLoaded', function () {

// Popup successo auto-chiudibile
function showSuccessPopup(message, timeout = 5000, onClose = null) {
  // Rimuovi eventuali popup esistenti
  const existing = document.getElementById('successPopupOverlay');
  if (existing) existing.remove();

  const overlay = document.createElement('div');
  overlay.id = 'successPopupOverlay';
  overlay.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:9999;';

  const popup = document.createElement('div');
  popup.style.cssText = 'background:#fff;padding:30px 50px;border-radius:12px;text-align:center;box-shadow:0 4px 20px rgba(0,0,0,0.3);max-width:400px;';

  const icon = document.createElement('div');
  icon.innerHTML = '<i class="bi bi-check-circle-fill" style="font-size:48px;color:#28a745;"></i>';
  popup.appendChild(icon);

  const text = document.createElement('p');
  text.style.cssText = 'margin:15px 0 20px;font-size:18px;font-weight:500;';
  text.textContent = message;
  popup.appendChild(text);

  const countdown = document.createElement('small');
  countdown.style.cssText = 'color:#888;';
  countdown.textContent = `Chiusura automatica in ${Math.ceil(timeout/1000)} secondi...`;
  popup.appendChild(countdown);

  const btnOk = document.createElement('button');
  btnOk.className = 'btn btn-success mt-3 d-block w-100';
  btnOk.textContent = 'Ok';
  btnOk.onclick = () => overlay.remove();
  popup.appendChild(btnOk);

  overlay.appendChild(popup);
  document.body.appendChild(overlay);

  // Countdown visivo
  let remaining = Math.ceil(timeout / 1000);
  const countdownInterval = setInterval(() => {
    remaining--;
    if (remaining > 0) {
      countdown.textContent = `Chiusura automatica in ${remaining} secondi...`;
    } else {
      clearInterval(countdownInterval);
    }
  }, 1000);

  const closePopup = () => {
    overlay.remove();
    if (onClose) onClose();
  };

  btnOk.onclick = closePopup;

  // Auto-chiusura
  setTimeout(() => {
    if (document.getElementById('successPopupOverlay')) {
      closePopup();
    }
  }, timeout);
}

  // Funzione per capitalizzare nome/cognome (prima lettera maiuscola per ogni parola)
  function capitalizeName(name) {
    if (!name) return name || '';
    return String(name).toLowerCase().replace(/\b\w/g, l => l.toUpperCase());
  }
  window.capitalizeName = capitalizeName;

  // Carica le carte prepagate attive di un cliente
  function caricaPrepagateCliente(clientId, nomeCliente) {
    if (!clientId) {
      window.clientePrepagate = [];
      aggiornaOpzioniPrepagata();
      return;
    }
    fetch(`/pacchetti/api/prepagate-cliente/${clientId}`)
      .then(res => res.json())
      .then(prepagate => {
        window.clientePrepagate = Array.isArray(prepagate) ? prepagate : [];
        console.log('Prepagate caricate:', window.clientePrepagate);
        aggiornaOpzioniPrepagata();
        
        // Mostra modal se ci sono prepagate attive
        if (window.clientePrepagate.length > 0 && nomeCliente) {
          mostraModalPrepagate(window.clientePrepagate, nomeCliente);
        }
      })
      .catch((err) => {
        console.error('Errore caricamento prepagate:', err);
        window.clientePrepagate = [];
        aggiornaOpzioniPrepagata();
      });
  }
  window.caricaPrepagateCliente = caricaPrepagateCliente;

  // Observer: carica prepagate automaticamente quando dataset.selectedClient cambia
  // (copre tutti i casi: calendar, my-spia, dropdown manuale)
  (function observeClientSelection() {
    const clientInput = document.getElementById('clientSearchInputCassa');
    if (!clientInput) return;
    let lastClientId = null;
    setInterval(function() {
      const currentId = clientInput.dataset.selectedClient || null;
      if (currentId && currentId !== lastClientId) {
        lastClientId = currentId;
        const nomeCliente = clientInput.value || '';
        caricaPrepagateCliente(currentId, nomeCliente);
      } else if (!currentId && lastClientId) {
        lastClientId = null;
        window.clientePrepagate = [];
        aggiornaOpzioniPrepagata();
      }
    }, 800);
  })();

  // Aggiorna tutte le select per mostrare/nascondere opzione prepagata
  function aggiornaOpzioniPrepagata() {
    const haPrepagate = window.clientePrepagate && window.clientePrepagate.length > 0;
    document.querySelectorAll('.scontrino-row').forEach(row => {
      const sel = row.querySelector('select[name="metodo_pagamento[]"]');
      if (!sel) return;
      
      let optPrepagata = sel.querySelector('option[value="prepagata"]');
      
      if (haPrepagate) {
        // Recupera info servizio dalla riga
        const servizioId = row.dataset.servizioId ? parseInt(row.dataset.servizioId) : null;
        const categoria = row.dataset.categoria || null;
        const sottocategoriaId = row.dataset.sottocategoriaId ? parseInt(row.dataset.sottocategoriaId) : null;
        
        const servizioInfo = {
          id: servizioId,
          categoria: categoria,
          sottocategoria_id: sottocategoriaId
        };
        
        // Verifica se il servizio è compatibile con i vincoli
        const compatibile = verificaVincoliPrepagata(servizioInfo);
        
        if (compatibile) {
          if (!optPrepagata) {
            optPrepagata = document.createElement('option');
            optPrepagata.value = 'prepagata';
            optPrepagata.textContent = 'Prepagata';
            sel.appendChild(optPrepagata);
          }
        } else {
          // Servizio non compatibile: rimuovi opzione prepagata
          if (optPrepagata) {
            if (sel.value === 'prepagata') sel.value = 'pos';
            optPrepagata.remove();
          }
        }
      } else {
        if (optPrepagata) {
          if (sel.value === 'prepagata') sel.value = 'pos';
          optPrepagata.remove();
        }
      }
    });
  }
  window.aggiornaOpzioniPrepagata = aggiornaOpzioniPrepagata;

  // Verifica se un servizio è compatibile con i vincoli della prepagata
  function verificaVincoliPrepagata(servizio) {
    if (!window.clientePrepagate || window.clientePrepagate.length === 0) return false;
    
    // Controlla se almeno una prepagata consente il servizio
    for (const prepagata of window.clientePrepagate) {
      const vincoli = prepagata.vincoli_utilizzo;
      
      // Se non ci sono vincoli o tipo è "tutti", il servizio è consentito
      if (!vincoli || vincoli.tipo === 'tutti') {
        return true;
      }
      
      // Vincolo per categoria
      if (vincoli.tipo === 'categoria') {
        if (servizio.categoria === vincoli.categoria) {
          return true;
        }
      }
      
      // Vincolo per sottocategoria
      if (vincoli.tipo === 'sottocategoria') {
        if (servizio.sottocategoria_id === vincoli.sottocategoria_id) {
          return true;
        }
      }
      
      // Vincolo per servizi specifici
      if (vincoli.tipo === 'servizi') {
        if (vincoli.servizi_ids && vincoli.servizi_ids.includes(servizio.id)) {
          return true;
        }
      }
    }
    
    return false;
  }
  window.verificaVincoliPrepagata = verificaVincoliPrepagata;

  // Calcola il saldo totale disponibile delle prepagate
  function getSaldoTotalePrepagata() {
    if (!window.clientePrepagate || window.clientePrepagate.length === 0) return 0;
    return window.clientePrepagate.reduce((sum, p) => sum + (p.credito_residuo || 0), 0);
  }

  // Calcola quanto è già assegnato a prepagata nelle righe
  function getTotaleAssegnatoPrepagata() {
    let totale = 0;
    document.querySelectorAll('.scontrino-row').forEach(row => {
      const metodo = row.querySelector('select')?.value;
      if (metodo === 'prepagata') {
        const prezzo = parseFloat(row.querySelector('.scontrino-row-prezzo')?.value || '0');
        totale += prezzo;
      }
    });
    return totale;
  }

  // Verifica se si può assegnare prepagata a una riga
  function verificaSaldoPrepagata(prezzoRiga, selectElement) {
    const saldoDisponibile = getSaldoTotalePrepagata();
    const giàAssegnato = getTotaleAssegnatoPrepagata();
    // Sottrai il prezzo della riga corrente se già era prepagata (per ricalcolo corretto)
    const row = selectElement.closest('.scontrino-row');
    const vecchioMetodo = row?.dataset?.vecchioMetodo || 'pos';
    const prezzoGiàContato = (vecchioMetodo === 'prepagata') ? prezzoRiga : 0;
    
    const nuovoTotale = giàAssegnato - prezzoGiàContato + prezzoRiga;
    
    if (nuovoTotale > saldoDisponibile) {
      const residuo = saldoDisponibile - (giàAssegnato - prezzoGiàContato);
      const mancante = prezzoRiga - residuo;
      
      alert(
        `⚠️ Saldo prepagata insufficiente!\n\n` +
        `Saldo disponibile: € ${saldoDisponibile.toFixed(2)}\n` +
        `Già assegnato ad altre righe: € ${(giàAssegnato - prezzoGiàContato).toFixed(2)}\n` +
        `Residuo utilizzabile: € ${Math.max(0, residuo).toFixed(2)}\n\n` +
        `Importo riga: € ${prezzoRiga.toFixed(2)}\n` +
        `Mancante: € ${mancante.toFixed(2)}\n\n` +
        `Suggerimento: riduci l'importo a € ${Math.max(0, residuo).toFixed(2)} ` +
        `oppure paga la differenza con un altro metodo.`
      );
      return false;
    }
    return true;
  }
  window.verificaSaldoPrepagata = verificaSaldoPrepagata;

  // Mostra modal informativo quando il cliente ha carte prepagate
  function mostraModalPrepagate(prepagate, nomeCliente) {
    // Rimuovi eventuale modal esistente
    const existing = document.getElementById('prepagateInfoModal');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'prepagateInfoModal';
    overlay.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:9999;';

    const modal = document.createElement('div');
    modal.style.cssText = 'background:#fff;padding:20px 30px;border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,0.3);max-width:450px;width:90%;position:relative;';

    // Pulsante X per chiudere
    const closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.innerHTML = '&times;';
    closeBtn.style.cssText = 'position:absolute;top:10px;right:15px;background:none;border:none;font-size:24px;cursor:pointer;color:#666;';
    closeBtn.onclick = () => overlay.remove();
    modal.appendChild(closeBtn);

    // Icona carta prepagata
    const iconDiv = document.createElement('div');
    iconDiv.innerHTML = '<i class="bi bi-credit-card-fill" style="font-size:40px;color:#0d6efd;"></i>';
    iconDiv.style.textAlign = 'center';
    iconDiv.style.marginBottom = '15px';
    modal.appendChild(iconDiv);

    // Titolo
    const title = document.createElement('h5');
    title.style.cssText = 'margin:0 0 15px;text-align:center;font-weight:600;';
    title.textContent = `${nomeCliente} ha carte prepagate attive!`;
    modal.appendChild(title);

    // Lista delle prepagate
    const lista = document.createElement('div');
    lista.style.cssText = 'max-height:200px;overflow-y:auto;';
    
    prepagate.forEach(p => {
      const item = document.createElement('div');
      item.style.cssText = 'padding:10px;margin-bottom:8px;background:#f8f9fa;border-radius:8px;border-left:4px solid #0d6efd;';
      
      const saldo = document.createElement('div');
      saldo.style.cssText = 'font-size:1.1em;font-weight:600;color:#198754;';
      saldo.textContent = `Saldo: € ${p.credito_residuo.toFixed(2)}`;
      item.appendChild(saldo);
      
      if (p.beneficiario && p.beneficiario !== nomeCliente) {
        const benef = document.createElement('div');
        benef.style.cssText = 'font-size:0.85em;color:#666;';
        benef.textContent = `Beneficiario: ${p.beneficiario}`;
        item.appendChild(benef);
      }
      
      if (p.data_scadenza) {
        const scad = document.createElement('div');
        scad.style.cssText = 'font-size:0.85em;color:#666;';
        scad.textContent = `Scadenza: ${p.data_scadenza}`;
        item.appendChild(scad);
      }
      
      lista.appendChild(item);
    });
    modal.appendChild(lista);

    // Nota
    const nota = document.createElement('p');
    nota.style.cssText = 'margin:15px 0 0;font-size:0.9em;color:#666;text-align:center;';
    nota.innerHTML = 'Puoi selezionare <b>"Prepagata"</b> come metodo di pagamento per ogni riga.';
    modal.appendChild(nota);

    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    // Chiudi cliccando fuori dal modal
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) overlay.remove();
    });
  }

  // MEMORIZZA gli appointment_id originali portati in cassa (set globale)
  window.originalAppointmentIds = window.originalAppointmentIds || new Set();

  // Flag per modifiche (inizialmente false)
  window.hasModifications = false;

  // Prepagate attive del cliente selezionato
  window.clientePrepagate = [];

  if (window.SERVIZI_PRECOMPILATI && window.SERVIZI_PRECOMPILATI.length > 0) {
    localStorage.removeItem('scontrinoServizi');
    localStorage.removeItem('scontrinoCliente');
    localStorage.removeItem('scontrinoOperatore');
    
    // Crea le righe per ogni servizio precompilato
    window.SERVIZI_PRECOMPILATI.forEach(s => {
      aggiungiRigaServizio(s, false);
    });
    
    // Verifica se ci sono operatori diversi tra i servizi precompilati
    const operatorIds = new Set();
    window.SERVIZI_PRECOMPILATI.forEach(s => {
      if (s.operator_id) operatorIds.add(String(s.operator_id));
    });
    
    // Se ci sono almeno 2 operatori diversi, attiva il toggle E svuota il campo globale
    if (operatorIds.size >= 2) {
      setTimeout(function() {
        const toggleBtn = document.getElementById('toggleOperatoriRiga');
        if (toggleBtn && !toggleBtn.classList.contains('active')) {
          toggleBtn.classList.add('active');
          document.body.classList.add('show-op-per-riga');
        }
        
        // IMPORTANTE: Svuota il campo operatore globale per evitare conflitti
        const operatorInput = document.getElementById('operatorSelectInput');
        if (operatorInput) {
          operatorInput.value = '';
          delete operatorInput.dataset.selectedOperator;
          operatorInput.placeholder = 'Multi-operatore';
          operatorInput.disabled = true;
        }
        
        // Aggiorna colonne operatore per ogni riga
        document.querySelectorAll('.scontrino-row').forEach(r => {
          const opCol = r.querySelector('.op-col');
          if (opCol) {
            const nome = r.dataset.operatorNome || '';
            opCol.textContent = nome ? capitalizeName(nome) : '—';
          }
        });
      }, 200);
    }
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
        const nome = (op.nome || '').trim();
        const cognome = (op.cognome || '').trim();
        const label = [nome, cognome].filter(Boolean).map(capitalizeName).join(' ');
        const item = document.createElement('button');
        item.type = 'button';
        item.className = 'dropdown-item';
        item.textContent = label || '—';
        item.dataset.operatorId = op.id;
        item.onclick = function () {
          operatorInput.value = label || '';
          operatorInput.dataset.selectedOperator = op.id;
          operatorDropdown.style.display = 'none';
          operatorInput.dispatchEvent(new Event('change'));
        };
        operatorDropdown.appendChild(item);
      });
      operatorDropdown.style.display = operators.length ? 'block' : 'none';
    });
});

    // Se ci sono servizi precompilati dal calendar, IGNORA il localStorage
  // per evitare che si sommino voci vecchie a quelle nuove
  if (window.SERVIZI_PRECOMPILATI && window.SERVIZI_PRECOMPILATI.length > 0) {
    localStorage.removeItem('scontrinoServizi');
    localStorage.removeItem('scontrinoCliente');
    localStorage.removeItem('scontrinoOperatore');
  }

  // --- RIPRISTINA SERVIZI DAL LOCALSTORAGE AL CARICAMENTO ---
  // Solo se NON ci sono servizi precompilati
  if (!window.SERVIZI_PRECOMPILATI || window.SERVIZI_PRECOMPILATI.length === 0) {
    let serviziSalvati = JSON.parse(localStorage.getItem('scontrinoServizi') || '[]');
    serviziSalvati.forEach(servizio => aggiungiRigaServizio(servizio, false));
  }

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
            window.settingClientProgrammatically = true;
            const nomeCompleto = `${capitalizeName(c.nome)} ${capitalizeName(c.cognome)}`;
            clientInput.value = nomeCompleto;
            clientInput.dataset.selectedClient = c.id;
            clientDropdown.style.display = 'none';
            caricaPrepagateCliente(c.id, nomeCompleto);
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

    // Raccogliamo prima tutte le voci con i loro prezzi originali
    const vociConPrepagata = [];
    let hasValidationError = false;
    
    rows.forEach(row => {
      const isGrigia = row.style.background === 'rgb(220, 220, 220)' || row.style.background === '#dcdcdc';
      const nome = row.querySelector('.flex-grow-1')?.textContent.trim() || '';
      const prezzo = parseFloat(row.querySelector('.scontrino-row-prezzo')?.value || '0');
      const sconto_riga = parseInt(row.querySelector('.scontrino-row-sconto')?.value || '0');
      const metodo = row.querySelector('select')?.value || 'cash';
      
      if (!isFinite(prezzo) || isNaN(prezzo)) {
        alert('Prezzo non valido in una riga. Correggi prima di inviare.');
        hasValidationError = true;
        return;
      }
      if (prezzo < 0) {
        alert('Prezzi negativi non sono consentiti.');
        hasValidationError = true;
        return;
      }
      
      const servizio_id = row.dataset.servizioId || null;
      const appointment_id = row.dataset.appointmentId || null;
      const rata_id = row.dataset.rataId || null;
      const pacchetto_id = row.dataset.pacchettoId || null;
      
      // Se metodo è prepagata, salviamo il prezzo originale e imposteremo a 0 dopo lo scalamento
      const isPrepagata = (metodo === 'prepagata');
      
      const operator_id_riga = row.dataset.operatorId || null;
      
      // Operatore specifico per questa riga (se toggle attivo) oppure globale
      const operatorIdRiga = row.dataset.operatorId || document.getElementById('operatorSelectInput')?.dataset.selectedOperator || null;
      
      const voce = {
        servizio_id,
        nome,
        prezzo: isPrepagata ? 0 : prezzo,
        prezzo_originale: prezzo,
        sconto_riga,
        tipo: 'service',
        metodo_pagamento: metodo,
        is_fiscale: isPrepagata ? false : !isGrigia,
        operator_id: operatorIdRiga
      };
      if (appointment_id) voce.appointment_id = appointment_id;
      if (rata_id) voce.rata_id = parseInt(rata_id);
      if (pacchetto_id) voce.pacchetto_id = parseInt(pacchetto_id);
      
      // IMPORTANTE: Copia prepagata_id e ricarica_prepagata_id dal dataset della riga
      const prepagataId = row.dataset.prepagataId;
      const ricaricaPrepagataId = row.dataset.ricaricaPrepagataId;
      if (prepagataId) voce.prepagata_id = parseInt(prepagataId);
      if (ricaricaPrepagataId) voce.ricarica_prepagata_id = parseInt(ricaricaPrepagataId);
      
      if (isPrepagata) {
        vociConPrepagata.push({ voce, prezzo });
      }
      
      // Se pagato con prepagata, va sempre nei non fiscali (registro con prezzo 0)
      // Altrimenti, segue la logica normale (grigio = non fiscale, chiaro = fiscale)
      if (isPrepagata || isGrigia) {
        voci_non_fiscali.push(voce);
      } else {
        voci_fiscali.push(voce);
      }
    });

    if (hasValidationError) { stampaLock = false; return; }
    
    const cliente_id = document.getElementById('clientSearchInputCassa').dataset.selectedClient || null;
    const operatore_id = document.getElementById('operatorSelectInput').dataset.selectedOperator || null;
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    
    // ========== GESTIONE PAGAMENTO CON PREPAGATA ==========
    // Se ci sono voci pagate con prepagata, scala il credito dalla carta
    if (vociConPrepagata.length > 0 && window.clientePrepagate && window.clientePrepagate.length > 0) {
      const totalePrepagata = vociConPrepagata.reduce((sum, v) => sum + v.prezzo, 0);
      const prepagata = window.clientePrepagate[0]; // Usiamo la prima carta disponibile
      
      try {
        const scalaturaRes = await fetch(`/pacchetti/api/pacchetti/${prepagata.id}/utilizza`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(csrfToken ? { 'X-CSRFToken': csrfToken } : {})
          },
          body: JSON.stringify({
            importo: totalePrepagata,
            descrizione: vociConPrepagata.map(v => v.voce.nome).join(', ')
          })
        });
        
        const scalaturaData = await scalaturaRes.json();
        
        if (!scalaturaRes.ok || !scalaturaData.success) {
          alert(`Errore scalamento prepagata: ${scalaturaData.error || 'Errore sconosciuto'}`);
          stampaLock = false;
          return;
        }
        
        console.log(`Scalati €${totalePrepagata.toFixed(2)} dalla prepagata. Nuovo saldo: €${scalaturaData.credito_residuo.toFixed(2)}`);
        
        // Aggiorna il saldo locale della prepagata
        prepagata.credito_residuo = scalaturaData.credito_residuo;
        
      } catch (err) {
        alert('Errore durante lo scalamento della prepagata: ' + err.message);
        stampaLock = false;
        return;
      }
    }

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
  // Nascondi lo spinner RCH prima di mostrare il modal
  if (typeof window.hideRchSpinner === 'function') {
    window.hideRchSpinner();
  }

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
  overlay.style.zIndex = '13000'; 

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
        // 1. Nascondi lo spinner se visibile
        if (typeof window.hideRchSpinner === 'function') {
          window.hideRchSpinner();
        }

        // 2. Se ci sono voci non fiscali (grigi), salva Receipt non fiscale
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

        // 3. Aggiorna stati appuntamenti
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

        // 4. Pulisci gli ID originali
        if (window.originalAppointmentIds && typeof window.originalAppointmentIds.clear === 'function') {
          window.originalAppointmentIds.clear();
        }

        // 5. Svuota lo pseudoscontrino (DOM + localStorage) PRIMA del popup
        resetScontrino(true);
        await Promise.allSettled(updatePromises);

        // 4. Pulisci le modifiche salvate in localStorage per questi appointment
        try {
          const allApptIds = Array.from(new Set([
            ...Array.from(document.querySelectorAll('.scontrino-row')).map(r => r.dataset.appointmentId).filter(Boolean),
            ...(window.originalAppointmentIds ? Array.from(window.originalAppointmentIds) : []),
            ...(window.lastPseudoscontrinoAppointmentIds || [])
          ])).map(String).sort();
          if (allApptIds.length) {
            localStorage.removeItem(`pseudoscontrino_modifiche_group_${allApptIds.join('_')}`);
            allApptIds.forEach(id => localStorage.removeItem(`pseudoscontrino_modifiche_for_${id}`));
          }
          if (typeof window.unmarkEditedIds === 'function') window.unmarkEditedIds(allApptIds);
        } catch(_) {}

        // Pulisci gli ID originali
        if (window.originalAppointmentIds && typeof window.originalAppointmentIds.clear === 'function') {
          window.originalAppointmentIds.clear();
        }
        // 6. Mostra popup successo e poi redirect (UNICO showSuccessPopup)
        showSuccessPopup('Scontrino stampato con successo!', 3000, () => {
          if (nonFiscaleResponse && nonFiscaleResponse.redirect_to_pacchetto) {
            const url = `/pacchetti/detail/${nonFiscaleResponse.redirect_to_pacchetto}`;
            if (nonFiscaleResponse.rata_importo_modificato) {
              window.location.href = url + '?ricalcola_rate=1';
            } else {
              window.location.href = url;
            }
          } else {
            window.location.href = '/cassa';
          }
        });
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

        if (!res.ok) {
          stampaLock = false;
          alert((data && data.error) || 'Errore durante la stampa fiscale!');
          return;
        }

        // Successo immediato
        await fiscaleOkFinalize();
        return;
      } catch (err) {
        stampaLock = false;
        alert('Errore di rete durante la stampa fiscale.');
        return;
      }
    }

    // Se ci sono voci non fiscali, salva Receipt non fiscale (NON invia a RCH)
    let nonFiscaleResponse = null;
    if (voci_non_fiscali.length > 0) {
      const payloadNonFiscale = {
        voci: voci_non_fiscali,
        cliente_id,
        operatore_id,
        is_fiscale: false
      };
      try {
        const res = await fetch('/cassa/send-to-rch', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(csrfToken ? { 'X-CSRFToken': csrfToken } : {})
          },
          body: JSON.stringify(payloadNonFiscale)
        });
        nonFiscaleResponse = await res.json();
        console.log('Non fiscale response:', nonFiscaleResponse);
      } catch (err) {
        console.error('Errore invio non fiscale:', err);
      }
    }

    // Gestione redirect per prepagata/pacchetto (flusso solo non fiscale)
    let redirectUrl = null;
    
    if (nonFiscaleResponse && nonFiscaleResponse.redirect_to_pacchetto) {
        redirectUrl = `/pacchetti/detail/${nonFiscaleResponse.redirect_to_pacchetto}`;
    } else {
        // Cerca prepagata_id o ricarica_prepagata_id nelle voci originali
        const tutteLeVoci = [...(voci_fiscali || []), ...(voci_non_fiscali || [])];
        for (const v of tutteLeVoci) {
            const pid = v.prepagata_id || v.ricarica_prepagata_id;
            if (pid) {
                redirectUrl = `/pacchetti/detail/${pid}`;
                break;
            }
        }
    }

    // Svuota lo pseudoscontrino e sblocca
    resetScontrino(true);
    stampaLock = false;

    console.log('DEBUG: redirectUrl finale =', redirectUrl);

    showSuccessPopup('Pagamento registrato con successo!', 5000, () => {
      if (redirectUrl) {
        console.log('DEBUG: Eseguo redirect a:', redirectUrl);
        window.location.href = redirectUrl;
      } else {
        window.location.href = '/cassa';
      }
    });

    // Termina qui il flusso non fiscale
    return;
});

  // === ANNULLA ULTIMO SCONTRINO ===
  document.getElementById('btnAnnullaScontrino').addEventListener('click', function(e) {
    e.preventDefault();
    
    if (!confirm('Sei sicuro di voler ANNULLARE l\'ultimo scontrino fiscale emesso?\n\nQuesta operazione invierà uno storno alla stampante RCH.')) {
      return;
    }
    
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    
    // Mostra spinner
    window.showRchSpinner && window.showRchSpinner();
    
    fetch('/cassa/annulla-ultimo-scontrino', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      }
    })
    .then(res => res.json().then(data => ({ status: res.status, data })))
    .then(({ status, data }) => {
      window.hideRchSpinner && window.hideRchSpinner();
      
      if (status === 200 && data.status === 'ok') {
        alert(`Scontrino annullato con successo!\nProgressivo storno: ${data.progressivo}`);
        // Opzionale: ricarica la pagina o aggiorna la UI
      } else {
        alert(`Errore durante l'annullamento: ${data.error || 'Errore sconosciuto'}`);
      }
    })
    .catch(err => {
      window.hideRchSpinner && window.hideRchSpinner();
      alert('Errore di rete durante l\'annullamento: ' + err.message);
    });
  });

});

// Funzione per aggiornare il totale
function aggiornaTotale() {
  let totaleScontrino = 0;
  let totaleComplessivo = 0;
  document.querySelectorAll('.scontrino-row').forEach(row => {
    const input = row.querySelector('.scontrino-row-prezzo');
    const prezzo = parseFloat(input.value) || 0;
    const metodo = row.querySelector('select')?.value || 'cash';
    const isGrigia = row.style.background === 'rgb(220, 220, 220)' || row.style.background === '#dcdcdc';
    // Servizi in chiaro (non grigi) e non prepagata
    if (!isGrigia && metodo !== 'prepagata') {
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
  /* filepath: c:\Program Files\SunBooking\appl\static\js\cassa.js */
row.className = 'd-flex align-items-center scontrino-row';
  row.style.background = '#fff';
  row.dataset.servizioId = servizio.id || '';
  row.dataset.categoria = servizio.categoria || '';
  row.dataset.sottocategoriaId = servizio.sottocategoria_id || '';
  row.dataset.operatorId = servizio.operator_id || '';
  row.dataset.operatorNome = servizio.operator_nome || '';

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

  // Colonna operatore (visibile solo con toggle attivo)
  const opCol = document.createElement('span');
  opCol.className = 'op-col';
  opCol.textContent = servizio.operator_nome ? capitalizeName(servizio.operator_nome) : '—';
  opCol.title = 'Clicca per cambiare operatore';
  opCol.style.cursor = 'pointer';
  opCol.addEventListener('click', function(e) {
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();
    console.log('DEBUG: Click su op-col rilevato');
    console.log('DEBUG: row =', row);
    console.log('DEBUG: window.apriModalOperatoreRiga =', typeof window.apriModalOperatoreRiga);
    window.currentRowForOperator = row;
    // Usa window.apriModalOperatoreRiga per essere sicuri che sia accessibile
    if (typeof window.apriModalOperatoreRiga === 'function') {
      window.apriModalOperatoreRiga(row);
    } else {
      console.error('apriModalOperatoreRiga non definita!');
    }
  });
  row.appendChild(opCol);

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

  // Se è il pagamento di una carta prepagata, blocca la modifica del prezzo
  if (servizio.prepagata_id) {
    prezzo.readOnly = true;
    prezzo.style.backgroundColor = '#e8f5e9';
    prezzo.title = 'Importo fisso: il credito caricato sulla carta è definito alla creazione';
    row.dataset.prepagataId = servizio.prepagata_id;
    row.dataset.creditoDaCaricare = servizio.credito_da_caricare || servizio.prezzo || '0';
  }
  // Se è una ricarica prepagata, blocca anche qui
  if (servizio.ricarica_prepagata_id) {
    prezzo.readOnly = true;
    prezzo.style.backgroundColor = '#e8f5e9';
    prezzo.title = 'Importo fisso per ricarica carta prepagata';
    row.dataset.ricaricaPrepagataId = servizio.ricarica_prepagata_id;
    row.dataset.creditoDaCaricare = servizio.credito_da_caricare || servizio.prezzo || '0';
  }

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
    
    // Se il metodo è prepagata e il nuovo prezzo supera il saldo, avvisa
    if (selectPay.value === 'prepagata') {
      const saldoDisponibile = typeof getSaldoTotalePrepagata === 'function' ? getSaldoTotalePrepagata() : 0;
      const altreRighe = getTotaleAssegnatoPrepagata() - nuovoPrezzo;
      if (nuovoPrezzo + altreRighe > saldoDisponibile) {
        console.warn('Attenzione: prezzo modificato supera saldo prepagata disponibile');
      }
    }
    
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

  // Salva il metodo precedente per controlli
  row.dataset.vecchioMetodo = 'pos';

  // Cambia icona al cambio select
  selectPay.addEventListener('change', function () {
    const nuovoMetodo = selectPay.value;
    const vecchioMetodo = row.dataset.vecchioMetodo || 'pos';
    
    // Se si seleziona prepagata, verifica il saldo
    if (nuovoMetodo === 'prepagata') {
      const prezzoRiga = parseFloat(prezzo.value) || 0;
      if (!verificaSaldoPrepagata(prezzoRiga, selectPay)) {
        // Ripristina il metodo precedente
        selectPay.value = vecchioMetodo;
        return;
      }
    }
    
    // Aggiorna il metodo salvato
    row.dataset.vecchioMetodo = nuovoMetodo;
    
    if (nuovoMetodo === 'pos') payIcon.className = 'bi bi-calculator ms-2';
    else if (nuovoMetodo === 'cash') payIcon.className = 'bi bi-cash ms-2';
    else if (nuovoMetodo === 'bank') payIcon.className = 'bi bi-bank ms-2';
    else if (nuovoMetodo === 'prepagata') payIcon.className = 'bi bi-credit-card ms-2';

    // Se NON è cash, la riga torna bianca subito
    if (nuovoMetodo !== 'cash') {
      row.style.background = '#fff';
    }
    aggiornaTotale();
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
  
  // Aggiorna opzione prepagata se il cliente ha carte prepagate
  if (typeof window.aggiornaOpzioniPrepagata === 'function') {
    window.aggiornaOpzioniPrepagata();
  }

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

  // Toggle automatico se ci sono operatori diversi tra le righe
  setTimeout(function() {
    const allRows = document.querySelectorAll('.scontrino-row');
    if (allRows.length < 2) return;
    
    const operatorIds = new Set();
    allRows.forEach(r => {
      const opId = r.dataset.operatorId;
      if (opId && opId !== '') operatorIds.add(opId);
    });
    
    // Se ci sono almeno 2 operatori diversi, attiva il toggle E disabilita campo globale
    if (operatorIds.size >= 2) {
      const toggleBtn = document.getElementById('toggleOperatoriRiga');
      if (toggleBtn && !toggleBtn.classList.contains('active')) {
        toggleBtn.classList.add('active');
        document.body.classList.add('show-op-per-riga');
      }
      
      // Disabilita e svuota il campo operatore globale
      const operatorInput = document.getElementById('operatorSelectInput');
      if (operatorInput && !operatorInput.disabled) {
        operatorInput.value = '';
        delete operatorInput.dataset.selectedOperator;
        operatorInput.placeholder = 'Multi-operatore';
        operatorInput.disabled = true;
      }
      
      // Assicurati che ogni riga mostri il suo operatore
      allRows.forEach(r => {
        const opCol = r.querySelector('.op-col');
        if (opCol) {
          const nome = r.dataset.operatorNome || '';
          opCol.textContent = nome ? capitalizeName(nome) : '—';
        }
      });
    }
  }, 100);
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
        else if (tipo === 'prepagata') icon.className = 'bi bi-credit-card ms-2';
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
  let subtotali = { pos: 0, cash: 0, bank: 0, prepagata: 0 };
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
    if (subtotali.prepagata > 0) {
      const div = document.createElement('div');
      div.appendChild(document.createTextNode('- subtotale PREPAGATA: '));
      const b = document.createElement('b');
      b.textContent = `€ ${subtotali.prepagata.toFixed(2)}`;
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
      if (op) document.getElementById('operatorSelectInput').value = op.nome;
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

// Toggle visibilità colonna operatore per riga
document.getElementById('toggleOperatoriRiga')?.addEventListener('click', function() {
  this.classList.toggle('active');
  document.body.classList.toggle('show-op-per-riga');
  
  const isActive = this.classList.contains('active');
  const operatorInput = document.getElementById('operatorSelectInput');
  
  if (isActive) {
    // Disabilita campo operatore globale quando toggle è attivo
    if (operatorInput) {
      operatorInput.value = '';
      delete operatorInput.dataset.selectedOperator;
      operatorInput.placeholder = 'Multi-operatore';
      operatorInput.disabled = true;
    }
  } else {
    // Riabilita campo operatore globale quando toggle è disattivato
    if (operatorInput) {
      operatorInput.disabled = false;
      operatorInput.placeholder = 'Seleziona operatore...';
    }
  }
});

// Funzione per aprire mini-modal selezione operatore
function apriModalOperatoreRiga(row) {
  console.log('apriModalOperatoreRiga chiamata con row:', row);

  const lista = document.getElementById('listaOperatoriRigaModal');
  if (!lista) {
    console.error('Elemento listaOperatoriRigaModal non trovato!');
    return;
  }
  lista.innerHTML = '<div class="text-center"><div class="spinner-border spinner-border-sm"></div></div>';
  
  const modalEl = document.getElementById('modalSelezionaOperatoreRiga');
  if (!modalEl) {
    console.error('Elemento modalSelezionaOperatoreRiga non trovato!');
    return;
  }

  const modal = new bootstrap.Modal(modalEl);
  modal.show();
  
  fetch('/cassa/api/operators')
    .then(res => res.json())
    .then(operators => {
      console.log('Operatori ricevuti:', operators);
      lista.innerHTML = '';
      if (!Array.isArray(operators) || operators.length === 0) {
        lista.innerHTML = '<p class="text-muted small">Nessun operatore disponibile</p>';
        return;
      }
      operators.forEach(op => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'btn btn-outline-secondary w-100 mb-1 text-start py-1';
        btn.style.fontSize = '0.8em';
        // Usa window.capitalizeName oppure fallback
        const capName = (typeof window.capitalizeName === 'function') 
          ? window.capitalizeName(op.nome) 
          : (op.nome || '');
        btn.textContent = capName;
        
        // Evidenzia se già selezionato
        if (String(row.dataset.operatorId) === String(op.id)) {
          btn.classList.remove('btn-outline-secondary');
          btn.classList.add('btn-primary');
        }
        
        btn.addEventListener('click', function() {
          row.dataset.operatorId = op.id;
          row.dataset.operatorNome = op.nome;
          const opCol = row.querySelector('.op-col');
          if (opCol) opCol.textContent = capitalizeName(op.nome);
          modal.hide();
          
          // Segna come modificato
          window.hasModifications = true;
          if (typeof mostraPulsanteSalva === 'function') mostraPulsanteSalva();
        });
        lista.appendChild(btn);
      });
    })
    .catch(err => {
      console.error('Errore fetch operatori:', err);
      lista.innerHTML = '<p class="text-danger small">Errore nel caricamento</p>';
    });
}
window.apriModalOperatoreRiga = apriModalOperatoreRiga;