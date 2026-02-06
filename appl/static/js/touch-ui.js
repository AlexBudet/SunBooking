(function(){
  // Attiva solo se abilitato da settings (localStorage)
  try {
    if (localStorage.getItem('sun_touch_ui') !== '1') return;
  } catch(e) { return; }

  const CSRF = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

 // Helper sicuro per icone Bootstrap (evita innerHTML)
  function biIcon(name) {
    const i = document.createElement('i');
    i.className = `bi bi-${name}`;
    i.setAttribute('aria-hidden', 'true');
    return i;
  }

// Tooltip: rimuovi Bootstrap tooltip e attributi correlati (uniforma ai tooltip di default)
function stripTooltip(el) {
  try {
    if (window.bootstrap?.Tooltip) {
      const inst = bootstrap.Tooltip.getInstance(el);
      if (inst) inst.dispose();
    }
  } catch(_) {}
  el.removeAttribute('data-bs-toggle');
  el.removeAttribute('data-toggle');
  el.removeAttribute('data-bs-placement');
  el.removeAttribute('data-placement');
  el.removeAttribute('data-bs-original-title');
  el.removeAttribute('data-original-title');
  el.removeAttribute('aria-describedby');
}

function normalizeTooltips(container = document) {
  container.querySelectorAll('.appointment-block .btn-popup').forEach(stripTooltip);
  container.querySelectorAll('.myspia-item .btn-popup').forEach(stripTooltip);
}

// Helper per creare pulsanti bottom bar
function makeBottomBtn(cls, title, icon, onClick) {
  const b = document.createElement('button');
  b.type = 'button';
  b.className = `btn-popup ${cls}`;
  b.title = title;
  b.appendChild(biIcon(icon));
  b.addEventListener('click', (e) => {
    e.stopPropagation();
    try { onClick && onClick(e); } catch(_) {}
    closeAllPopups();
  });
  return b;
}

(function installTouchNoShowListener() {
  if (window.__touchNoShowListenerInstalled) return;
  window.__touchNoShowListenerInstalled = true;

  document.addEventListener('click', function (e) {
    const btn = e.target && e.target.closest && e.target.closest('.btn-popup.touch-no-show, .btn-popup.touch-noshow');
    if (!btn) return;

    // Intercetta qui per impedire l'handler inline e duplicazioni
    e.preventDefault();
    e.stopPropagation();
    if (typeof e.stopImmediatePropagation === 'function') e.stopImmediatePropagation();

    // Risali al blocco appuntamento in modo robusto
    let block = btn.closest && btn.closest('.appointment-block');
    let appointmentId = '';

    if (block) {
      appointmentId = block.getAttribute('data-appointment-id') || '';
    } else {
      appointmentId = btn.getAttribute && btn.getAttribute('data-appointment-id') || '';
      if (!appointmentId) {
        const active = document.querySelector('.appointment-block.active-popup');
        if (active) {
          block = active;
          appointmentId = active.getAttribute('data-appointment-id') || '';
        }
      } else {
        block = document.querySelector(`.appointment-block[data-appointment-id="${appointmentId}"]`) || null;
      }
    }

    if (!appointmentId) return;

    // Usa la stessa logica del modal Delete/NoShow: chiama setNoShow(appointmentId)
    if (typeof window.setNoShow === 'function') {
      try { window.setNoShow(appointmentId); } catch(_) {}
    } else {
      // Fallback: clicca il bottone no-show del blocco (se presente)
      const noShow = block && block.querySelector('.btn-popup.no-show-button');
      if (noShow && typeof noShow.click === 'function') {
        noShow.click();
      }
    }

    // Chiudi i popup dopo l’azione
    setTimeout(() => { try { closeAllPopups(); } catch (_) {} }, 0);
  }, true);
})();

function closeAllPopups() {
  // Reset active state and z-index
  document.querySelectorAll('.appointment-block.active-popup')
    .forEach(b => {
      b.classList.remove('active-popup');
      b.style.zIndex = '100';
    });

  // Restore any client-info links disabled during "only cut" mode
  document.querySelectorAll('.client-info-link[data-touch-only-cut="1"]').forEach(a => {
    a.style.pointerEvents = '';
    a.removeAttribute('data-touch-only-cut');
  });

  // Close client popups forcefully
  const clientPopup = document.getElementById('clientHistoryPopup');
  if (clientPopup) clientPopup.style.display = 'none';
  const small = document.getElementById('clientInfoPopup');
  if (small) small.style.display = 'none';
  forceHideClientInfoPopup();

  // Ripristina esplicitamente gli stili dei bottoni noti (uno per uno)
  const restoreSelectors = [
    '.btn-popup.delete-appointment-block',
    '.btn-popup.nota',
    '.btn-popup.copia',
    '.btn-popup.sposta',
    '.btn-popup.colore',
    '.btn-popup.color',
    '.btn-popup.to-cash',
    '.btn-popup.go-cash',
    '.btn-popup.cassa',
    '.btn-popup.add-services',
    '.btn-popup.aggiungi-servizi',
    '.btn-popup.aggiungi-servizio',
    '.btn-popup.add-service',
    '.btn-popup.whatsapp-btn',
    '.btn-popup.copy-off-block',
    '.btn-popup.delete-off-block',
    '.btn-popup.touch-top-copy',
    '.btn-popup.touch-top-delete',
    '.btn-popup.taglia',
    '.btn-popup.touch-top-cut'
  ];
restoreSelectors.forEach(sel => {
  document.querySelectorAll(sel).forEach(btn => {
    btn.style.display = '';
    btn.style.visibility = '';
    btn.style.zIndex = '';
    // Ripristina eventuali override applicati al TAGLIA
    btn.style.flex = '';
    btn.style.width = '';
  });
});

  // Rimuovi eventuali fallback creati (.btn-popup.taglia.touch-only-cut)
  document.querySelectorAll('.btn-popup.taglia.touch-only-cut').forEach(btn => {
    try { btn.remove(); } catch(_) {}
  });

  // Restore bars and clear inline overrides on containers
  document.querySelectorAll('.appointment-block .popup-buttons, .appointment-block .popup-buttons-bottom')
    .forEach(el => {
      el.style.zIndex = '';
      el.style.display = '';
    });

  // Close any my-spia popups
  closeAllMySpiaPopups();
}

// In touch mode: disabilita hover e abilita solo click per i my-spia
function injectTouchMySpiaCSS() {
  if (document.getElementById('touch-myspia-css')) return;
  const css = `
    body.touch-ui .myspia-item .myspia-actions { display: none !important; }
    body.touch-ui .myspia-item:hover .myspia-actions { display: none !important; }
    body.touch-ui .myspia-item.myspia-open .myspia-actions { display: inline-flex !important; }
  `;
  const style = document.createElement('style');
  style.id = 'touch-myspia-css';
  style.textContent = css;
  document.head.appendChild(style);
}

function installInterceptClientNameClicks() {
  if (window.__touchClientLinkEditInterceptorInstalled) return;

  const handlerEdit = function(e) {
    if (!document.body.classList.contains('touch-ui')) return;

    const link = e.target && e.target.closest && e.target.closest('.client-info-link');
    if (!link) return;

    const block = link.closest('.appointment-block');
    if (!block) return;

    // Stato 0 (cambio cliente) solo se blocco già attivo
    if (!block.classList.contains('active-popup')) return;
    if (String(block.getAttribute('data-status')) !== '0') return;

    e.preventDefault();
    e.stopPropagation();
    if (typeof e.stopImmediatePropagation === 'function') e.stopImmediatePropagation();

    // Apri modal cambio cliente / info cliente (ordina fallback)
    const apptId = block.getAttribute('data-appointment-id') || '';
    const cid = block.getAttribute('data-client-id') || link.getAttribute('data-client-id') || '';

    if (apptId && typeof window.openModifyPopup === 'function') {
      window.openModifyPopup(apptId);
      return;
    }
    if (typeof window.openClientInfoMobileModal === 'function') {
      window.openClientInfoMobileModal(block);
      return;
    }
    if (typeof window.showClientInfoModal === 'function' && cid) {
      window.showClientInfoModal(cid);
      return;
    }
    if (typeof window.showClientInfoForBlock === 'function') {
      window.showClientInfoForBlock(block);
    }
  };

  document.addEventListener('click', handlerEdit, true);
  document.querySelectorAll('.client-info-link').forEach(a => {
    try { a.addEventListener('click', handlerEdit, true); } catch(_) {}
  });
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.client-info-link').forEach(a => {
      try { a.addEventListener('click', handlerEdit, true); } catch(_) {}
    });
  });

  window.__touchClientLinkEditInterceptorInstalled = true;
}

