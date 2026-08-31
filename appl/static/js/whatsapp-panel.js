// Pannello di anteprima/conferma per l'invio WhatsApp in background (via WhatsApp Web/Unipile).
// Condiviso tra Agenda (pulsante WhatsApp del popup blocco) e Cassa (invio dopo pagamento con
// carta prepagata): mostra sempre il testo in una textarea modificabile, l'invio parte SOLO al
// click su "Invia", mai in automatico senza conferma esplicita (i messaggi WhatsApp via API
// hanno un costo).
// Riquadro di riepilogo del movimento su carta prepagata, in cima al pannello.
// Lo prepara la Cassa e lo passa in payload.riepilogo:
//   intestatario     nome e cognome del titolare della carta
//   numeroTessera    numero della tessera, se c'e'
//   creditoPrecedente / creditoResiduo   saldo prima e dopo lo scontrino
//   movimenti        [{ etichetta, importo, verso: '+' | '-' }]
// Tutto in stili inline, come il resto del pannello: gira su tre pagine
// diverse (Agenda, Cassa, scheda pacchetto) e non dipende da un CSS suo.
function costruisciRiquadroRiepilogo(dati) {
  const eur = (v) => '€ ' + Number(v || 0).toLocaleString('it-IT', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });

  const box = document.createElement('div');
  box.style.border = '1px solid #e0e0e0';
  box.style.borderRadius = '8px';
  box.style.padding = '14px 16px';
  box.style.background = '#fafafa';

  // Intestazione: chi e' il titolare e su quale tessera si sta lavorando.
  const testa = document.createElement('div');
  testa.style.display = 'flex';
  testa.style.alignItems = 'baseline';
  testa.style.justifyContent = 'space-between';
  testa.style.gap = '10px';
  testa.style.paddingBottom = '10px';
  testa.style.borderBottom = '1px solid #e8e8e8';

  const chi = document.createElement('div');
  chi.style.fontWeight = '700';
  chi.style.fontSize = '1.05em';
  chi.style.textTransform = 'uppercase';
  chi.textContent = dati.intestatario || 'Cliente';
  testa.appendChild(chi);

  if (dati.numeroTessera) {
    const tessera = document.createElement('div');
    tessera.style.fontSize = '0.85em';
    tessera.style.color = '#666';
    tessera.style.whiteSpace = 'nowrap';
    tessera.textContent = 'Tessera n. ' + dati.numeroTessera;
    testa.appendChild(tessera);
  }
  box.appendChild(testa);

  function riga(etichetta, valore, opzioni) {
    const o = opzioni || {};
    const r = document.createElement('div');
    r.style.display = 'flex';
    r.style.alignItems = 'baseline';
    r.style.justifyContent = 'space-between';
    r.style.gap = '14px';
    r.style.marginTop = o.marginTop || '7px';

    const sx = document.createElement('div');
    sx.style.color = o.coloreEtichetta || '#555';
    if (o.grande) {
      sx.style.fontWeight = '700';
      sx.style.fontSize = '0.9em';
      sx.style.letterSpacing = '0.04em';
    }
    sx.textContent = etichetta;

    const dx = document.createElement('div');
    dx.style.whiteSpace = 'nowrap';
    dx.style.fontVariantNumeric = 'tabular-nums';
    dx.style.fontWeight = o.grande ? '700' : '600';
    if (o.grande) dx.style.fontSize = '1.6em';
    if (o.colore) dx.style.color = o.colore;
    dx.textContent = valore;

    r.appendChild(sx);
    r.appendChild(dx);
    box.appendChild(r);
    return r;
  }

  riga('Credito precedente', eur(dati.creditoPrecedente));

  (dati.movimenti || []).forEach(function (m) {
    const scalo = m.verso === '-';
    riga(m.etichetta || (scalo ? 'Scalato' : 'Ricarica'),
         (scalo ? '− ' : '+ ') + eur(m.importo),
         { colore: scalo ? '#b3261e' : '#1b7f3b' });
  });

  const separatore = document.createElement('div');
  separatore.style.borderTop = '1px solid #e8e8e8';
  separatore.style.marginTop = '11px';
  box.appendChild(separatore);

  riga('CREDITO RESIDUO', eur(dati.creditoResiduo), {
    grande: true,
    marginTop: '9px',
    coloreEtichetta: '#333'
  });

  return box;
}

