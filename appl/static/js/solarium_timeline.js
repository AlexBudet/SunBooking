// Timeline sedute Solarium (pagina Impostazioni > Solarium > Statistiche
// Sedute). Componente autonomo: non condivide markup/logica col Calendario
// principale, solo l'idea di colonne + blocchi posizionati per orario.
(function () {
  var cfg = window.SOLARIUM_TIMELINE_CONFIG;
  var root = document.getElementById('solariumTimelineGrid');
  if (!cfg || !root) return;

  var PX_PER_MIN = 4;
  var MIN_BLOCK_PX = 38;

  var dateInput = document.getElementById('solariumTimelineDate');
  var btnPrev = document.getElementById('solariumTimelinePrev');
  var btnNext = document.getElementById('solariumTimelineNext');
  var btnToday = document.getElementById('solariumTimelineToday');
  var popup = document.getElementById('solariumSessionPopup');
  var popupBody = document.getElementById('solariumSessionPopupBody');
  var popupClose = document.getElementById('solariumSessionPopupClose');

  var pollTimer = null;
  var currentDate = todayStr();

  function todayStr() {
    var d = new Date();
    return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate());
  }

  function pad2(n) { return (n < 10 ? '0' : '') + n; }

  function addDays(dateStr, delta) {
    var parts = dateStr.split('-').map(Number);
    var d = new Date(parts[0], parts[1] - 1, parts[2]);
    d.setDate(d.getDate() + delta);
    return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate());
  }

  function timeToMinutes(hhmm) {
    var p = (hhmm || '00:00').split(':');
    return parseInt(p[0], 10) * 60 + parseInt(p[1], 10);
  }

  function csrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
  }

  function statoLabel(stato) {
    if (stato === 'collegato') return { text: 'Pagamento collegato', cls: 'ok' };
    if (stato === 'appuntamento') return { text: 'Da appuntamento (pagamento da abbinare)', cls: 'appt' };
    if (stato === 'in_sospeso') return { text: 'Da collegare', cls: 'warn' };
    if (stato === 'in_attesa') return { text: 'In attesa abbinamento', cls: 'wait' };
    return { text: 'In corso', cls: 'live' };
  }

  function setDate(dateStr) {
    currentDate = dateStr;
    if (dateInput) dateInput.value = dateStr;
    load();
    restartPolling();
  }

  function buildGrid(data) {
    root.innerHTML = '';

    var openMin = timeToMinutes(data.opening_time);
    var closeMin = timeToMinutes(data.closing_time);
    var totalMin = Math.max(60, closeMin - openMin);
    var gridHeight = totalMin * PX_PER_MIN;

    var axis = document.createElement('div');
    axis.className = 'solarium-tl-axis';

    var axisHead = document.createElement('div');
    axisHead.className = 'solarium-tl-col-head';
    axisHead.innerHTML = '&nbsp;';
    axis.appendChild(axisHead);

    var axisBody = document.createElement('div');
    axisBody.className = 'solarium-tl-axis-body';
    axisBody.style.height = gridHeight + 'px';
    for (var m = openMin; m <= closeMin; m += 60) {
      var label = document.createElement('div');
      label.className = 'solarium-tl-axis-label';
      label.style.top = ((m - openMin) * PX_PER_MIN) + 'px';
      label.textContent = pad2(Math.floor(m / 60)) + ':00';
      axisBody.appendChild(label);
    }
    axis.appendChild(axisBody);
    root.appendChild(axis);

    if (!data.devices.length) {
      var empty = document.createElement('div');
      empty.className = 'text-muted';
      empty.style.padding = '1rem';
      empty.textContent = 'Nessun macchinario configurato (Impostazioni > Solarium).';
      root.appendChild(empty);
      return;
    }

    data.devices.forEach(function (dev) {
      var col = document.createElement('div');
      col.className = 'solarium-tl-col';

      var head = document.createElement('div');
      head.className = 'solarium-tl-col-head';
      head.textContent = dev.nome;
      col.appendChild(head);

      var body = document.createElement('div');
      body.className = 'solarium-tl-col-body';
      body.style.height = gridHeight + 'px';

      // righe guida ogni ora, per leggibilita'
      for (var mm = openMin; mm <= closeMin; mm += 60) {
        var line = document.createElement('div');
        line.className = 'solarium-tl-hour-line';
        line.style.top = ((mm - openMin) * PX_PER_MIN) + 'px';
        body.appendChild(line);
      }

      data.sedute
        .filter(function (s) { return s.device_id === dev.id; })
        .forEach(function (s) {
          var fineMin = s.fine_minuti != null ? s.fine_minuti : s.inizio_minuti + Math.max(1, s.durata_minuti);
          var top = (Math.max(openMin, s.inizio_minuti) - openMin) * PX_PER_MIN;
          var height = Math.max(MIN_BLOCK_PX, (Math.min(closeMin, fineMin) - Math.max(openMin, s.inizio_minuti)) * PX_PER_MIN);

          var stato = statoLabel(s.in_corso ? null : s.stato_pagamento);
          var block = document.createElement('div');
          block.className = 'solarium-tl-block ' + stato.cls;
          block.style.top = top + 'px';
          block.style.height = height + 'px';
          block.innerHTML =
            '<div class="solarium-tl-block-time">' + s.inizio + (s.fine ? (' - ' + s.fine) : '') + '</div>' +
            '<div class="solarium-tl-block-who">' + (s.cliente || stato.text) + '</div>';
          block.addEventListener('click', function () { openPopup(s, dev); });
          body.appendChild(block);
        });

      col.appendChild(body);
      root.appendChild(col);
    });
  }

  function openPopup(s, dev) {
    var stato = statoLabel(s.in_corso ? null : s.stato_pagamento);
    var html = '' +
      '<h5>' + dev.nome + '</h5>' +
      '<p class="mb-1"><strong>Orario:</strong> ' + s.inizio + (s.fine ? (' - ' + s.fine) : ' (in corso)') + '</p>' +
      '<p class="mb-1"><strong>Durata:</strong> ' + s.durata_minuti + ' min</p>' +
      '<p class="mb-1"><strong>Stato pagamento:</strong> <span class="solarium-tl-badge ' + stato.cls + '">' + stato.text + '</span></p>';
    if (s.cliente) html += '<p class="mb-1"><strong>Cliente:</strong> ' + s.cliente + '</p>';
    if (s.scontrino) html += '<p class="mb-1"><strong>Scontrino:</strong> ' + s.scontrino + '</p>';
    if (s.operatore) html += '<p class="mb-1"><strong>Operatore:</strong> ' + s.operatore + '</p>';

    popupBody.innerHTML = html;
    popup.style.display = 'flex';

    // Anche una seduta gia' identificata dall'appuntamento resta da abbinare
    // al pagamento: si offrono comunque i candidati.
    if (!s.in_corso && (s.stato_pagamento === 'in_sospeso' || s.stato_pagamento === 'appuntamento')) {
      var candBox = document.createElement('div');
      candBox.className = 'mt-3';
      candBox.innerHTML = '<div class="text-muted small mb-1">Ricerca pagamenti e appuntamenti vicini...</div>';
      popupBody.appendChild(candBox);

      var url = cfg.candidatesUrlTemplate.replace('999999', s.id);
      fetch(url)
        .then(function (r) { return r.json(); })
        .then(function (data) { renderCandidates(candBox, s.id, data.candidati || []); })
        .catch(function () { candBox.innerHTML = '<div class="text-danger small">Errore nel caricamento dei candidati.</div>'; });
    }
  }

  function renderCandidates(box, sessionId, candidati) {
    if (!candidati.length) {
      box.innerHTML = '<div class="text-muted small">Nessuno scontrino né appuntamento trovato nelle vicinanze per questo macchinario.</div>';
      return;
    }
    var html = '<div class="text-muted small mb-1">Candidati (scontrini e appuntamenti):</div>';
    candidati.forEach(function (c) {
      var isAppuntamento = (c.tipo === 'appuntamento');
      var etichetta = isAppuntamento
        ? '<span class="solarium-tl-badge appt">Appuntamento</span>'
        : '<span class="solarium-tl-badge ok">' + (c.numero_progressivo || 'Scontrino') + '</span>';
      html += '' +
        '<div class="solarium-tl-candidate">' +
        '<div>' +
        etichetta + ' ' + (c.cliente || 'cliente non indicato') +
        '<br><span class="text-muted small">' + (c.orario || '') + ' - a ' + c.distanza_minuti + ' min - € ' + (c.importo != null ? parseFloat(c.importo).toFixed(2) : '') + '</span>' +
        '</div>' +
        '<button type="button" class="btn btn-sm btn-outline-success" data-tipo="' + (isAppuntamento ? 'appuntamento' : 'scontrino') + '"' +
        ' data-target-id="' + (isAppuntamento ? c.appointment_id : c.receipt_id) + '">Collega</button>' +
        '</div>';
    });
    box.innerHTML = html;
    box.querySelectorAll('button[data-target-id]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        linkSession(sessionId, btn.getAttribute('data-target-id'), btn.getAttribute('data-tipo'));
      });
    });
  }

  function linkSession(sessionId, targetId, tipo) {
    var body = new URLSearchParams();
    body.set('csrf_token', csrfToken());
    body.set('session_id', sessionId);
    body.set(tipo === 'appuntamento' ? 'appointment_id' : 'receipt_id', targetId);
    fetch(cfg.linkUrl, { method: 'POST', body: body })
      .then(function () {
        closePopup();
        load();
      })
      .catch(function () {});
  }

  function closePopup() {
    popup.style.display = 'none';
    popupBody.innerHTML = '';
  }

  function load() {
    fetch(cfg.dataUrl + '?data=' + encodeURIComponent(currentDate))
      .then(function (r) { return r.json(); })
      .then(buildGrid)
      .catch(function () {});
  }

  function restartPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = null;
    if (currentDate === todayStr()) {
      pollTimer = setInterval(load, 5000);
    }
  }

  if (btnPrev) btnPrev.addEventListener('click', function () { setDate(addDays(currentDate, -1)); });
  if (btnNext) btnNext.addEventListener('click', function () { setDate(addDays(currentDate, 1)); });
  if (btnToday) btnToday.addEventListener('click', function () { setDate(todayStr()); });
  if (dateInput) dateInput.addEventListener('change', function () { setDate(dateInput.value || todayStr()); });
  if (popupClose) popupClose.addEventListener('click', closePopup);
  if (popup) popup.addEventListener('click', function (e) { if (e.target === popup) closePopup(); });

  setDate(currentDate);
})();