// Installa l'intercettore
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', installInterceptClientNameClicks);
} else {
  installInterceptClientNameClicks();
}

// Gestione click-to-open per “Blocchi in istituto” (myspia) in modalità touch
function ensureMySpiaTouchOnItem(item) {
  if (!item || item._touchBound) return;
  item._touchBound = true;

  // apertura/chiusura su click dell’intero item (ma non sui bottoni)
  item.addEventListener('click', (e) => {
    if (e.target.closest('.myspia-actions .btn-popup')) return; // lascia ai bottoni
    const wasOpen = item.classList.contains('myspia-open');
    closeAllMySpiaPopups(); // chiudi altri
    if (!wasOpen) openMySpiaItem(item);
  });

  // prevenzione bubbling sui bottoni (restano cliccabili)
  item.querySelectorAll('.myspia-actions .btn-popup').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
    });
  });
}

function openMySpiaItem(item) {
  item.classList.add('myspia-open');
}

function closeMySpiaItem(item) {
  item.classList.remove('myspia-open');
}

function closeAllMySpiaPopups() {
  document.querySelectorAll('.myspia-item.myspia-open').forEach(closeMySpiaItem);
}

function initMySpiaTouch(root = document) {
  root.querySelectorAll('.myspia-item').forEach(ensureMySpiaTouchOnItem);
}

function _filterOffTopBarButtons(topBar) {
  const isAllowed = (btn) =>
    btn.classList.contains('delete-appointment-block') ||
    (btn.classList.contains('nota') && btn.classList.contains('touch-top-note')) ||
    (btn.classList.contains('copia') && btn.classList.contains('touch-top-copy')) ||
    btn.classList.contains('vai-pacchetto') ||  // <-- AGGIUNTO: permetti vai-pacchetto
    // Consenti il CUT touch anche senza classe "taglia"
    btn.classList.contains('touch-top-cut');

  // Nascondi tutti i non consentiti
  topBar.querySelectorAll('.btn-popup').forEach(btn => {
    if (!isAllowed(btn)) btn.style.display = 'none';
  });

  // Nascondi in modo esplicito le azioni note richieste
  topBar.querySelectorAll(
    '.btn-popup.colore, .btn-popup.color, ' + // colore
    '.btn-popup.to-cash, .btn-popup.go-cash, .btn-popup.cassa, .btn-popup.pagamento:not(.vai-pacchetto), ' + // porta in cassa (MA NON vai-pacchetto)
    '.btn-popup.add-services, .btn-popup.aggiungi-servizi, .btn-popup.aggiungi-servizio, .btn-popup.add-service, ' + // aggiungi servizi
    '.btn-popup.copia:not(.touch-top-copy)' // copia generica (interna) non la nostra top
  ).forEach(btn => { btn.style.display = 'none'; });
}

function _filterStatus2TopBarButtons(topBar) {
  console.log('=== FILTRO STATUS-2 CHIAMATO ===');
  const allButtons = topBar.querySelectorAll('.btn-popup');
  console.log('Bottoni totali trovati:', allButtons.length);
  
  allButtons.forEach(btn => {
    const classList = Array.from(btn.classList).join(' ');
    const hasVaiPacchetto = btn.classList.contains('vai-pacchetto');
    console.log('Bottone:', classList, '| vai-pacchetto?', hasVaiPacchetto);
    
    if (btn.classList.contains('copia') || 
        btn.classList.contains('nota') || 
        btn.classList.contains('vai-pacchetto')) {
      btn.style.setProperty('display', 'inline-flex', 'important');
      btn.style.setProperty('visibility', 'visible', 'important');
      console.log('  -> MOSTRATO');
    } else {
      btn.style.setProperty('display', 'none', 'important');
      btn.style.setProperty('visibility', 'hidden', 'important');
      console.log('  -> NASCOSTO');
    }
  });
}

