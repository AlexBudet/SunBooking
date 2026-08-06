/* ============================================================================
   Agenda su dispositivi mobile: suggerimento d'uso e gestione dello zoom.

   Sta in un file a parte apposta: sono due comportamenti aggiunti, non legati
   alla logica dei blocchi. Se danno fastidio basta togliere la riga di include
   da calendar.html e non resta niente in giro.

   Soglia 1199.98px: e' la stessa che calendar.js usa gia' ovunque per
   distinguere il mobile, meglio non introdurne una seconda.
   ============================================================================ */
(function () {
  'use strict';

  function isMobile() {
    return !!(window.matchMedia && window.matchMedia('(max-width: 1199.98px)').matches);
  }
  if (!isMobile()) return;

  /* ==========================================================================
     1. ZOOM: ritorno alla scala di default quando si apre una finestra

     Con lo zoom a due dita attivo, un modal si apre con misure sballate:
     Bootstrap lo dimensiona sul layout viewport mentre il browser mostra
     quello visuale, ingrandito. Non esiste una API per azzerare il pinch
     zoom; la strada praticabile e' imporre per un istante maximum-scale=1
     sul meta viewport e poi rimettere il valore originale, cosi' subito
     dopo l'utente puo' tornare a zoomare come prima.
     ========================================================================== */
  var metaViewport = document.querySelector('meta[name="viewport"]');
  var viewportOriginale = metaViewport ? metaViewport.getAttribute('content') : null;
  var timerRipristino = null;

  function riportaZoomADefault() {
    if (!metaViewport) return;
    clearTimeout(timerRipristino);
    metaViewport.setAttribute(
      'content',
      'width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=0'
    );
    // Rimettere subito il valore originale annullerebbe l'effetto: il vincolo
    // deve restare applicato per qualche frame perche' il browser lo recepisca.
    timerRipristino = setTimeout(function () {
      metaViewport.setAttribute(
        'content',
        viewportOriginale || 'width=device-width, initial-scale=1.0'
      );
    }, 400);
  }

  // In cattura: cosi' lo zoom e' gia' a posto quando Bootstrap calcola le
  // dimensioni del dialog. Vale per QUALSIASI modal dell'Agenda.
  document.addEventListener('show.bs.modal', riportaZoomADefault, true);

  /* ==========================================================================
     2. SUGGERIMENTO D'USO all'apertura dell'Agenda
     ========================================================================== */
  // Si mostra UNA VOLTA SOLA, al primo ingresso in Agenda da questo
  // dispositivo: e' un suggerimento iniziale, non un promemoria ricorrente.
  // Per rivederlo basta cancellare questa chiave dal localStorage.
  var CHIAVE_GIA_VISTO = 'sun_mobile_agenda_tips_visto';

  function giaVisto() {
    try { return localStorage.getItem(CHIAVE_GIA_VISTO) === '1'; }
    catch (e) { return true; }   // storage non disponibile: meglio non insistere
  }

  function segnaComeVisto() {
    try { localStorage.setItem(CHIAVE_GIA_VISTO, '1'); } catch (e) { /* privato / quota */ }
  }

  function costruisciModal() {
    var wrapper = document.createElement('div');
    wrapper.className = 'modal fade';
    wrapper.id = 'MobileAgendaTipsModal';
    wrapper.tabIndex = -1;
    wrapper.setAttribute('aria-labelledby', 'MobileAgendaTipsLabel');
    wrapper.setAttribute('aria-hidden', 'true');
    // Markup interamente statico: nessun dato utente finisce qui dentro.
    wrapper.innerHTML = [
      '<div class="modal-dialog modal-dialog-centered">',
      '  <div class="modal-content">',
      '    <div class="modal-header">',
      '      <h5 class="modal-title" id="MobileAgendaTipsLabel">📱 Agenda sul telefono</h5>',
      '      <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Chiudi"></button>',
      '    </div>',
      '    <div class="modal-body">',
      '      <p class="mb-3">Due accorgimenti per lavorare comodo:</p>',
      '      <div class="d-flex mb-3">',
      '        <div class="me-3" style="font-size:1.5rem;line-height:1">↕️</div>',
      '        <div><strong>Per scorrere</strong> trascina sulla <strong>barra delle ore</strong> ',
      '        (di lato) o sulla <strong>barra degli operatori</strong> (in alto). ',
      '        Lì il dito non incontra appuntamenti, quindi non rischi di spostarli ',
      '        o di aprire per sbaglio la creazione di un appuntamento.</div>',
      '      </div>',
      '      <div class="d-flex mb-2">',
      '        <div class="me-3" style="font-size:1.5rem;line-height:1">🤏</div>',
      '        <div><strong>Per ingrandire o rimpicciolire</strong> usa <strong>due dita</strong>. ',
      '        Aprendo una finestra lo zoom torna da solo alla misura normale.</div>',
      '      </div>',
      '    </div>',
      '    <div class="modal-footer">',
      '      <button type="button" class="btn btn-primary" data-bs-dismiss="modal">Ho capito</button>',
      '    </div>',
      '  </div>',
      '</div>'
    ].join('');
    return wrapper;
  }

  function mostraSuggerimenti() {
    if (giaVisto()) return;
    if (!window.bootstrap || !document.body) return;
    if (document.getElementById('MobileAgendaTipsModal')) return;

    var el = costruisciModal();
    document.body.appendChild(el);

    // Segnato subito, non alla chiusura: se l'utente cambia pagina senza
    // chiudere il modal l'ha comunque visto, e non deve ritrovarselo.
    segnaComeVisto();

    el.addEventListener('hidden.bs.modal', function () { el.remove(); });

    bootstrap.Modal.getOrCreateInstance(el).show();
  }

  // Un attimo dopo il caricamento: l'Agenda deve essersi disegnata, altrimenti
  // il suggerimento appare su una pagina ancora vuota e si capisce meno.
  function avvia() {
    setTimeout(mostraSuggerimenti, 700);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', avvia);
  } else {
    avvia();
  }
})();
