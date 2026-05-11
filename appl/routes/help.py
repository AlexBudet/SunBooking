

"""
Contenuti Help per Tosca.
Modifica questo file per aggiornare i testi di aiuto nell'app.
"""
HELP_IMAGES = {
    "navigator_appuntamenti": ["NavigatorAppuntamenti_Chiuso.png"],
    "campo_ricerca_cliente": ["NavigatorAppuntamenti_CercaCliente.png"]
}
HELP_TOPICS = {
    
    # ========== CALENDARIO ==========
"calendar_create_appointment": {
    "title": "✏️ Crea un Appuntamento in Agenda",
    "content": """Hai due modi per creare un appuntamento in Agenda: il <span class="help-strong-dark">click su cella vuota</span> per la creazione rapida, oppure il <span class="help-strong-dark">Navigator Appuntamenti</span> per flussi più articolati.

<span class="help-strong-dark help-subtitle-pill">▸ Click su cella vuota (metodo rapido)</span>
[[VIDEO|1]]
1️⃣ fai <span class="help-strong-dark">click su una cella vuota</span>
2️⃣ si apre il modal <span class="help-strong-dark">Crea Appuntamento</span>
3️⃣ nel campo cliente scrivi almeno 3 caratteri e seleziona il nominativo (oppure crea un nuovo cliente al volo con il tasto <span class="help-calendar-btn plus">+</span>)
4️⃣ nel campo servizio scrivi almeno 3 caratteri e scegli il trattamento
5️⃣ per ogni servizio che cliccherai dai risultati della ricerca, saranno creati dei <span class="help-strong-dark">mini-blocchi</span> visibili nella parte in basso del Navigator.
6️⃣ conferma la creazione

Il sistema precompila già operatore, data e orario partendo dalla cella cliccata. Puoi anche creare un <span class="help-strong-dark">[[BLOCCO OFF|calendar_off_block]]</span> se non stai prenotando un cliente.

<span class="help-strong-dark help-subtitle-pill">▸ Navigator Appuntamenti (metodo flessibile)</span>
[[VIDEO|2]]
Il <span class="help-strong-dark">Navigator Appuntamenti</span> è il riquadro in alto a destra nell'Agenda. Conviene usarlo quando devi preparare uno o più servizi prima di decidere dove posizionarli, oppure lavorare con più servizi, spostare o copiare blocchi esistenti.

Flusso:
1. cerca il cliente
2. seleziona uno o più servizi
3. controlla i mini-blocchi nel riquadro basso
4. muovi il mouse sulle celle vuote del calendario
5. clicca per posizionare

Ogni mini-blocco rappresenta un servizio pronto da inserire. Se ne prepari più di uno, l'<span class="help-strong-dark">ombra di posizionamento</span> ti mostra dove finiranno in agenda. Per posizionare solo un servizio specifico, seleziona il singolo mini-blocco prima del click sulla griglia.

Se è attivo il <span class="help-strong-dark">modulo opzionale WhatsApp</span>, dopo la conferma può comparire la richiesta per inviare un memo automatico al cliente.

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Se devi inserire una persona nuova senza uscire dal flusso Agenda, vai direttamente a <span class="help-strong-dark">[[AGGIUNGI NUOVO CLIENTE|client_search]]</span>.</span>
</div>""",
},

"calendar_drag": {
    "title": "🖱️ Spostare un appuntamento? Facilissimo!",
    "content": """[[VIDEO|3]]

Funziona come sul telefono: tocca, tieni premuto e trascina!

📍 **Per spostare:** clicca sulla parte alta dell'appuntamento, sulla **BARRA DI TRASCINAMENTO** (la riconosci perché passandoci sopra col mouse il puntatore diventa una manina) e trascinalo dove vuoi

⏱️ **Per allungare/accorciare:** afferra il bordo in basso, la **BARRA DELLA DURATA** e tira su o giù di un quarto d'ora

👥 **Cambiare operatore:** trascina semplicemente l'appuntamento in un'altra colonna per assegnarlo ad un altro operatore

È tutto automatico, non devi salvare nulla! Se è attivo il <span class="help-strong-dark">modulo opzionale WhatsApp</span>, in alcuni flussi potrà comparire la conferma di invio memo al cliente ✨""",
},

    "calendar_status": {
        "title": "🎨 I colori dei blocchi appuntamento - cosa significano",
        "content": """Ogni colore ti dice subito lo stato del blocco appuntamento:

🟢🟤🔴🟡 **Colorato** → L'appuntamento è programmato (il colore si può modificare)
⚪ **Grigio chiaro, scritta in grigio** → Tutto fatto e pagato ✓
🔘  **Grigio a puntini, scritta in nero** → Blocco OFF, non prenotabile!
⚫ **Nero a puntini, scritta in bianco** → Il cliente non si è presentato: No-Show! 😢
🔵 **Blu** → colore tipico degli appuntamenti provenienti dal <span class="help-strong-dark">modulo opzionale Booking via Web</span>

**Per cambiare stato ad un blocco appuntamento prosegui nella lettura per vedere le funzioni nascoste di ogni blocco...

<div class="help-approfondimento-box">
<span class="help-approfondimento-label">Approfondimenti — leggere il calendario</span><br>
<span class="help-approfondimento-text">
<strong>Linea rossa orizzontale</strong> → è l'indicatore dell'ora corrente, si sposta in tempo reale durante la giornata.<br>
<strong>Ogni casella equivale a 15 minuti</strong>: quattro caselle formano un'ora. L'altezza di un blocco corrisponde alla durata del servizio.<br>
<strong>Una colonna per ogni operatore</strong>: il nome è visibile nell'intestazione in cima alla colonna.<br>
<strong>Cella vuota</strong>: un click apre direttamente la finestra di creazione appuntamento, precompilata con operatore e orario.
</span>
</div>""",
    },

"calendar_block_buttons": {
    "title": "Blocco Appuntamento - I PULSANTI",
    "content": """[[VIDEO|9]]

I pulsanti **popup** compaiono passando il puntatore sul blocco; i pulsanti **interni** sono sempre visibili dentro il blocco stesso.

<span class="help-strong-dark help-subtitle-pill">▸ Pulsanti popup — compaiono al passaggio del puntatore</span>
<span style="display:inline-flex;align-items:center;justify-content:center;width:26px;height:21px;background:linear-gradient(to top,#5c5c5c,#2c2c2c);color:#fff;border-radius:6px;box-shadow:0 0 0 0.8px hsla(0,0%,96%,0.76);font-size:13px;vertical-align:middle;pointer-events:none;margin-right:5px;"><i class="bi bi-scissors"></i></span> **TOGLI E SPOSTA** — Taglia il blocco e lo deposita nel Navigator come mini-blocco. Il posto originale resta segnato da un'ombra; riposiziona il blocco dove vuoi cliccando su una cella libera.
<span style="display:inline-flex;align-items:center;justify-content:center;width:26px;height:21px;background:linear-gradient(to top,#5c5c5c,#2c2c2c);color:#fff;border-radius:6px;box-shadow:0 0 0 0.8px hsla(0,0%,96%,0.76);font-size:13px;vertical-align:middle;pointer-events:none;margin-right:5px;"><i class="bi bi-files"></i></span> **COPIA BLOCCO** — Copia il blocco nel Navigator lasciando l'originale al suo posto. Utile per duplicare rapidamente lo stesso appuntamento su altre date o orari.
<span style="display:inline-flex;align-items:center;justify-content:center;width:26px;height:21px;background:linear-gradient(to top,#5c5c5c,#2c2c2c);color:#fff;border-radius:6px;box-shadow:0 0 0 0.8px hsla(0,0%,96%,0.76);font-size:13px;vertical-align:middle;pointer-events:none;margin-right:5px;"><i class="bi bi-palette"></i></span> **IMPOSTA COLORE** — Apre il selettore colore del blocco. Il colore del testo si adatta automaticamente per restare leggibile su qualsiasi sfondo.
<span style="display:inline-flex;align-items:center;justify-content:center;width:26px;height:21px;background:linear-gradient(to top,#5c5c5c,#2c2c2c);color:#fff;border-radius:6px;box-shadow:0 0 0 0.8px hsla(0,0%,96%,0.76);font-size:13px;vertical-align:middle;pointer-events:none;margin-right:5px;"><i class="bi bi-currency-euro"></i></span> **PORTA IN CASSA** — Porta in Cassa il servizio del blocco (e gli eventuali blocchi contigui dello stesso cliente) per il pagamento.
<span style="display:inline-flex;align-items:center;justify-content:center;width:26px;height:21px;background:linear-gradient(to top,#5c5c5c,#2c2c2c);color:#fff;border-radius:6px;box-shadow:0 0 0 0.8px hsla(0,0%,96%,0.76);font-size:13px;vertical-align:middle;pointer-events:none;margin-right:5px;"><i class="bi bi-plus"></i></span> **AGGIUNGI SERVIZI** — Apre il Navigator già precompilato con il cliente del blocco, per aggiungere altri servizi senza rifare la ricerca.
<span style="display:inline-flex;align-items:center;justify-content:center;width:26px;height:21px;background:linear-gradient(to top,#5c5c5c,#2c2c2c);color:#fff;border-radius:6px;box-shadow:0 0 0 0.8px hsla(0,0%,96%,0.76);font-size:13px;vertical-align:middle;pointer-events:none;margin-right:5px;"><i class="bi bi-pencil-square"></i></span> **NOTA APPUNTAMENTO** — Aggiunge o modifica la nota del singolo appuntamento, distinta dalle note permanenti dell'anagrafica cliente.
<span style="display:inline-flex;align-items:center;justify-content:center;width:26px;height:21px;background:linear-gradient(to top,#5c5c5c,#2c2c2c);color:#fff;border-radius:6px;box-shadow:0 0 0 0.8px hsla(0,0%,96%,0.76);font-size:13px;vertical-align:middle;pointer-events:none;margin-right:5px;"><i class="bi bi-whatsapp"></i></span> **INVIA WHATSAPP** — Solo con il <span class="help-strong-dark">modulo opzionale WhatsApp</span>: invia un promemoria diretto al cliente.

<span class="help-strong-dark help-subtitle-pill">▸ Pulsanti interni al blocco</span>
<span style="display:inline-flex;align-items:center;justify-content:center;width:26px;height:21px;background:linear-gradient(to top,#5c5c5c,#2c2c2c);color:#fff;border-radius:6px;box-shadow:0 0 0 0.8px hsla(0,0%,96%,0.76);font-size:13px;vertical-align:middle;pointer-events:none;margin-right:5px;"><i class="bi bi-trash"></i></span> **CESTINO** (in alto a sinistra) — Apre il menu azioni: elimina il singolo blocco, elimina il gruppo contiguo se presente, oppure imposta No-Show.
<span style="display:inline-block;width:16px;height:16px;border-radius:50%;border:1px solid rgba(0,0,0,0.4);background:rgba(0,0,0,0.08);vertical-align:middle;pointer-events:none;margin-right:5px;"></span> **CLIENTE IN ISTITUTO** (pallino in alto a destra) — Clicca per mostrare che il cliente è arrivato in istituto, il cerchiò si riempirà di giallo lampeggiante. Dopo l'ora corrente, se ancora in istituto, diventerò rosso lampeggiante ma non cambierà nulla, è solo un indicatore.
**NOME CLIENTE** (al centro del blocco) — Un click sul nome apre la finestra per riassegnare l'appuntamento (e gli altri della stessa data) a un altro cliente.""",
},

"calendar_block_click": {
    "title": "🖱️ Click dentro il blocco appuntamento",
    "content": """• 🗑️ **Cestino** (in alto a sinistra) → Apre una finestra con diverse opzioni:
   - **ELIMINA** il singolo blocco
   - Elimina tutto il gruppo di blocchi appuntamento per quel cliente in quella data (se più di uno)
   - Imposta **NO-SHOW** (se il cliente non si è presentato!)
   - **ANNULLA** se si vuole uscire senza fare modifiche

[[VIDEO|7]]

•  ◯ **Cliente in Istituto** (in alto a destra) → Indica che il cliente è arrivato ed è attualmente in istituto
• 👤 **Nome Cliente** (al centro) → Cliccando sul nome si apre la finestra per assegnare quell'appuntamento (e gli altri della stessa data) ad un altro cliente

[[VIDEO|8]]

🔔 **Spie lampeggianti**
• 🟡 **Spia gialla** → Il cliente è in istituto, tutto ok!
• 🔴 **Spia rossa** → Il cliente è in istituto ma siamo in ritardo rispetto all'orario previsto per la fine dell'appuntamento.
""",
},

    "funzioni_blocchi": {
        "title": "✂️ Maneggiare i blocchi appuntamenti: le funzioni 'Togli e Sposta', 'Copia Blocco' e 'Aggiungi Servizio'",
        "content": """Sopra ogni blocco appuntamento trovi tre pulsanti fondamentali per gestire gli appuntamenti in modo rapido ed efficiente!

<span class="help-strong-dark help-subtitle-pill">✂️ TAGLIA (Togli e Sposta)</span>
[[VIDEO|4]]
Cliccando su questo pulsante, i blocchi appuntamento **scompaiono** dal calendario (lasciando un'ombra al loro posto) e vengono trasformati in **mini-blocchi** visibili nel **Navigator Appuntamenti** in alto a destra.
Da lì puoi riposizionarli dove preferisci: basta muovere il mouse su una cella vuota del calendario e cliccare per confermare la nuova posizione.
Puoi tagliare anche più blocchi appuntamento e spostarli tutti con un click in agenda! Vedrai un'**ombra** sulle celle di calendario in prossimità del puntatore dove verranno creati i blocchi, e un'ombra sulle celle da cui sono stati tagliati i blocchi. Se annulli l'operazione (per es. con SVUOTA da Navigator Appuntamenti) i blocchi appuntamento torneranno al loro posto originario!

<span class="help-strong-dark help-subtitle-pill">📋 COPIA (Copia Blocco)</span>
Funziona in modo simile a "Taglia", ma **lascia i blocchi originali al loro posto**!
I blocchi vengono copiati come mini-blocchi nel Navigator Appuntamenti, pronti per essere posizionati su un'altra data.
**Esempio pratico:** un cliente vuole prenotare lo stesso trattamento una volta al mese per diversi mesi? Copia il blocco e posizionalo velocemente sulle date successive. Fatto in pochi secondi! 🚀

<span class="help-strong-dark help-subtitle-pill">➕ AGGIUNGI (Aggiungi Servizi)</span>
[[VIDEO|5]]
Cliccando su "Aggiungi", si apre il **Navigator Appuntamenti** già **pre-caricato con il nome del cliente** del blocco da cui hai cliccato.
In questo modo puoi aggiungere altri servizi allo stesso cliente per lo stesso appuntamento, senza doverlo cercare di nuovo.
Ideale quando il cliente decide di aggiungere un trattamento extra! 💆""",
    },

    "calendar_note": {
        "title": "📝 Tooltip e Note nel blocco appuntamento",
        "content": """[[VIDEO|6]]

In Tosca puoi visualizzare informazioni e aggiungere due tipi di note, tutte visibili nel tooltip informativo del blocco appuntamento!

<span class="help-strong-dark help-subtitle-pill">▸ TOOLTIP SUL NOME CLIENTE</span>
Passa il mouse sul nome del cliente e appare un **TOOLTIP CON INFORMAZIONI** con informazioni utili su quel blocco appuntamento:
• 🕰️ Data e ora di creazione (ed eventualmente di ultima modifica) di quel blocco appuntamento
• 👤 Nome e Cognome del cliente associato
• 📝 Note Cliente (se presenti)
• 📞 Numero di telefono
• 📅 Data e ora dell'appuntamento
• 💇 Servizio associato al blocco appuntamento
• 📝 Note Appuntamento (se presenti)

<span class="help-strong-dark help-subtitle-pill">▸ NOTE: CLIENTE E APPUNTAMENTO</span>
In Tosca puoi aggiungere due tipi di note, entrambe visibili nel tooltip informativo:

👤 **NOTE CLIENTE**
Sono note permanenti legate al cliente, utili per informazioni che valgono sempre (es: allergie, preferenze, richieste particolari).
• **Come aggiungerle:** vai in **Impostazioni → Clienti**, cerca il cliente e compila il campo "Note"
• **Dove si vedono:** nel tooltip che appare passando il mouse sul nome cliente nel blocco appuntamento, nella parte **superiore**

📅 **NOTE APPUNTAMENTO**
Sono note specifiche per quel singolo appuntamento (es: "porta il prodotto X", "arriva 10 min prima").
• **Come aggiungerle:** clicca sul pulsante **📝 Nota Appuntamento** che appare sopra il blocco al passaggio del mouse
• **Dove si vedono:** nel tooltip informativo, nella parte **inferiore**, sotto le note cliente

👁️ **VISUALIZZAZIONE NEL TOOLTIP**
Passando il mouse sul nome del cliente nel blocco appuntamento, il tooltip mostra:
1. In alto: **Note Cliente** (se presenti)
2. In basso: **Note Appuntamento** (se presenti)

⭐ **NOTE APPUNTAMENTO AUTOMATICHE**
Alcune note appuntamento vengono create automaticamente dal sistema:
• 🌐 **Prenotazioni da Booking Online:** compaiono solo con <span class="help-strong-dark">modulo opzionale Booking via Web</span> e mostrano informazioni sulla prenotazione web
• 🆕 **Nuovo Cliente:** quando un cliente prenota per la prima volta, appare la dicitura ****NUOVO CLIENTE**** per avvisarti che è alla sua prima visita!

Queste note speciali ti aiutano a riconoscere subito situazioni particolari! ✨""",
    },

    "calendar_paid_block": {
        "title": "✅ Blocchi \"PAGATO\" - appuntamenti completati",
        "content": """I blocchi **grigio chiaro** sono appuntamenti già **completati e pagati**. Hanno funzionalità ridotte rispetto ai blocchi normali, perché rappresentano lo storico del cliente!

🎨 **COME RICONOSCERLI**
• Sfondo **grigio chiaro**
• Testo in **grigio**
• Rappresentano appuntamenti già passati in cassa

🖱️ **FUNZIONI DISPONIBILI**
I blocchi pagati hanno meno pulsanti rispetto ai blocchi normali:

• 📋 **Copia Blocco** → L'unica funzione davvero utile! Permette di **ripetere lo stesso appuntamento** in un'altra data. Perfetto quando il cliente, dopo aver pagato, vuole già prenotare il prossimo trattamento identico.

• 🗑️ **Cestino** → Permette di eliminare il blocco, ma è **sconsigliato**! Eliminando i blocchi pagati perdi lo **storico degli appuntamenti** del cliente, che è prezioso per:
   - Vedere quante volte è venuto
   - Calcolare la spesa totale
   - Analizzare le sue abitudini

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Non eliminare mai i blocchi pagati! Lasciali sul calendario come archivio storico. Se danno fastidio visivamente, ricorda che cambiando data nel calendario non li vedrai più. Lo storico è oro per conoscere i tuoi clienti! 📊</span>
</div>""",
    },

    "calendar_off_block": {
        "title": "🚫 I Blocchi OFF - pause e impegni di servizio",
        "content": """[[VIDEO|10]]

I **Blocchi OFF** sono diversi dai blocchi appuntamento: servono per bloccare fasce orarie per attività di servizio come pause, riunioni o altri impegni. In pratica disattivano le celle del calendario, impostandole come "non prenotabili" per i clienti.

📌 **A COSA SERVONO**
Puoi usarli per segnare sul calendario:
• ☕ **UNA PAUSA** → Pausa caffè o pranzo
• 🗣️ **UN TURNO DI RECEPTION** → Turno alla reception
• 📚 **UN BRIEFING O UNA RIUNIONE** → Sessioni di formazione
• 🧹 **PULIZIE** → Tempo per riordino
...e qualsiasi altro impegno non legato a un cliente!

✏️ **COME CREARE UN BLOCCO OFF**
1️⃣ **Clicca su una cella vuota** del calendario (come per creare un appuntamento)
2️⃣ Nella finestra che si apre, clicca il pulsante **"Crea Blocco OFF"** in basso a destra
3️⃣ Inserisci il **titolo** che descrive l'attività (es: "PAUSA", "RIUNIONE")
4️⃣ Imposta la **durata** in quarti d'ora (15 min, 30 min, 45 min, ecc.)
5️⃣ Conferma e il blocco OFF appare sul calendario!

🖱️ **FUNZIONI INTERATTIVE DEL BLOCCO OFF**
Una volta creato, il blocco OFF ha questi controlli:

• 🗑️ **Cestino** (in alto a sinistra dentro il blocco) → Clicca per eliminare il blocco OFF

• 📋 **Copia Blocco OFF** (in alto a destra dentro il blocco) → Copia il blocco in memoria. Al prossimo click su una cella vuota del calendario, il blocco verrà duplicato in quella posizione. Utile per replicare la stessa pausa su più giorni o più volte durante la stessa giornata!

• 📝 **Titolo** (al centro del blocco) → Cliccando sul titolo si apre una finestra per modificarlo

💡 **Nota:** a differenza della copia dei blocchi appuntamento (che usa il Navigator), i blocchi OFF copiati rimangono in memoria e vengono posizionati direttamente al click successivo su una cella libera.""",
    },

    # ========== CASSA ==========
    "cassa_crea_scontrino": {
        "title": "🧾 Creare uno scontrino",
        "content": """[[VIDEO|13]]

Creare uno scontrino è semplicissimo!

1️⃣ Vai nella sezione **Cassa**
2️⃣ Nel campo di ricerca digita le prime lettere dei Servizi o Prodotti da scontrinare, oppure cambia visuale pulsanti con i tab in alto ("Frequenti", "Ultimi", ecc.), poi clicca sui servizi da portare nel **CARRELLO** in basso a sinistra
3️⃣ Seleziona l'operatore o il cliente (opzionale)
4️⃣ Modifica il metodo di pagamento per una o per tutte le voci (con i tasti in fondo: "cash", "pos", "bank")
5️⃣ Conferma cliccando su **Avanti** oppure annulla
6️⃣ Infine stampa lo scontrino cliccando su **Stampa**

Lo scontrino viene creato e salvato automaticamente! 🎉""",
    },
    
    "cassa_pagamento": {
        "title": "💰 Registrare un pagamento",
        "content": """Registra i pagamenti in pochi click!

**Metodi di pagamento disponibili:**
• 💵 Contanti (Cash)
• 💳 Bancomat/Carta di credito/debito (POS)
• 📱 Bonifico/altri digitali (Bank)

Se il cliente ha una prepagata attiva, puoi scalare il costo direttamente da lì!
• 💳 Carta prepagata cliente (Prepagata)


**Come fare:**
1️⃣ A lato della voce da pagare, clicca sulla casella del metodo di pagamento (di default è "POS")
2️⃣ Scegli il metodo di pagamento desiderato
3️⃣ Oppure, se vuoi modificare il metodo per tutte le voci, usa i tasti in fondo: "cash", "pos", "bank"
4️⃣ Procedi cliccando su "Avanti"!

Puoi anche dividere il pagamento su più metodi! 💡""",
    },
    
    "cassa_blocchi_appuntamento": {
        "title": "📅 Collegare cassa e appuntamenti",
        "content": """[[VIDEO|14]]

La cassa si collega automaticamente agli appuntamenti!

**Come funziona:**
• Quando vuoi pagare un appuntamento, clicca il tasto <span class="help-strong-dark">€ Porta in Cassa</span> che appare sopra al blocco
• I servizi dell'appuntamento vengono caricati automaticamente nella bozza scontrino
• Il cliente e l'operatore sono già selezionati

**Flusso completo:**
1️⃣ Passa il mouse sul blocco appuntamento in Agenda
2️⃣ Clicca <span class="help-strong-dark">€ Porta in Cassa</span>
3️⃣ Verifica i servizi e imposta il metodo di pagamento
4️⃣ Clicca <span class="help-strong-dark">Conferma</span> e poi <span class="help-strong-dark">Stampa</span>

Tutto collegato, zero errori! ✨""",
    },
    
    # ========== CLIENTI ==========
    "client_search": {
        "title": "🔍 Ricerca cliente in Agenda + Nuovo cliente + Info rapida",
        "content": """[[VIDEO|17]]

Questa è la guida unica per tutto il flusso cliente in Agenda: ricerca, inserimento rapido nuovo cliente e finestra info.

<span class="help-strong-dark help-subtitle-pill">▸ RICERCA CLIENTE IN AGENDA</span>
Nei campi di <span>ricerca cliente</span>, puoi cercare per:
• Nome (es: "Maria")
• Cognome (es: "Rossi")
• Telefono (es: "333")

Bastano 3 lettere (o i primi 3 numeri del cellulare) e i risultati corrispondenti appaiono subito sotto.

<span class="help-strong-dark help-subtitle-pill">▸ AGGIUNGI NUOVO CLIENTE</span>
Il modo più veloce per aggiungere un nuovo cliente è usare il tasto <span class="help-calendar-btn plus">+</span> accanto al campo di ricerca cliente nella finestra di creazione appuntamento o nel Navigator Appuntamenti in Agenda.

Da lì, basta scrivere **NOME, COGNOME e CELLULARE**: il cliente viene subito aggiunto alla rubrica.

Se il cellulare è già presente per un altro cliente, compare un messaggio di avviso (non è ammesso lo stesso numero di cellulare per più clienti).

Il **SESSO** viene capito automaticamente dal nome (ma puoi correggerlo nelle impostazioni).

Verifica sempre il <span class="help-strong-dark">cellulare</span>: è un dato fondamentale per contatto, recall e, se attivo il modulo opzionale, anche per l'invio WhatsApp.

<span class="help-strong-dark help-subtitle-pill">▸ FINESTRA INFO CLIENTE</span>
Al click sull'icona <span class="help-calendar-btn info">i</span> a fianco dei risultati della ricerca cliente si apre una finestra dove puoi visualizzare e modificare rapidamente i dati del cliente.

Puoi modificare **NOME, COGNOME, CELLULARE ed EMAIL** nei campi in alto, e aggiungere o modificare la **NOTA SALVATA** per quel cliente.

Più sotto trovi:
• **Prossimi appuntamenti prenotati** per quel cliente
• **Storico appuntamenti** per quel cliente

Cliccando sulle righe della tabella, la vista Agenda si sposta direttamente nella giornata selezionata.

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Cerca il cliente con poche lettere e selezionalo dalla lista, oppure usa <span class="help-calendar-btn plus">+</span> per aggiungerlo in rubrica se non c'è, infine clicca l'icona <span class="help-calendar-btn info">i</span> per info, storico e appuntamenti: fai tutto da Agenda senza saltare tra più schermate.</span>
</div>""",
    },
    
"client_new": {
    "title": "👤 Aggiungere un nuovo cliente",
    "content": """Il modo più veloce per aggiungere un nuovo cliente è usare il **TASTO +** accanto al campo di ricerca cliente nella finestra di creazione appuntamento o nel Navigator Appuntamenti in Agenda!

Da lì, basta scrivere **NOME, COGNOME e CELLULARE**: il cliente viene subito aggiunto alla tua rubrica clienti!

Se il cellulare è già presente per un altro cliente, vieni avvisato con un messaggio (non è ammesso lo stesso numero di cellulare per più clienti!).

Il **SESSO** viene capito automaticamente dal nome (ma puoi correggerlo nelle impostazioni)

Verifica sempre il <span class="help-strong-dark">cellulare</span>: è un dato fondamentale per contatto, recall e, se attivo il modulo opzionale, anche per l'invio WhatsApp.

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Se vuoi vedere il flusso completo da Agenda (click cella vuota e Navigator), apri <span class="help-strong-dark">[[CREA BLOCCO APPUNTAMENTO|calendar_create_appointment]]</span>.</span>
</div>

Puoi inserire clienti anche da **Impostazioni → Clienti** (tab "Clienti"), dove trovi molte altre funzioni avanzate per la gestione e modifica dei dati cliente.
""",
},

"client_info_window": {
    "title": "ℹ️ Finestra Info Cliente",
    "content": """Al click sull'**ICONA "i"** a fianco dei risultati della ricerca cliente si apre una finestra dove puoi visualizzare e modificare rapidamente i dati del cliente.

Puoi modificare **NOME, COGNOME, CELLULARE ed EMAIL** nei campi in alto, e aggiungere o modificare la **NOTA SALVATA** per quel cliente.

Più sotto trovi:
- **Prossimi appuntamenti prenotati** per quel cliente, in una tabella con tutti i dati dell'appuntamento. Cliccando sulla riga relativa, la vista Agenda si sposterà in quella giornata.
- **Storico appuntamenti** per quel cliente, anche qui cliccando sulla riga della tabella si sposterà la vista Agenda in quella giornata.

Così hai tutto sotto controllo e puoi gestire i dati cliente in modo semplice e veloce!
""",
},

    "client_history": {
        "title": "📊 Storico cliente: lettura rapida e uso operativo",
        "content": """Questa sezione ti guida sulla lettura dello storico cliente, utile per decisioni veloci durante la giornata.

<span class="help-strong-dark help-subtitle-pill">▸ COSA VEDI NELLO STORICO</span>
Aprendo lo storico cliente trovi in un unico punto:
• 📅 appuntamenti passati, con le date registrate in istituto
• 💰 totale speso
• 💆 operatori associati
• 📝 dati cliente e note salvate

<span class="help-strong-dark help-subtitle-pill">▸ COME APRIRLO</span>
Percorso rapido:
1️⃣ vai in **Impostazioni → Clienti**
2️⃣ cerca il cliente nella tabella-rubrica
3️⃣ clicca il pulsante **STORICO** sulla riga del cliente

<span class="help-strong-dark help-subtitle-pill">▸ COME USARLO IN MODO SMART</span>
Usa lo storico per:
• proporre richiami in base alle abitudini
• verificare frequenza e spesa prima di una proposta commerciale
• contestualizzare meglio le richieste del cliente prima del nuovo appuntamento

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Prima di confermare una nuova prenotazione, controlla al volo storico + note: la consulenza risulta più personalizzata e professionale.</span>
</div>""",
    },

    "client_settings": {
        "title": "⚙️ Gestione Clienti da Impostazioni",
        "content": """[[VIDEO|18]]

In **Impostazioni → Clienti** (tab "Clienti") trovi tutte le funzioni avanzate per gestire la tua rubrica clienti!

➕ **INSERIRE UN NUOVO CLIENTE**
Dal menu in alto clicca su **Tools** per aggiungere un nuovo cliente con tutti i dati:
• Nome e Cognome
• Cellulare
• **Data di nascita** (utile per chi segna i compleanni! 🎂)
• **E-mail**
• Cliccando sulla colonna **SESSO** puoi modificare il sesso del cliente

🔍 **RICERCA E VISUALIZZAZIONE**
Usa il campo di ricerca in basso per trovare i clienti. Nella tabella puoi vedere:
• Tutti i dati anagrafici inseriti
• **Data di inserimento** in rubrica
• **Ultimo passaggio** in istituto

Per il flusso operativo completo in Agenda (ricerca cliente, tasto + e finestra info), vedi <span class="help-strong-dark">[[RICERCA CLIENTE IN AGENDA|client_search]]</span>.

Per la lettura guidata dello storico cliente, vedi <span class="help-strong-dark">[[STORICO CLIENTE IN AGENDA|client_history]]</span>.

🔘 **TASTI AZIONE**
Per ogni cliente hai a disposizione questi pulsanti:
• **MODIFICA** → Apre una finestra per modificare i dati anagrafici del cliente
• **NOTE** → Apre una finestra per creare, visualizzare o modificare la nota per quel cliente
• **STORICO** → Apre lo storico completo del cliente (appuntamenti, spese, ecc.)
• **ELIMINA** → Elimina il cliente dalla rubrica (attenzione, operazione irreversibile!)

Qui hai il controllo totale sulla tua rubrica clienti! 📋""",
    },
    
    # ========== PACCHETTI ==========
    "pacchetto_panorama": {
        "title": "🎁 Come creare un pacchetto",
        "content": """Questa guida copre la creazione del <span class="help-strong-dark">Pacchetto servizi</span> vero e proprio: cioè un programma a sedute che vuoi vendere a un cliente, con eventuale sconto commerciale, omaggi e piano rateale.

Se vuoi prima configurare modelli e impostazioni pacchetti, vai a <span class="help-strong-dark">[[TOOLS / PACCHETTI|tools_tab_pacchetti]]</span>.

<span class="help-strong-dark help-subtitle-pill">▸ CREAZIONE BASE</span>
Flusso standard:
1️⃣ entra in <span class="help-strong-dark">Pacchetti</span>
2️⃣ clicca per creare un nuovo pacchetto
3️⃣ seleziona il cliente
4️⃣ scegli i servizi che faranno parte del programma
5️⃣ imposta <span class="help-strong-dark">quantità sedute</span>, automaticamente verrà calcolato il costo totale da listino del pacchetto


<span class="help-strong-dark help-subtitle-pill">▸ SCONTO O SEDUTE OMAGGIO?</span>
Subito dopo, potrai scegliere tra due modi principali per rendere il pacchetto più conveniente:

• applicare uno <span class="help-strong-dark">SCONTO</span> sul totale del prezzo del pacchetto

oppure

• lasciare il prezzo pieno ma aggiungere una o più <span class="help-strong-dark">SEDUTE OMAGGIO</span>


<span class="help-strong-dark help-subtitle-pill">▸ PACCHETTI GIÀ PREIMPOSTATI DA TOOLS</span>
Se dalle impostazioni in <span class="help-strong-dark">Tools / Pacchetti</span> sono già stati impostate tipologie di pacchetto ricorrenti, puoi selezionare quelle per velocizzare (le vedrai in "Tipo Sconto" nella sezione in fondo, "Promo Salvate").
È la soluzione migliore quando vendi spesso lo stesso programma (es. 10 sedute corpo, 6 sedute viso, ciclo laser, ecc.), perché riduce errori e mantiene una proposta commerciale standardizzata.

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Quando il pacchetto è ricorrente, conviene creare prima una struttura standard in Tools / Pacchetti e poi personalizzare solo cliente, rate e data delle sedute.</span>
</div>

Si può poi selezionare un'<span class="help-strong-dark">operatrice preferita</span> per quel pacchetto, che sarà proposta come default in agenda quando si prenotano le sedute collegate al pacchetto.

Infine per creare il pacchetto cliccare su <span class="help-strong-dark">SALVA</span>
""",
    },

    "pacchetto_tools_settings": {
        "title": "⚙️ Impostazioni del Pacchetto",
        "content": """Prima di vendere un pacchetto al cliente, conviene configurare bene le sue impostazioni in <span class="help-strong-dark">Tools / Pacchetti</span>.

<span class="help-strong-dark help-subtitle-pill">⚙️ ▸ COSA TROVI IN TOOLS / PACCHETTI</span>
Qui puoi:
• creare e gestire i modelli pacchetti dalla sezione <span class="help-strong-dark">Promo Personalizzate</span>
• inserire le <span class="help-strong-dark">controindicazioni</span> per ogni servizio nella sezione <span class="help-strong-dark">Template Disclaimer / Consenso Informato</span>
• modificare il template del consenso informato tramite il campo <span class="help-strong-dark">Disclaimer del servizio</span>
• configurare <span class="help-strong-dark">Template WhatsApp</span> e memo collegati per inviare un riassunto al cliente via Whatsapp

<span class="help-strong-dark help-subtitle-pill">⚙️ ▸ PERCHÉ FARLO PRIMA</span>
Più lavori bene qui, meno dovrai improvvisare quando sei con il cliente!

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">I testi e i modelli impostati in questa sezione si possono riutilizzare automaticamente durante la creazione del pacchetto, la stampa del consenso e l'invio dei memo. Dove presenti, i pulsanti-tag inseriscono i tag con parentesi graffe nel punto del cursore, evitando di riscriverli manualmente.</span>
</div>""",
    },

    "pacchetto_create": {
        "title": "📝 Gestire il Consenso Informato",
        "content": """[[VIDEO|28]]

Per molti pacchetti è utile, o necessario, collegare un <span class="help-strong-dark">consenso informato</span> firmato dal cliente. Dalla pagina del Pacchetto creato per il cliente potrai scaricare, far firmare e caricare il documento.

<span class="help-strong-dark help-subtitle-pill">📝 ▸ FLUSSO OPERATIVO CONSIGLIATO</span>
1️⃣ prepara il testo corretto in <span class="help-strong-dark">Tools / Pacchetti</span> (controindicazioni e template)
2️⃣ genera o scarica il consenso informato del cliente direttamente dalla scheda pacchetto. Per ogni servizio incluso nel pacchetto, il sistema aggiunge automaticamente le controindicazioni già impostate
3️⃣ stampalo e fallo firmare dal cliente in istituto
4️⃣ scannerizzalo oppure fotografalo bene anche dal cellulare
5️⃣ caricalo sul computer, poi da Tosca sempre tramite il tasto del consenso informato lo potrai caricare, e sarà tenuto in memoria nel database di Tosca

<span class="help-strong-dark help-subtitle-pill">📝 ▸ SCANSIONE DA CELLULARE</span>
Se non hai uno scanner a portata di mano, va benissimo usare il telefono:
• inquadra il foglio dritto
• usa una buona luce
• evita ombre e pieghe
• preferisci PDF o immagine ben leggibile per salvare, e invialo al computer via email o WhatsApp

L'obiettivo non è solo archiviare, ma poter recuperare il consenso in modo chiaro anche dopo mesi.

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Meglio caricare subito il consenso appena firmato, invece di rimandare: quando il pacchetto parte davvero, tutta la documentazione è già in ordine.</span>
</div>""",
    },

    "pacchetto_stati_dettaglio": {
        "title": "🎨 Colori STATUS pacchetti, sezioni e tooltip",
        "content": """[[VIDEO|31]]

La pagina Pacchetti non serve solo a vedere l'elenco: ti aiuta a leggere velocemente lo stato commerciale e operativo di ogni programma.

<span class="help-strong-dark help-subtitle-pill">▸ COLORI / STATUS</span>
I colori e gli status servono per capire in un colpo d'occhio se il pacchetto è:
🟡 <span class="help-strong-dark">PREVENTIVO</span> = non ancora pagato o non ancora effettuata la prima seduta
🔵 <span class="help-strong-dark">ATTIVO</span> = pacchetto in corso
⚫ <span class="help-strong-dark">COMPLETATO</span> = pacchetto con tutte le sedute effettuate e già pagato
🔴 <span class="help-strong-dark">ABBANDONATO</span> = pacchetto non aggiornato da almeno TOT giorni (i giorni si possono impostare come admin da Tools / Pacchetti)

Il significato preciso dipende dalla configurazione già impostata nel modulo, ma la logica è questa: il colore ti fa capire subito se devi lavorarci sopra oppure no.

<span class="help-strong-dark help-subtitle-pill">▸ COSA TROVI IN TOOLS/PACCHETTI</span>
Di norma nella pagina trovi:
• elenco pacchetti
• stato del pacchetto
• cliente collegato
• sedute nel pacchetto
• data di creazione
• prezzo da listino e prezzo scontato

gli admin potranno inoltre ELIMINARE I PACCHETTI dalla tabella: è un'operazione da fare con cautela, altamente sconsigliata

<span class="help-strong-dark help-subtitle-pill">▸ NOTE INFORMATIVE AL PASSAGGIO DEL MOUSE</span>
Al passaggio del mouse su alcuni elementi della pagina Tools/Pacchetti si apriranno finestrelle nere con note esplicative: servono proprio a spiegare campi e pulsanti in caso di dubbio.

Questa è la sezione giusta da consultare quando vuoi una <span class="help-strong-dark">lettura rapida</span> di cosa è attivo, cosa è quasi finito e cosa richiede follow-up.

da qui basterà <span class="help-strong-dark">cliccare sul pacchetto</span> per entrare nel dettaglio e gestire sedute, pagamenti, memo e tutto il resto!
""",
    },
    
    "pacchetto_uso": {
        "title": "📅 Come segnare un appuntamento collegato a un Pacchetto",
        "content": """[[VIDEO|30]]

Un pacchetto è davvero utile quando viene collegato bene anche alla parte Agenda.

<span class="help-strong-dark help-subtitle-pill">▸ PARTENDO DA PACCHETTO</span>
Dal pacchetto puoi preparare o avviare la prenotazione di una seduta collegata.

Questo approccio è comodo quando:
• stai lavorando dal dettaglio del pacchetto
• vuoi essere sicuro di usare una seduta compatibile
• vuoi controllare prima residuo e situazione commerciale

<span class="help-strong-dark help-subtitle-pill">▸ PARTENDO DA AGENDA</span>
Puoi anche lavorare al contrario, cioè da Agenda:
1️⃣ selezioni il cliente
2️⃣ scegli un servizio
3️⃣ se quel servizio rientra in un pacchetto attivo, Tosca ti mostra la logica pacchetto disponibile

Nella pratica, in Agenda compare l'<span class="help-strong-dark">icona pacchetto</span> quando il servizio può essere collegato a un pacchetto del cliente.

<span class="help-strong-dark help-subtitle-pill">▸ COSA SUCCEDE POI</span>
Quando il collegamento è corretto:
• la seduta viene associata al pacchetto giusto
• il residuo si aggiorna secondo le regole del programma
• eviti scarichi manuali o confusione tra sedute pagate e non pagate

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Se il cliente ha più programmi attivi, controlla sempre bene quale pacchetto stai usando prima di confermare l'appuntamento: così lo scarico resta pulito e coerente.</span>
</div>""",
    },
    
    "pacchetto_pagamento": {
        "title": "💶 Come pagare un pacchetto e come funzionano le rate",
        "content": """[[VIDEO|29]]

La vendita del pacchetto non è solo "creazione": deve essere collegata bene anche alla parte economica.

<span class="help-strong-dark help-subtitle-pill">▸ PAGAMENTO IMMEDIATO O RATEALE</span>
Un pacchetto può essere:
• pagato tutto subito
• pagato in più rate
• avviato con acconto e saldo successivo

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Imposta sempre le rate in modo da incassare un importo superiore a quello delle singole sedute! Questo ti eviterà perdite economiche in caso di pacchetto abbandonato...</span>
</div>

<span class="help-strong-dark help-subtitle-pill">▸ COME LEGGERE LE RATE</span>
Nel dettaglio pacchetto devi poter controllare rapidamente:
• quanto è già stato incassato
• quanto manca ancora
• quante rate sono previste
• quali risultano ancora aperte

<span class="help-strong-dark help-subtitle-pill">▸ COME SI PAGA UNA RATA</span>
Le rate <span class="help-strong-dark">non si pagano direttamente dall'Agenda</span>: devono essere portate in Cassa manualmente.

Flusso corretto:
1️⃣ apri il dettaglio del pacchetto
2️⃣ individua la rata da incassare
3️⃣ portala in Cassa tramite l'apposita azione
4️⃣ registra il pagamento normalmente (Cash, POS, Bank)

<span class="help-strong-dark help-subtitle-pill">▸ SEDUTA DA AGENDA → PORTA IN PACCHETTO</span>
Quando da Agenda clicchi <span class="help-strong-dark">€ Porta in Cassa</span> su un appuntamento <span class="help-strong-dark">collegato a un pacchetto</span>, il flusso cambia rispetto a un normale scontrino:

invece di aprire la Cassa, si apre il <span class="help-strong-dark">dettaglio del pacchetto</span>.

Da lì dovrai:
1️⃣ individuare la seduta corrispondente nella lista
2️⃣ cliccare il box per segnare la seduta come <span class="help-strong-dark">effettuata</span>

Questo tiene distinti i due piani operativi:
• <span class="help-strong-dark">consumo sedute</span> → si gestisce dal pacchetto
• <span class="help-strong-dark">pagamento rate</span> → si gestisce dalla Cassa

<span class="help-strong-dark help-subtitle-pill">▸ BUONA LOGICA OPERATIVA</span>
Non sempre consumo sedute e pagamento rate coincidono: il cliente può avere sedute già prenotabili ma rate ancora aperte, in base alla tua politica commerciale.

<span class="help-strong-dark help-subtitle-pill">▸ DOVE CONTROLLARE</span>
Controlla sempre il dettaglio pacchetto prima di intervenire se hai dubbi su:
• rate mancanti
• importo residuo
• blocchi commerciali
• stato generale del programma

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Quando vendi a rate, concorda subito una logica chiara con il cliente e registrala bene nel pacchetto: evita equivoci tra sedute già fatte e importi ancora da saldare.</span>
</div>""",
    },

    "pacchetto_memo": {
        "title": "💬 Memo pacchetto: WhatsApp, PDF e stampa",
        "content": """Dopo aver creato un pacchetto, spesso conviene consegnare al cliente un riepilogo chiaro del programma acquistato.

<span class="help-strong-dark help-subtitle-pill">💬 ▸ INVIO MEMO VIA WHATSAPP</span>
Se il modulo WhatsApp è attivo, puoi usare il memo per inviare al cliente un riepilogo del pacchetto o delle sedute.

È utile per ricordare:
• nome del pacchetto
• sedute previste
• eventuali residui
• note utili o promemoria organizzativi

<span class="help-strong-dark help-subtitle-pill">📄 ▸ SCARICARE MEMO SEDUTE IN PDF</span>
Quando ti serve un documento più ordinato o archiviabile, puoi scaricare il memo sedute in <span class="help-strong-dark">PDF</span>.

Questo è comodo quando vuoi:
• consegnarlo al cliente
• salvarlo in archivio
• inviarlo manualmente da altri canali

<span class="help-strong-dark help-subtitle-pill">🖨️ ▸ STAMPA</span>
In alternativa puoi stampare il memo direttamente, per far avere al cliente un riepilogo cartaceo del percorso acquistato.

Tra WhatsApp, PDF e stampa scegli in base alla situazione:
• WhatsApp = rapido
• PDF = ordinato e condivisibile
• stampa = consegna immediata in istituto

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Dai sempre al cliente un riepilogo semplice del pacchetto: riduce domande successive e rende più chiara la percezione del valore acquistato.</span>
</div>""",
    },

    "prepagata": {
        "title": "💳 Prepagate: panoramica operativa completa",
        "content": """La <span class="help-strong-dark">prepagata</span> non è un pacchetto a sedute: è un <span class="help-strong-dark">credito economico</span> che il cliente usa nel tempo.

<span class="help-strong-dark help-subtitle-pill">▸ DIFFERENZA CHIAVE RISPETTO AL PACCHETTO</span>
• il pacchetto ragiona soprattutto per <span class="help-strong-dark">sedute / programma</span>
• la prepagata ragiona soprattutto per <span class="help-strong-dark">saldo economico residuo</span>

<span class="help-strong-dark help-subtitle-pill">▸ COME SI CREA</span>
1️⃣ apri la sezione Pacchetti / Prepagate
2️⃣ seleziona il cliente
3️⃣ imposta importo caricato
4️⃣ salva la carta o il credito

<span class="help-strong-dark help-subtitle-pill">▸ COME SI USA</span>
La prepagata viene poi richiamata soprattutto in Cassa, dove puoi scegliere <span class="help-strong-dark">Prepagata</span> come metodo di pagamento.

Il sistema scala il credito usato e aggiorna il residuo.

<span class="help-strong-dark help-subtitle-pill">▸ RICARICHE, RESIDUO E CONTROLLO</span>
Devi poter controllare rapidamente:
• importo iniziale
• eventuali ricariche successive
• movimenti effettuati
• saldo residuo

<span class="help-strong-dark help-subtitle-pill">▸ USO OPERATIVO CORRETTO</span>
La prepagata è ideale per:
• clienti abituali
• buoni regalo
• credito lasciato disponibile per servizi/prodotti futuri

Quando la usi, ragiona sempre come su un portafoglio cliente: non si scaricano sedute, si scala denaro.

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Se un cliente usa spesso credito residuo, controlla il saldo prima di chiudere la vendita: una lettura chiara del residuo evita contestazioni e fa percepire ordine professionale.</span>
</div>""",
    },

    "prepagata_create": {
        "title": "💳 Come creare una prepagata",
        "content": """[[VIDEO|32]]

Per creare una prepagata devi ragionare in termini di <span class="help-strong-dark">credito caricato</span>, non di numero sedute.

Flusso base:
1️⃣ entra nella sezione Pacchetti / Prepagate
2️⃣ crea una nuova prepagata
3️⃣ seleziona il cliente
4️⃣ imposta l'importo iniziale
5️⃣ salva

Se previsto dalla tua organizzazione commerciale, puoi usare anche una logica da:
• buono regalo
• credito promozionale
• carta cliente ricaricabile

Questa è la configurazione giusta quando il cliente non sta acquistando un protocollo chiuso, ma vuole lasciare credito disponibile da usare nel tempo.""",
    },

    "prepagata_uso": {
        "title": "📅 Collegare servizi e appuntamenti a una prepagata",
        "content": """La prepagata si usa soprattutto a valle del lavoro operativo, cioè quando il cliente consuma servizi o prodotti.

Nella pratica:
• l'appuntamento si gestisce normalmente in Agenda
• il collegamento economico avviene soprattutto in <span class="help-strong-dark">Cassa</span>

Quando il cliente arriva al pagamento:
1️⃣ apri la bozza scontrino
2️⃣ verifica che il cliente abbia una prepagata disponibile
3️⃣ scegli <span class="help-strong-dark">Prepagata</span> come metodo di pagamento
4️⃣ conferma lo scarico del credito

Così il servizio resta normale a livello Agenda, ma il consumo economico viene preso dal saldo della prepagata.""",
    },

    "prepagata_pagamento": {
        "title": "💶 Prepagate: pagamenti, ricariche e saldo residuo",
        "content": """La vita economica della prepagata ruota intorno a tre elementi:
• carico iniziale
• eventuali ricariche
• scarichi successivi in Cassa

<span class="help-strong-dark help-subtitle-pill">▸ PAGARE CON PREPAGATA</span>
Quando il cliente usa il credito:
• in Cassa selezioni <span class="help-strong-dark">Prepagata</span>
• il sistema scala l'importo usato
• il residuo viene aggiornato

<span class="help-strong-dark help-subtitle-pill">▸ RICARICARE</span>
Quando il saldo si abbassa, puoi caricare nuovo credito e continuare a usare la stessa logica carta/portafoglio.

<span class="help-strong-dark help-subtitle-pill">▸ COSA CONTROLLARE SEMPRE</span>
• saldo residuo
• movimenti effettuati
• eventuali usi anomali o dubbi cliente

La regola pratica è semplice: ogni volta che la prepagata viene usata, il cliente deve poter capire chiaramente quanto aveva e quanto resta.""",
    },

    "prepagata_controllo": {
        "title": "🎯 Prepagate: controlli utili, memo e lettura rapida",
        "content": """Una buona gestione della prepagata non è solo incasso: è anche chiarezza nel tempo.

<span class="help-strong-dark help-subtitle-pill">▸ LETTURA RAPIDA</span>
Quando apri la scheda o la sezione relativa, dovresti leggere subito:
• cliente associato
• importo caricato
• saldo residuo
• movimenti principali

<span class="help-strong-dark help-subtitle-pill">▸ MEMO O RIEPILOGO</span>
Quando serve, conviene consegnare o inviare un riepilogo semplice del credito residuo, soprattutto nei casi in cui il cliente usa la prepagata a distanza di settimane o mesi.

<span class="help-strong-dark help-subtitle-pill">▸ QUANDO CONTROLLARLA</span>
Meglio dare un'occhiata a una prepagata:
• prima della chiusura scontrino
• quando il cliente chiede quanto credito resta
• quando il saldo sta per finire e può essere proposta una ricarica

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">La prepagata funziona benissimo quando il cliente percepisce sempre trasparenza: saldo chiaro, movimenti leggibili e nessuna incertezza su quanto resta.</span>
</div>""",
    },

    "pacchetto_settings": {
        "title": "⚙️ Tools / Pacchetti: impostazioni, modelli e configurazioni utili",
        "content": """La sezione <span class="help-strong-dark">Tools / Pacchetti</span> è il punto in cui prepari il terreno prima della vendita vera e propria.

Qui conviene configurare tutto ciò che poi rende il lavoro più rapido e uniforme:
• modelli pacchetto ricorrenti
• regole commerciali
• testi e parti documentali
• memo o template collegati
• controindicazioni e contenuti per consenso informato

Più lavori bene in questa sezione, meno dovrai improvvisare quando sei con il cliente davanti.

Questa non è la schermata dove "usi" il pacchetto: è la schermata dove lo <span class="help-strong-dark">prepari bene</span> per farlo funzionare in modo ordinato in Pacchetti, Agenda, Cassa e comunicazioni.

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Quando lavori sui template, usa i pulsanti-tag (se disponibili): con un click il tag con parentesi graffe viene inserito vicino al puntatore nel campo testo, così non devi riscrivere ogni variabile.</span>
</div>""",
    },
    
    # ========== WHATSAPP ==========
    "whatsapp_panorama": {
        "title": "💬 WhatsApp: panoramica del modulo opzionale",
        "content": """La sezione <span class="help-strong-dark">WhatsApp e Marketing</span> appartiene a un <span class="help-strong-dark">modulo opzionale separato</span> rispetto al gestionale standard.

Se il modulo non è attivo:
• non compaiono le funzioni di invio WhatsApp
• non vengono mostrati i flussi automatici relativi ai messaggi

Se il modulo è attivo, puoi gestire:
• connessione account WhatsApp Business
• messaggi manuali e automatici
• reminder giornalieri
• memo turni operatori
• campagne marketing""",
    },

    "whatsapp_connect": {
        "title": "📱 Collegare WhatsApp",
        "content": """[[VIDEO|33]]

Per usare il modulo WhatsApp devi prima collegare l'account Business.

Flusso base:
1️⃣ vai in <span class="help-strong-dark">Impostazioni → WhatsApp</span>
2️⃣ clicca <span class="help-strong-dark">Connetti WhatsApp</span>
3️⃣ si apre il flusso con QR code o pagina di connessione
4️⃣ dal telefono apri WhatsApp → Dispositivi collegati
5️⃣ inquadra il QR

Quando la connessione è attiva, la schermata mostra lo stato collegato e il numero associato.

Nota operativa:
• nella versione desktop locale sono disponibili più opzioni di connessione
• il telefono/account deve restare correttamente connesso per permettere gli invii

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Fai un test con il tuo numero interno subito dopo la connessione: conferma prima invio manuale e poi invio automatico.</span>
</div>""",
    },

    "whatsapp_messaggi_template": {
        "title": "📝 WhatsApp: messaggi manuali e template",
        "content": """[[VIDEO|34]]

Nel modulo puoi configurare diversi testi WhatsApp.

I principali sono:
• messaggio manuale da calendario
• messaggio automatico alla conferma appuntamento
• reminder giornaliero

Ogni template può usare variabili come:
• {{nome}}
• {{data}}
• {{ora}}
• {{servizi}}

Questo ti permette di mantenere un messaggio coerente ma personalizzato per ogni cliente.

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Mantieni i template brevi e chiari: una frase di conferma, data/ora e call-to-action sono spesso sufficienti. Cliccando uno dei pulsanti-tag, nel punto del cursore viene inserito automaticamente il tag completo con parentesi graffe, senza riscriverlo ogni volta.</span>
</div>""",
    },
    
    "whatsapp_auto": {
        "title": "⏰ Promemoria automatici",
        "content": """Con il modulo attivo puoi automatizzare più tipi di invio.

<span class="help-strong-dark">Conferma automatica</span>
Messaggio inviato al momento della creazione appuntamento, se il flusso lo prevede.

<span class="help-strong-dark">Reminder giornaliero</span>
Puoi attivare un invio automatico a orario fisso ogni giorno, usando il template dedicato.

<span class="help-strong-dark">Opzione utile</span>
Puoi anche disattivare la richiesta di conferma WhatsApp nel modal di creazione appuntamento, se vuoi un flusso più rapido.

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Imposta un orario reminder che non risulti invasivo: la fascia tardo pomeriggio del giorno prima funziona spesso meglio.</span>
</div>""",
    },

    "whatsapp_operatori": {
        "title": "👩‍💼 WhatsApp: memo turni operatori del giorno dopo",
        "content": """[[VIDEO|36]]

Il modulo può inviare ogni sera a ciascun operatore il riepilogo del turno del <span class="help-strong-dark">giorno successivo</span>, con il primo impegno della giornata e l'eventuale pausa.

<span class="help-strong-dark help-subtitle-pill">▸ CONFIGURAZIONE</span>
Dal pannello WhatsApp imposta:
• <span class="help-strong-dark">attivazione</span> memo turni operatori
• <span class="help-strong-dark">orario di invio</span> (es. 20:00)
• <span class="help-strong-dark">template messaggio</span> con le variabili

Per ogni operatore va inoltre spuntato il flag <span class="help-strong-dark">"Notifica turni via WhatsApp"</span> in <span class="help-strong-dark">[[OPERATORI|tools_tab_operatori]]</span>: senza quello, il singolo non riceve il memo.

<span class="help-strong-dark help-subtitle-pill">▸ CHI RICEVE E CHI NO</span>
Il memo viene inviato solo a operatori:
• non cancellati e visibili
• non di tipo <span class="help-strong-dark">macchinario</span>
• con il flag di notifica attivo
• con un <span class="help-strong-dark">turno impostato</span> per il giorno dopo (giorni di riposo esclusi)
• con cellulare valido in anagrafica

<span class="help-strong-dark help-subtitle-pill">▸ COSA CONTIENE IL MESSAGGIO</span>
Il template viene popolato con il turno e gli appuntamenti del giorno dopo, considerando anche gli OFF interni (es. pausa pranzo). I blocchi sui clienti fittizi/dummy sono esclusi dalla lista impegni.

<span class="help-strong-dark help-subtitle-pill">▸ VARIABILI DISPONIBILI</span>
• <span class="help-strong-dark">{{operatore}}</span> → nome dell'operatore
• <span class="help-strong-dark">{{data}}</span> → giorno della settimana e data in italiano (es. "Martedì 12 Marzo")
• <span class="help-strong-dark">{{ora_inizio}}</span>, <span class="help-strong-dark">{{ora_fine}}</span> → estremi del turno
• <span class="help-strong-dark">{{ora_primo_app}}</span>, <span class="help-strong-dark">{{primo_app}}</span> → orario ed etichetta del primo appuntamento (saltando OFF)
• <span class="help-strong-dark">{{ora_pausa}}</span>, <span class="help-strong-dark">{{pausa}}</span> → orario ed etichetta della pausa, se presente
• <span class="help-strong-dark">{{sezione_pausa}}</span> → blocco "Pausa: HH:MM" già pronto, vuoto se non c'è pausa
• <span class="help-strong-dark">{{sezione_primo_app}}</span> → frase completa sul primo impegno, vuota se non c'è
• <span class="help-strong-dark">{{nome_istituto}}</span>, <span class="help-strong-dark">{{sito}}</span> → dati del centro

<span class="help-strong-dark help-subtitle-pill">▸ INVIO 1 MESSAGGIO AL MINUTO</span>
Come per il memo clienti, anche qui Tosca invia un messaggio al minuto fino a esaurire la coda, per non stressare WhatsApp.

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Imposta l'orario del memo a fine giornata (es. 20:00): gli operatori ricevono il turno di domani in tempo per organizzarsi. Prima di attivare per tutti, prova il template con la funzione di anteprima.</span>
</div>""",
    },
    
    # ========== MARKETING ==========
    "marketing_panorama": {
        "title": "📣 Marketing: panoramica del modulo opzionale",
        "content": """La parte Marketing è inclusa nello stesso <span class="help-strong-dark">modulo opzionale WhatsApp</span>.

Serve a inviare campagne mirate ai clienti usando filtri e template.

Non fa parte del gestionale standard: se il modulo non è attivo, questa sezione non rientra nei flussi operativi base di Agenda e Cassa.

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Definisci 2-3 campagne tipo (riattivazione, promo stagionale, fedeltà) e riusale come base per risparmiare tempo.</span>
</div>""",
    },

    "marketing_send": {
        "title": "📣 Inviare messaggi marketing",
        "content": """[[VIDEO|37]]

La schermata Marketing è divisa in tre parti:

• <span class="help-strong-dark">filtri clienti</span>
• <span class="help-strong-dark">risultati selezionabili</span>
• <span class="help-strong-dark">template messaggio e anteprima</span>

Flusso corretto:
1️⃣ attiva uno o più filtri
2️⃣ cerca i clienti
3️⃣ seleziona i destinatari
4️⃣ scegli o scrivi il template
5️⃣ verifica l'anteprima
6️⃣ invia

⚠️ Mantieni sempre un uso misurato degli invii per non stressare i clienti e non saturare il canale WhatsApp.

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Meglio una campagna ben mirata che molti invii generici. Qualità del target prima della quantità.</span>
</div>""",
    },

    "marketing_variables": {
        "title": "✨ Personalizzare i messaggi",
        "content": """Le variabili trasformano un messaggio generico in un messaggio personalizzato.

Esempio:
• testo scritto: "Ciao {{nome}}, sono passati {{giorni_assenza}} giorni..."
• testo ricevuto: "Ciao Maria, sono passati 45 giorni..."

Variabili tipiche:
• {{nome}}
• {{cognome}}
• {{centro}}
• {{giorni_assenza}}
• {{totale_visite}}
• {{totale_speso}}

Usale con criterio: poche variabili, ma ben scelte, rendono la comunicazione molto più efficace.

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Evita template con troppe variabili: se un dato manca, il messaggio rischia di risultare meno naturale. Cliccando uno dei pulsanti-tag, nel punto del cursore compare subito il tag con parentesi graffe, pronto da usare.</span>
</div>""",
    },

    "marketing_filtri_template": {
        "title": "🧩 Marketing: filtri, template salvati e anteprima",
        "content": """Nel modulo marketing puoi costruire campagne usando filtri combinabili.

Esempi di filtri presenti:
• clienti inattivi
• top spender
• utilizzo di un servizio specifico
• frequenza visite
• categoria servizi
• nuovi clienti
• genere

In più puoi:
• usare template predefiniti
• salvare i tuoi template personalizzati
• vedere l'anteprima sul primo cliente selezionato prima dell'invio

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Prima di inviare a molti clienti, esegui sempre un micro-test su un gruppo ristretto e controlla il testo finale. Per compilare più velocemente i template, usa i pulsanti-tag: inseriscono i tag con parentesi graffe direttamente vicino al puntatore nel campo testo.</span>
</div>""",
    },
    
    # ========== BOOKING ONLINE ==========
    "booking_panorama": {
        "title": "🌐 Booking via Web: panoramica del modulo opzionale",
        "content": """La sezione <span class="help-strong-dark">Booking via Web</span> è un <span class="help-strong-dark">modulo opzionale separato</span> dal gestionale standard.

Se il modulo non è attivo:
• non compare il flusso prenotazioni web
• non vengono mostrati gli elementi collegati alle prenotazioni online
• in Agenda non compaiono gli elementi specifici del booking web

Se il modulo è attivo, puoi pubblicare servizi online, gestire regole e associare operatori prenotabili.

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Gestisci il Booking via Web come canale separato: prima configuralo bene, poi promuovi il link ai clienti.</span>
</div>""",
    },

    "booking_setup": {
        "title": "🌐 Prenotazioni online",
        "content": """[[VIDEO|38]]

Per attivare il modulo Booking via Web:

1️⃣ entra in <span class="help-strong-dark">Impostazioni → Booking Web</span>
2️⃣ scegli quali servizi rendere visibili online
3️⃣ associa gli operatori prenotabili per ogni servizio
4️⃣ configura le regole di prenotazione
5️⃣ pubblica e condividi il link booking

Il link può essere usato su sito, social, Google Business e canali del centro.

Questo modulo consente ai clienti di richiedere prenotazioni anche fuori dagli orari di apertura.

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Pubblica online solo i servizi davvero adatti all'auto-prenotazione, lasciando quelli complessi al contatto diretto.</span>
</div>""",
    },
    
    "booking_rules": {
        "title": "⚙️ Regole prenotazione online",
        "content": """[[VIDEO|39]]

Le regole booking servono a proteggere l'agenda da prenotazioni online non adatte.

Regole principali disponibili:
• durata massima prenotabile
• prezzo massimo prenotabile

Per ciascuna regola puoi scegliere se:
• mostrare solo un <span class="help-strong-dark">warning</span>
• oppure <span class="help-strong-dark">bloccare</span> la prenotazione

Inoltre puoi personalizzare il messaggio mostrato al cliente, così il sito comunica chiaramente il motivo della limitazione.

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Parti con limiti prudenti e poi allargali gradualmente in base ai risultati reali delle prenotazioni web.</span>
</div>""",
        },

        "booking_servizi_operatori": {
        "title": "👩‍💼 Booking via Web: servizi visibili e operatori associati",
        "content": """Nel pannello Booking Web trovi una tabella servizi dedicata al modulo online.

Qui puoi decidere:
• se un servizio è visibile online
• quanti operatori sono associati a quel servizio
• quali operatori possono essere prenotati dal cliente via web

Questo è un punto chiave: un servizio pubblicato online senza corretta associazione operatori non produrrà un'esperienza di prenotazione coerente.

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Dopo ogni modifica operatori/servizi, testa una prenotazione completa dal link pubblico per verificare il risultato reale.</span>
</div>""",
        },

        "booking_agenda_separazione": {
        "title": "🧭 Booking via Web: cosa compare in Agenda e cosa no",
        "content": """Le funzioni del Booking via Web devono essere lette come <span class="help-strong-dark">aggiuntive</span> rispetto all'Agenda standard.

Se il modulo non è attivo:
• non devi aspettarti la presenza di elementi dedicati al booking web
• la normale Agenda continua a funzionare senza icone o tabelle collegate al mondo online

Se il modulo è attivo, alcuni blocchi o pannelli possono mostrare informazioni specifiche del booking web, ma questi contenuti appartengono a questa sezione e non alla guida Agenda standard.

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Quando formi lo staff, separa sempre i flussi: prima Agenda standard, poi add-on Booking via Web.</span>
</div>""",
    },
    
    # ========== OPERATORI ==========
    "operator_shifts": {
        "title": "📅 Impostare i turni",
        "content": """Gestisci gli orari di lavoro facilmente!

1️⃣ Vai nel **Calendario Turni**
2️⃣ Seleziona l'**operatore**
3️⃣ Clicca sui **giorni** per impostare gli orari
4️⃣ Usa i **preset** per velocizzare (es: "Full time", "Part time")

Gli appuntamenti si potranno creare **solo** negli orari di turno!

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Crea preset per i turni più usati, e magari scegli un nome che mostri già le caratteristiche del turno stesso (es: "9-18 pausa 12"), risparmi tempo 🚀</span>
</div>""",
    },

# filepath: c:\Program Files\SunBooking\appl\routes\help.py
    # ========== SERVIZI ==========
    "service_create": {
        "title": "💆 Creare un servizio",
        "content": """[[VIDEO|19]]

Aggiungi i tuoi trattamenti in pochi click!

1️⃣ Vai in **Impostazioni → Servizi**

2️⃣ Clicca **"Nuovo Servizio"**

3️⃣ Compila i campi richiesti:
   • **NOME** → Nome completo del servizio (es: "Ceretta Gambe Completa Donna")
   • **ABBREVIAZIONE/TAG** → Codice breve (es: "Cera Gamb Lei") - molto comodo perché è più leggibile e si incastra meglio con pulsanti e funzioni del gestionale!
   • **DURATA** → Obbligatoria per i servizi!
   • **PREZZO**
   • **CATEGORIA** e **SOTTOCATEGORIA**

4️⃣ Salva!

Il servizio appare subito nel menu appuntamenti 🎉

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Usa nomi chiari per il cliente e abbreviazioni intuitive per lo staff. Se attivi Booking via Web, questa chiarezza diventa ancora piu' importante.</span>
</div>""",
    },

    "service_categories": {
        "title": "📂 Categorie e Sottocategorie",
        "content": """I servizi sono organizzati in **CATEGORIE** e **SOTTOCATEGORIE** per una gestione ordinata!

📁 **CATEGORIE PRINCIPALI**
Le categorie di default sono:
• **Estetica** → Tutti i trattamenti estetici
• **Solarium** → Lampade e abbronzatura

Le **CATEGORIE** di Servizi sono fondamentali per organizzare i servizi, e per TOSCA di default sono solo queste due, ma se te ne servissero altre puoi provare a chiedere al supporto di TOSCA!

📂 **SOTTOCATEGORIE**
All'interno di ogni categoria puoi creare sottocategorie, ad esempio:
• Ceretta
• Manicure
• Pedicure
• Trattamenti viso
• Massaggi
• ...e qualsiasi altra tu voglia!

Le **SOTTOCATEGORIE** di Servizi a differenza delle categorie sono **completamente personalizzabili** e ti aiutano a trovare velocemente i servizi nel calendario e in cassa.

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Organizza bene le categorie fin dall'inizio, ti farà risparmiare tempo dopo!</span>
</div>""",
    },

    "service_vs_products": {
        "title": "🛒 Servizi vs Prodotti",
        "content": """In Tosca puoi gestire sia **SERVIZI** che **PRODOTTI**, ma hanno caratteristiche diverse!

💆 **SERVIZI**
• Hanno una **DURATA** obbligatoria (15 min, 30 min, ecc.)
• Occupano celle sul calendario
• Esempi: ceretta, massaggio, manicure, lampada

🛍️ **PRODOTTI**
• **NON hanno durata** (non occupano il calendario)
• Sono **scontrinati separatamente** dai servizi (tu non devi fare niente, ci pensa già Tosca!)
• Hanno **categorie merceologiche diverse** a livello fiscale
• Esempi: crema, smalto, shampoo

⚠️ **I PRODOTTI IN CASSA**
I prodotti hanno una scontrinazione particolare perché appartengono a categorie merceologiche diverse. Questo è fondamentale per la corretta gestione fiscale!

📦 **ABBONAMENTI E SERVIZI SPECIALI**
Alcuni servizi come gli **abbonamenti** o le **carte prepagate** non hanno durata sul calendario: vengono gestiti nella sezione **Pacchetti** e scalati in cassa.""",
    },

    "service_duration": {
        "title": "⏱️ Durata dei servizi",
        "content": """La **DURATA** è fondamentale per i servizi sul calendario!

⏰ **COME FUNZIONA**
• Ogni servizio ha una durata espressa in **minuti**
• La durata determina quante celle occupa sul calendario
• Durate standard: 15, 30, 45, 60, 90 minuti...

🔧 **IMPOSTARE LA DURATA**
1️⃣ Vai in **Impostazioni → Servizi**
2️⃣ Seleziona il servizio da modificare
3️⃣ Imposta la durata nel campo dedicato
4️⃣ Salva

📝 **SERVIZI SENZA DURATA**
Alcuni elementi **NON** hanno durata:
• **Prodotti** → Vendita diretta, niente calendario
• **Abbonamenti/Pacchetti** → Gestiti nella sezione Pacchetti
• **Carte prepagate** → Gestite come credito cliente

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Imposta durate realistiche! Se un massaggio dura 50 minuti, meglio impostare 60 per avere un margine.</span>
</div>""",
    },

    # ========== AGENDA (NUOVA STRUTTURA) ==========
    "agenda_create_modify_delete": {
        "title": "🗂️ Agenda: creare, modificare e cancellare appuntamenti",
        "content": """La sezione Agenda serve a <span class=\"help-strong-dark\">creare</span>, <span class=\"help-strong-dark\">modificare</span>, <span class=\"help-strong-dark\">spostare</span> e <span class=\"help-strong-dark\">chiudere</span> gli appuntamenti.

<span class=\"help-strong-dark\">Creazione</span>
• da cella vuota con modal rapido
• con Navigator Appuntamenti per flussi più complessi

<span class=\"help-strong-dark\">Modifica</span>
• trascinamento verticale/orizzontale
• cambio durata dal bordo inferiore
• cambio cliente, colore, nota o servizi aggiuntivi

<span class=\"help-strong-dark\">Cancellazione / chiusura</span>
• cestino del blocco
• opzione No-Show
• passaggio in Cassa per completamento e pagamento

L'idea corretta è questa: l'Agenda è la vista operativa del lavoro giornaliero, mentre la Cassa e i Report leggono quello che succede qui.""",
    },

    "agenda_turni": {
        "title": "🕒 Impostare i turni degli operatori",
        "content": """[[VIDEO|11]]

I turni definiscono quando un operatore è disponibile per nuove prenotazioni. Gli appuntamenti si potranno creare <span class=\"help-strong-dark\">solo</span> negli orari di turno impostati.

<span class=\"help-strong-dark help-subtitle-pill\">▸ IMPOSTARE TURNI DA TOOLS/OPERATORI</span>
Da qui gestisci i turni di base di ogni operatore, insieme all'anagrafica e alle altre impostazioni.

Flusso:
1️⃣ vai in <span class=\"help-strong-dark\">Tools → Operatori</span>
2️⃣ seleziona l'operatore
3️⃣ imposta gli orari nei giorni della settimana
4️⃣ usa i <span class=\"help-strong-dark\">preset</span> per velocizzare (es. \"9-18 pausa 12\")

<span class=\"help-strong-dark help-subtitle-pill\">▸ IMPOSTARE TURNI DA CLICK SU NOME OPERATORE IN AGENDA</span>
Clicca il nome dell'operatore nell'intestazione colonna: si apre il pannello turno del giorno, dove puoi modificare l'orario oppure impostare un giorno di riposo.

È il metodo più rapido per gestire <span class=\"help-strong-dark\">variazioni occasionali</span> senza toccare le impostazioni globali.

Sempre nella stessa finestra, troverai la sezione <span class=\"help-strong-dark\">Visualizzazione rapida per operatore</span>, che mostra un calendario mensile con i turni impostati, così puoi verificare a colpo d'occhio la copertura di ogni operatore.

<span class=\"help-strong-dark\">Buona pratica</span>
• imposta i turni standard da Tools → Operatori
• usa l'Agenda per le eccezioni giornaliere
• usa i Blocchi OFF solo per impegni di servizio, non per sostituire la logica dei turni

<div class=\"help-hint-box\">
<span class=\"help-hint-label\">Consiglio:</span>
<span class=\"help-hint-text\">Crea preset con nomi descrittivi (es. \"9-18 pausa 12\") e risparmia tempo ogni volta che devi impostare un turno ricorrente.</span>
</div>""",
    },

    "agenda_touch_mode": {
        "title": "📱 Agenda in modalità TOUCH: differenze operative",
        "content": """[[VIDEO|42]]

La modalità TOUCH cambia il modo in cui interagisci con i blocchi appuntamento.

<span class=\"help-strong-dark help-subtitle-pill\">▸ MODALITÀ TOUCH: COME E QUANDO ATTIVARLA</span>
È consigliata quando usi schermi touch/tablet (anche iPad in contesti kiosk) oppure quando alcune operatrici sono più a proprio agio con il tocco rispetto al mouse.

<span class=\"help-strong-dark\">Attivazione da Tools</span>
Percorso:
1️⃣ vai in <span class=\"help-strong-dark\">Tools → Info Azienda</span>
2️⃣ cerca l'opzione <span class=\"help-strong-dark\">Touch-screen</span>
3️⃣ attiva il checkbox <span class=\"help-strong-dark\">\"Abilita interfaccia touch per i blocchi agenda\"</span>
4️⃣ ricarica l'Agenda

Nota: l'impostazione è salvata <span class=\"help-strong-dark\">su questo computer</span>.

<span class=\"help-strong-dark help-subtitle-pill\">▸ DIFFERENZE OPERATIVE IN MODALITÀ TOUCH</span>
In modalità touch non lavori con hover/passaggio mouse come su desktop classico.

Flusso tipico:
1️⃣ fai <span class=\"help-strong-dark\">click sul blocco appuntamento</span>
2️⃣ il blocco diventa attivo
3️⃣ compaiono i comandi rapidi nelle <span class=\"help-strong-dark\">barre del blocco (sopra e sotto)</span>

Azioni tipiche disponibili:
• allunga/accorcia durata di 15 minuti
• cliente in istituto
• no-show
• copia/elimina/taglia

Nella pratica: prima selezioni il blocco, poi tocchi i pulsanti contestuali.

<div class=\"help-hint-box\">
<span class=\"help-hint-label\">Consiglio:</span>
<span class=\"help-hint-text\">È altamente raccomandato usare un computer con mouse, senza touch-screen, per maggiore comodità e stabilità operativa. Su schermi touch usurati o poco calibrati possono comparire sfarfallamenti e comportamenti anomali.</span>
</div>""",
    },

    # ========== CASSA (DETTAGLIO OPERATIVO) ==========
    "cassa_filtri_ricerca": {
        "title": "🧾 Cassa: bozza scontrino, metodi di pagamento e stampa",
        "content": """[[VIDEO|12]]

Qui trovi il flusso completo in 3 parti, senza passaggi separati.

<span class=\"help-strong-dark help-subtitle-pill\">▸ PARTE 1: Creare la bozza scontrino</span>
Usa i controlli in alto:
• <span class=\"help-strong-dark\">campo CERCA</span>: ricerca veloce con autocomplete di Servizi e Prodotti
• <span class=\"help-strong-dark\">filtri rapidi</span>: Frequenti, Ultimi, Solarium, Estetica, Prodotti

Sotto i filtri compaiono i <span class=\"help-strong-dark\">pulsanti servizi/prodotti</span>, che cambiano in base al filtro selezionato.
Ogni click su un pulsante aggiunge la voce nella bozza.

In alternativa, puoi partire da Agenda: clicca <span class=\"help-strong-dark\">€ Porta in Cassa</span> su un blocco appuntamento e i servizi vengono caricati automaticamente.

<span class=\"help-strong-dark help-subtitle-pill\">▸ PARTE 2: Rifinire la bozza e impostare il pagamento</span>
Nella bozza puoi gestire:
• righe servizi/prodotti
• cliente e operatore selezionati
• prezzo e sconto percentuale (es. 10 = 10%)
• metodo di pagamento

Metodi supportati:
• Cash = pagamento in contanti 💵
• POS = pagamento con carta/bancomat 💳
• Bank = bonifico, assegno, pagamento online, ecc. 📱
• Prepagata = disponibile solo se il cliente ha una carta prepagata 💳

Quando la bozza scontrino viene creata a partire da appuntamenti in Agenda, compaiono anche dei tasti aggiuntivi per gestire le modifiche:
• <span class=\"help-strong-dark\">Salva Modifiche</span>
• <span class=\"help-strong-dark\">Reset</span>

<span class=\"help-strong-dark help-subtitle-pill\">▸ PARTE 3: Confermare, registrare il pagamento e stampare</span>
Quando la bozza scontrino è pronta:
1. clicca <span class=\"help-strong-dark\">CONFERMA</span> (o Avanti)
2. verifica il riepilogo
3. clicca <span class=\"help-strong-dark\">Stampa</span> per emettere lo scontrino

Se previsto dal flusso fiscale, può comparire la <span class=\"help-strong-dark\">Lotteria Scontrini</span>.
I documenti non fiscali/test sono trattati in modo distinto nel Registro.""",
    },

    "cassa_myspia_save_reset": {
        "title": "💾 Cassa: Clienti in istituto + Salva/Reset bozza",
        "content": """In basso a destra trovi il riquadro <span class=\"help-strong-dark help-subtitle-pill\">Clienti in istituto</span>

Mostra gli appuntamenti per ogni cliente che in Agenda è indicato come <span class=\"help-strong-dark\">presente in istituto</span>. Puoi usarlo per:

• tornare in Agenda con il tasto &nbsp;<span class=\"help-strong-dark\"><i class="bi bi-calendar2-week"></i></span>
• portare i servizi relativi nella bozza scontrino con il tasto <span class=\"help-strong-dark\"><i class="bi bi-currency-euro"></i></span>

Quando la bozza scontrino viene creata a partire da appuntamenti in Agenda, compaiono anche dei tasti aggiuntivi per gestire le modifiche:

• <span class=\"help-strong-dark\">Salva Modifiche</span>: conserva la versione modificata della bozza
• <span class=\"help-strong-dark\">Reset</span>: ricostruisce la bozza partendo dai dati originali del calendario

Questa logica è utile quando, prima di stampare, cambi prezzi, righe o metodi ma vuoi mantenere coerenza con l'Agenda.""",
    },

    "cassa_sconti_metodi_stampa_test": {
        "title": "🧮 Cassa: sconti e metodi di pagamento",
        "content": """[[VIDEO|15]]

Ogni riga della bozza può essere rifinita prima della conferma.

<span class=\"help-strong-dark\">Per singola riga puoi gestire</span>
• prezzo
• sconto percentuale (basta scrivere il numero nel campo sconto, es. 10 per 10%)
• metodo di pagamento

<span class=\"help-strong-dark\">Metodi pagamento supportati</span>
• Cash = pagamento in contanti 💵
• POS = pagamento con carta, bancomat ecc. 💳
• Bank = altro tipo di pagamento: bonifico, assegno, pagamento online, ecc. 📱
• Prepagata (solo quando c'è una CARTA PREPAGATA associata al cliente) 💳

In basso trovi anche i bottoni rapidi per applicare il metodo a tutte le righe e leggere i subtotali per metodo.""",
    },

    "cassa_registro_ruoli": {
        "title": "📚 Cassa: Registro Scontrini e differenze per ruolo",
        "content": """Il <span class=\"help-strong-dark\">Registro Scontrini</span> è lo storico giornaliero dei documenti emessi.

Che cosa puoi fare:
• cambiare data visualizzata
• aprire il dettaglio di uno scontrino
• distinguere fiscale / non fiscale / storno
• usare azioni aggiuntive se il tuo ruolo lo consente

<span class=\"help-strong-dark\">Differenze per ruolo</span>
• <span class=\"help-strong-dark\">user</span>: vista più limitata, senza strumenti critici
• <span class=\"help-strong-dark\">admin</span>: più strumenti, tra cui eliminazione nei casi consentiti e console RCH

Nel dettaglio scontrino puoi leggere righe, metodi di pagamento, totale e stato fiscale del documento.

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Controlla il Registro Scontrini ogni volta sorgesse un dubbio su uno scontrino già stampato: riduce errori e correzioni a posteriori.</span>
</div>""",
    },

    "cassa_strumenti_fiscali_rch": {
        "title": "🖨️ Cassa: strumenti fiscali, DGFE e console RCH",
        "content": """[[VIDEO|16]]

Nella colonna destra alta della Cassa trovi gli strumenti legati alla stampante fiscale:

• <span class=\"help-strong-dark\">Registro Scontrini</span>
• <span class=\"help-strong-dark\">Registro DGFE</span>
• <span class=\"help-strong-dark\">Chiusura Giornaliera</span>
• <span class=\"help-strong-dark\">Annulla Scontrino</span>
• <span class=\"help-strong-dark\">Console RCH</span> (solo admin)

Che cosa fanno:
• DGFE: legge la memoria fiscale del giorno
• Chiusura Giornaliera: esegue la chiusura del registratore
• Annulla Scontrino: avvia il flusso di storno/annullo previsto
• Console RCH: strumento tecnico avanzato per sblocco e diagnostica

Questi pulsanti vanno usati con attenzione perché incidono sulla parte fiscale e sul dialogo con la stampante.""",
    },

    # ========== REPORT ==========
    "report_navigazione_filtri": {
        "title": "📊 Report: navigazione data e filtri avanzati",
        "content": """[[VIDEO|21]]

La pagina Report include una barra di navigazione simile all'Agenda:

• frecce giorno precedente/successivo
• campo data con giorno della settimana
• tasto "Vai a Oggi"
• versione mobile dedicata della navigazione data

Con i filtri avanzati puoi analizzare:
• un singolo giorno
• un intervallo date (Da/A)
• mese/anno

Dopo aver impostato i filtri usa il tasto **VAI** per ricalcolare tutti i widget e le tabelle.""",
    },

    "report_sezioni_principali": {
        "title": "📈 Report: sezioni principali e pannelli KPI",
        "content": """In alto trovi i <span class=\"help-strong-dark\">pannelli KPI</span> (in precedenza indicati anche come tile) e sotto i pulsanti di sezione.

<span class=\"help-strong-dark\">Che cosa significa KPI?</span>
KPI è l'acronimo di <span class=\"help-strong-dark\">Key Performance Indicator</span>, cioè <span class=\"help-strong-dark\">Indicatore Chiave di Performance</span>.
In pratica è un numero sintetico che ti dice rapidamente se stai andando nella direzione giusta.

Nel Report, i KPI mostrano ad esempio:
• incasso totale
• passaggi in cassa
• trend o scostamento

I <span class=\"help-strong-dark\">pannelli KPI</span> sono i riquadri riassuntivi: ogni pannello mostra un dato chiave e il relativo significato operativo.""",
    },

    "report_previsioni_tile_edit": {
        "title": "🧠 Report: calcoli previsionali e gestione pannelli KPI",
        "content": """[[VIDEO|22]]

La parte previsionale confronta i dati correnti con obiettivi e andamento temporale.

In termini operativi:
• il sistema legge i dati reali disponibili nel periodo selezionato
• li confronta con un target di riferimento
• mostra la differenza nei pannelli KPI (trend/scostamento)

<span class=\"help-strong-dark\">Come leggere un pannello previsionale</span>
• valore principale: dato attuale
• testo secondario: contesto (giorno/periodo)
• trend: sei sopra o sotto target

<span class=\"help-strong-dark\">Come si modificano</span>
I pannelli non si modificano "a mano" direttamente dal widget: si aggiornano cambiando filtri e impostazioni disponibili nel report/settings (quando abilitate per il tuo ruolo).""",
    },

    "report_corrispettivi_ufficiali": {
        "title": "🧾 Report: sezione Corrispettivi (dati ufficiali)",
        "content": """[[VIDEO|23]]

La sezione <span class=\"help-strong-dark\">Corrispettivi</span> raccoglie i <span class=\"help-strong-dark\">dati ufficiali degli incassi</span> generati dalla cassa.

Questa è la sezione di riferimento per la contabilità ordinaria.

Uso pratico:
1. seleziona il periodo corretto
2. verifica il totale e i dettagli
3. esporta il file di riepilogo
4. invialo al commercialista

<span class=\"help-strong-dark\">Nota importante</span>
L'export Corrispettivi è pensato proprio per essere inviato comodamente al commercialista per la normale tenuta contabile.""",
    },

    "report_pulsanti_operativi": {
        "title": "🔘 Report: come usare i pulsanti operativi",
        "content": """I pulsanti principali cambiano il tipo di analisi mostrata:

• <span class=\"help-strong-dark\">Corrispettivi</span>: quadro ufficiale incassi
• <span class=\"help-strong-dark\">Incasso per categoria</span>: distribuzione per categorie servizi/prodotti
• <span class=\"help-strong-dark\">Passaggi cassa</span>: volumi e frequenza pagamenti
• <span class=\"help-strong-dark\">Clienti</span>: indicatori legati alla clientela
• <span class=\"help-strong-dark\">Operatori</span>: performance per operatore

Alcuni pulsanti sono visibili solo a ruoli abilitati (admin).""",
    },

    "report_esportazione_lettura": {
        "title": "🧠 Report: lettura dati ed esportazione",
        "content": """[[VIDEO|24]]

I report sono pensati per controllo giornaliero e analisi periodica.

Suggerimenti:
• confronta sempre periodo selezionato e giorno visualizzato
• usa i filtri per isolare categorie/operatori
• interpreta insieme KPI + dettaglio tabellare per decisioni operative

Quando disponibile, usa strumenti di esportazione/stampa in coerenza con i permessi del tuo ruolo.

Per invii amministrativi, usa sempre la vista Corrispettivi del periodo corretto prima dell'export.""",
    },

    # ========== TOOLS / SETTINGS ==========
    "tools_panorama": {
        "title": "🧰 Tools: guida completa tab per tab",
        "content": """La sezione Tools (Settings) contiene tutti i tab di configurazione del gestionale. Qui sotto trovi una guida completa con <span class=\"help-strong-dark\">una sottosezione per ogni tab</span>, spiegando le varie parti visibili in pagina e il loro uso pratico.

<span class=\"help-strong-dark help-subtitle-pill\">▸ OPERATORI</span>
In questo tab gestisci l'anagrafica del team e l'operatività in agenda.
• elenco operatori: tabella con i profili già inseriti
• campi anagrafici: nome, colore, stato attivo/non attivo
• visibilità in agenda: decide in quali viste compare l'operatore
• ordine di visualizzazione: posizione delle colonne in Agenda
• turni e memo: configurazioni utili a copertura oraria e promemoria interni
• azioni riga: modifica o eliminazione del singolo operatore

<span class=\"help-strong-dark help-subtitle-pill\">▸ SERVIZI</span>
Qui definisci tutto ciò che poi può essere venduto o prenotato.
• tabella servizi: catalogo dei trattamenti presenti
• creazione/modifica servizio: nome, durata, prezzo e descrizione
• classificazione: categoria e sottocategoria per analisi/report
• opzioni operative: attivo/non attivo, visibilità e ordinamento
• pulsanti azione: salva, aggiorna, elimina
• area ricerca/filtri (se presente): per trovare rapidamente un servizio

<span class=\"help-strong-dark help-subtitle-pill\">▸ CLIENTI</span>
Sezione dedicata alla base clienti e alla loro manutenzione.
• ricerca clienti: per nome, telefono o altri riferimenti
• elenco risultati: vista rapida con accesso diretto alla scheda
• scheda cliente: dati anagrafici, contatti, note e informazioni utili
• storico cliente: appuntamenti, passaggi e dati collegati
• strumenti operativi: modifica, eliminazione, eventuale esportazione

<span class=\"help-strong-dark help-subtitle-pill\">▸ WHATSAPP</span>
Tab disponibile quando è attivo il modulo dedicato.
• stato connessione: verifica se il canale è attivo
• area configurazione: parametri di collegamento e impostazioni invio
• template/messaggi: testi riutilizzabili per comunicazioni frequenti
• pulsanti test/invio: controllo rapido del funzionamento
• note operative: eventuali avvisi su modulo opzionale o permessi

<span class=\"help-strong-dark help-subtitle-pill\">▸ PACCHETTI</span>
Configurazione della struttura pacchetti prima della vendita.
• impostazioni generali: regole base dei pacchetti
• modelli preimpostati: strutture ricorrenti pronte all'uso
• parametri commerciali: sconti, rate, validità e logiche collegate
• testi e note standard: contenuti ricorrenti da riutilizzare
• controlli finali: verifica coerenza prima dell'uso in Cassa/Agenda

<span class=\"help-strong-dark help-subtitle-pill\">▸ MARKETING</span>
Tab dedicato alle comunicazioni promozionali e ai filtri contatto.
• editor messaggio: composizione contenuti campagna
• variabili dinamiche: personalizzazione automatica del testo
• filtri destinatari: selezione target clienti
• template salvati: riuso rapido di comunicazioni già pronte
• pulsanti invio/simulazione: controllo e lancio campagna

<span class=\"help-strong-dark help-subtitle-pill\">▸ INFO AZIENDA</span>
Raccoglie i dati identificativi del centro e alcune utilità di sistema.
• dati aziendali: ragione sociale, contatti, informazioni intestazione
• impostazioni documentali: dati usati in stampe e riepiloghi
• sezione aggiornamenti app: controllo versione e update (istanza locale)
• avvisi di stato: messaggi su aggiornamento disponibile o non disponibile
• azioni principali: salva dati e avvia controllo aggiornamenti

<span class=\"help-strong-dark help-subtitle-pill\">▸ BOOKING WEB</span>
Tab visibile ai ruoli abilitati, legato al <span class=\"help-strong-dark\">modulo opzionale Booking via Web</span>.
• attivazione/disattivazione: gestione disponibilità prenotazione online
• regole booking: vincoli, finestre e logiche di pubblicazione
• associazione servizi/operatori: cosa può essere prenotato online
• impostazioni operative: comportamento del flusso prenotazione web
• controlli finali: verifica configurazione prima di andare online

<span class=\"help-strong-dark help-subtitle-pill\">▸ UTENTI</span>
Tab visibile ai ruoli admin per accessi e sicurezza.
• elenco account: utenti attivi e relativi ruoli
• creazione utente: nuovo accesso con credenziali dedicate
• gestione ruolo: profilo user o admin in base alle responsabilità
• azioni amministrative: reset dati accesso, disattivazione, aggiornamenti
• principi consigliati: un account per persona, permessi minimi necessari

<span class=\"help-strong-dark help-subtitle-pill\">▸ CENTRO ASSISTENZA</span>
È il tab di supporto integrato in cui ti trovi ora.
• home categorie: ingresso rapido per area funzionale
• ricerca guide: campo di ricerca per parole chiave
• vista categoria: elenco argomenti correlati
• vista topic: pagina guida con navigazione precedente/successivo
• utilità finali: contatto supporto e riattivazione tour guidato

<div class=\"help-hint-box\">
<span class=\"help-hint-label\">Consiglio:</span>
<span class=\"help-hint-text\">Per una configurazione ordinata, segui questa sequenza: Operatori → Servizi → Clienti → Info Azienda → Utenti, poi completa i tab opzionali (WhatsApp, Pacchetti, Marketing, Booking Web).</span>
</div>""",
    },

    "tools_tab_operatori": {
        "title": "👩‍💼 OPERATORI: cosa trovi in pagina e come usarla",
        "content": """[[VIDEO|20]]

Questo tab serve per gestire persone e risorse che compaiono in Agenda.

<span class=\"help-strong-dark help-subtitle-pill\">▸ FORM "AGGIUNGI OPERATORE"</span>
Nella parte alta trovi il form di inserimento:
• tipo operatore (estetista o macchinario/solarium)
• nome
• cognome (mostrato per estetista)
• cellulare (mostrato per estetista)
• pulsante aggiunta

Il form adatta i campi in base al tipo selezionato: per i macchinari alcuni campi non sono richiesti.

<span class=\"help-strong-dark help-subtitle-pill\">▸ TABELLA OPERATORI</span>
Nella tabella centrale vedi:
• nome e cognome
• tipo
• cellulare (visibile in base al ruolo)
• flag <span class=\"help-strong-dark\">Visibile in Agenda</span>
• flag <span class=\"help-strong-dark\">Invia Memo turni</span> (quando applicabile)
• azioni: Modifica, Elimina, Turni

<span class=\"help-strong-dark help-subtitle-pill\">▸ COMANDI OPERATIVI IMPORTANTI</span>
• <span class=\"help-strong-dark\">Visibile in Agenda</span>: decide se l'operatore compare nelle colonne Agenda
• <span class=\"help-strong-dark\">Memo turni</span>: disponibile solo in condizioni valide (operatore idoneo, visibile e con numero)
• <span class=\"help-strong-dark\">Turni</span>: apre il modal per la gestione turni senza uscire dal tab

Per il dettaglio sui turni vedi anche: <span class=\"help-strong-dark\">[[IMPOSTARE I TURNI OPERATORI|agenda_turni]]</span>.

<span class=\"help-strong-dark help-subtitle-pill\">▸ PERMESSI</span>
In base al ruolo, alcune azioni possono essere limitate o mostrate in sola lettura (es. modifica/eliminazione).""",
    },

    "tools_tab_servizi": {
        "title": "💆 SERVIZI: form, tabella, descrizioni e sottocategorie",
        "content": """Questo tab gestisce il catalogo operativo usato in Agenda, Cassa, Report e moduli opzionali.

<span class=\"help-strong-dark help-subtitle-pill\">▸ FORM "AGGIUNGI SERVIZIO"</span>
Campi principali in alto:
• nome servizio
• abbreviazione/tag
• durata (in minuti, inclusa opzione senza durata)
• prezzo
• categoria
• sottocategoria
• pulsante Aggiungi Servizio

<span class=\"help-approfondimento-box\"><span class=\"help-approfondimento-label\">Approfondimento:</span><span class=\"help-approfondimento-text\"><br><span class=\"help-strong-dark\">1) CATEGORIE E SOTTOCATEGORIE</span><br>Le categorie ti aiutano a organizzare i servizi in macro-aree, mentre le sottocategorie servono per una classificazione più precisa (esempio: categoria Estetica, sottocategoria Manicure).<br>Usarle bene migliora velocità di ricerca, chiarezza in Cassa e lettura nei Report.<br><span class=\"help-strong-dark\">2) PRODOTTI vs SERVIZI</span><br>Un <span class=\"help-strong-dark\">servizio</span> normalmente ha durata e impatta la pianificazione Agenda.<br>Un <span class=\"help-strong-dark\">prodotto</span> non occupa tempo in Agenda (nessuna durata) ed è gestito come voce di vendita in Cassa.<br>Distinguere correttamente i due tipi evita errori in prenotazione, incasso e reportistica.</span></span>

<span class=\"help-strong-dark help-subtitle-pill\">▸ RICERCA SERVIZI</span>
Subito sotto trovi la casella di ricerca per nome o tag: utile quando il listino è ampio.

<span class=\"help-strong-dark help-subtitle-pill\">▸ TABELLA SERVIZI</span>
La tabella mostra:
• nome
• abbreviazione
• categoria
• sottocategoria
• durata
• prezzo
• azioni

Nelle azioni trovi:
• <span class=\"help-strong-dark\">Descrizione</span> (apre un modal editor del testo servizio)
• <span class=\"help-strong-dark\">Modifica</span>
• <span class=\"help-strong-dark\">Elimina</span> (eliminazione logica)

<span class=\"help-strong-dark help-subtitle-pill\">▸ GESTIONE SOTTOCATEGORIE</span>
Con il pulsante dedicato apri una sezione con:
• form creazione sottocategoria
• tabella sottocategorie esistenti
• eliminazione sottocategoria

<span class=\"help-strong-dark help-subtitle-pill\">▸ SCARICA LISTINO PREZZI</span>
In fondo pagina puoi esportare il listino in TXT/PDF, con opzione per includere le descrizioni.""",
    },

    "tools_tab_clienti": {
        "title": "👤 CLIENTI: inserimento, ricerca, note, storico e duplicati",
        "content": """Questo tab è il centro di gestione anagrafica clienti.

<span class=\"help-strong-dark help-subtitle-pill\">▸ FORM "AGGIUNGI NUOVO CLIENTE"</span>
In alto trovi il form con campi:
• nome (obbligatorio)
• cognome (obbligatorio)
• cellulare (obbligatorio)
• data di nascita
• email
• pulsante Aggiungi Cliente

Il salvataggio applica controlli: in particolare su nome/cognome/cellulare e verifica numero già presente.

<span class=\"help-strong-dark help-subtitle-pill\">▸ COME GESTISCE I DOPPI CELLULARI</span>
Il sistema controlla i duplicati sul numero normalizzato (es. varianti con spazi/prefisso) e, se trova un cliente già associato, blocca l'inserimento con messaggio di avviso.

<span class=\"help-strong-dark help-subtitle-pill\">▸ CASELLA "CERCA CLIENTI REGISTRATI"</span>
Nella ricerca sotto al form puoi filtrare rapidamente la tabella clienti (nome/cognome e dati utili alla selezione veloce).

<span class=\"help-strong-dark help-subtitle-pill\">▸ TABELLA CLIENTI: DATI VISUALIZZATI</span>
La tabella mostra colonne come:
• nome, cognome, cellulare
• email
• data nascita
• sesso
• data creazione
• passaggi
• ultimo passaggio
• azioni

<span class=\"help-strong-dark help-subtitle-pill\">▸ AZIONI SU OGNI CLIENTE</span>
• <span class=\"help-strong-dark\">Modifica</span>: apre la scheda di editing completa
• <span class=\"help-strong-dark\">Elimina</span>: rimozione logica del cliente (soft delete)
• <span class=\"help-strong-dark\">Note</span>: apre modal dedicato note cliente
• <span class=\"help-strong-dark\">Storico</span>: apre modal appuntamenti storici del cliente

<span class=\"help-strong-dark help-subtitle-pill\">▸ PERMESSI</span>
Le azioni possono variare in base al ruolo attivo (utente operativo o amministrativo). Se non hai diritti su un comando, va richiesto adeguamento permessi all'admin.""",
    },

    "tools_tab_whatsapp": {
        "title": "💬 WHATSAPP: connessione, test e uso operativo",
        "content": """Questo tab è dedicato al <span class=\"help-strong-dark\">modulo opzionale WhatsApp</span>.

<span class=\"help-strong-dark help-subtitle-pill\">▸ PARTI PRINCIPALI DELLA PAGINA</span>
• stato connessione canale
• parametri di collegamento/configurazione
• pulsanti di connessione/disconnessione/test
• aree informative su stato sessione e errori

<span class=\"help-strong-dark help-subtitle-pill\">▸ COSA SI PUÒ FARE DA QUI</span>
• avviare o verificare la connessione
• controllare che il canale sia pronto all'invio
• diagnosticare problemi di sessione

Per i flussi completi di messaggistica e automazioni vai anche a:
• <span class=\"help-strong-dark\">[[WHATSAPP: PANORAMICA|whatsapp_panorama]]</span>
• <span class=\"help-strong-dark\">[[WHATSAPP: CONNESSIONE|whatsapp_connect]]</span>
• <span class=\"help-strong-dark\">[[WHATSAPP: TEMPLATE|whatsapp_messaggi_template]]</span>
• <span class=\"help-strong-dark\">[[WHATSAPP: AUTOMAZIONI|whatsapp_auto]]</span>""",
    },

    "tools_tab_pacchetti": {
        "title": "🎁 PACCHETTI: configurazioni prima della vendita",
        "content": """Questo tab prepara tutte le regole che poi userai quando crei e vendi pacchetti.

<span class=\"help-strong-dark help-subtitle-pill\">▸ PARTI DELLA PAGINA</span>
• impostazioni generali pacchetti
• modelli e promo salvate
• parametri commerciali e condizioni
• sezioni di testo/controindicazioni/template
• tooltip esplicativi sui campi più delicati

<span class=\"help-strong-dark help-subtitle-pill\">▸ COSA SI PUÒ FARE</span>
• creare strutture standard riutilizzabili
• impostare regole coerenti per vendita e gestione
• uniformare testi e condizioni operative
• velocizzare il lavoro in Cassa/Pacchetti

Approfondimenti:
• <span class=\"help-strong-dark\">[[TOOLS / PACCHETTI: IMPOSTAZIONI|pacchetto_settings]]</span>
• <span class=\"help-strong-dark\">[[CONFIGURAZIONE PACCHETTI|pacchetto_tools_settings]]</span>
• <span class=\"help-strong-dark\">[[CREARE PACCHETTO|pacchetto_create]]</span>""",
    },

    "tools_tab_marketing": {
        "title": "📣 MARKETING: campagne, filtri e template",
        "content": """Questo tab raccoglie gli strumenti per comunicazioni mass marketing ai clienti.

<span class=\"help-strong-dark help-subtitle-pill\">▸ PARTI DELLA PAGINA</span>
• editor messaggio
• filtri destinatari
• variabili dinamiche
• gestione template salvati
• pulsanti anteprima/invio

<span class=\"help-strong-dark help-subtitle-pill\">▸ COSA SI PUÒ FARE</span>
• preparare messaggi promozionali riutilizzabili
• inviare comunicazioni segmentate per target
• personalizzare i testi con variabili cliente
• mantenere uno storico template interno

Approfondimenti:
• <span class=\"help-strong-dark\">[[MARKETING: PANORAMICA|marketing_panorama]]</span>
• <span class=\"help-strong-dark\">[[MARKETING: INVIO|marketing_send]]</span>
• <span class=\"help-strong-dark\">[[MARKETING: VARIABILI|marketing_variables]]</span>
• <span class=\"help-strong-dark\">[[MARKETING: FILTRI E TEMPLATE|marketing_filtri_template]]</span>""",
    },

    "tools_tab_info_azienda": {
        "title": "🏢 INFO AZIENDA: dati impresa, touch e aggiornamenti",
        "content": """[[VIDEO|25]]

Questo tab contiene i dati identificativi dell'attività e impostazioni tecniche locali.

<span class=\"help-strong-dark help-subtitle-pill\">▸ DATI AZIENDALI</span>
Qui compili/aggiorni informazioni anagrafiche dell'azienda usate nel gestionale e in varie stampe.

I campi aziendali sono modificabili dagli utenti con ruolo <span class=\"help-strong-dark\">admin</span>. Alcuni dati (es. <span class=\"help-strong-dark\">nome attività</span>, <span class=\"help-strong-dark\">email</span>, <span class=\"help-strong-dark\">sito web</span>) possono comparire anche nei documenti prodotti da Tosca e, se attivo il modulo online, nel sito di Booking Web visibile ai clienti.

Per questo è importante inserire diciture esatte e professionali (evita abbreviazioni casuali o refusi).

<span class=\"help-strong-dark help-subtitle-pill\">▸ LOGO NEGOZIO</span>
In questa sezione puoi caricare/aggiornare il <span class=\"help-strong-dark\">logo del negozio</span>.

Se è attivo il modulo Booking Web, il logo può essere mostrato anche nel sito prenotazioni cliente.

<span class=\"help-strong-dark help-subtitle-pill\">▸ ORARI ISTITUTO</span>
Qui compili/aggiorni gli <span class=\"help-strong-dark\">orari di apertura e chiusura dell'istituto</span>, utilizzati nel gestionale e nelle comunicazioni ai clienti, oltre che gli orari di apertura e chiusura e le ore visualizzate nella pagina Agenda.

<span class=\"help-strong-dark help-subtitle-pill\">▸ STAMPANTE FISCALE: IP E PING RCH</span>
Nel tab trovi anche i campi tecnici legati alla stampante fiscale, in particolare:
• <span class=\"help-strong-dark\">IP stampante fiscale</span>
• test di connessione / <span class=\"help-strong-dark\">Ping RCH</span>

Questi controlli servono per verificare rapidamente se la stampante risponde in rete prima di operazioni fiscali in Cassa.

<span class=\"help-strong-dark help-subtitle-pill\">▸ OPZIONE TOUCH (LOCALE)</span>
Nel tab è presente la configurazione della modalità touch per Agenda (utile su schermi touch).
Per il dettaglio operativo: <span class=\"help-strong-dark\">[[AGENDA MODALITÀ TOUCH|agenda_touch_mode]]</span>.

<span class=\"help-strong-dark help-subtitle-pill\">▸ AGGIORNAMENTI APP</span>
In questa pagina trovi anche la sezione aggiornamenti locali con controllo versione, note rilascio e avvio update.
Trovi istruzioni e pulsanti direttamente in questa sezione della pagina.

<span class=\"help-strong-dark help-subtitle-pill\">▸ BUONA PRATICA</span>
Aggiorna i dati aziendali prima di attivare nuovi moduli e pianifica gli update in orari di bassa operatività.""",
    },

    "tools_tab_centro_assistenza": {
        "title": "🆘 CENTRO ASSISTENZA: come usare bene le guide",
        "content": """[[VIDEO|26]]

Questo tab apre il sistema guida integrato dell'applicazione.

<span class=\"help-strong-dark help-subtitle-pill\">▸ HOME GUIDE</span>
Mostra le categorie principali (Agenda, Cassa, Report, Tools, ecc.).

<span class=\"help-strong-dark help-subtitle-pill\">▸ RICERCA</span>
La barra cerca parole chiave in tutti i topic e porta direttamente al risultato utile.

<span class=\"help-strong-dark help-subtitle-pill\">▸ NAVIGAZIONE PER CATEGORIA</span>
Aprendo una categoria, trovi la lista topic e puoi entrare nel dettaglio di ogni guida.

<span class=\"help-strong-dark help-subtitle-pill\">▸ PAGINA TOPIC</span>
Ogni guida ha:
• titolo e contenuto
• navigazione precedente/successivo
• eventuale condivisione WhatsApp del topic

<span class=\"help-strong-dark help-subtitle-pill\">▸ UTILITY FINALI</span>
In home trovi anche:
• contatto supporto
• riattivazione tour guidato""",
    },

    "tools_tab_booking_web": {
        "title": "🌐 BOOKING WEB: setup modulo prenotazione online",
        "content": """Tab visibile a ruoli abilitati (admin) e legato al <span class=\"help-strong-dark\">modulo opzionale Booking via Web</span>.

<span class=\"help-strong-dark help-subtitle-pill\">▸ PARTI DELLA PAGINA</span>
• configurazione generale booking online
• regole e vincoli prenotazione
• tabella servizi pubblicabili
• associazione operatori ai servizi pubblicati
• controlli stato e salvataggio

<span class=\"help-strong-dark help-subtitle-pill\">▸ COSA SI PUÒ FARE</span>
• decidere cosa rendere prenotabile online
• impostare regole coerenti con Agenda interna
• verificare che i servizi online abbiano operatori associati

<span class=\"help-strong-dark help-subtitle-pill\">▸ MENU SCELTA SERVIZIO NEL BOOKING</span>
Nel menu di scelta servizio della pagina di prenotazione vengono visualizzate anche le <span class=\"help-strong-dark\">informazioni del servizio</span>.
Queste informazioni si inseriscono/modificano in <span class=\"help-strong-dark\">Tools / Servizi</span> (campo descrizione servizio).

Approfondimenti:
• <span class=\"help-strong-dark\">[[BOOKING WEB: SETUP|booking_setup]]</span>
• <span class=\"help-strong-dark\">[[BOOKING WEB: REGOLE|booking_rules]]</span>
• <span class=\"help-strong-dark\">[[BOOKING WEB: SERVIZI E OPERATORI|booking_servizi_operatori]]</span>
&nbsp;""",
    },

    "tools_tab_utenti": {
        "title": "👥 UTENTI: account, ruoli, password e cancellazione",
        "content": """[[VIDEO|27]]

Questo tab è dedicato alla gestione accessi applicazione.

<span class=\"help-strong-dark help-subtitle-pill\">▸ TABELLA UTENTI</span>
Mostra account esistenti con ruolo assegnato e principali azioni disponibili.

<span class=\"help-strong-dark help-subtitle-pill\">▸ AGGIUNTA UTENTE</span>
Con il form dedicato puoi creare nuovi account e assegnare un ruolo.

<span class=\"help-strong-dark help-subtitle-pill\">▸ GESTIONE RUOLI E LIMITI</span>
Le azioni dipendono dal ruolo di chi opera:
• admin: permessi estesi con limiti su alcune operazioni sensibili
• user: accesso operativo limitato

<span class=\"help-strong-dark help-subtitle-pill\">▸ AZIONI DISPONIBILI</span>
• cambio password utente
• eliminazione account (se consentita dal ruolo)
• revisione ruoli in ottica sicurezza

Guida collegata:
• <span class=\"help-strong-dark\">[[UTENTI, RUOLI E ACCESSI ADMIN|tools_users_ruoli]]</span>""",
    },

    "tools_clienti_servizi_operatori": {
        "title": "⚙️ Tools: clienti, servizi, operatori",
        "content": """In questa parte di Tools gestisci gli elementi che usi tutti i giorni.

    <span class="help-strong-dark">Clienti</span>
    • ricerca, modifica, note, storico, export

    <span class="help-strong-dark">Servizi</span>
    • nome, tag, durata, prezzo, categorie, sottocategorie, descrizioni

    <span class="help-strong-dark">Operatori</span>
    • anagrafica, visibilità, ordine, memo turni, turni operativi

    Ogni modifica qui ha effetto diretto sui flussi quotidiani del centro.""",
    },

    "tools_info_azienda_utenti": {
        "title": "🏢 Tools: Info Azienda, utenti e permessi",
        "content": """Da questa area puoi configurare:

    • <span class="help-strong-dark">Info Azienda</span>: dati centro, informazioni usate nei documenti e nelle integrazioni
    • <span class="help-strong-dark">Utenti</span>: creazione account e assegnazione ruolo (solo admin)

    I ruoli influenzano ciò che ogni persona può vedere o fare, ad esempio in Cassa, Report e negli strumenti fiscali avanzati.

    <span class="help-strong-dark">Differenze pratiche tra ruoli</span>
    • <span class="help-strong-dark">user</span>: operatività quotidiana con funzioni limitate
    • <span class="help-strong-dark">admin</span>: accesso esteso a configurazioni, utenti, strumenti fiscali e funzioni avanzate

    Buona pratica CRM: assegna permessi minimi necessari per ruolo, evitando account condivisi.""",
        },

    "tools_users_ruoli": {
        "title": "👥 Tools: utenti, ruoli e accessi admin",
        "content": """La gestione utenti è un punto chiave per sicurezza e tracciabilità operativa.

<span class="help-strong-dark help-subtitle-pill">▸ CHI FA COSA</span>
• <span class="help-strong-dark">user</span>: usa il gestionale nelle attività quotidiane con accesso controllato
• <span class="help-strong-dark">admin</span>: può configurare utenti, permessi, impostazioni critiche e funzioni avanzate

<span class="help-strong-dark help-subtitle-pill">▸ PERCHÉ È IMPORTANTE</span>
Nei CRM moderni la separazione ruoli riduce errori, migliora audit e aumenta sicurezza dati.

<span class="help-strong-dark help-subtitle-pill">▸ BEST PRACTICE CONSIGLIATE</span>
• un account per ogni persona (no account condivisi)
• permessi minimi necessari (principio del minimo privilegio)
• revisione periodica degli accessi attivi
• disattivazione rapida utenti non più operativi""",
    },

    "tools_touch_updates": {
        "title": "🆕 Tools: aggiornamenti app",
        "content": """In <span class=\"help-strong-dark\">Tools → Info Azienda</span> trovi la sezione <span class=\"help-strong-dark\">Aggiornamenti App</span> (istanza locale).

<span class=\"help-strong-dark help-subtitle-pill\">▸ AGGIORNAMENTI APP: COME FUNZIONA</span>
Nella sezione <span class=\"help-strong-dark\">Aggiornamenti App</span> (istanza locale) trovi:
• versione attuale
• pulsante <span class=\"help-strong-dark\">Controlla aggiornamenti</span>
• se disponibile, pulsante <span class=\"help-strong-dark\">Aggiorna ora</span>
• note di rilascio e stato download/installazione

Messaggi tipici:
• nessun aggiornamento disponibile
• sei già alla versione più recente
• aggiornamento disponibile ma file non trovato (contattare supporto)

<span class=\"help-strong-dark help-subtitle-pill\">▸ COSA FARE QUANDO C'È UN AGGIORNAMENTO</span>
Flusso consigliato:
1️⃣ clicca <span class=\"help-strong-dark\">Controlla aggiornamenti</span>
2️⃣ leggi versione e note rilascio
3️⃣ clicca <span class=\"help-strong-dark\">Aggiorna ora</span> e conferma
4️⃣ attendi download e installazione automatica
5️⃣ quando l'app si chiude, attendi circa 1 minuto e riavvia Tosca

Se la finestra non si chiude entro ~30 secondi, chiudila manualmente come indicato nel messaggio a schermo.

<div class=\"help-hint-box\">
<span class=\"help-hint-label\">Consiglio:</span>
<span class=\"help-hint-text\">Esegui gli aggiornamenti in un momento di bassa operatività (es. fine giornata), così eviti interruzioni durante il lavoro in Agenda/Cassa.</span>
</div>""",
    },

        "tools_workflow_consigliato": {
        "title": "🧭 Tools: ordine consigliato di configurazione",
        "content": """Se stai configurando Tosca da zero, l'ordine più sensato è questo:

    1️⃣ crea gli operatori
    2️⃣ inserisci i servizi con durata e categoria
    3️⃣ carica i clienti principali
    4️⃣ completa le info aziendali
    5️⃣ crea gli utenti con i ruoli corretti

    Seguendo questo ordine eviti configurazioni parziali e fai partire più velocemente Agenda e Cassa.

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Documenta questa sequenza in una checklist interna: accelera onboarding di nuovi collaboratori e nuove aperture.</span>
</div>""",
    },

    # ========== GENERALI ==========
    "generali_panorama": {
        "title": "ℹ️ Generali: panoramica rapida",
        "content": """La sezione Generali raccoglie informazioni varie, utili a tutto il team:

• credits e contatti
• informazioni tecniche di base
• note operative su installazione/hosting

Questa sezione è pensata per onboarding un rapido e un successivo allineamento interno.""",
    },

    "generali_crediti_tecnica_hosting": {
        "title": "🧩 Generali: credits, info tecniche e hosting",
        "content": """<span class="help-strong-dark help-subtitle-pill">▸ CREDITS E SUPPORTO</span>
Tosca è stato sviluppato da Alessio Budetta, gestore di centri estetici e programmatore, a partire dal 2024.

<span class="help-strong-dark help-subtitle-pill">▸ INFO TECNICHE (ALTO LIVELLO)</span>
Tosca segue logiche tipiche dei CRM moderni:
• separazione tra moduli operativi (Agenda, Cassa, Report, Tools)
• gestione ruoli/permessi
• software on-premise (locale) o cloud (web), con sincronizzazione dati sempre in cloud (web)

<span class="help-strong-dark help-subtitle-pill">▸ DOVE È HOSTATO</span>
I database e la web app di Tosca sono hostati su server professionali, con salvataggio dati giornalieri.
""",
    },

    # ========== BOOKING VIA WEB - APPROFONDIMENTI OPERATIVI ==========
    "booking_logica_slot": {
        "title": "🧮 Come Tosca calcola gli slot disponibili online",
        "content": """Quando un cliente apre la pagina di prenotazione e sceglie data e servizi, Tosca calcola in tempo reale gli orari proponibili. Capire questa logica aiuta a impostare correttamente turni, servizi e operatori.

<span class="help-strong-dark help-subtitle-pill">▸ PUNTO DI PARTENZA: TURNI DEL GIORNO</span>
Il sistema parte dai <span class="help-strong-dark">turni di tutti gli operatori visibili</span> per la data scelta, intersecati con gli <span class="help-strong-dark">orari di apertura e chiusura</span> dell'istituto. Se un operatore non ha un turno specifico per quel giorno, viene considerato in turno per l'intera fascia di apertura.

I <span class="help-strong-dark">giorni di chiusura</span> impostati per il negozio escludono completamente la data: nessuno slot viene proposto.

<span class="help-strong-dark help-subtitle-pill">▸ FILTRI DI ESCLUSIONE</span>
Su ogni intervallo di turno il sistema scarta le finestre occupate:
• <span class="help-strong-dark">blocchi OFF globali</span> (senza operatore) → bloccano tutte le colonne
• <span class="help-strong-dark">blocchi OFF di un singolo operatore</span> → bloccano solo quella colonna
• <span class="help-strong-dark">appuntamenti già esistenti</span> sulla colonna dell'operatore
• <span class="help-strong-dark">appuntamenti cancellati</span> (soft-delete) non bloccano lo slot

<span class="help-strong-dark help-subtitle-pill">▸ SOLO SERVIZI E OPERATORI ABILITATI</span>
Vengono considerati solo i servizi con flag <span class="help-strong-dark">"visibile online"</span> e con <span class="help-strong-dark">operatori associati</span>. Un servizio pubblicato senza operatori abilitati non produce slot.

<span class="help-strong-dark help-subtitle-pill">▸ DURATA TOTALE E PASSO 15 MINUTI</span>
Se il cliente seleziona più servizi, la durata richiesta è la <span class="help-strong-dark">somma di tutte le durate</span>. Lo slot viene proposto solo se l'intera catena entra in un intervallo libero. Il passo di scansione è di <span class="help-strong-dark">15 minuti</span>.

<span class="help-strong-dark help-subtitle-pill">▸ DUE STRATEGIE DI ASSEGNAZIONE OPERATORI</span>
Per ogni slot candidato Tosca prova due strategie, in ordine di priorità:

1️⃣ <span class="help-strong-dark">Stesso operatore per tutti i servizi</span> (preferita)
Cerca un operatore abilitato a tutti i servizi richiesti e libero per l'intera catena. È il caso più comodo per il cliente.

2️⃣ <span class="help-strong-dark">A cascata</span> (fallback)
Se nessun singolo operatore copre tutto, assegna servizio per servizio cercando di rimanere sulla <span class="help-strong-dark">stessa colonna</span> del servizio precedente quando possibile. Se anche questo fallisce su un servizio, lo slot non viene proposto.

<span class="help-strong-dark help-subtitle-pill">▸ OPERATORE PREFERITO DAL CLIENTE</span>
Se il cliente sceglie esplicitamente un operatore per uno o più servizi, lo slot è valido <span class="help-strong-dark">solo</span> se la sequenza calcolata combacia con le preferenze. Le altre colonne non vengono nemmeno considerate per quei servizi.

<span class="help-strong-dark help-subtitle-pill">▸ FILTRO ORARI PASSATI</span>
Se la data scelta è oggi, vengono nascosti gli slot la cui partenza è già passata. Le date passate restituiscono sempre lista vuota.

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Se un cliente lamenta "non vedo orari disponibili" controlla in ordine: 1) il giorno è chiusura? 2) gli operatori hanno turno? 3) i servizi sono visibili online e hanno operatori associati? 4) la durata totale richiesta entra in un buco libero?</span>
</div>""",
    },

    "booking_codice_conferma_e_limiti": {
        "title": "🔐 Codice email, limiti e annullamento prenotazione",
        "content": """Per evitare abusi e prenotazioni accidentali, il portale online applica diversi controlli prima e dopo la prenotazione.

<span class="help-strong-dark help-subtitle-pill">▸ CODICE DI CONFERMA VIA EMAIL</span>
Quando il cliente compila nome, cognome, telefono e email, deve premere <span class="help-strong-dark">"Invia codice di conferma"</span>: Tosca genera un codice numerico a 6 cifre e lo spedisce all'indirizzo email indicato.

Regole sul codice:
• validità <span class="help-strong-dark">10 minuti</span> dall'invio
• per inviare un nuovo codice c'è un <span class="help-strong-dark">cooldown di 5 minuti</span>
• dopo il <span class="help-strong-dark">2° tentativo</span> ravvicinato, il sistema blocca ulteriori invii fino allo scadere del cooldown
• il codice è legato alla coppia codice ↔ email: se il cliente cambia email deve richiederne uno nuovo

<span class="help-strong-dark help-subtitle-pill">▸ LIMITE PRENOTAZIONI RAVVICINATE</span>
A protezione del centro, Tosca accetta al massimo <span class="help-strong-dark">3 prenotazioni complete ogni 4 minuti</span> sul portale (per tutto il negozio). Oltre questa soglia, il cliente vede un messaggio che indica fra quanti minuti potrà riprovare. È una difesa contro bot e click ripetuti, non un limite del cliente singolo.

<span class="help-strong-dark help-subtitle-pill">▸ REGOLE DURATA E PREZZO</span>
Se in <span class="help-strong-dark">[[REGOLE PRENOTAZIONE|booking_rules]]</span> hai impostato un limite di durata o prezzo:
• tipo <span class="help-strong-dark">warning</span> → il cliente vede un alert ma può proseguire
• tipo <span class="help-strong-dark">block</span> → il sistema rifiuta la prenotazione mostrando il messaggio configurato

<span class="help-strong-dark help-subtitle-pill">▸ EMAIL DOPO LA PRENOTAZIONE</span>
A prenotazione conclusa, Tosca invia due email:
• al <span class="help-strong-dark">cliente</span> → "richiesta ricevuta" con dettagli appuntamenti, totale durata, totale costo e link di annullamento
• al <span class="help-strong-dark">centro</span> (email dell'azienda) → notifica con nome cliente e riepilogo

Importante: l'email al cliente parla di <span class="help-strong-dark">richiesta</span>, non di conferma automatica. Sarà il centro a confermare via WhatsApp o telefono.

<span class="help-strong-dark help-subtitle-pill">▸ ANNULLAMENTO DA PARTE DEL CLIENTE</span>
Nell'email di conferma il cliente trova un <span class="help-strong-dark">link di annullamento</span> univoco. Cliccandolo:
1️⃣ vede la pagina di conferma con data e ora del primo appuntamento
2️⃣ deve premere <span class="help-strong-dark">"Conferma annullamento"</span>
3️⃣ tutti gli appuntamenti <span class="help-strong-dark">futuri</span> della stessa sessione di prenotazione vengono cancellati (soft-delete)
4️⃣ il centro riceve un'email automatica di notifica dell'annullamento

Gli appuntamenti già passati al momento del click non vengono toccati. Se il link è stato già usato o non esiste, il cliente vede "Link non valido o già usato".

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Se un cliente ti dice che non riceve il codice email, fai controllare lo spam e ricorda il cooldown di 5 minuti tra un invio e l'altro. Se l'email è stata digitata male non c'è modo di recuperare: deve ripartire dalla pagina.</span>
</div>""",
    },

    "booking_pagina_pubblica": {
        "title": "📱 Cosa vede il cliente sulla pagina di prenotazione",
        "content": """[[VIDEO|40]]

La pagina di prenotazione pubblica è ciò che il cliente apre dal link <span class="help-strong-dark">[[PAGINA PRENOTAZIONI|tools_tab_booking_web]]</span>. Conoscere il flusso aiuta a guidare i clienti al telefono.

<span class="help-strong-dark help-subtitle-pill">▸ INTESTAZIONE NEGOZIO</span>
In alto compaiono:
• <span class="help-strong-dark">logo</span> del centro (se caricato e con visibilità attiva nel booking)
• <span class="help-strong-dark">nome azienda</span>
• <span class="help-strong-dark">indirizzo</span>, eventuale città e <span class="help-strong-dark">telefono</span>

Questi dati arrivano da <span class="help-strong-dark">[[INFO AZIENDA|tools_tab_info_azienda]]</span>: se mancano o sono incompleti, mancheranno anche nella pagina pubblica.

<span class="help-strong-dark help-subtitle-pill">▸ FLUSSO DI PRENOTAZIONE A TAPPE</span>
La pagina si compone in modo guidato, mostrando un passo alla volta:

1️⃣ <span class="help-strong-dark">Scelta servizio</span> → cerca per nome o sfoglia per sottocategoria. Cliccando "i" si apre la descrizione del servizio.
2️⃣ <span class="help-strong-dark">Scelta operatore</span> → "Qualsiasi" oppure operatrice specifica fra quelle abilitate al servizio
3️⃣ <span class="help-strong-dark">Aggiungi altro servizio</span> (opzionale) → si possono accodare più servizi, ognuno con la sua operatrice preferita
4️⃣ <span class="help-strong-dark">Data</span> → calendario con minimo "oggi"
5️⃣ <span class="help-strong-dark">Orario</span> → si popola con gli slot calcolati come spiegato in <span class="help-strong-dark">[[LOGICA SLOT|booking_logica_slot]]</span>
6️⃣ <span class="help-strong-dark">Dati cliente</span> → nome, cognome, telefono, email
7️⃣ <span class="help-strong-dark">Codice di conferma</span> → vedi <span class="help-strong-dark">[[CODICE E LIMITI|booking_codice_conferma_e_limiti]]</span>
8️⃣ <span class="help-strong-dark">Conferma prenotazione</span>

<span class="help-strong-dark help-subtitle-pill">▸ ALERT REGOLE</span>
Se sono attive regole di durata o prezzo (tipo "warning" o "block"), gli alert vengono mostrati in pagina con il <span class="help-strong-dark">messaggio personalizzato</span> impostato dal centro.

<span class="help-strong-dark help-subtitle-pill">▸ PRIVACY E CONDIZIONI</span>
La pagina ha link a <span class="help-strong-dark">Informativa Privacy</span> e <span class="help-strong-dark">Condizioni di Vendita</span> precompilati con i dati del negozio. Proseguendo con la prenotazione, il cliente le accetta implicitamente.

<span class="help-strong-dark help-subtitle-pill">▸ COSA NON VEDE IL CLIENTE</span>
• operatori marcati come <span class="help-strong-dark">non visibili</span> in Tosca
• operatori di tipo <span class="help-strong-dark">macchinario</span> nella selezione per servizi estetici
• servizi senza flag <span class="help-strong-dark">visibile online</span>
• servizi senza operatori associati al booking

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Compila bene la descrizione dei servizi: è ciò che il cliente legge cliccando la "i" prima di prenotare. Un servizio ben descritto riduce le richieste telefoniche di chiarimento.</span>
</div>""",
    },

    "booking_appuntamenti_in_agenda": {
        "title": "🔵 Come appaiono in Agenda le prenotazioni dal web",
        "content": """[[VIDEO|41]]

Le prenotazioni create dal portale online compaiono in Agenda con caratteristiche specifiche, per distinguerle subito da quelle inserite manualmente.

<span class="help-strong-dark help-subtitle-pill">▸ COLORE BLU</span>
Tutti gli appuntamenti provenienti dal Booking via Web sono di default <span class="help-strong-dark">blu</span>. Il colore è ricavato dalla sorgente dell'appuntamento (`web`) e ti aiuta a riconoscerli a colpo d'occhio.

<span class="help-strong-dark help-subtitle-pill">▸ CLIENTE FITTIZIO "BOOKING ONLINE"</span>
Finché il cliente non viene riconosciuto e riassegnato, l'appuntamento è intestato al cliente fittizio <span class="help-strong-dark">BOOKING ONLINE</span>. I dati veri del cliente sono nella <span class="help-strong-dark">nota appuntamento</span>:
"PRENOTATO DA BOOKING ONLINE - Nome: …, Cognome: …, Telefono: …, Email: … - ha selezionato l'operatrice? Sì/No"

Per assegnare l'appuntamento all'anagrafica reale, clicca sul nome del cliente nel blocco e seleziona la persona corretta (o creala al volo). Da quel momento l'appuntamento è collegato a un cliente vero.

<span class="help-strong-dark help-subtitle-pill">▸ DICITURA "NUOVO CLIENTE"</span>
Quando un cliente prenota online per la prima volta e poi lo riassegni a una nuova anagrafica, sopra il blocco compare la nota automatica <span class="help-strong-dark">NUOVO CLIENTE</span>, per ricordare a chi è in turno che è una prima visita.

<span class="help-strong-dark help-subtitle-pill">▸ CATENA MULTI-SERVIZIO</span>
Se il cliente ha prenotato più servizi, in Agenda compaiono tanti blocchi quanti sono i servizi, contigui e collegati dalla stessa <span class="help-strong-dark">sessione di prenotazione</span>. Cancellando uno solo dei blocchi gli altri restano: per disdire l'intera sessione c'è il link nell'email del cliente.

<span class="help-strong-dark help-subtitle-pill">▸ COSA FARE AL MATTINO</span>
1️⃣ scorri l'Agenda del giorno e individua i blocchi blu
2️⃣ verifica le note: nome, cognome, telefono
3️⃣ se è un cliente già esistente, riassegna l'appuntamento all'anagrafica giusta
4️⃣ se è un cliente nuovo, crea l'anagrafica e riassegna
5️⃣ chiama o manda un WhatsApp per confermare definitivamente

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Il booking online genera "richieste", non conferme automatiche: prendi l'abitudine di sbloccare i blocchi blu ogni mattina prima dell'apertura, così non rischi di dimenticare di confermare al cliente.</span>
</div>""",
    },

    # ========== WHATSAPP - APPROFONDIMENTO MEMO MATTUTINO ==========
    "whatsapp_memo_clienti_mattino": {
        "title": "🌅 WhatsApp: memo mattutino ai clienti del giorno",
        "content": """[[VIDEO|35]]

Se è attivo il modulo WhatsApp, Tosca può inviare automaticamente a ogni cliente che ha appuntamento oggi un messaggio promemoria, partendo da un orario configurabile.

<span class="help-strong-dark help-subtitle-pill">▸ COSA SERVE PER ATTIVARLO</span>
Dal pannello WhatsApp imposta:
• <span class="help-strong-dark">attivazione</span> del memo mattutino
• <span class="help-strong-dark">orario di partenza</span> (es. 08:00)
• <span class="help-strong-dark">template messaggio</span> con le variabili

<span class="help-strong-dark help-subtitle-pill">▸ COME VIENE COSTRUITA LA CODA</span>
All'orario configurato, Tosca prepara la lista dei clienti da contattare oggi:
• prende tutti gli appuntamenti del giorno
• <span class="help-strong-dark">esclude</span> blocchi OFF, blocchi tecnici e cliente fittizio "BOOKING ONLINE"
• <span class="help-strong-dark">deduplica</span> blocchi contigui dello stesso cliente (un solo messaggio per persona, anche se ha più servizi accodati)
• prende <span class="help-strong-dark">sempre il cellulare dall'anagrafica</span> del cliente, non dalla nota

<span class="help-strong-dark help-subtitle-pill">▸ INVIO 1 MESSAGGIO AL MINUTO</span>
Per non saturare WhatsApp e ridurre il rischio di blocchi anti-spam, Tosca invia <span class="help-strong-dark">un messaggio al minuto</span> fino a esaurire la coda. La coda viene costruita una sola volta al giorno, al minuto del reminder; se il sistema viene riavviato dopo, riprende automaticamente dal punto in cui era.

<span class="help-strong-dark help-subtitle-pill">▸ VARIABILI DISPONIBILI NEL TEMPLATE</span>
Nel testo puoi usare:
• <span class="help-strong-dark">{{nome}}</span> → nome del cliente (capitalizzato)
• <span class="help-strong-dark">{{cognome}}</span>
• <span class="help-strong-dark">{{data}}</span> → DD/MM/YYYY
• <span class="help-strong-dark">{{ora}}</span> → HH:MM del primo blocco
• <span class="help-strong-dark">{{servizi}}</span> → lista puntata dei servizi del blocco contiguo
• <span class="help-strong-dark">{{azienda}}</span> o <span class="help-strong-dark">{{nome_istituto}}</span> → ragione sociale
• <span class="help-strong-dark">{{sito}}</span> → sito web del centro

<span class="help-strong-dark help-subtitle-pill">▸ CHI NON RICEVE IL MEMO</span>
• clienti senza cellulare nell'anagrafica (campo vuoto o "000000000")
• appuntamenti OFF o tecnici
• prenotazioni online ancora intestate al cliente fittizio "BOOKING ONLINE" (riassegna l'anagrafica prima del memo)

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Imposta l'orario di invio almeno 2-3 ore prima del primo appuntamento, così anche l'ultimo della coda riceve il memo con anticipo utile. Verifica sempre i numeri sulle anagrafiche: il memo legge da lì, non dalla nota dell'appuntamento.</span>
</div>""",
    },
}