function ensureTopBarForTouch(block) {
  let topBar = block.querySelector('.popup-buttons');
  const isOff = block.classList.contains('note-off');

  if (!topBar) {
    topBar = document.createElement('div');
    topBar.className = 'popup-buttons';
    block.insertBefore(topBar, block.firstChild);
  }

  if (isOff) {
    topBar.style.justifyContent = 'flex-end';
    topBar.style.alignItems = 'center';
    topBar.style.gap = '6px';

    // Nascondi tutto, poi mostriamo solo i 4 consentiti (aggiunto taglia)
    topBar.querySelectorAll('.btn-popup').forEach(btn => (btn.style.display = 'none'));

    // DELETE (invariato)
    let del = topBar.querySelector('.btn-popup.delete-appointment-block.touch-top-delete');
    if (!del) {
      del = document.createElement('button');
      del.className = 'btn-popup delete-appointment-block touch-top-delete';
      del.title = 'Elimina appuntamento';
      del.appendChild(biIcon('trash'));
      del.addEventListener('click', (e) => {
        e.stopPropagation();
        const id = block.getAttribute('data-appointment-id');
        if (id && typeof window.deleteAppointment === 'function') window.deleteAppointment(id);
        closeAllPopups();
      });
      topBar.appendChild(del);
    }
    del.style.display = 'inline-block';

    // COPY (vecchia logica OFF)
    let copy = topBar.querySelector('.btn-popup.copia.touch-top-copy');
    if (!copy) {
      copy = document.createElement('button');
      copy.className = 'btn-popup copia touch-top-copy';
      copy.title = 'Copia blocco OFF';
      copy.appendChild(biIcon('files'));
      copy.addEventListener('click', async (e) => {
        e.stopPropagation();
        let oldCopyBtn = block.querySelector('.btn-popup.copy-off-block');
        if (oldCopyBtn) { oldCopyBtn.click(); closeAllPopups(); return; }
        try {
          if (typeof window.copyAndPasteBlockOff === 'function') {
            window.copyAndPasteBlockOff();
            await new Promise(r => setTimeout(r, 0));
            oldCopyBtn = block.querySelector('.btn-popup.copy-off-block');
          }
        } catch(_) {}
        if (oldCopyBtn) { oldCopyBtn.click(); closeAllPopups(); return; }
        const genericCopy = block.querySelector('.popup-buttons .btn-popup.copia');
        if (genericCopy && genericCopy !== copy) genericCopy.click();
        closeAllPopups();
      });
      topBar.appendChild(copy);
    }
    copy.style.display = 'inline-block';

    // NOTE (invariata)
    let note = topBar.querySelector('.btn-popup.nota.touch-top-note');
    if (!note) {
      note = document.createElement('button');
      note.className = 'btn-popup nota touch-top-note';
      note.title = 'Nota appuntamento';
      note.appendChild(biIcon('pencil-square'));
      note.addEventListener('click', (e) => {
        e.stopPropagation();
        if (typeof window.openNoteModal === 'function') window.openNoteModal(block);
        closeAllPopups();
      });
      topBar.appendChild(note);
    }
    note.style.display = 'inline-block';

// TAGLIA / SPOSTA OFF (modalità touch-ui) — bottone dedicato alla touch-ui
let cut = topBar.querySelector('.btn-popup.taglia.touch-top-cut');
if (!cut) {
  cut = document.createElement('button');
  cut.className = 'btn-popup taglia touch-top-cut'; 
  cut.title = 'Sposta blocco OFF';
  cut.appendChild(biIcon('scissors'));
  cut.addEventListener('pointerdown', (e) => {
    e.stopPropagation();
    e.preventDefault();
    e.stopImmediatePropagation();
    startOffMove(block);
    closeAllPopups();
  }, true);
  topBar.appendChild(cut);
}
cut.style.display = 'inline-block';

    // Filtra e mantieni nascosti i bottoni non consentiti
    _filterOffTopBarButtons(topBar);

    // Protezione: se altri bottoni vengono aggiunti dopo, nascondili subito
    if (!topBar._offFilterObserver) {
      const mo = new MutationObserver(() => _filterOffTopBarButtons(topBar));
      mo.observe(topBar, { childList: true });
      topBar._offFilterObserver = mo;
    }

    // Nascondi anche le icone interne al blocco (non nella top bar)
    block.querySelectorAll(
      '.btn-popup.delete-appointment-block, .btn-popup.copia, .btn-popup.copy-off-block, .btn-popup.delete-off-block,' +
      '[data-action="delete"], [data-action="copy"], .icon-trash, .icon-copy, .fa-trash, .fa-copy,' +
      '.bi-trash, .bi-clipboard, .bi-files, .bi-copy'
    ).forEach(el => {
      if (el.closest('.popup-buttons') !== topBar) el.style.display = 'none';
    });

    return;
  }

    // TOUCH-UI: blocchi disable-popup (cliente eliminato) -> crea pulsante DELETE nella topBar
  const isDisablePopup = block.classList.contains('disable-popup');
  if (isDisablePopup) {
    // Nascondi tutti i bottoni esistenti
    topBar.querySelectorAll('.btn-popup').forEach(btn => (btn.style.display = 'none'));
    
    // Crea o trova il pulsante delete
    let del = topBar.querySelector('.btn-popup.delete-appointment-block');
    if (!del) {
      del = document.createElement('button');
      del.type = 'button';
      del.className = 'btn-popup delete-appointment-block';
      del.title = 'Elimina appuntamento';
      del.setAttribute('data-appointment-id', block.getAttribute('data-appointment-id') || '');
      del.appendChild(biIcon('trash'));
      del.addEventListener('click', (e) => {
        e.stopPropagation();
        const id = block.getAttribute('data-appointment-id');
        if (id && typeof window.deleteAppointment === 'function') window.deleteAppointment(id);
        closeAllPopups();
      });
      topBar.appendChild(del);
    }
    del.style.display = 'inline-flex';
    
    // Nascondi my-spia
    const mySpia = block.querySelector('.my-spia');
    if (mySpia) mySpia.style.display = 'none';
    
    return;
  }

  // Per blocchi STATUS-2 (pagati): la topBar esiste già nel DOM con i bottoni renderizzati da Jinja
  // Non fare nulla qui, il filtering verrà fatto nel click handler
  const status = block.getAttribute('data-status');
  if (status === '2') {
    console.log('ensureTopBarForTouch: blocco status-2, topBar già presente nel DOM');
    return;
  }
}

  // Calcola nuova durata assoluta e salva via /calendar/edit/<id>
  async function setDuration(block, newDuration) {
    newDuration = Math.max(15, Math.round(newDuration / 15) * 15);
    const id = block.getAttribute('data-appointment-id');
    if (!id) return;
    try {
      const res = await fetch(`/calendar/edit/${encodeURIComponent(id)}`, {
        method: 'POST',
        headers: {
          'Content-Type':'application/json',
          'Accept':'application/json',
          'X-Requested-With':'XMLHttpRequest',
          'X-CSRFToken': CSRF
        },
        credentials: 'same-origin',
        body: JSON.stringify({ duration: newDuration })
      });
      if (!res.ok) {
        const txt = await res.text().catch(()=>'');
        console.error('setDuration error', res.status, txt);
        return;
      }
      block.setAttribute('data-duration', String(newDuration));
      if (typeof window.updateAppointmentBlockStyles === 'function') {
        window.updateAppointmentBlockStyles(block);
      } else {
        const q = (typeof window.getQuarterPx === 'function') ? window.getQuarterPx() : 60;
        block.style.height = (newDuration/15)*q + 'px';
      }
    } catch(e) {
      console.error('setDuration exception', e);
    }
  }