function showWhatsappAutoSendPanel(payload) {
  const existing = document.getElementById('whatsappAutoSendOverlay');
  if (existing) existing.remove();

  const overlay = document.createElement('div');
  overlay.id = 'whatsappAutoSendOverlay';
  overlay.style.position = 'fixed';
  overlay.style.top = '0';
  overlay.style.left = '0';
  overlay.style.right = '0';
  overlay.style.bottom = '0';
  overlay.style.background = 'rgba(0,0,0,0.35)';
  overlay.style.zIndex = '99998';
  overlay.style.display = 'flex';
  overlay.style.alignItems = 'center';
  overlay.style.justifyContent = 'center';

  const panel = document.createElement('div');
  panel.style.background = '#fff';
  panel.style.borderRadius = '8px';
  panel.style.boxShadow = '0 6px 18px rgba(0,0,0,0.25)';
  panel.style.padding = '20px';
  panel.style.width = '560px';
  panel.style.maxWidth = '94vw';
  panel.style.zIndex = '99999';

  // Riepilogo del movimento carta (lo passa la Cassa): quando c'e', il riquadro
  // e' prima di tutto un riepilogo, e il messaggio WhatsApp e' una coda
  // facoltativa. La parte WhatsApp sparisce se l'operatore l'ha spenta in
  // Tools > WhatsApp (whatsappAbilitato) o se non c'e' un numero a cui scrivere.
  const riepilogo = payload.riepilogo || null;
  const conWhatsapp = payload.whatsappAbilitato !== false && !!payload.numero;

  const title = document.createElement('div');
  title.style.fontWeight = '700';
  title.style.marginBottom = '10px';
  title.textContent = riepilogo
    ? 'Riepilogo carta prepagata'
    : `Invia WhatsApp a ${payload.nome || 'cliente'}${payload.numero ? ' (' + payload.numero + ')' : ''}`;
  panel.appendChild(title);

  if (riepilogo) panel.appendChild(costruisciRiquadroRiepilogo(riepilogo));

  let textarea = null;
  let sendBtn = null;
  let manualLink = null;

  if (conWhatsapp) {
    if (riepilogo) {
      const waTitle = document.createElement('div');
      waTitle.style.fontWeight = '700';
      waTitle.style.marginTop = '18px';
      waTitle.style.marginBottom = '10px';
      waTitle.textContent = `Invia WhatsApp a ${payload.nome || 'cliente'}${payload.numero ? ' (' + payload.numero + ')' : ''}`;
      panel.appendChild(waTitle);
    }

    const warn = document.createElement('div');
    warn.className = 'text-muted';
    warn.style.fontSize = '0.85em';
    warn.style.marginBottom = '8px';
    warn.textContent = 'Invio via WhatsApp Web collegato: ogni messaggio ha un costo. Controlla/modifica il testo prima di inviare.';
    panel.appendChild(warn);

    textarea = document.createElement('textarea');
    textarea.value = payload.testo || '';
    textarea.className = 'form-control';
    textarea.rows = riepilogo ? 6 : 11;
    textarea.style.marginBottom = '14px';
    panel.appendChild(textarea);
  }

  const btnRow = document.createElement('div');
  btnRow.style.display = 'flex';
  btnRow.style.gap = '10px';
  btnRow.style.justifyContent = 'flex-end';
  if (!conWhatsapp) btnRow.style.marginTop = '16px';

  const cancelBtn = document.createElement('button');
  cancelBtn.type = 'button';
  // Senza la parte WhatsApp non c'e' niente da annullare: il pulsante chiude e basta.
  cancelBtn.className = conWhatsapp ? 'btn btn-secondary' : 'btn btn-primary';
  cancelBtn.textContent = conWhatsapp ? 'Annulla' : 'Chiudi';
  btnRow.appendChild(cancelBtn);

  if (conWhatsapp) {
    sendBtn = document.createElement('button');
    sendBtn.type = 'button';
    sendBtn.className = 'btn btn-success';
    sendBtn.textContent = 'Invia';
    btnRow.appendChild(sendBtn);
  }
  panel.appendChild(btnRow);

  if (conWhatsapp) {
    const manualRow = document.createElement('div');
    manualRow.style.marginTop = '12px';
    manualRow.style.paddingTop = '10px';
    manualRow.style.borderTop = '1px solid #e5e5e5';
    manualRow.style.textAlign = 'center';

    manualLink = document.createElement('a');
    manualLink.href = '#';
    manualLink.style.fontSize = '0.85em';
    manualLink.textContent = 'Preferisci inviarlo tu manualmente? Apri WhatsApp con il messaggio pronto';
    manualRow.appendChild(manualLink);
    panel.appendChild(manualRow);
  }

  overlay.appendChild(panel);
  document.body.appendChild(overlay);
  if (textarea) setTimeout(() => textarea.focus(), 50);

  function cleanup() {
    document.removeEventListener('keydown', onKey);
    // Rimozione differita di un tick: se si toglie l'overlay mentre il click è
    // ancora in corso, chi più avanti nella catena usa elementFromPoint trova
    // il buco e legge l'elemento sottostante, cioè il calendario.
    // Sparisce subito alla vista, ma resta cliccabile fino alla rimozione:
    // con pointer-events:none il buco si aprirebbe comunque.
    overlay.style.opacity = '0';
    setTimeout(function() {
      if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
    }, 0);
    // Fires on ANY chiusura del pannello (invio, annulla, invio manuale, Esc): utile a chi
    // ha aperto il pannello per riprendere il proprio flusso solo dopo che l'operatore ha
    // deciso, indipendentemente dall'esito.
    if (typeof payload.onClose === 'function') payload.onClose();
  }
  function onKey(e) {
    if (e.key === 'Escape') cleanup();
  }
  document.addEventListener('keydown', onKey);

  // L'overlay copre lo schermo ma è figlio di <body>: senza questo blocco ogni
  // click ci passa sopra e continua a salire fino a document, dove l'Agenda ha
  // molti handler delegati (creazione blocchi, chiusura popup, gestori touch).
  // Il risultato erano click che "attraversavano" il pannello e finivano per
  // agire sul calendario sottostante. I pulsanti del pannello continuano a
  // funzionare: i loro handler girano prima, mentre l'evento sale fino a qui.
  ['mousedown', 'mouseup', 'click', 'dblclick', 'pointerdown', 'pointerup',
   'touchstart', 'touchend', 'contextmenu'].forEach(function(evento) {
    overlay.addEventListener(evento, function(e) { e.stopPropagation(); });
  });

  // Chiude solo se il click è iniziato E finito sull'overlay stesso: durante il
  // ridimensionamento della textarea il mouseup può ricadere sull'overlay pur
  // essendo partito dalla maniglia di resize, e non deve chiudere il pannello.
  let overlayMouseDownOnSelf = false;
  overlay.addEventListener('mousedown', function(e) { overlayMouseDownOnSelf = (e.target === overlay); });
  overlay.addEventListener('click', function(e) {
    if (e.target === overlay && overlayMouseDownOnSelf) cleanup();
    overlayMouseDownOnSelf = false;
  });
  cancelBtn.addEventListener('click', cleanup);

  if (manualLink) manualLink.addEventListener('click', function(e) {
    e.preventDefault();
    const testoManuale = textarea.value.trim();
    const numero = String(payload.numero || '').replace(/^\+/, '');
    const url = `https://wa.me/${numero}?text=${encodeURIComponent(testoManuale)}`;
    window.open(url, '_blank');
    cleanup();
  });

  if (sendBtn) sendBtn.addEventListener('click', async function() {
    const testoFinale = textarea.value.trim();
    if (!testoFinale) { textarea.focus(); return; }
    sendBtn.disabled = true;
    cancelBtn.disabled = true;
    sendBtn.textContent = 'Invio...';
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
    try {
      const resp = await fetch('/calendar/send-whatsapp-auto', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
        credentials: 'same-origin',
        body: JSON.stringify({
          numero: payload.numero,
          messaggio: testoFinale,
          nome: payload.nome || '',
          client_id: payload.clientId || '',
          data: payload.data || '',
          ora: payload.ora || '',
          appointment_ids: payload.appointmentIds || []
        })
      });
      const ct = (resp.headers.get('content-type') || '').toLowerCase();
      const json = ct.includes('application/json') ? await resp.json().catch(() => ({})) : {};
      if (!resp.ok || json.error) {
        throw new Error(json.error || `Errore ${resp.status}`);
      }
      cleanup();
      if (typeof payload.onSent === 'function') payload.onSent();
      alert('Messaggio WhatsApp inviato.');
    } catch (err) {
      console.error('Invio WhatsApp automatico fallito', err);
      sendBtn.disabled = false;
      cancelBtn.disabled = false;
      sendBtn.textContent = 'Invia';
      alert('Invio WhatsApp non riuscito: ' + (err.message || 'errore sconosciuto'));
    }
  });
}
window.showWhatsappAutoSendPanel = showWhatsappAutoSendPanel;
