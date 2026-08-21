/* ===========================================================================
   TOSCA — MODALITA' SCURA AD ALTO CONTRASTO: parte a runtime
   ---------------------------------------------------------------------------
   Il foglio tosca-dark-a11y.css copre tutto cio' che nasce dal CSS. Restano
   fuori i colori dei blocchi appuntamento, che l'agenda scrive INLINE
   (block.style.backgroundColor = data-colore del cliente): un foglio di
   stile non puo' saperli in anticipo e non puo' nemmeno appiattirli tutti a
   una tinta sola, perche' il colore identifica il cliente nella giornata.

   Qui si fa l'unica cosa corretta: si tiene la TINTA e si abbassa la
   luminosita' fino a garantire il rapporto di contrasto 7:1 (WCAG 2.2
   livello AAA, criterio 1.4.6) fra il fondo del blocco e il testo chiaro.
   La ricerca e' binaria e cerca il valore PIU' CHIARO che rispetta il
   vincolo: cosi' i blocchi restano distinguibili fra loro invece di
   diventare tutti quasi neri.

   Il dato sul database non viene toccato: si trasforma solo la resa. Se la
   modalita' viene spenta, i colori tornano quelli di sempre. Unica
   eccezione voluta: quando in questa modalita' si SCEGLIE un colore dal
   selettore, il colore viene riportato entro il limite prima del
   salvataggio (cosi' non si possono piu' impostare blocchi troppo chiari).
   =========================================================================== */