// --- SOLO OFF: endpoint separato + fallback UI ---
async function setOffDuration(block, newDuration) {
  newDuration = Math.max(15, Math.round(newDuration / 15) * 15);

  // Usa SEMPRE adjust-duration per OFF se esiste un appointment-id
  const apptId = block.getAttribute('data-appointment-id');
  try {
    if (apptId) {
      const res = await fetch(`/calendar/adjust-duration/${encodeURIComponent(apptId)}`, {
        method: 'POST',
        headers: {
          'Content-Type':'application/json',
          'Accept':'application/json',
          'X-Requested-With':'XMLHttpRequest',
          'X-CSRFToken': CSRF
        },
        credentials: 'same-origin',
        body: JSON.stringify({ adjustment: newDuration }) // durata totale in minuti
      });
      if (!res.ok) {
        const txt = await res.text().catch(()=> '');
        console.error('setOffDuration error', res.status, txt);
      }
    } else {
      // Se non c’è apptId, aggiorna solo UI (nessuna chiamata a /calendar/edit)
      console.warn('OFF senza appointment-id: aggiorno solo UI');
    }
  } catch(e) {
    console.error('setOffDuration exception', e);
  }

  // Aggiorna comunque la UI (fallback locale)
  block.setAttribute('data-duration', String(newDuration));
  if (typeof window.updateAppointmentBlockStyles === 'function') {
    window.updateAppointmentBlockStyles(block);
  } else {
    const q = (typeof window.getQuarterPx === 'function') ? window.getQuarterPx() : 60;
    block.style.height = (newDuration/15) * q + 'px';
  }
}

function changeOffDurationByQuarter(block, deltaQuarters) {
  const cur = parseInt(block.getAttribute('data-duration') || '15', 10);
  const next = cur + (deltaQuarters * 15);
  return setOffDuration(block, next);
}

  // Costruisce la barra inferiore (6 pulsanti)
function ensureBottomBar(block) {
  let topBar = block.querySelector('.popup-buttons');
  const status = block.getAttribute('data-status');
  const isOff = block.classList.contains('note-off');

  if (status === '2') {
    const existing = block.querySelector('.popup-buttons-bottom');
    if (existing) existing.style.display = 'none';
    return;
  }

    if (!topBar) {
    topBar = document.createElement('div');
    topBar.className = 'popup-buttons';
    block.insertBefore(topBar, block.firstChild);
  }

  if (isOff) {
    let bottomBar = block.querySelector('.popup-buttons-bottom');
    if (bottomBar) bottomBar.remove();
    bottomBar = document.createElement('div');
    bottomBar.className = 'popup-buttons-bottom';
    bottomBar.style.display = 'none';

    // OFF: usa la logica dedicata ai blocchi OFF
    const btnDown = makeBottomBtn('touch-resize-down', 'Aumenta durata di 15 min', 'arrow-down',
      () => changeOffDurationByQuarter(block, +1));
    const btnUp = makeBottomBtn('touch-resize-up', 'Riduci durata di 15 min', 'arrow-up',
      () => changeOffDurationByQuarter(block, -1));

    bottomBar.appendChild(btnDown);
    bottomBar.appendChild(btnUp);
    block.appendChild(bottomBar);
    return;
  }

  if (block.querySelector('.popup-buttons-bottom')) return;

  const bar = document.createElement('div');
  bar.className = 'popup-buttons-bottom';
  bar.style.display = 'none';

  // Costruisci i 6 pulsanti in modo sicuro
  buildBottomButtons(block).forEach(b => bar.appendChild(b));
  block.appendChild(bar);
}

function initTouchOnBlock(block){
  const status = block.getAttribute('data-status');
  const apptId = block.getAttribute('data-appointment-id');
  console.log('>>> initTouchOnBlock chiamato per blocco', apptId, 'status:', status, '_touchToggleBound?', block._touchToggleBound);
  
  ensureTopBarForTouch(block);
  ensureBottomBar(block);

  const tb = block.querySelector('.popup-buttons');
  if (tb) tb.style.display = '';
  const bb = block.querySelector('.popup-buttons-bottom');
  if (bb) {
    bb.style.display = '';
    if (block.getAttribute('data-status') === '2') bb.style.display = 'none';
  }

  if (!block.classList.contains('active-popup')) {
    block.style.zIndex = '100';
  }

  console.log('>>> Sto per aggiungere listener? _touchToggleBound:', block._touchToggleBound);
  if (!block._touchToggleBound) {
    block.addEventListener('click', (e) => {
      console.log('=== CLICK SU BLOCCO ===', 'status:', block.getAttribute('data-status'));
      
      // BLOCCA se in modalità copia (solo COPIA visibile)
      if (block.hasAttribute('data-copia-mode')) {
        console.log('>>> BLOCCO IN MODALITA\' COPIA, esco');
        e.stopPropagation();
        return;
      }
      
      // Pulsanti popup: lascia la gestione originale
      if (e.target.closest('.btn-popup')) {
        console.log('>>> CLICK SU BOTTONE POPUP, esco');
        return;
      }

      const isTouchUI = document.body.classList.contains('touch-ui');
      const isPaid = String(block.getAttribute('data-status')) === '2';
      const clientLink = e.target.closest?.('.client-info-link') || null;
      
      console.log('>>> isTouchUI:', isTouchUI, 'isPaid:', isPaid, 'clientLink:', !!clientLink);

// Click sul nome cliente in stato 2 (pagato): apri modal, non chiudere popup
if (isTouchUI && isPaid && clientLink) {
  e.preventDefault();
  e.stopPropagation();
  if (typeof e.stopImmediatePropagation === 'function') e.stopImmediatePropagation();

  // Attiva il blocco se non lo è ancora (mostra eventuali barre top; bottom bar già nascosta per stato 2)
  if (!block.classList.contains('active-popup')) {
    closeAllPopups();
    block.classList.add('active-popup');
    block.style.zIndex = '9400';
    const topBar = block.querySelector('.popup-buttons');
    const bottomBar = block.querySelector('.popup-buttons-bottom');
    if (topBar) {
      topBar.style.zIndex = '9410';
      _filterStatus2TopBarButtons(topBar);
    }
    if (bottomBar) bottomBar.style.zIndex = '9410';
  }

        // Apri modal info cliente robustamente
        const cid = block.getAttribute('data-client-id') || clientLink.getAttribute('data-client-id') || '';
        if (typeof window.openClientInfoMobileModal === 'function') {
          window.openClientInfoMobileModal(block);
          return;
        }
        if (typeof window.showClientInfoModal === 'function' && cid) {
            window.showClientInfoModal(cid);
            return;
        }
        if (typeof window.showClientInfoForBlock === 'function') {
          window.showClientInfoForBlock(block);
        }
        return;
      }

// Click sul resto del blocco: toggle popup
console.log('>>> CLICK CORPO BLOCCO, isPaid?', isPaid, 'status:', block.getAttribute('data-status'));
const wasActive = block.classList.contains('active-popup');
closeAllPopups();
if (!wasActive) {
  console.log('>>> Blocco NON era attivo, lo attivo ora');
  block.classList.add('active-popup');
  block.style.zIndex = '11940';
  const topBar = block.querySelector('.popup-buttons');
  const bottomBar = block.querySelector('.popup-buttons-bottom');
  console.log('>>> topBar trovata?', !!topBar);
  if (topBar) {
    const buttons = topBar.querySelectorAll('.btn-popup');
    console.log('>>> Bottoni nella topBar:', buttons.length);
    buttons.forEach(btn => {
      console.log('  - Bottone classi:', Array.from(btn.classList).join(' '));
    });
    topBar.style.zIndex = '11950';
    topBar.style.display = 'flex';
    if (isPaid) {
      console.log('>>> È STATUS-2, chiamo filtro...');
      _filterStatus2TopBarButtons(topBar);
    }
    // SCAPPATOIA: per blocchi OFF, marca il bottone CUT come "pronto"
    const isOff = block.classList.contains('note-off') || block.classList.contains('off');
    if (isOff) {
      const cutBtn = topBar.querySelector('.btn-popup.touch-top-cut');
      if (cutBtn) {
        cutBtn._offCutReady = true;
      }
    }
  } else {
    console.log('>>> ERRORE: topBar NON TROVATA!');
  }
  if (bottomBar) {
    bottomBar.style.zIndex = '11950';
  }
} else {
  console.log('>>> Blocco GIA\' attivo, chiudo tutto');
}
    }, true);

    block._touchToggleBound = true;
  }
}

