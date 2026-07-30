// Pannello di anteprima/conferma per l'invio WhatsApp in background (via WhatsApp Web/Unipile).
// Condiviso tra Agenda (pulsante WhatsApp del popup blocco) e Cassa (invio dopo pagamento con
// carta prepagata): mostra sempre il testo in una textarea modificabile, l'invio parte SOLO al
// click su "Invia", mai in automatico senza conferma esplicita (i messaggi WhatsApp via API
// hanno un costo).
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

  const title = document.createElement('div');
  title.style.fontWeight = '700';
  title.style.marginBottom = '10px';
  title.textContent = `Invia WhatsApp a ${payload.nome || 'cliente'}${payload.numero ? ' (' + payload.numero + ')' : ''}`;
  panel.appendChild(title);

  const warn = document.createElement('div');
  warn.className = 'text-muted';
  warn.style.fontSize = '0.85em';
  warn.style.marginBottom = '8px';
  warn.textContent = 'Invio via WhatsApp Web collegato: ogni messaggio ha un costo. Controlla/modifica il testo prima di inviare.';
  panel.appendChild(warn);

  const textarea = document.createElement('textarea');
  textarea.value = payload.testo || '';
  textarea.className = 'form-control';
  textarea.rows = 11;
  textarea.style.marginBottom = '14px';
  panel.appendChild(textarea);

  const btnRow = document.createElement('div');
  btnRow.style.display = 'flex';
  btnRow.style.gap = '10px';
  btnRow.style.justifyContent = 'flex-end';

  const cancelBtn = document.createElement('button');
  cancelBtn.type = 'button';
  cancelBtn.className = 'btn btn-secondary';
  cancelBtn.textContent = 'Annulla';

  const sendBtn = document.createElement('button');
  sendBtn.type = 'button';
  sendBtn.className = 'btn btn-success';
  sendBtn.textContent = 'Invia';

  btnRow.appendChild(cancelBtn);
  btnRow.appendChild(sendBtn);
  panel.appendChild(btnRow);

  const manualRow = document.createElement('div');
  manualRow.style.marginTop = '12px';
  manualRow.style.paddingTop = '10px';
  manualRow.style.borderTop = '1px solid #e5e5e5';
  manualRow.style.textAlign = 'center';

  const manualLink = document.createElement('a');
  manualLink.href = '#';
  manualLink.style.fontSize = '0.85em';
  manualLink.textContent = 'Preferisci inviarlo tu manualmente? Apri WhatsApp con il messaggio pronto';
  manualRow.appendChild(manualLink);
  panel.appendChild(manualRow);

  overlay.appendChild(panel);
  document.body.appendChild(overlay);
  setTimeout(() => textarea.focus(), 50);

  function cleanup() {
    document.removeEventListener('keydown', onKey);
    if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
    // Fires on ANY chiusura del pannello (invio, annulla, invio manuale, Esc): utile a chi
    // ha aperto il pannello per riprendere il proprio flusso solo dopo che l'operatore ha
    // deciso, indipendentemente dall'esito.
    if (typeof payload.onClose === 'function') payload.onClose();
  }
  function onKey(e) {
    if (e.key === 'Escape') cleanup();
  }
  document.addEventListener('keydown', onKey);

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

  manualLink.addEventListener('click', function(e) {
    e.preventDefault();
    const testoManuale = textarea.value.trim();
    const numero = String(payload.numero || '').replace(/^\+/, '');
    const url = `https://wa.me/${numero}?text=${encodeURIComponent(testoManuale)}`;
    window.open(url, '_blank');
    cleanup();
  });

  sendBtn.addEventListener('click', async function() {
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