(function () {
  'use strict';

  var CHIAVE = 'sun_dark_a11y';
  var TESTO = '#F2F5F7';          // stesso testo del foglio CSS
  /* Due soglie, non una, e la differenza conta:
     - ACCETTA (7.0) e' il requisito vero, quello di WCAG 1.4.6 AAA: un
       colore che gia' lo rispetta viene lasciato esattamente com'e';
     - PRODUCI (7.25) e' il bersaglio di quando il colore va scurito, con un
       margine perche' i canali RGB sono interi e l'arrotondamento finale
       puo' far scendere un 7.00 calcolato a 6,97 reale.
     Se le due soglie fossero uguali, un colore appena prodotto non
     supererebbe il proprio controllo alla passata successiva e verrebbe
     scurito ancora, un po' a ogni giro: con l'agenda che ridisegna i blocchi
     in continuazione, i blocchi sarebbero diventati neri da soli. */
  var CONTRASTO_ACCETTA = 7.0;
  var CONTRASTO_PRODUCI = 7.25;
  var L_MINIMA = 0.10;            // in HSL: sotto si perde la tinta
  var SATURAZIONE_MASSIMA = 0.72; // tinte troppo acide vibrano sul nero

  /* ------------------------------------------------------------------ colore */

  function hexToRgb(valore) {
    if (!valore) return null;
    var v = String(valore).trim();

    var m = v.match(/^rgba?\(([^)]+)\)$/i);
    if (m) {
      var p = m[1].split(',').map(function (x) { return parseFloat(x); });
      if (p.length < 3 || p.some(isNaN)) return null;
      return { r: p[0], g: p[1], b: p[2] };
    }

    v = v.replace('#', '');
    if (v.length === 3) v = v.split('').map(function (c) { return c + c; }).join('');
    if (!/^[0-9a-f]{6}$/i.test(v)) return null;
    return {
      r: parseInt(v.substring(0, 2), 16),
      g: parseInt(v.substring(2, 4), 16),
      b: parseInt(v.substring(4, 6), 16)
    };
  }

  function rgbToHex(r, g, b) {
    var due = function (n) {
      var s = Math.round(Math.max(0, Math.min(255, n))).toString(16);
      return s.length === 1 ? '0' + s : s;
    };
    return '#' + due(r) + due(g) + due(b);
  }

  /* Luminanza relativa secondo WCAG 2.x (formula ufficiale, non una media
     dei canali: il verde pesa molto piu' del blu). */
  function luminanza(rgb) {
    var canali = [rgb.r, rgb.g, rgb.b].map(function (v) {
      v = v / 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * canali[0] + 0.7152 * canali[1] + 0.0722 * canali[2];
  }

  function contrasto(rgb1, rgb2) {
    var l1 = luminanza(rgb1);
    var l2 = luminanza(rgb2);
    var chiaro = Math.max(l1, l2);
    var scuro = Math.min(l1, l2);
    return (chiaro + 0.05) / (scuro + 0.05);
  }

  function rgbToHsl(rgb) {
    var r = rgb.r / 255, g = rgb.g / 255, b = rgb.b / 255;
    var max = Math.max(r, g, b), min = Math.min(r, g, b);
    var h = 0, s = 0, l = (max + min) / 2;
    if (max !== min) {
      var d = max - min;
      s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
      if (max === r) h = ((g - b) / d + (g < b ? 6 : 0));
      else if (max === g) h = (b - r) / d + 2;
      else h = (r - g) / d + 4;
      h /= 6;
    }
    return { h: h, s: s, l: l };
  }

  function hslToRgb(hsl) {
    var h = hsl.h, s = hsl.s, l = hsl.l;
    if (s === 0) { var v = l * 255; return { r: v, g: v, b: v }; }
    var f = function (p, q, t) {
      if (t < 0) t += 1;
      if (t > 1) t -= 1;
      if (t < 1 / 6) return p + (q - p) * 6 * t;
      if (t < 1 / 2) return q;
      if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
      return p;
    };
    var q = l < 0.5 ? l * (1 + s) : l + s - l * s;
    var p = 2 * l - q;
    return { r: f(p, q, h + 1 / 3) * 255, g: f(p, q, h) * 255, b: f(p, q, h - 1 / 3) * 255 };
  }

  var RGB_TESTO = hexToRgb(TESTO);

  /* Colore del blocco per la modalita' scura: stessa tinta, luminosita' la
     piu' alta possibile che tenga il contrasto col testo >= 7:1. */
  function scurisciPerContrasto(valore) {
    var rgb = hexToRgb(valore);
    if (!rgb) return null;

    // Il colore com'e' davvero: va misurato questo, non una sua versione
    // gia' desaturata, altrimenti si dichiara "a posto" un colore che a
    // posto non e'.
    if (contrasto(rgb, RGB_TESTO) >= CONTRASTO_ACCETTA) {
      return rgbToHex(rgb.r, rgb.g, rgb.b);
    }

    var hsl = rgbToHsl(rgb);
    hsl.s = Math.min(hsl.s, SATURAZIONE_MASSIMA);

    // La verifica avviene sempre sul colore ARROTONDATO a interi, cioe' su
    // quello che finira' davvero nel DOM.
    var reso = function (l) {
      var c = hslToRgb({ h: hsl.h, s: hsl.s, l: l });
      return hexToRgb(rgbToHex(c.r, c.g, c.b));
    };
    var vaBene = function (l, soglia) {
      return contrasto(reso(l), RGB_TESTO) >= soglia;
    };

    if (!vaBene(L_MINIMA, CONTRASTO_PRODUCI)) {
      // Non capita con questi valori, ma se capitasse meglio un fondo neutro
      // sicuro che un blocco illeggibile.
      return '#1E2226';
    }

    // La luminosita' PIU' ALTA che rispetta il bersaglio: cosi' i blocchi
    // restano distinguibili l'uno dall'altro invece di finire tutti neri.
    var basso = L_MINIMA, alto = hsl.l;
    for (var i = 0; i < 24; i++) {
      var mezzo = (basso + alto) / 2;
      if (vaBene(mezzo, CONTRASTO_PRODUCI)) basso = mezzo; else alto = mezzo;
    }

    // Ultima rete: se l'arrotondamento ha eroso il margine, si scende ancora
    // di un soffio finche' il requisito vero (7:1) e' rispettato.
    var giri = 0;
    while (!vaBene(basso, CONTRASTO_ACCETTA) && basso > L_MINIMA && giri < 60) {
      basso -= 0.004;
      giri++;
    }

    var finale = hslToRgb({ h: hsl.h, s: hsl.s, l: basso });
    return rgbToHex(finale.r, finale.g, finale.b);
  }

  /* ------------------------------------------------------------------ stato */

  function attiva() {
    try { return localStorage.getItem(CHIAVE) === '1'; } catch (e) { return false; }
  }

  function eNero(valore) {
    var rgb = hexToRgb(valore);
    return !!rgb && rgb.r < 12 && rgb.g < 12 && rgb.b < 12;
  }

  var inCorso = false;   // guardia: le nostre scritture non devono richiamarci

  function sistemaBlocco(blocco) {
    // Blocco in "taglia": l'agenda lo porta a nero di proposito e lo
    // ripristina da sola. Non e' un colore cliente, non va toccato.
    if (eNero(blocco.style.backgroundColor)) return;

    var sorgente = blocco.getAttribute('data-colore') || blocco.style.backgroundColor;
    if (!sorgente) return;

    var scuro = scurisciPerContrasto(sorgente);
    if (!scuro) return;

    if (blocco.getAttribute('data-a11y-da') !== String(sorgente) ||
        blocco.style.backgroundColor !== scuro) {
      blocco.setAttribute('data-a11y-da', String(sorgente));
      blocco.style.setProperty('background-color', scuro, 'important');
    }

    // Il testo: l'agenda a volte lo scrive inline con !important sui figli, e
    // una dichiarazione inline important batte qualsiasi foglio di stile.
    // Quindi va riscritto qui, non nel CSS.
    blocco.style.setProperty('color', TESTO, 'important');
    var figli = blocco.querySelectorAll('.appointment-content, .appointment-content p, .appointment-content a, .client-name, .client-info-link, .off-title');
    for (var i = 0; i < figli.length; i++) {
      if (figli[i].style && figli[i].style.color) {
        figli[i].style.setProperty('color', TESTO, 'important');
      }
    }
  }

  function sistemaTutti() {
    if (inCorso) return;
    inCorso = true;
    try {
      var blocchi = document.querySelectorAll('.appointment-block');
      for (var i = 0; i < blocchi.length; i++) sistemaBlocco(blocchi[i]);
    } finally {
      inCorso = false;
    }
  }

  /* L'agenda ricrea e ricolora i blocchi in continuazione (refresh, drag,
     resize, cambio stato, cambio colore): un giro solo all'avvio non basta.
     L'osservatore ripassa a ogni modifica, accorpando le raffiche in un
     unico giro con requestAnimationFrame. */
  var programmato = false;
  function programmaGiro() {
    if (programmato || inCorso) return;
    programmato = true;
    requestAnimationFrame(function () {
      programmato = false;
      sistemaTutti();
    });
  }

  function osserva() {
    var radice = document.querySelector('.calendar-table') || document.body;
    if (!radice) return;
    new MutationObserver(function (mutazioni) {
      for (var i = 0; i < mutazioni.length; i++) {
        var m = mutazioni[i];
        if (m.type === 'childList' && m.addedNodes.length) { programmaGiro(); return; }
        if (m.type === 'attributes') {
          var t = m.target;
          if (t && t.classList && t.classList.contains('appointment-block')) { programmaGiro(); return; }
        }
      }
    }).observe(radice, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['style', 'data-colore', 'class', 'data-status']
    });
  }

  /* ------------------------------------------- fondi chiari rimasti in giro */

  /* Alcune superfici non si possono correggere dal foglio di stile: gli
     header dei modali, per esempio, sono dipinti da regole con selettore a
     ID e !important (#CreateAppointmentModal .modal-header { background:
     linear-gradient(...) !important }). Una regola per classe, per quanto
     specifica, non le batte: gli identificatori pesano di piu'. E sono
     GRADIENTI, quindi non basta nemmeno impostare un background-color.
     L'unica dichiarazione che vince e' quella inline con important, ed e'
     quello che si fa qui.

     Il criterio non e' un elenco di nomi da inseguire (domani ne nascono
     altri) ma la condizione che rende il testo illeggibile: fondo CHIARO
     con sopra testo CHIARO. Un fondo chiaro con testo scuro - i pulsanti
     giallo/azzurro - resta com'e', perche' si legge benissimo. */

  function chiarezza(colore) {
    var m = String(colore).match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    var p = m[1].split(',').map(Number);
    if (p.length > 3 && p[3] < 0.5) return null;      // troppo trasparente
    return (0.299 * p[0] + 0.587 * p[1] + 0.114 * p[2]) / 255;
  }

  function fondoChiaro(stile) {
    var valori = [];
    var c = chiarezza(stile.backgroundColor);
    if (c !== null) valori.push(c);
    if (stile.backgroundImage && stile.backgroundImage !== 'none') {
      var colori = stile.backgroundImage.match(/rgba?\([^)]+\)/g) || [];
      for (var i = 0; i < colori.length; i++) {
        var v = chiarezza(colori[i]);
        if (v !== null) valori.push(v);
      }
    }
    return valori.length ? Math.max.apply(null, valori) : -1;
  }

  function spegniFondiChiari(radice) {
    if (!radice || !radice.querySelectorAll) return;
    var elementi = radice.querySelectorAll('*');
    for (var i = 0; i < elementi.length; i++) {
      var el = elementi[i];
      if (el.closest('.appointment-block')) continue;   // li fa sistemaBlocco
      var stile = window.getComputedStyle(el);
      if (stile.display === 'none' || stile.visibility === 'hidden') continue;
      if (fondoChiaro(stile) < 0.62) continue;
      var testo = chiarezza(stile.color);
      if (testo === null || testo <= 0.6) continue;     // fondo chiaro + testo scuro: si legge
      el.style.setProperty('background-color', '#23282D', 'important');
      el.style.setProperty('background-image', 'none', 'important');
      el.style.setProperty('color', TESTO, 'important');
      el.setAttribute('data-a11y-fondo', 'corretto');
    }
  }

  /* --------------------------------------------- selettore colore del blocco */

  /* "Colori troppo chiari non impostabili": si interviene in fase di CATTURA,
     prima del gestore dell'agenda, riscrivendo il valore dell'input. Il
     codice che salva legge quindi gia' il colore corretto, e da li' in poi
     tutto (font automatico bianco, salvataggio sul database, blocchi
     aggiornati) segue senza altre modifiche. */
  function limitaSelettoreColore() {
    document.addEventListener('click', function (e) {
      if (!attiva()) return;
      var bottone = e.target && e.target.closest && e.target.closest('#saveColorBtn');
      if (!bottone) return;
      var input = document.getElementById('colorPickerInput');
      if (!input || !input.value) return;
      var corretto = scurisciPerContrasto(input.value);
      if (corretto && corretto.toLowerCase() !== String(input.value).toLowerCase()) {
        input.value = corretto;
      }
    }, true);

    // Avviso dentro il modal: la regola va spiegata, non subita.
    document.addEventListener('shown.bs.modal', function (e) {
      if (!attiva()) return;
      var modale = e.target;
      if (!modale || modale.id !== 'ColorPickerModal') return;
      var corpo = modale.querySelector('.modal-body') || modale;
      if (corpo.querySelector('.a11y-nota-colore')) return;
      var nota = document.createElement('p');
      nota.className = 'a11y-nota-colore';
      nota.style.cssText = 'margin-top:10px;font-size:0.9rem;font-weight:600;color:#FFC96B;';
      nota.textContent = 'Modalità scura ad alto contrasto: i colori troppo chiari vengono ' +
                         'automaticamente scuriti per restare leggibili (contrasto minimo 7:1).';
      corpo.appendChild(nota);
    });
  }

  /* ------------------------------------------------------------------ avvio */

  function avvia() {
    if (!attiva()) return;
    document.documentElement.classList.add('tosca-dark');
    sistemaTutti();
    osserva();
    limitaSelettoreColore();

    // Rete di sicurezza sui fondi chiari: una passata sulla pagina e una a
    // ogni modale che si apre (i modali nascono nascosti, quindi vanno
    // guardati quando sono davvero a schermo).
    spegniFondiChiari(document.body);
    document.addEventListener('shown.bs.modal', function (e) {
      if (e && e.target) spegniFondiChiari(e.target);
    });
    // Alcune parti dell'agenda arrivano dopo le fetch iniziali.
    setTimeout(sistemaTutti, 800);
    setTimeout(sistemaTutti, 2500);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', avvia);
  } else {
    avvia();
  }

  // Esposto per i test e per un eventuale riuso in altre pagine.
  window.ToscaDarkA11y = {
    attiva: attiva,
    scurisciPerContrasto: scurisciPerContrasto,
    contrasto: function (a, b) { return contrasto(hexToRgb(a), hexToRgb(b)); },
    sistemaTutti: sistemaTutti,
    spegniFondiChiari: spegniFondiChiari
  };
})();