document.addEventListener('DOMContentLoaded', function(){

    // Rimuovi i tooltip Bootstrap su tutti i bottoni già presenti
  normalizeTooltips(document);

    // Inizializza la modalità touch per i blocchi in istituto (cassa.html)
  initMySpiaTouch(document);

  if (document.body.classList.contains('touch-ui')) {
    document.querySelectorAll('.appointment-block').forEach(initTouchOnBlock);
  }

// Observer per blocchi aggiunti dinamicamente
  const obs = new MutationObserver(muts => {
    muts.forEach(m => {
      m.addedNodes && m.addedNodes.forEach(node => {
        if (node.nodeType === 1) {
          if (node.classList?.contains('appointment-block')) initTouchOnBlock(node);
          node.querySelectorAll?.('.appointment-block').forEach(initTouchOnBlock);
          // Rimuovi tooltip Bootstrap su nuovi nodi
          normalizeTooltips(node);

          // Inizializza anche i nuovi myspia-item creati via renderMySpiaList()
          if (node.classList?.contains('myspia-item')) ensureMySpiaTouchOnItem(node);
          node.querySelectorAll?.('.myspia-item').forEach(ensureMySpiaTouchOnItem);
        }
      });
    });
  });
  obs.observe(document.body, {childList:true, subtree:true});
});

// --- START: global handler che chiude i popup dopo ogni interazione (capture) ---
document.addEventListener('click', function (e) {
  const anyApptActive = document.querySelector('.appointment-block.active-popup');
  const anyMySpiaOpen = document.querySelector('.myspia-item.myspia-open');
  if (!anyApptActive && !anyMySpiaOpen) return;
  if (window._touchPopupOpenLock) return;

  if (e.target.closest('.appointment-block') || e.target.closest('.myspia-item')) return;

  setTimeout(() => {
    if (document.querySelector('.appointment-block.active-popup')) {
      closeAllPopups();
    } else if (document.querySelector('.myspia-item.myspia-open')) {
      closeAllMySpiaPopups();
    }
  }, 10);
}, true);
// --- END: global handler ---

  // ===== SPOSTA BLOCCO OFF (touch-ui) =====
  let __offMovePayload = null;

