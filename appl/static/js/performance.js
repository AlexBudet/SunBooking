/* ===========================================================================
   PERFORMANCE — pannello dell'INFO BOX in Agenda (solo admin e owner)
   ---------------------------------------------------------------------------
   Si apre dal pulsante "📊 Performance" dell'INFO BOX (calendar.js) e dalle
   schede Servizio/Operatore. Tre schede: Negozio, Servizi, Operatori, su un
   periodo a scelta con un secondo periodo facoltativo per il confronto.

   - I numeri arrivano tutti da UNA chiamata: /calendar/api/info/performance
     (routes/calendar.py -> appl/services/performance.py, dove stanno le
     definizioni). Il server rifiuta il ruolo user: nascondere il pulsante non
     basta.
   - Chart.js (la stessa versione del Report) si scarica solo alla prima
     apertura: l'Agenda non paga niente finche' il pannello non serve.
   - Due colori di dato: blu = periodo scelto, grigio = confronto. Le
     variazioni hanno sempre freccia + testo, mai il solo colore.
   - Il file sta FUORI dalla IIFE di calendar.js: comunica solo tramite
     window.cdApriPerformance.
   =========================================================================== */
(function () {
  'use strict';

  var CHART_SRC = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js';
  var PREF_KEY = 'perf_pref_v1';
  var COL_ACCENT = '#2a78d6';
  var COL_CMP = '#a8a69e';
  var COL_GRID = '#e1e0d9';
  var COL_MUTED = '#6b6a65';
  var MESI = ['GEN', 'FEB', 'MAR', 'APR', 'MAG', 'GIU', 'LUG', 'AGO', 'SET', 'OTT', 'NOV', 'DIC'];
  var GIORNI_SETT = ['Lun', 'Mar', 'Mer', 'Gio', 'Ven', 'Sab', 'Dom'];

  // Il CSS sta accanto, in static/css: lo si ricava dall'indirizzo di questo
  // script, cosi' funziona anche col negozio montato su /s/<n>.
  var CSS_HREF = (function () {
    try {
      var src = document.currentScript && document.currentScript.src;
      if (src) return src.replace(/js\/performance\.js(\?.*)?$/, 'css/performance.css');
    } catch (_) {}
    return null;
  })();

  var PRESETS = [
    { id: 'oggi',      label: 'Oggi' },
    { id: 'ieri',      label: 'Ieri' },
    { id: 'settimana', label: 'Questa settimana' },
    { id: 'mese',      label: 'Questo mese' },
    { id: 'mese_prec', label: 'Mese scorso' },
    { id: '30g',       label: 'Ultimi 30 giorni' },
    { id: '12m',       label: 'Ultimi 12 mesi' },
    { id: 'anno',      label: "Quest'anno" },
    { id: 'date',      label: 'Date…' }
  ];
  var CONFRONTI = [
    { id: 'precedente', label: 'Periodo precedente' },
    { id: 'anno_prec',  label: 'Stesso periodo anno scorso' },
    { id: 'nessuno',    label: 'Nessun confronto' },
    { id: 'date',       label: 'Date a scelta…' }
  ];
  var CAT_LABEL = {
    estetica: 'Estetica', solarium: 'Solarium', prodotti: 'Prodotti',
    carte: 'Carte prepagate', pacchetti: 'Pacchetti (rate)',
    dgfe: 'Allineamento DGFE', altro: 'Altre voci'
  };

  var S = {
    preset: 'mese', cmp: 'precedente', tab: 'negozio',
    dal: null, al: null, cmpDal: null, cmpAl: null,
    grana: 'auto',
    data: null, req: null,
    serv: { q: '', cat: 'tutte', sort: 'incasso', dir: 'desc', tutti: false },
    ops: { tipo: 'tutti', sort: 'incasso', dir: 'desc', aperti: {}, evidenzia: null },
    charts: {}, tips: []
  };
  var M = null;          // elementi della finestra
  var chartLoad = null;  // promessa di caricamento di Chart.js

  // ── Utilita' ──────────────────────────────────────────────────────────
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  // Numeri all'italiana con il punto delle migliaia SEMPRE: Intl in it-IT non
  // raggruppa le quattro cifre ("6266,00 €") e useGrouping:'always' non c'e'
  // in Chrome 105, il minimo supportato.
  function gruppi(n, dec) {
    n = Number(n) || 0;
    var s = Math.abs(n).toFixed(dec).split('.');
    s[0] = s[0].replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    var neg = n < 0 && Number(s.join('.').replace(/\./g, '')) !== 0;
    return (neg ? '-' : '') + s[0] + (s[1] ? ',' + s[1] : '');
  }
  function euro(n) { return gruppi(n, 2) + ' €'; }
  function euro0(n) { return gruppi(n, 0) + ' €'; }
  function num(n) { var v = Math.round((Number(n) || 0) * 10) / 10; return gruppi(v, v % 1 ? 1 : 0); }
  var fmtNum = { format: num };
  function pct1(n) { return num(n) + '%'; }

  function iso(d) {
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  }
  function daIso(s) { var p = String(s).split('-'); return new Date(+p[0], +p[1] - 1, +p[2]); }
  function piuGiorni(d, n) { var x = new Date(d.getFullYear(), d.getMonth(), d.getDate()); x.setDate(x.getDate() + n); return x; }
  function giorniTra(a, b) { return Math.round((daIso(iso(b)) - daIso(iso(a))) / 86400000); }
  function fineMese(y, m) { return new Date(y, m + 1, 0).getDate(); }
  // Date a video "06 NOV 2026" (regola dell'app, formati.data_it)
  function dataIT(s) { if (!s) return ''; var d = typeof s === 'string' ? daIso(s) : s; return String(d.getDate()).padStart(2, '0') + ' ' + MESI[d.getMonth()] + ' ' + d.getFullYear(); }
  function dataBreve(s) { var d = typeof s === 'string' ? daIso(s) : s; return String(d.getDate()).padStart(2, '0') + ' ' + MESI[d.getMonth()]; }
  function intervalloIT(a, b) { return a === b ? dataIT(a) : dataIT(a) + ' – ' + dataIT(b); }
  function stessoGiornoAnno(d, delta) {
    var y = d.getFullYear() + delta, m = d.getMonth();
    return new Date(y, m, Math.min(d.getDate(), fineMese(y, m)));
  }

  function leggiPref() {
    try {
      var p = JSON.parse(localStorage.getItem(PREF_KEY) || '{}');
      if (p.preset && p.preset !== 'date' && PRESETS.some(function (x) { return x.id === p.preset; })) S.preset = p.preset;
      if (p.cmp && p.cmp !== 'date' && CONFRONTI.some(function (x) { return x.id === p.cmp; })) S.cmp = p.cmp;
      if (p.tab) S.tab = p.tab;
    } catch (_) {}
  }
  function salvaPref() {
    try { localStorage.setItem(PREF_KEY, JSON.stringify({ preset: S.preset, cmp: S.cmp, tab: S.tab })); } catch (_) {}
  }

  // ── Periodi ───────────────────────────────────────────────────────────
  function calcolaPeriodo() {
    var t = new Date(); t = new Date(t.getFullYear(), t.getMonth(), t.getDate());
    var dal, al;
    switch (S.preset) {
      case 'oggi':      dal = al = t; break;
      case 'ieri':      dal = al = piuGiorni(t, -1); break;
      case 'settimana': dal = piuGiorni(t, -((t.getDay() + 6) % 7)); al = t; break;
      case 'mese':      dal = new Date(t.getFullYear(), t.getMonth(), 1); al = t; break;
      case 'mese_prec': dal = new Date(t.getFullYear(), t.getMonth() - 1, 1); al = new Date(t.getFullYear(), t.getMonth(), 0); break;
      case '30g':       dal = piuGiorni(t, -29); al = t; break;
      case '12m':       dal = piuGiorni(stessoGiornoAnno(t, -1), 1); al = t; break;
      case 'anno':      dal = new Date(t.getFullYear(), 0, 1); al = t; break;
      default:
        dal = S.dal ? daIso(S.dal) : new Date(t.getFullYear(), t.getMonth(), 1);
        al = S.al ? daIso(S.al) : t;
    }
    S.dal = iso(dal); S.al = iso(al);

    var n = giorniTra(dal, al) + 1, cd = null, ca = null;
    if (S.cmp === 'anno_prec') {
      cd = stessoGiornoAnno(dal, -1); ca = stessoGiornoAnno(al, -1);
    } else if (S.cmp === 'precedente') {
      // Il confronto "naturale" del periodo: il mese corrente fino a oggi si
      // confronta con gli stessi giorni del mese prima, la settimana con la
      // settimana prima, l'anno con lo stesso tratto dell'anno prima; per il
      // resto, gli N giorni subito prima.
      if (S.preset === 'mese' || S.preset === 'mese_prec') {
        var y = dal.getFullYear(), m = dal.getMonth() - 1;
        cd = new Date(y, m, 1);
        var ultimo = fineMese(cd.getFullYear(), cd.getMonth());
        ca = S.preset === 'mese_prec' ? new Date(cd.getFullYear(), cd.getMonth(), ultimo)
                                      : new Date(cd.getFullYear(), cd.getMonth(), Math.min(al.getDate(), ultimo));
      } else if (S.preset === 'anno') {
        cd = new Date(dal.getFullYear() - 1, 0, 1); ca = stessoGiornoAnno(al, -1);
      } else if (S.preset === 'settimana') {
        cd = piuGiorni(dal, -7); ca = piuGiorni(al, -7);
      } else {
        ca = piuGiorni(dal, -1); cd = piuGiorni(ca, -(n - 1));
      }
    } else if (S.cmp === 'date') {
      cd = S.cmpDal ? daIso(S.cmpDal) : piuGiorni(dal, -n);
      ca = S.cmpAl ? daIso(S.cmpAl) : piuGiorni(dal, -1);
    }
    S.cmpDal = cd ? iso(cd) : null;
    S.cmpAl = ca ? iso(ca) : null;
  }

  // ── Variazioni ────────────────────────────────────────────────────────
  // Percentuale fra due valori. Con confronto a zero la percentuale non
  // esiste: si dice "prima 0" invece di inventare un +100%.
  function delta(cur, cmp, opt) {
    opt = opt || {};
    if (cmp === null || cmp === undefined || !S.data || !S.data.confronto) return '';
    var fmt = opt.fmt || num;
    var cmpTxt = '<span class="pf-delta-cmp">vs ' + esc(fmt(cmp)) + '</span>';
    if (!cmp) {
      if (!cur) return '<div class="pf-delta pf-flat">= ' + cmpTxt + '</div>';
      return '<div class="pf-delta pf-flat">prima 0 ' + '</div>';
    }
    var p = (cur - cmp) / Math.abs(cmp) * 100;
    if (Math.abs(p) < 0.5) return '<div class="pf-delta pf-flat">= invariato ' + cmpTxt + '</div>';
    var su = p > 0, buono = opt.invert ? !su : su;
    return '<div class="pf-delta ' + (buono ? 'pf-up' : 'pf-down') + '">' + (su ? '▲' : '▼') + ' ' +
           fmtNum.format(Math.abs(Math.round(p * 10) / 10)) + '% ' + cmpTxt + '</div>';
  }
  // Per le percentuali (no-show, online, agenda occupata): differenza in punti.
  function deltaPunti(cur, cmp, opt) {
    opt = opt || {};
    if (cmp === null || cmp === undefined || cur === null || cur === undefined || !S.data || !S.data.confronto) return '';
    var d = cur - cmp;
    var cmpTxt = '<span class="pf-delta-cmp">vs ' + esc(pct1(cmp)) + '</span>';
    if (Math.abs(d) < 0.05) return '<div class="pf-delta pf-flat">= invariato ' + cmpTxt + '</div>';
    var su = d > 0, buono = opt.invert ? !su : su;
    return '<div class="pf-delta ' + (buono ? 'pf-up' : 'pf-down') + '">' + (su ? '▲' : '▼') + ' ' +
           fmtNum.format(Math.abs(Math.round(d * 10) / 10)) + (Math.abs(d) >= 0.95 && Math.abs(d) < 1.05 ? ' punto ' : ' punti ') + cmpTxt + '</div>';
  }
  function deltaCella(cur, cmp, invert) {
    if (cmp === null || cmp === undefined) return '<span class="pf-flat">—</span>';
    if (!cmp) return cur ? '<span class="pf-flat">prima 0</span>' : '<span class="pf-flat">—</span>';
    var p = (cur - cmp) / Math.abs(cmp) * 100;
    if (Math.abs(p) < 0.5) return '<span class="pf-flat">=</span>';
    var su = p > 0, buono = invert ? !su : su;
    return '<span class="' + (buono ? 'pf-up' : 'pf-down') + '">' + (su ? '▲' : '▼') + ' ' + fmtNum.format(Math.abs(Math.round(p))) + '%</span>';
  }
  function quota(parte, totale) { return totale ? parte / totale * 100 : null; }

  // ── Tooltip Bootstrap (mai il tooltip nativo) ─────────────────────────
  function info(testo) {
    return '<i class="bi bi-info-circle pf-info" tabindex="0" role="img" aria-label="' + esc(testo) +
           '" data-bs-toggle="tooltip" data-bs-title="' + esc(testo) + '"></i>';
  }
  function chiudiTooltip() {
    S.tips.forEach(function (t) { try { t.dispose(); } catch (_) {} });
    S.tips = [];
  }
  function agganciaTooltip(root) {
    if (!window.bootstrap || !bootstrap.Tooltip) return;
    root.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
      // Le tabelle si ridisegnano da sole e poi la scheda intera: un secondo
      // Tooltip sullo stesso elemento mostrerebbe due fumetti.
      if (bootstrap.Tooltip.getInstance(el)) return;
      // container = la finestra stessa: col body finirebbe sotto il backdrop
      S.tips.push(new bootstrap.Tooltip(el, { container: M.modal, trigger: 'hover focus' }));
    });
  }

  // ── Finestra ──────────────────────────────────────────────────────────
  function costruisci() {
    if (M) return M;
    if (CSS_HREF && !document.querySelector('link[data-perf-css]')) {
      var l = document.createElement('link');
      l.rel = 'stylesheet'; l.href = CSS_HREF; l.setAttribute('data-perf-css', '1');
      document.head.appendChild(l);
    }
    var presets = PRESETS.map(function (p) {
      return '<button type="button" class="pf-chip" data-preset="' + p.id + '" aria-pressed="false">' + esc(p.label) + '</button>';
    }).join('');
    var confronti = CONFRONTI.map(function (c) { return '<option value="' + c.id + '">' + esc(c.label) + '</option>'; }).join('');

    var el = document.createElement('div');
    el.className = 'modal fade';
    el.id = 'perfModal';
    el.tabIndex = -1;
    el.setAttribute('aria-labelledby', 'perfTitle');
    el.setAttribute('aria-hidden', 'true');
    el.innerHTML =
      '<div class="modal-dialog modal-xl modal-fullscreen-lg-down modal-dialog-scrollable">' +
        '<div class="modal-content">' +
          '<div class="pf-head">' +
            '<i class="bi bi-graph-up-arrow" aria-hidden="true"></i>' +
            '<h5 id="perfTitle">PERFORMANCE</h5>' +
            '<span class="pf-head-sub" id="perfSub"></span>' +
            '<button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Chiudi"></button>' +
          '</div>' +
          '<div class="pf-toolbar">' +
            '<div class="pf-field"><span class="pf-field-label" id="perfLblPeriodo">Periodo</span>' +
              '<div class="pf-presets" role="group" aria-labelledby="perfLblPeriodo">' + presets + '</div>' +
              '<span class="pf-dates" id="perfDates"><input type="date" id="perfDal" aria-label="Dal"> – <input type="date" id="perfAl" aria-label="Al"></span>' +
            '</div>' +
            '<div class="pf-field"><label class="pf-field-label" for="perfCmp">Confronta con</label>' +
              '<select class="pf-select" id="perfCmp">' + confronti + '</select>' +
              '<span class="pf-dates" id="perfCmpDates"><input type="date" id="perfCmpDal" aria-label="Confronto dal"> – <input type="date" id="perfCmpAl" aria-label="Confronto al"></span>' +
            '</div>' +
          '</div>' +
          '<div class="pf-tabs" role="tablist" aria-label="Sezioni">' +
            '<button type="button" class="pf-tab" role="tab" id="perfTab-negozio" data-tab="negozio" aria-controls="perfPanel-negozio">Negozio</button>' +
            '<button type="button" class="pf-tab" role="tab" id="perfTab-servizi" data-tab="servizi" aria-controls="perfPanel-servizi">Servizi</button>' +
            '<button type="button" class="pf-tab" role="tab" id="perfTab-operatori" data-tab="operatori" aria-controls="perfPanel-operatori">Operatori</button>' +
          '</div>' +
          '<div class="modal-body" id="perfBody">' +
            '<div class="pf-panel" role="tabpanel" id="perfPanel-negozio" aria-labelledby="perfTab-negozio"></div>' +
            '<div class="pf-panel" role="tabpanel" id="perfPanel-servizi" aria-labelledby="perfTab-servizi" hidden></div>' +
            '<div class="pf-panel" role="tabpanel" id="perfPanel-operatori" aria-labelledby="perfTab-operatori" hidden></div>' +
          '</div>' +
        '</div>' +
      '</div>';
    document.body.appendChild(el);

    M = {
      modal: el, sub: el.querySelector('#perfSub'), body: el.querySelector('#perfBody'),
      dates: el.querySelector('#perfDates'), dal: el.querySelector('#perfDal'), al: el.querySelector('#perfAl'),
      cmp: el.querySelector('#perfCmp'), cmpDates: el.querySelector('#perfCmpDates'),
      cmpDal: el.querySelector('#perfCmpDal'), cmpAl: el.querySelector('#perfCmpAl'),
      panels: { negozio: el.querySelector('#perfPanel-negozio'), servizi: el.querySelector('#perfPanel-servizi'), operatori: el.querySelector('#perfPanel-operatori') }
    };

    el.querySelectorAll('[data-preset]').forEach(function (b) {
      b.addEventListener('click', function () {
        S.preset = b.getAttribute('data-preset');
        if (S.preset === 'date') { calcolaPeriodo(); aggiornaToolbar(); M.dal.focus(); return; }
        salvaPref(); carica();
      });
    });
    function suDate() {
      if (!M.dal.value || !M.al.value || M.al.value < M.dal.value) return;
      S.dal = M.dal.value; S.al = M.al.value; carica();
    }
    M.dal.addEventListener('change', suDate);
    M.al.addEventListener('change', suDate);
    M.cmp.addEventListener('change', function () {
      S.cmp = M.cmp.value;
      if (S.cmp === 'date') { S.cmpDal = null; S.cmpAl = null; calcolaPeriodo(); aggiornaToolbar(); M.cmpDal.focus(); }
      salvaPref(); carica();
    });
    function suCmpDate() {
      if (!M.cmpDal.value || !M.cmpAl.value || M.cmpAl.value < M.cmpDal.value) return;
      S.cmpDal = M.cmpDal.value; S.cmpAl = M.cmpAl.value; carica(true);
    }
    M.cmpDal.addEventListener('change', suCmpDate);
    M.cmpAl.addEventListener('change', suCmpDate);

    el.querySelectorAll('[data-tab]').forEach(function (b) {
      b.addEventListener('click', function () { mostraScheda(b.getAttribute('data-tab')); });
      b.addEventListener('keydown', function (e) {
        if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
        var ord = ['negozio', 'servizi', 'operatori'];
        var i = ord.indexOf(b.getAttribute('data-tab'));
        var n = ord[(i + (e.key === 'ArrowRight' ? 1 : 2)) % 3];
        mostraScheda(n);
        el.querySelector('#perfTab-' + n).focus();
      });
    });

    el.addEventListener('show.bs.modal', function () { document.body.classList.add('perf-aperto'); });
    el.addEventListener('hidden.bs.modal', function () {
      document.body.classList.remove('perf-aperto');
      chiudiTooltip();
    });
    return M;
  }

  function aggiornaToolbar() {
    M.modal.querySelectorAll('[data-preset]').forEach(function (b) {
      b.setAttribute('aria-pressed', b.getAttribute('data-preset') === S.preset ? 'true' : 'false');
    });
    M.dates.classList.toggle('on', S.preset === 'date');
    M.dal.value = S.dal || ''; M.al.value = S.al || '';
    M.cmp.value = S.cmp;
    M.cmpDates.classList.toggle('on', S.cmp === 'date');
    M.cmpDal.value = S.cmpDal || ''; M.cmpAl.value = S.cmpAl || '';
    var giorni = giorniTra(daIso(S.dal), daIso(S.al)) + 1;
    var t = intervalloIT(S.dal, S.al) + ' (' + giorni + (giorni === 1 ? ' giorno)' : ' giorni)');
    if (S.cmpDal) t += ' · confronto con ' + intervalloIT(S.cmpDal, S.cmpAl);
    M.sub.textContent = t;
  }

  function mostraScheda(tab) {
    if (S.tab !== tab && M.body) M.body.scrollTop = 0;
    S.tab = tab; salvaPref();
    M.modal.querySelectorAll('[data-tab]').forEach(function (b) {
      var on = b.getAttribute('data-tab') === tab;
      b.setAttribute('aria-selected', on ? 'true' : 'false');
      b.tabIndex = on ? 0 : -1;
    });
    Object.keys(M.panels).forEach(function (k) { M.panels[k].hidden = (k !== tab); });
    if (S.data) disegna();
  }

  // ── Dati ──────────────────────────────────────────────────────────────
  function carica(soloConfronto) {
    if (!soloConfronto || S.cmp !== 'date') calcolaPeriodo();
    aggiornaToolbar();
    if (S.req) { try { S.req.abort(); } catch (_) {} }
    var ctrl = (typeof AbortController !== 'undefined') ? new AbortController() : null;
    S.req = ctrl;
    var q = new URLSearchParams({ dal: S.dal, al: S.al });
    if (S.cmpDal && S.cmpAl) { q.set('cmp_dal', S.cmpDal); q.set('cmp_al', S.cmpAl); }
    var url = (window.CD_PERF_URL || '/calendar/api/info/performance') + '?' + q.toString();
    M.body.classList.add('pf-loading');
    if (!S.data) M.panels[S.tab].innerHTML = '<div class="pf-msg">Caricamento…</div>';
    fetch(url, { credentials: 'same-origin', signal: ctrl ? ctrl.signal : undefined })
      .then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (j) {
          if (!r.ok) throw new Error(j.error || ('errore ' + r.status));
          return j;
        });
      })
      .then(function (j) {
        if (S.req !== ctrl) return;
        S.data = j;
        M.body.classList.remove('pf-loading');
        disegna();
      })
      .catch(function (e) {
        if (e && e.name === 'AbortError') return;
        M.body.classList.remove('pf-loading');
        S.data = null;
        chiudiTooltip();
        M.panels[S.tab].innerHTML = '<div class="pf-msg err"><strong>Non riesco a calcolare le performance.</strong><br>Motivo: ' +
          esc(e && e.message ? e.message : 'errore di rete') + '</div>';
      });
  }

  function disegna() {
    chiudiTooltip();
    distruggiGrafici();
    var p = M.panels[S.tab];
    if (S.tab === 'negozio') disegnaNegozio(p);
    else if (S.tab === 'servizi') disegnaServizi(p);
    else disegnaOperatori(p);
    agganciaTooltip(p);
  }

  // ── Scheda NEGOZIO ────────────────────────────────────────────────────
  function riquadro(o) {
    return '<div class="pf-kpi' + (o.hero ? ' hero' : '') + '">' +
             '<div class="pf-kpi-label">' + esc(o.label) + (o.info ? ' ' + info(o.info) : '') + '</div>' +
             '<div class="pf-kpi-value">' + o.value + '</div>' +
             (o.delta || '') +
             (o.sub ? '<div class="pf-kpi-sub">' + o.sub + '</div>' : '') +
           '</div>';
  }

  function disegnaNegozio(p) {
    var d = S.data, k = d.kpi, c = d.kpi_cmp || {};
    var hc = !!d.kpi_cmp;
    var r = [];
    r.push(riquadro({
      hero: true, label: 'Incasso',
      info: 'Soldi entrati: tutti gli scontrini del periodo, fiscali e non fiscali, come nel Report. Storni e resi si sottraggono.',
      value: esc(euro(k.incasso)),
      delta: delta(k.incasso, hc ? c.incasso : null, { fmt: euro }),
      sub: 'fiscale ' + esc(euro(k.incasso_fiscale)) + ' · non fiscale ' + esc(euro(k.incasso_non_fiscale)) +
           ' · media ' + esc(euro(k.incasso_medio_giorno)) + ' al giorno'
    }));
    r.push(riquadro({
      label: 'Scontrino medio',
      info: 'Incasso medio per passaggio in cassa. Non contano gli scontrini a zero (sedute scalate dalla carta) né le rettifiche.',
      value: esc(euro(k.scontrino_medio)),
      delta: delta(k.scontrino_medio, hc ? c.scontrino_medio : null, { fmt: euro }),
      sub: 'su ' + esc(num(k.scontrini)) + ' passaggi in cassa'
    }));
    r.push(riquadro({
      label: 'Appuntamenti',
      info: 'Un appuntamento è una persona in un giorno, qualunque sia il numero di servizi. Esclusi blocchi OFF e annullati dal cliente.',
      value: esc(num(k.visite)),
      delta: delta(k.visite, hc ? c.visite : null),
      sub: esc(num(k.servizi_agenda)) + ' servizi in agenda'
    }));
    r.push(riquadro({
      label: 'Clienti',
      info: 'Persone diverse con almeno un appuntamento nel periodo. Nuove schede = clienti inseriti in anagrafica nel periodo.',
      value: esc(num(k.clienti)),
      delta: delta(k.clienti, hc ? c.clienti : null),
      sub: esc(num(k.nuovi_clienti)) + (k.nuovi_clienti === 1 ? ' nuova scheda cliente' : ' nuove schede cliente') +
           (hc ? ' (prima ' + esc(num(c.nuovi_clienti)) + ')' : '')
    }));
    var on = quota(k.online, k.visite), onC = hc ? quota(c.online, c.visite) : null;
    r.push(riquadro({
      label: 'Prenotati online',
      info: 'Appuntamenti con almeno un servizio prenotato dal sito.',
      value: on === null ? '—' : esc(pct1(on)),
      delta: deltaPunti(on, onC),
      sub: esc(num(k.online)) + ' su ' + esc(num(k.visite)) + ' appuntamenti'
    }));
    var ns = quota(k.noshow, k.visite), nsC = hc ? quota(c.noshow, c.visite) : null;
    r.push(riquadro({
      label: 'No-show',
      info: 'Appuntamenti con almeno un servizio segnato "non arrivato".',
      value: esc(num(k.noshow)),
      delta: deltaPunti(ns, nsC, { invert: true }),
      sub: 'su ' + esc(num(k.visite)) + ' appuntamenti' + (ns === null ? '' : ' (' + esc(pct1(ns)) + ')')
    }));
    r.push(riquadro({
      label: 'Agenda occupata',
      info: 'Ore prenotate su ore di turno, solo per chi ha i turni inseriti. I blocchi OFF non sono ore prenotate.',
      value: k.occupazione === null ? '—' : esc(pct1(k.occupazione)),
      delta: deltaPunti(k.occupazione, hc ? c.occupazione : null),
      sub: k.ore_turno ? esc(num(k.ore_prenotate)) + ' h prenotate su ' + esc(num(k.ore_turno)) + ' h di turno' : 'turni non inseriti nel periodo'
    }));
    if (k.pagato_con_carta || (hc && c.pagato_con_carta)) {
      r.push(riquadro({
        label: 'Scalato dalle carte',
        info: 'Valore delle sedute pagate con carta prepagata. Non è incasso del periodo: i soldi sono entrati quando la carta è stata venduta o ricaricata.',
        value: esc(euro(k.pagato_con_carta)),
        delta: delta(k.pagato_con_carta, hc ? c.pagato_con_carta : null, { fmt: euro }),
        sub: 'sedute pagate con carta prepagata'
      }));
    }

    var legenda = '<div class="pf-legend"><span class="pf-key"><i></i>' + esc(intervalloIT(d.periodo.dal, d.periodo.al)) + '</span>' +
                  (hc ? '<span class="pf-key cmp"><i></i>' + esc(intervalloIT(d.confronto.dal, d.confronto.al)) + '</span>' : '') + '</div>';
    var legendaCorta = '<div class="pf-legend"><span class="pf-key"><i></i>Periodo</span>' + (hc ? '<span class="pf-key cmp"><i></i>Confronto</span>' : '') + '</div>';

    var giorni = d.periodo.giorni;
    var grane = [['giorno', 'Giorno'], ['settimana', 'Settimana'], ['mese', 'Mese']];
    var granaHtml = '<div class="pf-presets" role="group" aria-label="Raggruppa per">' + grane.map(function (g) {
      var dis = (g[0] === 'giorno' && giorni > 400) || (g[0] === 'settimana' && giorni < 14) || (g[0] === 'mese' && giorni < 45);
      return dis ? '' : '<button type="button" class="pf-chip" data-grana="' + g[0] + '" aria-pressed="' + (granaScelta() === g[0]) + '">' + g[1] + '</button>';
    }).join('') + '</div>';

    var andamento = giorni > 1
      ? '<div class="pf-card"><div class="pf-card-head"><span class="pf-card-title">Andamento incasso</span>' + granaHtml + legenda + '</div>' +
        '<div class="pf-chart"><canvas id="perfTrend" role="img" aria-label="Andamento dell\'incasso nel periodo"></canvas></div></div>'
      : '<div class="pf-card"><div class="pf-card-title">Andamento incasso</div><div class="pf-note">Scegli un periodo di più giorni per vedere l\'andamento.</div></div>';

    // Confronto vuoto (per esempio prima che il negozio usasse Tosca): lo si
    // dice una volta, invece di lasciare "prima 0" in ogni riquadro senza motivo.
    var avvisoCmp = (hc && !c.incasso && !c.visite)
      ? '<div class="pf-msg" style="margin-bottom:14px;">Nel periodo di confronto (' + esc(intervalloIT(d.confronto.dal, d.confronto.al)) +
        ') non ci sono né incassi né appuntamenti: le variazioni non si possono calcolare.</div>'
      : '';

    p.innerHTML =
      avvisoCmp +
      '<div class="pf-kpis">' + r.join('') + '</div>' +
      andamento +
      '<div class="pf-grid2">' +
        '<div class="pf-card"><div class="pf-card-head"><span class="pf-card-title">Incasso per categoria</span>' + legendaCorta + '</div>' +
          barreCategorie(d) +
          '<div class="pf-note">Carte prepagate e rate dei pacchetti sono vendite: le sedute scalate dopo non sono di nuovo incasso.</div></div>' +
        '<div class="pf-card"><div class="pf-card-head"><span class="pf-card-title">Incasso medio per giorno della settimana</span>' + legendaCorta + '</div>' +
          (giorni >= 7 ? '<div class="pf-chart small"><canvas id="perfSett" role="img" aria-label="Incasso medio per giorno della settimana"></canvas></div>'
                       : '<div class="pf-note">Serve un periodo di almeno 7 giorni.</div>') +
        '</div>' +
      '</div>' +
      '<div class="pf-note">Aggiornato alle ' + esc(d.generato_il || '') + '. I numeri sono calcolati come nel Report.</div>';

    p.querySelectorAll('[data-grana]').forEach(function (b) {
      b.addEventListener('click', function () { S.grana = b.getAttribute('data-grana'); disegna(); });
    });
    if (giorni > 1) graficoAndamento();
    if (giorni >= 7) graficoSettimana();
  }

  function barreCategorie(d) {
    var cats = d.categorie || [];
    if (!cats.length) return '<div class="pf-note">Nessun incasso nel periodo.</div>';
    var max = Math.max.apply(null, cats.map(function (c) { return Math.max(c.incasso, c.incasso_cmp || 0); }).concat([1]));
    var tot = d.kpi.incasso || 0;
    return '<div class="pf-bars">' + cats.map(function (c) {
      var w = Math.max(0, c.incasso) / max * 100, wc = Math.max(0, c.incasso_cmp || 0) / max * 100;
      var q = quota(c.incasso, tot);
      return '<div class="pf-bar-row">' +
               '<div class="pf-bar-name">' + esc(c.nome) + '</div>' +
               '<div class="pf-bar-track" aria-hidden="true"><div class="pf-bar" style="width:' + w.toFixed(1) + '%"></div>' +
                 (d.confronto ? '<div class="pf-bar cmp" style="width:' + wc.toFixed(1) + '%"></div>' : '') + '</div>' +
               '<div class="pf-bar-val">' + esc(euro(c.incasso)) +
                 '<small>' + (q === null ? '' : esc(pct1(q)) + ' del totale') + (d.confronto ? ' · ' + deltaCella(c.incasso, c.incasso_cmp) : '') + '</small></div>' +
             '</div>';
    }).join('') + '</div>';
  }

  // ── Grafici (Chart.js) ────────────────────────────────────────────────
  function caricaChart() {
    if (window.Chart) return Promise.resolve(window.Chart);
    if (chartLoad) return chartLoad;
    chartLoad = new Promise(function (ok, ko) {
      var s = document.createElement('script');
      s.src = CHART_SRC; s.async = true;
      s.onload = function () { window.Chart ? ok(window.Chart) : ko(new Error('Chart.js')); };
      s.onerror = function () { chartLoad = null; ko(new Error('Chart.js non raggiungibile')); };
      document.head.appendChild(s);
    });
    return chartLoad;
  }
  function distruggiGrafici() {
    Object.keys(S.charts).forEach(function (k) { try { S.charts[k].destroy(); } catch (_) {} });
    S.charts = {};
  }
  function graficoNonDisponibile(canvas) {
    if (!canvas || !canvas.parentNode) return;
    canvas.parentNode.innerHTML = '<div class="pf-note">Grafico non disponibile: la libreria dei grafici non si è caricata (connessione).</div>';
  }

  function granaScelta() {
    var g = S.data ? S.data.periodo.giorni : 30;
    var auto = g <= 62 ? 'giorno' : (g <= 400 ? 'settimana' : 'mese');
    var s = S.grana;
    if (s === 'giorno' && g > 400) s = 'auto';
    if (s === 'settimana' && g < 14) s = 'auto';
    if (s === 'mese' && g < 45) s = 'auto';
    return s === 'auto' ? auto : s;
  }

  // Raggruppa la serie giornaliera. Il confronto si allinea per POSIZIONE
  // (1° giorno con 1° giorno, 1ª settimana con 1ª settimana), non per data.
  function raggruppa(serie, grana) {
    if (!serie) return [];
    var out = [];
    if (grana === 'giorno') {
      serie.forEach(function (x) { out.push({ etichetta: dataBreve(x.data), da: x.data, a: x.data, v: x.incasso }); });
    } else if (grana === 'settimana') {
      for (var i = 0; i < serie.length; i += 7) {
        var pezzo = serie.slice(i, i + 7);
        out.push({ etichetta: dataBreve(pezzo[0].data), da: pezzo[0].data, a: pezzo[pezzo.length - 1].data,
                   v: pezzo.reduce(function (s, x) { return s + x.incasso; }, 0) });
      }
    } else {
      var cur = null;
      serie.forEach(function (x) {
        var k = x.data.slice(0, 7);
        if (!cur || cur.k !== k) { cur = { k: k, etichetta: MESI[+k.slice(5, 7) - 1] + ' ' + k.slice(0, 4), da: x.data, a: x.data, v: 0 }; out.push(cur); }
        cur.v += x.incasso; cur.a = x.data;
      });
    }
    return out;
  }

  function assiComuni() {
    return {
      x: { grid: { display: false }, border: { color: '#c3c2b7' },
           ticks: { color: COL_MUTED, maxRotation: 0, autoSkip: true, maxTicksLimit: 10, font: { size: 11 } } },
      y: { beginAtZero: true, grid: { color: COL_GRID }, border: { display: false },
           ticks: { color: COL_MUTED, font: { size: 11 }, maxTicksLimit: 6, callback: function (v) { return euro0(v); } } }
    };
  }
  function tooltipStile() {
    return { backgroundColor: '#1f2328', titleColor: '#fff', bodyColor: '#fff', padding: 10, cornerRadius: 8,
             boxPadding: 4, usePointStyle: true, titleFont: { weight: '600' } };
  }

  function graficoAndamento() {
    var canvas = M.modal.querySelector('#perfTrend');
    if (!canvas) return;
    var grana = granaScelta();
    var cur = raggruppa(S.data.serie, grana);
    var cmp = raggruppa(S.data.serie_cmp, grana);
    var intervallo = function (b) { return b.da === b.a ? dataIT(b.da) : (grana === 'mese' ? b.etichetta : intervalloIT(b.da, b.a)); };
    caricaChart().then(function (Chart) {
      if (!canvas.isConnected) return;
      var ds = [{
        label: 'Periodo', data: cur.map(function (b) { return b.v; }),
        borderColor: COL_ACCENT, backgroundColor: 'rgba(42,120,214,0.08)', fill: 'origin',
        borderWidth: 2, cubicInterpolationMode: 'monotone', pointRadius: cur.length <= 1 ? 4 : 0, pointHoverRadius: 5,
        pointBackgroundColor: COL_ACCENT, pointBorderColor: '#fff', pointBorderWidth: 2
      }];
      if (cmp.length) {
        ds.push({
          label: 'Confronto', data: cur.map(function (_, i) { return cmp[i] ? cmp[i].v : null; }),
          borderColor: COL_CMP, backgroundColor: COL_CMP, fill: false,
          borderWidth: 2, cubicInterpolationMode: 'monotone', pointRadius: 0, pointHoverRadius: 5,
          pointBackgroundColor: COL_CMP, pointBorderColor: '#fff', pointBorderWidth: 2
        });
      }
      S.charts.trend = new Chart(canvas, {
        type: 'line',
        data: { labels: cur.map(function (b) { return b.etichetta; }), datasets: ds },
        options: {
          responsive: true, maintainAspectRatio: false, animation: { duration: 250 },
          interaction: { mode: 'index', intersect: false },
          plugins: {
            legend: { display: false },
            tooltip: Object.assign(tooltipStile(), {
              callbacks: {
                title: function () { return ''; },
                label: function (ctx) {
                  var i = ctx.dataIndex;
                  var b = ctx.datasetIndex === 0 ? cur[i] : cmp[i];
                  if (!b) return null;
                  return intervallo(b) + ': ' + euro(ctx.parsed.y);
                }
              }
            })
          },
          scales: assiComuni()
        }
      });
    }).catch(function () { graficoNonDisponibile(canvas); });
  }

  function mediePerGiornoSettimana(serie) {
    var somma = [0, 0, 0, 0, 0, 0, 0], quanti = [0, 0, 0, 0, 0, 0, 0];
    (serie || []).forEach(function (x) {
      var g = (daIso(x.data).getDay() + 6) % 7;
      somma[g] += x.incasso; quanti[g] += 1;
    });
    return somma.map(function (s, i) { return quanti[i] ? s / quanti[i] : 0; });
  }

  function graficoSettimana() {
    var canvas = M.modal.querySelector('#perfSett');
    if (!canvas) return;
    var cur = mediePerGiornoSettimana(S.data.serie);
    var cmp = S.data.serie_cmp ? mediePerGiornoSettimana(S.data.serie_cmp) : null;
    caricaChart().then(function (Chart) {
      if (!canvas.isConnected) return;
      var ds = [{ label: 'Periodo', data: cur, backgroundColor: COL_ACCENT, borderRadius: 4, borderSkipped: 'start', maxBarThickness: 22 }];
      if (cmp) ds.push({ label: 'Confronto', data: cmp, backgroundColor: COL_CMP, borderRadius: 4, borderSkipped: 'start', maxBarThickness: 22 });
      S.charts.sett = new Chart(canvas, {
        type: 'bar',
        data: { labels: GIORNI_SETT, datasets: ds },
        options: {
          responsive: true, maintainAspectRatio: false, animation: { duration: 250 },
          interaction: { mode: 'index', intersect: false },
          datasets: { bar: { categoryPercentage: 0.7, barPercentage: 0.9 } },
          plugins: {
            legend: { display: false },
            tooltip: Object.assign(tooltipStile(), {
              callbacks: { label: function (ctx) { return ctx.dataset.label + ': ' + euro(ctx.parsed.y) + ' in media'; } }
            })
          },
          scales: assiComuni()
        }
      });
    }).catch(function () { graficoNonDisponibile(canvas); });
  }

  // ── Scheda SERVIZI ────────────────────────────────────────────────────
  function disegnaServizi(p) {
    var d = S.data, hc = !!d.confronto;
    var presenti = {};
    d.servizi.forEach(function (r) { presenti[r.categoria] = true; });
    var ordineCat = ['estetica', 'solarium', 'prodotti', 'carte', 'pacchetti', 'dgfe', 'altro'];
    if (S.serv.cat !== 'tutte' && !presenti[S.serv.cat]) S.serv.cat = 'tutte';
    var chips = '<button type="button" class="pf-chip" data-cat="tutte" aria-pressed="' + (S.serv.cat === 'tutte') + '">Tutte</button>' +
      ordineCat.filter(function (c) { return presenti[c]; }).map(function (c) {
        return '<button type="button" class="pf-chip" data-cat="' + c + '" aria-pressed="' + (S.serv.cat === c) + '">' + esc(CAT_LABEL[c]) + '</button>';
      }).join('');

    p.innerHTML =
      '<div class="pf-card">' +
        '<div class="pf-filters">' +
          '<input type="search" class="pf-search" id="perfServQ" placeholder="Cerca un servizio…" aria-label="Cerca un servizio" value="' + esc(S.serv.q) + '">' +
          '<div class="pf-presets" role="group" aria-label="Categoria">' + chips + '</div>' +
        '</div>' +
        '<div id="perfServTab"></div>' +
        '<div class="pf-note">Quantità = passaggi in cassa del servizio (una riga divisa fra carta e contanti conta una volta; storni e resi tolgono). ' +
          'Incasso = soldi entrati per quel servizio. Le sedute pagate con carta prepagata contano nella quantità ma non nell\'incasso.' +
          (hc ? ' Δ = variazione dell\'incasso rispetto al confronto.' : '') + '</div>' +
      '</div>';

    var q = p.querySelector('#perfServQ');
    q.addEventListener('input', function () { S.serv.q = q.value; S.serv.tutti = false; tabellaServizi(p); });
    p.querySelectorAll('[data-cat]').forEach(function (b) {
      b.addEventListener('click', function () {
        S.serv.cat = b.getAttribute('data-cat'); S.serv.tutti = false;
        p.querySelectorAll('[data-cat]').forEach(function (x) { x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); });
        tabellaServizi(p);
      });
    });
    tabellaServizi(p);
  }

  function normalizza(s) { return String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, ''); }

  function ordina(righe, campo, dir, valore) {
    var segno = dir === 'asc' ? 1 : -1;
    return righe.slice().sort(function (a, b) {
      var va = valore(a, campo), vb = valore(b, campo);
      if (typeof va === 'string' || typeof vb === 'string') return segno * String(va).localeCompare(String(vb), 'it');
      if (va === null || va === undefined) va = -Infinity;
      if (vb === null || vb === undefined) vb = -Infinity;
      return segno * (va - vb) || String(a.nome).localeCompare(String(b.nome), 'it');
    });
  }
  function intestazione(campi, stato) {
    return '<tr>' + campi.map(function (c) {
      if (!c.sort) return '<th scope="col">' + esc(c.label) + (c.info ? ' ' + info(c.info) : '') + '</th>';
      var dir = stato.sort === c.sort ? stato.dir : '';
      return '<th scope="col" aria-sort="' + (dir === 'asc' ? 'ascending' : dir === 'desc' ? 'descending' : 'none') + '">' +
               '<button type="button" class="pf-th-sort" data-sort="' + c.sort + '"' + (dir ? ' data-dir="' + dir + '"' : '') + '>' + esc(c.label) + '</button>' +
               (c.info ? ' ' + info(c.info) : '') + '</th>';
    }).join('') + '</tr>';
  }
  function agganciaOrdinamento(root, stato, ridisegna) {
    root.querySelectorAll('[data-sort]').forEach(function (b) {
      b.addEventListener('click', function () {
        var c = b.getAttribute('data-sort');
        if (stato.sort === c) stato.dir = stato.dir === 'desc' ? 'asc' : 'desc';
        else { stato.sort = c; stato.dir = c === 'nome' ? 'asc' : 'desc'; }
        ridisegna();
      });
    });
  }

  function tabellaServizi(p) {
    var d = S.data, hc = !!d.confronto;
    var box = p.querySelector('#perfServTab');
    chiudiTooltip();
    var f = normalizza(S.serv.q).trim();
    var righe = d.servizi.filter(function (r) {
      if (S.serv.cat !== 'tutte' && r.categoria !== S.serv.cat) return false;
      return !f || normalizza(r.nome).indexOf(f) !== -1;
    });
    var tot = d.kpi.incasso || 0;
    var valore = function (r, c) {
      if (c === 'nome') return r.nome;
      if (c === 'medio') return r.quantita > 0 ? r.incasso / r.quantita : null;
      if (c === 'quota') return r.incasso;
      if (c === 'delta') return (r.incasso_cmp ? (r.incasso - r.incasso_cmp) / Math.abs(r.incasso_cmp) : null);
      return r[c];
    };
    righe = ordina(righe, S.serv.sort, S.serv.dir, valore);
    var max = Math.max.apply(null, righe.map(function (r) { return r.incasso; }).concat([1]));
    var sommaInc = righe.reduce(function (s, r) { return s + r.incasso; }, 0);
    var sommaQ = righe.reduce(function (s, r) { return s + r.quantita; }, 0);
    var visibili = S.serv.tutti ? righe : righe.slice(0, 30);

    var campi = [
      { label: 'Servizio', sort: 'nome' },
      { label: 'Quantità', sort: 'quantita' },
      { label: 'Incasso', sort: 'incasso' },
      { label: 'Medio', sort: 'medio', info: 'Incasso diviso quantità: quanto rende in media ogni passaggio in cassa.' },
      { label: 'Quota', sort: 'quota', info: 'Parte dell\'incasso totale del periodo.' }
    ];
    if (hc) { campi.push({ label: 'Confronto', sort: 'incasso_cmp' }); campi.push({ label: 'Δ', sort: 'delta' }); }

    var corpo = visibili.map(function (r) {
      var q = quota(r.incasso, tot);
      var w = Math.max(0, r.incasso) / max * 100;
      var medio = r.quantita > 0 ? r.incasso / r.quantita : null;
      return '<tr>' +
        '<td class="pf-name">' + esc(r.nome) +
          (r.voce_cassa ? ' <span class="pf-tag">voci di cassa</span>' : ' <span class="pf-tag">' + esc(CAT_LABEL[r.categoria] || r.categoria) + '</span>') +
          (r.eliminato ? ' <span class="pf-tag">eliminato</span>' : '') + '</td>' +
        '<td>' + esc(num(r.quantita)) + (hc ? '<br><small class="pf-flat">prima ' + esc(num(r.quantita_cmp || 0)) + '</small>' : '') + '</td>' +
        '<td><div class="pf-cell-bar">' + esc(euro(r.incasso)) + '<span class="pf-mini" aria-hidden="true"><b style="width:' + w.toFixed(1) + '%"></b></span></div>' +
          (r.pagato_con_carta ? '<small class="pf-flat">+ ' + esc(euro(r.pagato_con_carta)) + ' con carta</small>' : '') + '</td>' +
        '<td>' + (medio === null ? '—' : esc(euro(medio))) + '</td>' +
        '<td>' + (q === null ? '—' : esc(pct1(q))) + '</td>' +
        (hc ? '<td>' + esc(euro(r.incasso_cmp || 0)) + '</td><td>' + deltaCella(r.incasso, r.incasso_cmp) + '</td>' : '') +
      '</tr>';
    }).join('');

    box.innerHTML =
      '<div class="pf-card-sub" style="margin-bottom:6px;">' + esc(num(righe.length)) + (righe.length === 1 ? ' voce' : ' voci') +
        ' · quantità ' + esc(num(sommaQ)) + ' · incasso ' + esc(euro(sommaInc)) +
        (tot ? ' (' + esc(pct1(quota(sommaInc, tot))) + ' del totale)' : '') + '</div>' +
      (righe.length
        ? '<div class="pf-table-wrap"><table class="pf-table"><thead>' + intestazione(campi, S.serv) + '</thead><tbody>' + corpo + '</tbody></table></div>' +
          (righe.length > visibili.length ? '<button type="button" class="btn btn-sm btn-outline-secondary pf-more" id="perfServTutti">Mostra tutti (' + righe.length + ')</button>' : '')
        : '<div class="pf-note">Nessun servizio con questi filtri.</div>');

    agganciaOrdinamento(box, S.serv, function () { tabellaServizi(p); });
    var piu = box.querySelector('#perfServTutti');
    if (piu) piu.addEventListener('click', function () { S.serv.tutti = true; tabellaServizi(p); });
    agganciaTooltip(p);
  }

  // ── Scheda OPERATORI ──────────────────────────────────────────────────
  function disegnaOperatori(p) {
    var d = S.data, hc = !!d.confronto;
    var haMacchine = d.operatori.some(function (o) { return o.tipo === 'macchinario'; });
    var haPersone = d.operatori.some(function (o) { return o.tipo !== 'macchinario'; });
    if (!(haMacchine && haPersone)) S.ops.tipo = 'tutti';
    var chips = (haMacchine && haPersone)
      ? '<div class="pf-presets" role="group" aria-label="Tipo">' +
          [['tutti', 'Tutti'], ['persone', 'Operatori'], ['macchinari', 'Macchinari e lampade']].map(function (t) {
            return '<button type="button" class="pf-chip" data-tipo="' + t[0] + '" aria-pressed="' + (S.ops.tipo === t[0]) + '">' + t[1] + '</button>';
          }).join('') + '</div>'
      : '';
    var legendaCorta = '<div class="pf-legend"><span class="pf-key"><i></i>Periodo</span>' + (hc ? '<span class="pf-key cmp"><i></i>Confronto</span>' : '') + '</div>';

    p.innerHTML =
      (chips ? '<div class="pf-filters">' + chips + '</div>' : '') +
      '<div class="pf-card"><div class="pf-card-head"><span class="pf-card-title">Incasso per operatore</span>' + legendaCorta + '</div><div id="perfOpBarre"></div></div>' +
      '<div class="pf-card"><div class="pf-card-head"><span class="pf-card-title">Dettaglio</span>' +
        '<span class="pf-card-sub">clic su un nome per i suoi servizi</span></div><div id="perfOpTab"></div>' +
        '<div class="pf-note">Incasso = voci di cassa assegnate all\'operatore (l\'operatore della riga, altrimenti quello dello scontrino). ' +
          'Servizi, appuntamenti e ore vengono dall\'agenda: esclusi blocchi OFF, annullati e no-show. ' +
          '€/ora = incasso diviso ore prenotate. Agenda occupata = ore prenotate su ore di turno.</div></div>';

    p.querySelectorAll('[data-tipo]').forEach(function (b) {
      b.addEventListener('click', function () { S.ops.tipo = b.getAttribute('data-tipo'); disegna(); });
    });
    tabellaOperatori(p);
  }

  function filtraOperatori() {
    return S.data.operatori.filter(function (o) {
      if (S.ops.tipo === 'persone') return o.tipo !== 'macchinario';
      if (S.ops.tipo === 'macchinari') return o.tipo === 'macchinario';
      return true;
    });
  }

  function tabellaOperatori(p) {
    var d = S.data, hc = !!d.confronto;
    var righe = filtraOperatori();
    chiudiTooltip();

    // Barre: sempre in ordine di incasso, indipendenti dall'ordinamento della tabella
    var perInc = righe.slice().sort(function (a, b) { return b.incasso - a.incasso; });
    var max = Math.max.apply(null, perInc.map(function (o) { return Math.max(o.incasso, o.incasso_cmp || 0); }).concat([1]));
    var tot = perInc.reduce(function (s, o) { return s + o.incasso; }, 0);
    p.querySelector('#perfOpBarre').innerHTML = perInc.length ? '<div class="pf-bars">' + perInc.map(function (o) {
      var w = Math.max(0, o.incasso) / max * 100, wc = Math.max(0, o.incasso_cmp || 0) / max * 100;
      var q = quota(o.incasso, tot);
      return '<div class="pf-bar-row">' +
               '<div class="pf-bar-name">' + esc(o.nome) + (o.eliminato ? ' <span class="pf-tag">eliminato</span>' : '') + '</div>' +
               '<div class="pf-bar-track" aria-hidden="true"><div class="pf-bar" style="width:' + w.toFixed(1) + '%"></div>' +
                 (hc ? '<div class="pf-bar cmp" style="width:' + wc.toFixed(1) + '%"></div>' : '') + '</div>' +
               '<div class="pf-bar-val">' + esc(euro(o.incasso)) +
                 '<small>' + (q === null ? '' : esc(pct1(q))) + (hc ? ' · ' + deltaCella(o.incasso, o.incasso_cmp) : '') + '</small></div>' +
             '</div>';
    }).join('') + '</div>' : '<div class="pf-note">Nessun dato nel periodo.</div>';

    var valore = function (r, c) {
      if (c === 'nome') return r.nome;
      if (c === 'delta') return (r.incasso_cmp ? (r.incasso - r.incasso_cmp) / Math.abs(r.incasso_cmp) : null);
      return r[c];
    };
    var ord = ordina(righe, S.ops.sort, S.ops.dir, valore);
    var campi = [
      { label: 'Operatore', sort: 'nome' },
      { label: 'Incasso', sort: 'incasso' }
    ];
    if (hc) campi.push({ label: 'Δ', sort: 'delta' });
    campi = campi.concat([
      { label: 'Servizi', sort: 'servizi' },
      { label: 'Appuntamenti', sort: 'visite', info: 'Persone in un giorno servite da questo operatore.' },
      { label: 'Ore prenotate', sort: 'ore_prenotate' },
      { label: '€/ora', sort: 'incasso_ora', info: 'Incasso diviso ore prenotate in agenda.' },
      { label: 'Agenda occupata', sort: 'occupazione', info: 'Ore prenotate su ore di turno. Vuoto se i turni non sono inseriti.' },
      { label: 'No-show', sort: 'noshow' }
    ]);
    var ncol = campi.length;

    var corpo = ord.map(function (o) {
      var k = String(o.id === null ? 'x' : o.id);
      var aperto = !!S.ops.aperti[k];
      var ev = S.ops.evidenzia !== null && String(S.ops.evidenzia) === String(o.id);
      var occ = o.occupazione;
      var riga = '<tr class="' + (aperto ? 'open' : '') + (ev ? ' pf-evidenzia' : '') + '" data-op="' + esc(k) + '">' +
        '<td class="pf-name"><button type="button" class="pf-row-btn" aria-expanded="' + aperto + '" data-apri="' + esc(k) + '"><i class="bi bi-chevron-right" aria-hidden="true"></i>' + esc(o.nome) + '</button>' +
          (o.tipo === 'macchinario' ? ' <span class="pf-tag">macchinario</span>' : '') + (o.eliminato ? ' <span class="pf-tag">eliminato</span>' : '') + '</td>' +
        '<td>' + esc(euro(o.incasso)) + '</td>' +
        (hc ? '<td>' + deltaCella(o.incasso, o.incasso_cmp) + '</td>' : '') +
        '<td>' + esc(num(o.servizi)) + (hc ? '<br><small class="pf-flat">prima ' + esc(num(o.servizi_cmp || 0)) + '</small>' : '') + '</td>' +
        '<td>' + esc(num(o.visite)) + '</td>' +
        '<td>' + esc(num(o.ore_prenotate)) + ' h</td>' +
        '<td>' + (o.incasso_ora === null ? '—' : esc(euro(o.incasso_ora))) + '</td>' +
        '<td>' + (occ === null ? '<span class="pf-flat">turni mancanti</span>'
                  : '<span class="pf-meter"><span class="pf-track" aria-hidden="true"><b style="width:' + Math.min(100, occ).toFixed(1) + '%"></b></span>' + esc(pct1(occ)) + '</span>' +
                    (hc && o.occupazione_cmp !== null && o.occupazione_cmp !== undefined ? '<br><small class="pf-flat">prima ' + esc(pct1(o.occupazione_cmp)) + '</small>' : '')) + '</td>' +
        '<td>' + esc(num(o.noshow)) + '</td>' +
      '</tr>';
      if (aperto) {
        var lista = (o.top_servizi || []).length
          ? (o.top_servizi || []).map(function (s) {
              return '<div><span>' + esc(s.nome) + ' <span class="pf-flat">× ' + esc(num(s.quantita)) + '</span></span><strong>' + esc(euro(s.incasso)) + '</strong></div>';
            }).join('')
          : '<div><span class="pf-flat">Nessuna voce di cassa nel periodo.</span></div>';
        riga += '<tr class="pf-detail"><td colspan="' + ncol + '">' +
          '<div class="pf-card-sub" style="padding-left:18px;">Servizi con più incasso' +
            (o.pagato_con_carta ? ' · in più ' + esc(euro(o.pagato_con_carta)) + ' di sedute pagate con carta prepagata' : '') +
            (o.ore_turno ? ' · ' + esc(num(o.ore_turno)) + ' h di turno' : '') + '</div>' +
          '<div class="pf-detail-list">' + lista + '</div></td></tr>';
      }
      return riga;
    }).join('');

    var box = p.querySelector('#perfOpTab');
    box.innerHTML = ord.length
      ? '<div class="pf-table-wrap"><table class="pf-table"><thead>' + intestazione(campi, S.ops) + '</thead><tbody>' + corpo + '</tbody></table></div>'
      : '<div class="pf-note">Nessun operatore con dati nel periodo.</div>';

    agganciaOrdinamento(box, S.ops, function () { tabellaOperatori(p); });
    box.querySelectorAll('[data-apri]').forEach(function (b) {
      b.addEventListener('click', function () {
        var k = b.getAttribute('data-apri');
        S.ops.aperti[k] = !S.ops.aperti[k];
        tabellaOperatori(p);
        var nb = p.querySelector('[data-apri="' + k + '"]');
        if (nb) nb.focus();
      });
    });
    agganciaTooltip(p);

    if (S.ops.evidenzia !== null) {
      var tr = box.querySelector('tr.pf-evidenzia');
      if (tr) setTimeout(function () { try { tr.scrollIntoView({ block: 'center', behavior: 'smooth' }); } catch (_) {} }, 60);
    }
  }

  // ── Apertura ──────────────────────────────────────────────────────────
  // opts: { tab: 'negozio'|'servizi'|'operatori', cerca: 'nome servizio', operatore: id }
  function apri(opts) {
    if (!window.CD_IS_PRIVILEGED) return;
    if (!window.bootstrap || !bootstrap.Modal) return;
    opts = opts || {};
    var primaVolta = !M;
    if (primaVolta) leggiPref();
    costruisci();
    if (opts.tab) S.tab = opts.tab;
    if (typeof opts.cerca === 'string') { S.serv.q = opts.cerca; S.serv.cat = 'tutte'; S.serv.tutti = false; S.tab = 'servizi'; }
    S.ops.evidenzia = null;
    if (opts.operatore !== undefined && opts.operatore !== null) {
      S.ops.evidenzia = opts.operatore; S.ops.aperti = {}; S.ops.aperti[String(opts.operatore)] = true;
      S.ops.tipo = 'tutti'; S.tab = 'operatori';
    }
    mostraScheda(S.tab);
    bootstrap.Modal.getOrCreateInstance(M.modal).show();
    caricaChart().catch(function () {});
    carica();
  }

  window.cdApriPerformance = apri;
})();