def get_help(topic):
    """Restituisce il contenuto help per un argomento specifico"""
    return HELP_TOPICS.get(topic, {
        "title": "🤔 Aiuto",
        "content": "Contenuto non disponibile per questo argomento. Contatta il supporto!",
    })

def get_all_topics():
    """Restituisce tutti gli argomenti help"""
    return HELP_TOPICS

# filepath: c:\Program Files\SunBooking\appl\routes\help.py
def get_topics_by_category():
    """Restituisce gli argomenti organizzati per categoria"""
    return {
        "Agenda": [
            "calendar_create_appointment",
            "client_search",
            "client_history",
            "calendar_block_buttons",
            "agenda_turni",
            "calendar_drag",
            "calendar_status",
            "calendar_note",
            "calendar_paid_block",
            "calendar_off_block"
        ],
        "Cassa": [
            "cassa_filtri_ricerca",
            "cassa_myspia_save_reset",
            "cassa_registro_ruoli",
            "cassa_strumenti_fiscali_rch",
            "cassa_blocchi_appuntamento"
        ],
        "Report": [
            "report_navigazione_filtri",
            "report_sezioni_principali",
            "report_previsioni_tile_edit",
            "report_corrispettivi_ufficiali",
            "report_pulsanti_operativi",
            "report_esportazione_lettura"
        ],
        "Pacchetti": [
            "pacchetto_panorama",
            "pacchetto_create",
            "pacchetto_memo",
            "pacchetto_pagamento",
            "pacchetto_stati_dettaglio",
            "pacchetto_uso",
            "prepagata",
            "prepagata_create",
            "prepagata_uso",
            "prepagata_pagamento",
            "prepagata_controllo",
            "pacchetto_settings"
        ],
        "Tools": [
            "tools_tab_operatori",
            "tools_tab_servizi",
            "tools_tab_clienti",
            "tools_tab_whatsapp",
            "tools_tab_pacchetti",
            "tools_tab_marketing",
            "tools_tab_info_azienda",
            "tools_tab_centro_assistenza",
            "tools_tab_booking_web",
            "tools_tab_utenti"
        ],
        "Generali": [
            "generali_panorama",
            "generali_crediti_tecnica_hosting"
        ],
        "Booking via Web": [
            "booking_panorama",
            "booking_setup",
            "booking_pagina_pubblica",
            "booking_logica_slot",
            "booking_rules",
            "booking_servizi_operatori",
            "booking_codice_conferma_e_limiti",
            "booking_appuntamenti_in_agenda",
            "booking_agenda_separazione"
        ],
        "WhatsApp e Marketing": [
            "whatsapp_panorama",
            "whatsapp_connect",
            "whatsapp_messaggi_template",
            "whatsapp_auto",
            "whatsapp_memo_clienti_mattino",
            "whatsapp_operatori",
            "marketing_panorama",
            "marketing_send",
            "marketing_variables",
            "marketing_filtri_template"
        ],
        "Versione Touch": [
            "agenda_touch_mode"
        ],
    }