function startOffMove(block) {
  if (!block || (!block.classList.contains('note-off') && !block.classList.contains('off'))) return;

    // Evita doppia esecuzione se il bottone viene ri‑cliccato velocemente
    if (block._offMoveStarted) return;
    block._offMoveStarted = true;

    // Lock contro chiusura popup immediata / handler globali
    window._touchPopupOpenLock = true;
    setTimeout(() => { window._touchPopupOpenLock = false; }, 300);

    const apptId = block.getAttribute('data-appointment-id') || '';
    const durata = parseInt(block.getAttribute('data-duration') || '15', 10) || 15;
    const nota = block.getAttribute('data-note') || block.querySelector('.off-title')?.textContent || '';
    const operatorId = block.getAttribute('data-operator-id') || '';
    const date = block.getAttribute('data-date') || window.selectedAppointmentDate || window.selectedDate || '';

    __offMovePayload = {
      oldId: apptId,
      duration: durata,
      note: nota,
      operatorId: operatorId,
      date: date
    };

    // Evidenzia range celle (se funzione disponibile)
    try { if (typeof addCutSourceHighlightRange === 'function') addCutSourceHighlightRange(block); } catch(_) {}

    // Elimina subito il blocco OFF dal backend (idempotenza lato UI)
    if (apptId) {
      fetch('/calendar/delete/' + encodeURIComponent(apptId), {
        method: 'POST',
        headers: { 'Content-Type':'application/json', 'X-CSRFToken': CSRF },
        credentials: 'same-origin'
      }).catch(()=>{});
    }

    // Rimuovi dal DOM (lascia highlight delle celle)
    try { block.remove(); } catch(_) {}

    // Feedback visivo: aggiungi banner temporaneo
    showOffMoveBanner('Seleziona una cella per spostare il blocco OFF (tap per annullare).');
  }

  function cancelOffMove() {
    __offMovePayload = null;
    hideOffMoveBanner();
    try { if (typeof clearCutSourceHighlights === 'function') clearCutSourceHighlights(); } catch(_) {}
  }

  function showOffMoveBanner(msg) {
    let bn = document.getElementById('offMoveBanner');
    if (!bn) {
      bn = document.createElement('div');
      bn.id = 'offMoveBanner';
      bn.style.position = 'fixed';
      bn.style.top = '6px';
      bn.style.left = '50%';
      bn.style.transform = 'translateX(-50%)';
      bn.style.background = '#222';
      bn.style.color = '#ffd400';
      bn.style.padding = '6px 14px';
      bn.style.borderRadius = '8px';
      bn.style.zIndex = '20000';
      bn.style.fontSize = '14px';
      bn.style.cursor = 'pointer';
      bn.title = 'Clic per annullare';
      bn.addEventListener('click', cancelOffMove);
      document.body.appendChild(bn);
    }
    bn.textContent = msg;
  }

  function hideOffMoveBanner() {
    const bn = document.getElementById('offMoveBanner');
    if (bn) try { bn.remove(); } catch(_) {}
  }

  // Listener click celle per completare lo spostamento
  document.addEventListener('click', function(e){
    if (!__offMovePayload) return;
    const cell = e.target.closest('.selectable-cell');
    if (!cell) return;
    if (cell.classList.contains('calendar-closed')) return;

    e.preventDefault();
    e.stopPropagation();

    const hour = cell.getAttribute('data-hour');
    const minute = cell.getAttribute('data-minute');
    const operatorId = cell.getAttribute('data-operator-id');
    const date = cell.getAttribute('data-date') || __offMovePayload.date;

    // Costruisci start_time HH:MM
    const h = String(hour).padStart(2,'0');
    const m = String(minute).padStart(2,'0');
    const startTime = `${h}:${m}`;

    // Payload creazione OFF (client/service dummy o null)
    const createBody = {
      client_id: null,
      service_id: null,
      operator_id: operatorId,
      appointment_date: date,
      start_time: startTime,
      duration: __offMovePayload.duration,
      note: __offMovePayload.note || '',
      status: 0
    };

    fetch('/calendar/create', {
      method: 'POST',
      headers: {
        'Content-Type':'application/json',
        'Accept':'application/json',
        'X-CSRFToken': CSRF
      },
      credentials: 'same-origin',
      body: JSON.stringify(createBody)
    }).then(r => r.json().catch(()=> ({})))
      .then(() => {
        cancelOffMove();
        // Ricarica per visualizzare il nuovo blocco OFF posizionato
        location.reload();
      })
      .catch(() => {
        cancelOffMove();
        alert('Errore creazione blocco OFF spostato');
      });
  }, true);

})();

function forceHideClientInfoPopup() {
  const el = document.getElementById('clientInfoPopup');
  if (!el) return;
  el.classList.remove('show','open','visible','active');
  el.style.setProperty('display','none','important');
  try {
    const tip = (window.bootstrap?.Tooltip?.getInstance(el)) || (window.bootstrap?.Popover?.getInstance(el));
    if (tip) tip.hide();
  } catch(_) {}
}

document.addEventListener('click', function(e) {
  const offBlock = e.target.closest && e.target.closest('.appointment-block.note-off');
  if (!offBlock) return;
  // chiusura robusta del tooltip piccolo cliente
  forceHideClientInfoPopup();
  // ridondanza contro eventuali riaperture da altri handler
  setTimeout(forceHideClientInfoPopup, 30);
}, true);

document.addEventListener('click', function(e) {
  const offBlock = e.target.closest && e.target.closest('.appointment-block.note-off');
  if (!offBlock) return;
  forceHideClientInfoPopup();
  setTimeout(forceHideClientInfoPopup, 30);
}, true);

// Funzione per trovare i blocchi contigui dello stesso cliente nella stessa colonna
function findContiguousBlocks(cutBlock) {
  const clientId = cutBlock.getAttribute('data-client-id');
  const operatorId = cutBlock.getAttribute('data-operator-id');
  const date = cutBlock.getAttribute('data-date');
  // Trova tutti i blocchi dello stesso cliente, operatore, data
  const allBlocks = Array.from(document.querySelectorAll(`.appointment-block[data-client-id="${clientId}"][data-operator-id="${operatorId}"][data-date="${date}"]`));
  // Ordina per start_time
  allBlocks.sort((a, b) => {
    const aTime = parseInt(a.getAttribute('data-hour')) * 60 + parseInt(a.getAttribute('data-minute'));
    const bTime = parseInt(b.getAttribute('data-hour')) * 60 + parseInt(b.getAttribute('data-minute'));
    return aTime - bTime;
  });
  // Trova l'indice del cutBlock
  const cutIndex = allBlocks.indexOf(cutBlock);
  if (cutIndex === -1) return [];
  const contiguous = [];
  // Controlla precedente
  if (cutIndex > 0) {
    const prev = allBlocks[cutIndex - 1];
    const prevEnd = parseInt(prev.getAttribute('data-hour')) * 60 + parseInt(prev.getAttribute('data-minute')) + parseInt(prev.getAttribute('data-duration'));
    const cutStart = parseInt(cutBlock.getAttribute('data-hour')) * 60 + parseInt(cutBlock.getAttribute('data-minute'));
    if (prevEnd === cutStart) contiguous.push(prev);
  }
  // Controlla successivo
  if (cutIndex < allBlocks.length - 1) {
    const next = allBlocks[cutIndex + 1];
    const cutEnd = parseInt(cutBlock.getAttribute('data-hour')) * 60 + parseInt(cutBlock.getAttribute('data-minute')) + parseInt(cutBlock.getAttribute('data-duration'));
    const nextStart = parseInt(next.getAttribute('data-hour')) * 60 + parseInt(next.getAttribute('data-minute'));
    if (cutEnd === nextStart) contiguous.push(next);
  }
  return contiguous;
}

function openTouchPopupForBlock(block) {
  if (!block) return;

  try { if (typeof ensureTopBarForTouch === 'function') ensureTopBarForTouch(block); } catch(_) {}
  try { if (typeof ensureBottomBar === 'function') ensureBottomBar(block); } catch(_) {}

  block.classList.add('active-popup');
  block.style.zIndex = '11940';

  const tb = block.querySelector('.popup-buttons');
  const bb = block.querySelector('.popup-buttons-bottom');

  if (tb) {
    tb.style.setProperty('display', 'flex', 'important');
    tb.style.zIndex = '11950';

// Nascondi TUTTI i bottoni esplicitamente, tranne TAGLIA
const hide = (sel) => tb.querySelectorAll(sel).forEach(btn => {
  btn.style.setProperty('display', 'none', 'important');
  btn.style.setProperty('visibility', 'hidden', 'important');
  btn.style.setProperty('flex', '0 0 0px', 'important');
  btn.style.setProperty('width', '0px', 'important');
  btn.style.setProperty('height', '0px', 'important');
  btn.style.setProperty('padding', '0', 'important');
  btn.style.setProperty('margin', '0', 'important');
  btn.style.setProperty('border', 'none', 'important');
  btn.style.setProperty('overflow', 'hidden', 'important');
});

    // Elenco esplicito dei bottoni da NASCONDERE (tranne taglia)
    hide('.btn-popup.delete-appointment-block');
    hide('.btn-popup.nota');
    hide('.btn-popup.copia');
    hide('.btn-popup.sposta');
    hide('.btn-popup.colore');
    hide('.btn-popup.color');
    hide('.btn-popup.to-cash');
    hide('.btn-popup.go-cash');
    hide('.btn-popup.cassa');
    // MODIFICATO: non nasconde .vai-pacchetto
    tb.querySelectorAll('.btn-popup.pagamento:not(.vai-pacchetto)').forEach(btn => { btn.style.display = 'none'; });
    hide('.btn-popup.add-services');
    hide('.btn-popup.aggiungi-servizi');
    hide('.btn-popup.aggiungi-servizio');
    hide('.btn-popup.add-service');
    hide('.btn-popup.whatsapp-btn');
    hide('.btn-popup.copy-off-block');
    hide('.btn-popup.delete-off-block');
    hide('.btn-popup.touch-top-copy');
    hide('.btn-popup.touch-top-delete');

    // Mostra SOLO il tasto TAGLIA:
    // 1) preferisci .taglia (blocchi normali)
    // 2) altrimenti usa .touch-top-cut (OFF)
    // 3) se nessuno esiste, crea un fallback .taglia touch-only-cut
    let cutBtn =
      tb.querySelector('.btn-popup.taglia') ||
      tb.querySelector('.btn-popup.touch-top-cut') ||
      tb.querySelector('.btn-popup.taglia.touch-only-cut');

    if (!cutBtn) {
      const fallback = document.createElement('button');
      fallback.className = 'btn-popup taglia touch-only-cut';
      fallback.title = 'Taglia';
      try { fallback.appendChild(biIcon('scissors')); } catch(_) {}
      tb.appendChild(fallback);
      cutBtn = fallback;
    }

    // Se il bottone taglia esiste ma è senza icona, inseriscila ora
    if (cutBtn && !cutBtn.querySelector('i')) {
      try { cutBtn.appendChild(biIcon('scissors')); } catch(_) { cutBtn.textContent = '✂'; }
    }

    if (cutBtn) {
      cutBtn.style.setProperty('display', 'inline-flex', 'important');
      cutBtn.style.visibility = 'visible';
      cutBtn.style.zIndex = '11960';
      // Mantieni la larghezza di 1/6 del blocco
      cutBtn.style.setProperty('flex', '0 0 16.6667%', 'important');
      cutBtn.style.setProperty('width', '16.6667%', 'important');
      cutBtn.style.boxSizing = 'border-box';
    }
  }

  // Nascondi sempre la bottom bar
  if (bb) {
    bb.style.setProperty('display', 'none', 'important');
    bb.style.zIndex = '11950';
  }

  // Disabilita il link sul nome cliente mentre è aperto "solo taglia"
  const clientLink = block.querySelector('.client-info-link');
  if (clientLink) {
    clientLink.setAttribute('data-touch-only-cut', '1');
    clientLink.style.setProperty('pointer-events', 'none', 'important');
  }
}

// === COPIA: mostra SOLO il bottone COPIA sui blocchi contigui (stessa logica di openTouchPopupForBlock ma per COPIA) ===
function openTouchPopupForBlockCopiaOnly(block) {
  if (!block) return;

  try { if (typeof ensureTopBarForTouch === 'function') ensureTopBarForTouch(block); } catch(_) {}
  try { if (typeof ensureBottomBar === 'function') ensureBottomBar(block); } catch(_) {}

  block.classList.add('active-popup');
  block.style.zIndex = '11940';

  // Marca il blocco per impedire che altri handler riaprano i popup
  block.setAttribute('data-copia-mode', '1');

  const tb = block.querySelector('.popup-buttons');
  const bb = block.querySelector('.popup-buttons-bottom');

  if (tb) {
    tb.style.setProperty('display', 'flex', 'important');
    tb.style.zIndex = '11950';

// Nascondi TUTTI i bottoni esplicitamente, tranne COPIA
const hide = (sel) => tb.querySelectorAll(sel).forEach(btn => {
  btn.style.setProperty('display', 'none', 'important');
  btn.style.setProperty('visibility', 'hidden', 'important');
  btn.style.setProperty('flex', '0 0 0px', 'important');
  btn.style.setProperty('width', '0px', 'important');
  btn.style.setProperty('height', '0px', 'important');
  btn.style.setProperty('padding', '0', 'important');
  btn.style.setProperty('margin', '0', 'important');
  btn.style.setProperty('border', 'none', 'important');
  btn.style.setProperty('overflow', 'hidden', 'important');
});

    // Elenco esplicito dei bottoni da NASCONDERE (tranne copia)
    hide('.btn-popup.delete-appointment-block');
    hide('.btn-popup.nota');
    hide('.btn-popup.taglia');
    hide('.btn-popup.sposta');
    hide('.btn-popup.colore');
    hide('.btn-popup.color');
    hide('.btn-popup.to-cash');
    hide('.btn-popup.go-cash');
    hide('.btn-popup.cassa');
    hide('.btn-popup.pagamento');
    hide('.btn-popup.add-services');
    hide('.btn-popup.aggiungi-servizi');
    hide('.btn-popup.aggiungi-servizio');
    hide('.btn-popup.add-service');
    hide('.btn-popup.whatsapp-btn');
    hide('.btn-popup.copy-off-block');
    hide('.btn-popup.delete-off-block');
    hide('.btn-popup.touch-top-delete');
    hide('.btn-popup.touch-top-cut');
    hide('.btn-popup.touch-top-note');

    // Mostra SOLO il tasto COPIA:
    let copiaBtn =
      tb.querySelector('.btn-popup.copia') ||
      tb.querySelector('.btn-popup.touch-top-copy');

    if (!copiaBtn) {
      const fallback = document.createElement('button');
      fallback.className = 'btn-popup copia touch-only-copia';
      fallback.title = 'Copia';
      try { fallback.appendChild(biIcon('copy')); } catch(_) { fallback.textContent = '📋'; }
      tb.appendChild(fallback);
      copiaBtn = fallback;
    }

    // Se il bottone copia esiste ma è senza icona, inseriscila ora
    if (copiaBtn && !copiaBtn.querySelector('i')) {
      try { copiaBtn.appendChild(biIcon('copy')); } catch(_) { copiaBtn.textContent = '📋'; }
    }

    if (copiaBtn) {
      copiaBtn.style.setProperty('display', 'inline-flex', 'important');
      copiaBtn.style.visibility = 'visible';
      copiaBtn.style.zIndex = '11960';
      // Mantieni la larghezza di 1/6 del blocco (come taglia)
      copiaBtn.style.setProperty('flex', '0 0 16.6667%', 'important');
      copiaBtn.style.setProperty('width', '16.6667%', 'important');
      copiaBtn.style.boxSizing = 'border-box';
    }
  }

  // Nascondi sempre la bottom bar
  if (bb) {
    bb.style.setProperty('display', 'none', 'important');
    bb.style.zIndex = '11950';
  }

  // Disabilita il link sul nome cliente mentre è aperto "solo copia"
  const clientLink = block.querySelector('.client-info-link');
  if (clientLink) {
    clientLink.setAttribute('data-touch-only-cut', '1');
    clientLink.style.setProperty('pointer-events', 'none', 'important');
  }
}

// Esponi globalmente
window.openTouchPopupForBlockCopiaOnly = openTouchPopupForBlockCopiaOnly;

// Esponi le funzioni globalmente
window.findContiguousBlocks = findContiguousBlocks;
window.openTouchPopupForBlock = openTouchPopupForBlock;

// =============================================================
// LISTENER DELEGATO PER COPIA SU BLOCCHI CONTIGUI (data-copia-mode)
// SOLO TOUCH-UI: Intercetta i click sui pulsanti COPIA mostrati dopo la prima copia
// =============================================================
document.addEventListener('click', function(e) {
  // Intercetta solo click su .btn-popup.copia
  const copiaBtn = e.target.closest('.btn-popup.copia');
  if (!copiaBtn) return;
  
  const block = copiaBtn.closest('.appointment-block');
  if (!block) return;
  
  // ESCLUDI blocchi OFF: hanno logica separata (copia diretta, non navigator)
  if (block.classList.contains('note-off')) return;
  
  // Gestisci SOLO blocchi in modalità copia (contigui)
  if (!block.hasAttribute('data-copia-mode')) return;
  
  // BLOCCA TUTTO SUBITO
  e.preventDefault();
  e.stopPropagation();
  e.stopImmediatePropagation();
  
  console.log("TOUCH-UI: COPIA delegato su blocco contiguo:", block.getAttribute('data-appointment-id'));
  
  // Chiudi tooltip
  document.querySelectorAll('.tooltip').forEach(t => t.remove());
  copiaBtn.removeAttribute('data-bs-original-title');
  copiaBtn.removeAttribute('aria-describedby');
  
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
  
  // Copia il blocco nel navigator
  if (typeof window.copyAsNewPseudoBlock === 'function') {
    window.copyAsNewPseudoBlock(block);
  }
  
  // Marca come già processato
  block.setAttribute('data-copia-mode-done', '1');
  block.removeAttribute('data-copia-mode');
  
  // Chiudi il popup di questo blocco SENZA chiamare closeAllPopups (evita sballare layout)
  block.classList.remove('active-popup');
  block.style.zIndex = '100';
  
  // Nascondi le barre popup di questo blocco specifico
  const tb = block.querySelector('.popup-buttons');
  const bb = block.querySelector('.popup-buttons-bottom');
  if (tb) tb.style.display = 'none';
  if (bb) bb.style.display = 'none';
  
  // Ripristina gli stili dei bottoni di questo blocco
  block.querySelectorAll('.btn-popup').forEach(btn => {
    btn.style.display = '';
    btn.style.visibility = '';
    btn.style.zIndex = '';
    btn.style.flex = '';
    btn.style.width = '';
  });
  
  // Riattiva il link cliente
  const clientLink = block.querySelector('.client-info-link');
  if (clientLink) {
    clientLink.removeAttribute('data-touch-only-cut');
    clientLink.style.removeProperty('pointer-events');
  }
  
  // Trova altri blocchi contigui NON ancora processati
  const contiguousBlocks = typeof window.getRelevantBlocks === 'function' 
    ? window.getRelevantBlocks(block) 
    : [block];
  
  const otherBlocks = contiguousBlocks.filter(b => 
    b !== block && 
    !b.hasAttribute('data-copia-mode-done') &&
    !b.hasAttribute('data-copia-mode')
  );
  
  if (otherBlocks.length > 0) {
    otherBlocks.forEach(otherBlock => {
      if (typeof window.openTouchPopupForBlockCopiaOnly === 'function') {
        window.openTouchPopupForBlockCopiaOnly(otherBlock);
      }
    });
    
    // Auto-reset dopo 8 secondi
    setTimeout(() => {
      document.querySelectorAll('[data-copia-mode], [data-copia-mode-done]').forEach(ob => {
        ob.removeAttribute('data-copia-mode');
        ob.removeAttribute('data-copia-mode-done');
        ob.classList.remove('active-popup');
        ob.style.zIndex = '100';
        // Nascondi popup bars
        const tbOb = ob.querySelector('.popup-buttons');
        const bbOb = ob.querySelector('.popup-buttons-bottom');
        if (tbOb) tbOb.style.display = 'none';
        if (bbOb) bbOb.style.display = 'none';
        // Ripristina stili bottoni
        ob.querySelectorAll('.btn-popup').forEach(btn => {
          btn.style.display = '';
          btn.style.visibility = '';
          btn.style.zIndex = '';
          btn.style.flex = '';
          btn.style.width = '';
        });
        // Riattiva link cliente
        const cl = ob.querySelector('.client-info-link');
        if (cl) {
          cl.removeAttribute('data-touch-only-cut');
          cl.style.removeProperty('pointer-events');
        }
      });
    }, 8000);
  } else {
    // Pulisci i marker dopo un attimo
    setTimeout(() => {
      document.querySelectorAll('[data-copia-mode-done]').forEach(ob => {
        ob.removeAttribute('data-copia-mode-done');
      });
    }, 100);
  }
}, true); // CAPTURE PHASE

// Listener delegato per pulsante "Vai al pacchetto" in touch mode
document.addEventListener('click', function(e) {
  const btn = e.target.closest('.btn-popup.vai-pacchetto');
  if (!btn) return;
  e.stopPropagation();
  e.preventDefault();
  const block = btn.closest('.appointment-block');
  const pacchettoId = block?.getAttribute('data-pacchetto-id') || btn.getAttribute('data-pacchetto-id');
  if (pacchettoId) {
    window.location.href = `/pacchetti/detail/${pacchettoId}`;
  }
}, true);