

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
1️⃣ fai <span class="help-strong-dark">click su una cella vuota</span>
2️⃣ si apre il modal <span class="help-strong-dark">Crea Appuntamento</span>
3️⃣ nel campo cliente scrivi almeno 3 caratteri e seleziona il nominativo (oppure crea un nuovo cliente al volo con il <span class="help-strong-dark">tasto verde "+"</span>)
4️⃣ nel campo servizio scrivi almeno 3 caratteri e scegli il trattamento
5️⃣ se vuoi, aggiungi più mini-blocchi servizio nello stesso modal
6️⃣ conferma la creazione

Il sistema precompila già operatore, data e orario partendo dalla cella cliccata. Puoi anche creare un <span class="help-strong-dark">Blocco OFF</span> se non stai prenotando un cliente.

<span class="help-strong-dark help-subtitle-pill">▸ Navigator Appuntamenti (metodo flessibile)</span>
Il <span class="help-strong-dark">Navigator Appuntamenti</span> è il riquadro in alto a destra nell'Agenda. Conviene usarlo quando devi preparare uno o più servizi prima di decidere dove posizionarli, oppure lavorare con più servizi, spostare o copiare blocchi esistenti. **[[NAVIGATOR APPUNTAMENTI|navigator_appuntamenti]]**

Flusso:
1. cerca il cliente **[[CAMPO DI RICERCA CLIENTE|campo_ricerca_cliente]]**
2. seleziona uno o più servizi
3. controlla i mini-blocchi nel riquadro basso
4. muovi il mouse sulle celle vuote del calendario
5. clicca per posizionare

Ogni mini-blocco rappresenta un servizio pronto da inserire. Se ne prepari più di uno, l'ombra di posizionamento ti mostra dove finiranno in agenda. Per posizionare solo un servizio specifico, seleziona il singolo mini-blocco prima del click sulla griglia.

Se è attivo il <span class="help-strong-dark">modulo opzionale WhatsApp</span>, dopo la conferma può comparire la richiesta per inviare un memo automatico al cliente.

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Se devi inserire una persona nuova senza uscire dal flusso Agenda, vai direttamente a <span class="help-strong-dark">[[AGGIUNGI NUOVO CLIENTE|client_new]]</span>.</span>
</div>""",
},

"calendar_drag": {
    "title": "🖱️ Spostare un appuntamento? Facilissimo!",
    "content": """Funziona come sul telefono: tocca, tieni premuto e trascina! 

📍 **Per spostare:** clicca sulla parte alta dell'appuntamento, sulla **BARRA DI TRASCINAMENTO** (la riconosci perché passandoci sopra col mouse il puntatore diventa una manina) e trascinalo dove vuoi

⏱️ **Per allungare/accorciare:** afferra il bordo in basso, la **BARRA DELLA DURATA** e tira su o giù di un quarto d'ora

👥 **Cambiare operatore:** trascina semplicemente l'appuntamento in un'altra colonna per assegnarlo ad un altro operatore

È tutto automatico, non devi salvare nulla! Se è attivo il <span class="help-strong-dark">modulo opzionale WhatsApp</span>, in alcuni flussi potrà comparire la conferma di invio memo al cliente ✨""",
},

    "calendar_status": {
        "title": "🎨 I colori dei blocchi appuntamento - cosa significano",
        "content": """Ogni colore ti dice subito lo stato del blocco appunbtamento:

🟢🟤🔴🟡 **Colorato** → L'appuntamento è programmato (il colore si può modificare)
⚪ **Grigio chiaro, scritta in grigio** → Tutto fatto e pagato ✓
🔘  **Grigio a puntini, scritta in nero** → Blocco OFF, non prenotabile!
⚫ **Nero a puntini, scritta in bianco** → Il cliente non si è presentato: No-Show! 😢
🔵 **Blu** → colore tipico degli appuntamenti provenienti dal <span class="help-strong-dark">modulo opzionale Booking via Web</span>

**Per cambiare stato ad un blocco appuntamento prosegui nella lettura per vedere le funzioni nascoste di ogni blocco...""",
    },

"calendar_block_buttons": {
    "title": "Blocco Appuntamento - I PULSANTI",
    "content": """Qui trovi una guida unica ai pulsanti del blocco appuntamento, con distinzione tra pulsanti popup e pulsanti interni (dentro il blocco).

<span class="help-strong-dark help-subtitle-pill">▸ Elenco rapido: pulsanti popup (al passaggio puntatore sul blocco)</span>
• ✂️ TOGLI E SPOSTA
• 📋 COPIA BLOCCO
• 🎨 IMPOSTA COLORE
• ➕ AGGIUNGI SERVIZI
• 📝 NOTA APPUNTAMENTO
• € PORTA IN CASSA
• 💬 INVIA WHATSAPP (modulo opzionale WhatsApp)

<span class="help-strong-dark help-subtitle-pill">▸ Elenco rapido: pulsanti interni al blocco</span>
• 🗑️ CESTINO (in alto a sinistra)
• ◯ CLIENTE IN ISTITUTO (in alto a destra)
• 👤 NOME CLIENTE (al centro)

<span class="help-strong-dark help-subtitle-pill">▸ Pulsanti Popup sul blocco</span>
<span class="help-strong-dark">✂️ TOGLI E SPOSTA</span>
Taglia il blocco e lo trasforma in mini-blocco nel Navigator Appuntamenti. Il blocco sparisce temporaneamente dalla cella (con ombra di riferimento) e puoi riposizionarlo dove vuoi.

<span class="help-strong-dark">📋 COPIA BLOCCO</span>
Copia il blocco nel Navigator lasciando l'originale al suo posto. Utile per duplicare rapidamente lo stesso appuntamento su altre date.

<span class="help-strong-dark">🎨 IMPOSTA COLORE</span>
Cambia colore al blocco. Se il colore è chiaro/scuro, il testo si adatta automaticamente per restare leggibile.

<span class="help-strong-dark">➕ AGGIUNGI SERVIZI</span>
Apre il Navigator già precompilato con il cliente del blocco corrente, così puoi aggiungere altri servizi senza rifare la ricerca cliente.

<span class="help-strong-dark">📝 NOTA APPUNTAMENTO</span>
Aggiunge/modifica la nota del singolo appuntamento. È distinta dalle note cliente (che sono permanenti e legate all'anagrafica).

<span class="help-strong-dark">€ PORTA IN CASSA</span>
Porta in Cassa il servizio del blocco (e gli eventuali contigui dello stesso cliente) per il pagamento.

<span class="help-strong-dark">💬 INVIA WHATSAPP</span>
Disponibile solo con <span class="help-strong-dark">modulo opzionale WhatsApp</span>, invia un promemoria al cliente.

<span class="help-strong-dark help-subtitle-pill">▸ Pulsanti interni al blocco</span>
<span class="help-strong-dark">🗑️ CESTINO</span>
Apre il menu azioni del blocco: elimina singolo blocco, elimina gruppo contiguo (quando presente), imposta No-Show o annulla.

<span class="help-strong-dark">◯ CLIENTE IN ISTITUTO</span>
Indica che il cliente è arrivato in istituto; da qui gestisci lo stato operativo di presenza.

<span class="help-strong-dark">👤 NOME CLIENTE</span>
Con click sul nome puoi aprire la finestra per riassegnare l'appuntamento (e gli altri della stessa data) a un altro cliente.""",
},

"calendar_block_click": {
    "title": "🖱️ Click dentro il blocco appuntamento",
    "content": """• 🗑️ **Cestino** (in alto a sinistra) → Apre una finestra con diverse opzioni:
   - **ELIMINA** il singolo blocco
   - Elimina tutto il gruppo di blocchi appuntamento per quel cliente in quella data (se più di uno)
   - Imposta **NO-SHOW** (se il cliente non si è presentato!)
   - **ANNULLA** se si vuole uscire senza fare modifiche

•  ◯ **Cliente in Istituto** (in alto a destra) → Indica che il cliente è arrivato ed è attualmente in istituto
• 👤 **Nome Cliente** (al centro) → Cliccando sul nome si apre la finestra per assegnare quell'appuntamento (e gli altri della stessa data) ad un altro cliente

🔔 **Spie lampeggianti**
• 🟡 **Spia gialla** → Il cliente è in istituto, tutto ok!
• 🔴 **Spia rossa** → Il cliente è in istituto ma siamo in ritardo rispetto all'orario previsto per la fine dell'appuntamento.
""",
},

    "funzioni_blocchi": {
        "title": "✂️ Maneggiare i blocchi appuntamenti: le funzioni 'Togli e Sposta', 'Copia Blocco' e 'Aggiungi Servizio'",
        "content": """Sopra ogni blocco appuntamento trovi tre pulsanti fondamentali per gestire gli appuntamenti in modo rapido ed efficiente!

<span class="help-strong-dark help-subtitle-pill">✂️ TAGLIA (Togli e Sposta)</span>
Cliccando su questo pulsante, i blocchi appuntamento **scompaiono** dal calendario (lasciando un'ombra al loro posto) e vengono trasformati in **mini-blocchi** visibili nel **Navigator Appuntamenti** in alto a destra.
Da lì puoi riposizionarli dove preferisci: basta muovere il mouse su una cella vuota del calendario e cliccare per confermare la nuova posizione.
Puoi tagliare anche più blocchi appuntamento e spostarli tutti con un click in agenda! Vedrai un'**ombra** sulle celle di calendario in prossimità del puntatore dove verranno creati i blocchi, e un'ombra sulle celle da cui sono stati tagliati i blocchi. Se annulli l'operazione (per es. con SVUOTA da Navigator Appuntamenti) i blocchi appuntamento torneranno al loro posto originario!

<span class="help-strong-dark help-subtitle-pill">📋 COPIA (Copia Blocco)</span>
Funziona in modo simile a "Taglia", ma **lascia i blocchi originali al loro posto**!
I blocchi vengono copiati come mini-blocchi nel Navigator Appuntamenti, pronti per essere posizionati su un'altra data.
**Esempio pratico:** un cliente vuole prenotare lo stesso trattamento una volta al mese per diversi mesi? Copia il blocco e posizionalo velocemente sulle date successive. Fatto in pochi secondi! 🚀

<span class="help-strong-dark help-subtitle-pill">➕ AGGIUNGI (Aggiungi Servizi)</span>
Cliccando su "Aggiungi", si apre il **Navigator Appuntamenti** già **pre-caricato con il nome del cliente** del blocco da cui hai cliccato.
In questo modo puoi aggiungere altri servizi allo stesso cliente per lo stesso appuntamento, senza doverlo cercare di nuovo.
Ideale quando il cliente decide di aggiungere un trattamento extra! 💆""",
    },

    "calendar_note": {
        "title": "📝 Tooltip e Note nel blocco appuntamento",
        "content": """In Tosca puoi visualizzare informazioni e aggiungere due tipi di note, tutte visibili nel tooltip informativo del blocco appuntamento!

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
        "content": """I **Blocchi OFF** sono diversi dai blocchi appuntamento: servono per bloccare fasce orarie per attività di servizio come pause, riunioni o altri impegni. In pratica disattivano le celle del calendario, impostandole come "non prenotabili" per i clienti.

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
        "content": """Creare uno scontrino è semplicissimo!

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
        "content": """La cassa si collega automaticamente agli appuntamenti!

**Come funziona:**
• Quando completi un appuntamento, puoi portare uno o più servizi associati a quel cliente cliccando sul tasto sopra al blocco "Vai in Cassa"
• I servizi dell'appuntamento vengono caricati automaticamente
• Il cliente e l'operatore sono già selezionati

**Per pagare un appuntamento:**
1️⃣ Clicca sull'appuntamento nel calendario
2️⃣ Seleziona **"Vai alla cassa"** o **"Completa e paga"**
3️⃣ Verifica i servizi e il totale
4️⃣ Registra il pagamento

Tutto collegato, zero errori! ✨""",
    },
    
    # ========== CLIENTI ==========
    "client_search": {
        "title": "🔍 Ricerca cliente in Agenda + Nuovo cliente + Info rapida",
        "content": """Questa è la guida unica per tutto il flusso cliente in Agenda: ricerca, inserimento rapido nuovo cliente e finestra info.

<span class="help-strong-dark help-subtitle-pill">▸ RICERCA CLIENTE IN AGENDA</span>
Nei campi di ricerca cliente, puoi cercare per:
• Nome (es: "Maria")
• Cognome (es: "Rossi")
• Telefono (es: "333")

Bastano 3 lettere (o i primi 3 numeri del cellulare) e i risultati corrispondenti appaiono subito sotto.

<span class="help-strong-dark help-subtitle-pill">▸ AGGIUNGI NUOVO CLIENTE (TASTO +)</span>
Il modo più veloce per aggiungere un nuovo cliente è usare il **TASTO +** accanto al campo di ricerca cliente nella finestra di creazione appuntamento o nel Navigator Appuntamenti in Agenda.

Da lì, basta scrivere **NOME, COGNOME e CELLULARE**: il cliente viene subito aggiunto alla rubrica.

Se il cellulare è già presente per un altro cliente, compare un messaggio di avviso (non è ammesso lo stesso numero di cellulare per più clienti).

Il **SESSO** viene capito automaticamente dal nome (ma puoi correggerlo nelle impostazioni).

Verifica sempre il <span class="help-strong-dark">cellulare</span>: è un dato fondamentale per contatto, recall e, se attivo il modulo opzionale, anche per l'invio WhatsApp.

<span class="help-strong-dark help-subtitle-pill">▸ FINESTRA INFO CLIENTE (ICONA i)</span>
Al click sull'**ICONA "i"** a fianco dei risultati della ricerca cliente si apre una finestra dove puoi visualizzare e modificare rapidamente i dati del cliente.

Puoi modificare **NOME, COGNOME, CELLULARE ed EMAIL** nei campi in alto, e aggiungere o modificare la **NOTA SALVATA** per quel cliente.

Più sotto trovi:
• **Prossimi appuntamenti prenotati** per quel cliente
• **Storico appuntamenti** per quel cliente

Cliccando sulle righe della tabella, la vista Agenda si sposta direttamente nella giornata selezionata.

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Cerca con poche lettere e usa subito + o icona i: fai tutto da Agenda senza saltare tra più schermate.</span>
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
        "content": """In **Impostazioni → Clienti** (tab "Clienti") trovi tutte le funzioni avanzate per gestire la tua rubrica clienti!

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
        "title": "🎁 Pacchetti: panoramica generale",
        "content": """La sezione Pacchetti serve a gestire due grandi strumenti commerciali:

• <span class="help-strong-dark">Pacchetti servizi</span>
• <span class="help-strong-dark">Carte prepagate</span>

Qui puoi creare programmi venduti in anticipo, seguirne avanzamento, controllare pagamenti, sedute e stato generale del cliente.

In pratica Pacchetti è il ponte tra vendita, Agenda e Cassa.""",
    },

    "pacchetto_create": {
        "title": "📦 Creare un pacchetto",
        "content": """Per creare un pacchetto:

1️⃣ entra nella sezione <span class="help-strong-dark">Pacchetti</span>
2️⃣ apri il modal di nuovo pacchetto
3️⃣ scegli il cliente
4️⃣ decidi se stai creando un programma a sedute oppure una carta/prepagata
5️⃣ compila nome, servizi, quantità, listino, eventuale sconto e struttura pagamento
6️⃣ salva

Durante la creazione puoi impostare anche elementi commerciali come omaggi, rate o promozioni, in base al tipo di pacchetto.""",
    },

    "pacchetto_stati_dettaglio": {
        "title": "🧾 Pacchetti: stati, dettaglio, sedute e rate",
        "content": """Ogni pacchetto ha uno <span class="help-strong-dark">stato</span> e una scheda dettaglio.

Stati tipici:
• preventivo
• attivo
• completato
• abbandonato

Nel dettaglio pacchetto puoi seguire:
• sedute effettuate e residue
• rate pagate e mancanti
• prossime date
• storico modifiche operative

Questa pagina è quella da consultare quando vuoi capire a colpo d'occhio quanto è stato usato e quanto resta da saldare o consumare.""",
    },
    
    "pacchetto_uso": {
        "title": "✂️ Usare un pacchetto",
        "content": """L'uso quotidiano del pacchetto avviene soprattutto passando da Agenda e Cassa.

Quando prenoti un cliente con pacchetto attivo:
1️⃣ seleziona il cliente
2️⃣ scegli un servizio compatibile
3️⃣ Tosca controlla se esiste una copertura da pacchetto
4️⃣ quando il flusso viene confermato, la seduta o il credito vengono scalati secondo le regole previste

Così eviti conteggi manuali e mantieni allineati appuntamento, pagamento e residuo pacchetto.

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Controlla periodicamente i pacchetti attivi con residuo basso: aiuta a proporre rinnovi in modo naturale al momento giusto.</span>
</div>""",
    },
    
    "prepagata": {
        "title": "💳 Carta prepagata",
        "content": """La carta prepagata funziona come un credito cliente disponibile nel tempo.

Come si usa:
1️⃣ carichi un importo iniziale
2️⃣ il cliente usa servizi o prodotti compatibili
3️⃣ in Cassa puoi scegliere <span class="help-strong-dark">Prepagata</span> come metodo di pagamento
4️⃣ il saldo residuo si aggiorna automaticamente

È utile per fidelizzazione, regali e clienti abituali che vogliono lasciare credito disponibile.""",
    },

    "pacchetto_settings": {
        "title": "⚙️ Pacchetti: impostazioni, promo e template",
        "content": """Nelle <span class="help-strong-dark">Impostazioni Pacchetti</span> puoi configurare la parte commerciale e comunicativa del modulo.

Qui trovi, ad esempio:
• regole per stato "abbandonato"
• promo personalizzate
• template WhatsApp per riepilogo pacchetto
• template per carte prepagate

Questa sezione è utile per standardizzare il modo in cui il centro vende e comunica i pacchetti.""",
    },
    
    # ========== WHATSAPP ==========
    "whatsapp_panorama": {
        "title": "💬 WhatsApp: panoramica del modulo opzionale",
        "content": """La sezione <span class="help-strong-dark">WhatsApp e Marketing</span> appartiene a un <span class="help-strong-dark">modulo opzionale separato</span> rispetto al gestionale standard.

Se il modulo non e' attivo:
• non compaiono le funzioni di invio WhatsApp
• non vengono mostrati i flussi automatici relativi ai messaggi

Se il modulo e' attivo, puoi gestire:
• connessione account WhatsApp Business
• messaggi manuali e automatici
• reminder giornalieri
• memo turni operatori
• campagne marketing""",
    },

    "whatsapp_connect": {
        "title": "📱 Collegare WhatsApp",
        "content": """Per usare il modulo WhatsApp devi prima collegare l'account Business.

Flusso base:
1️⃣ vai in <span class="help-strong-dark">Impostazioni → WhatsApp</span>
2️⃣ clicca <span class="help-strong-dark">Connetti WhatsApp</span>
3️⃣ si apre il flusso con QR code o pagina di connessione
4️⃣ dal telefono apri WhatsApp → Dispositivi collegati
5️⃣ inquadra il QR

Quando la connessione e' attiva, la schermata mostra lo stato collegato e il numero associato.

Nota operativa:
• nella versione desktop locale sono disponibili piu' opzioni di connessione
• il telefono/account deve restare correttamente connesso per permettere gli invii

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Fai un test con il tuo numero interno subito dopo la connessione: conferma prima invio manuale e poi invio automatico.</span>
</div>""",
    },

    "whatsapp_messaggi_template": {
        "title": "📝 WhatsApp: messaggi manuali e template",
        "content": """Nel modulo puoi configurare diversi testi WhatsApp.

I principali sono:
• messaggio manuale da calendario
• messaggio automatico alla conferma appuntamento
• reminder giornaliero

Ogni template puo' usare variabili come:
• {{nome}}
• {{data}}
• {{ora}}
• {{servizi}}

Questo ti permette di mantenere un messaggio coerente ma personalizzato per ogni cliente.

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Mantieni i template brevi e chiari: una frase di conferma, data/ora e call-to-action sono spesso sufficienti.</span>
</div>""",
    },
    
    "whatsapp_auto": {
        "title": "⏰ Promemoria automatici",
        "content": """Con il modulo attivo puoi automatizzare piu' tipi di invio.

<span class="help-strong-dark">Conferma automatica</span>
Messaggio inviato al momento della creazione appuntamento, se il flusso lo prevede.

<span class="help-strong-dark">Reminder giornaliero</span>
Puoi attivare un invio automatico a orario fisso ogni giorno, usando il template dedicato.

<span class="help-strong-dark">Opzione utile</span>
Puoi anche disattivare la richiesta di conferma WhatsApp nel modal di creazione appuntamento, se vuoi un flusso piu' rapido.

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Imposta un orario reminder che non risulti invasivo: la fascia tardo pomeriggio del giorno prima funziona spesso meglio.</span>
</div>""",
    },

    "whatsapp_operatori": {
        "title": "👩‍💼 WhatsApp: memo turni operatori",
        "content": """Il modulo puo' inviare automaticamente ai singoli operatori il riepilogo del turno del giorno successivo.

Configurazioni principali:
• attivazione generale memo turni
• orario di invio
• template messaggio operatori
• scelta degli operatori abilitati a riceverlo

E' una funzione utile per organizzare il team senza dover inviare manualmente i turni ogni sera.

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Prima di attivare l'invio per tutti, usa la funzione di preview e verifica il template su 1-2 operatori.</span>
</div>""",
    },
    
    # ========== MARKETING ==========
    "marketing_panorama": {
        "title": "📣 Marketing: panoramica del modulo opzionale",
        "content": """La parte Marketing e' inclusa nello stesso <span class="help-strong-dark">modulo opzionale WhatsApp</span>.

Serve a inviare campagne mirate ai clienti usando filtri e template.

Non fa parte del gestionale standard: se il modulo non e' attivo, questa sezione non rientra nei flussi operativi base di Agenda e Cassa.

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Definisci 2-3 campagne tipo (riattivazione, promo stagionale, fedelta') e riusale come base per risparmiare tempo.</span>
</div>""",
    },

    "marketing_send": {
        "title": "📣 Inviare messaggi marketing",
        "content": """La schermata Marketing e' divisa in tre parti:

• <span class="help-strong-dark">filtri clienti</span>
• <span class="help-strong-dark">risultati selezionabili</span>
• <span class="help-strong-dark">template messaggio e anteprima</span>

Flusso corretto:
1️⃣ attiva uno o piu' filtri
2️⃣ cerca i clienti
3️⃣ seleziona i destinatari
4️⃣ scegli o scrivi il template
5️⃣ verifica l'anteprima
6️⃣ invia

⚠️ Mantieni sempre un uso misurato degli invii per non stressare i clienti e non saturare il canale WhatsApp.

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Meglio una campagna ben mirata che molti invii generici. Qualita' del target prima della quantita'.</span>
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

Usale con criterio: poche variabili, ma ben scelte, rendono la comunicazione molto piu' efficace.

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Evita template con troppe variabili: se un dato manca, il messaggio rischia di risultare meno naturale.</span>
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

In piu' puoi:
• usare template predefiniti
• salvare i tuoi template personalizzati
• vedere l'anteprima sul primo cliente selezionato prima dell'invio

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Prima di inviare a molti clienti, esegui sempre un micro-test su un gruppo ristretto e controlla il testo finale.</span>
</div>""",
    },
    
    # ========== BOOKING ONLINE ==========
    "booking_panorama": {
        "title": "🌐 Booking via Web: panoramica del modulo opzionale",
        "content": """La sezione <span class="help-strong-dark">Booking via Web</span> e' un <span class="help-strong-dark">modulo opzionale separato</span> dal gestionale standard.

Se il modulo non e' attivo:
• non compare il flusso prenotazioni web
• non vengono mostrati gli elementi collegati alle prenotazioni online
• in Agenda non compaiono gli elementi specifici del booking web

Se il modulo e' attivo, puoi pubblicare servizi online, gestire regole e associare operatori prenotabili.

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Gestisci il Booking via Web come canale separato: prima configuralo bene, poi promuovi il link ai clienti.</span>
</div>""",
    },

    "booking_setup": {
        "title": "🌐 Prenotazioni online",
        "content": """Per attivare il modulo Booking via Web:

1️⃣ entra in <span class="help-strong-dark">Impostazioni → Booking Web</span>
2️⃣ scegli quali servizi rendere visibili online
3️⃣ associa gli operatori prenotabili per ogni servizio
4️⃣ configura le regole di prenotazione
5️⃣ pubblica e condividi il link booking

Il link puo' essere usato su sito, social, Google Business e canali del centro.

Questo modulo consente ai clienti di richiedere prenotazioni anche fuori dagli orari di apertura.

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Pubblica online solo i servizi davvero adatti all'auto-prenotazione, lasciando quelli complessi al contatto diretto.</span>
</div>""",
    },
    
    "booking_rules": {
        "title": "⚙️ Regole prenotazione online",
        "content": """Le regole booking servono a proteggere l'agenda da prenotazioni online non adatte.

    Regole principali disponibili:
    • durata massima prenotabile
    • prezzo massimo prenotabile

    Per ciascuna regola puoi scegliere se:
    • mostrare solo un <span class="help-strong-dark">warning</span>
    • oppure <span class="help-strong-dark">bloccare</span> la prenotazione

    Inoltre puoi personalizzare il messaggio mostrato al cliente, cosi' il sito comunica chiaramente il motivo della limitazione.

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Parti con limiti prudenti e poi allargali gradualmente in base ai risultati reali delle prenotazioni web.</span>
</div>""",
        },

        "booking_servizi_operatori": {
        "title": "👩‍💼 Booking via Web: servizi visibili e operatori associati",
        "content": """Nel pannello Booking Web trovi una tabella servizi dedicata al modulo online.

    Qui puoi decidere:
    • se un servizio e' visibile online
    • quanti operatori sono associati a quel servizio
    • quali operatori possono essere prenotati dal cliente via web

    Questo e' un punto chiave: un servizio pubblicato online senza corretta associazione operatori non produrra' un'esperienza di prenotazione coerente.

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Dopo ogni modifica operatori/servizi, testa una prenotazione completa dal link pubblico per verificare il risultato reale.</span>
</div>""",
        },

        "booking_agenda_separazione": {
        "title": "🧭 Booking via Web: cosa compare in Agenda e cosa no",
        "content": """Le funzioni del Booking via Web devono essere lette come <span class="help-strong-dark">aggiuntive</span> rispetto all'Agenda standard.

    Se il modulo non e' attivo:
    • non devi aspettarti la presenza di elementi dedicati al booking web
    • la normale Agenda continua a funzionare senza icone o tabelle collegate al mondo online

    Se il modulo e' attivo, alcuni blocchi o pannelli possono mostrare informazioni specifiche del booking web, ma questi contenuti appartengono a questa sezione e non alla guida Agenda standard.

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
        "content": """Aggiungi i tuoi trattamenti in pochi click!

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
        "content": """I turni definiscono quando un operatore è disponibile per nuove prenotazioni. Gli appuntamenti si potranno creare <span class=\"help-strong-dark\">solo</span> negli orari di turno impostati.

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
        "content": """La modalità TOUCH cambia il modo in cui interagisci con i blocchi appuntamento.

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
        "content": """Qui trovi il flusso completo in 3 parti, senza passaggi separati.

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
        "content": """A destra trovi il riquadro <span class=\"help-strong-dark\">Clienti in istituto</span>.

Serve per:
• vedere rapidamente chi è arrivato
• aprire il gruppo cliente presente in istituto
• portare i servizi relativi nella bozza scontrino

Quando la bozza scontrino viene creata a partire da appuntamenti in Agenda, compaiono anche dei tasti aggiuntivi per gestire le modifiche:
• <span class=\"help-strong-dark\">Salva Modifiche</span>: conserva la versione modificata della bozza
• <span class=\"help-strong-dark\">Reset</span>: ricostruisce la bozza partendo dai dati originali del calendario

Questa logica è utile quando, prima di stampare, cambi prezzi, righe o metodi ma vuoi mantenere coerenza con l'origine Agenda.""",
    },

    "cassa_sconti_metodi_stampa_test": {
        "title": "🧮 Cassa: sconti e metodi di pagamento",
        "content": """Ogni riga della bozza può essere rifinita prima della conferma.

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
• <span class=\"help-strong-dark\">admin/owner</span>: più strumenti, tra cui eliminazione nei casi consentiti e console RCH

Nel dettaglio scontrino puoi leggere righe, metodi di pagamento, totale e stato fiscale del documento.

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Rivedi il Registro Scontrini ogni giorno prima della chiusura: riduce errori e correzioni a posteriori.</span>
</div>""",
    },

    "cassa_strumenti_fiscali_rch": {
        "title": "🖨️ Cassa: strumenti fiscali, DGFE e console RCH",
        "content": """Nella colonna destra alta della Cassa trovi gli strumenti legati alla stampante fiscale:

• <span class=\"help-strong-dark\">Registro Scontrini</span>
• <span class=\"help-strong-dark\">Registro DGFE</span>
• <span class=\"help-strong-dark\">Chiusura Giornaliera</span>
• <span class=\"help-strong-dark\">Annulla Scontrino</span>
• <span class=\"help-strong-dark\">Console RCH</span> (solo admin/owner)

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
        "content": """La pagina Report include una barra di navigazione simile all'Agenda:

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
        "title": "📈 Report: sezioni principali e KPI",
        "content": """In alto trovi le <span class=\"help-strong-dark\">tile KPI</span> e sotto i pulsanti di sezione.

<span class=\"help-strong-dark\">Che cosa significa KPI?</span>
KPI è l'acronimo di <span class=\"help-strong-dark\">Key Performance Indicator</span>, cioè <span class=\"help-strong-dark\">Indicatore Chiave di Performance</span>.
In pratica è un numero sintetico che ti dice rapidamente se stai andando nella direzione giusta.

Nel Report, i KPI mostrano ad esempio:
• incasso totale
• passaggi in cassa
• trend o scostamento

Le <span class=\"help-strong-dark\">tile</span> sono i riquadri KPI: ogni tile riassume un dato e il relativo significato operativo.""",
    },

    "report_previsioni_tile_edit": {
        "title": "🧠 Report: calcoli previsionali e gestione tile",
        "content": """La parte previsionale confronta i dati correnti con obiettivi e andamento temporale.

In termini operativi:
• il sistema legge i dati reali disponibili nel periodo selezionato
• li confronta con un target di riferimento
• mostra la differenza nelle tile (trend/scostamento)

<span class=\"help-strong-dark\">Come leggere una tile previsionale</span>
• valore principale: dato attuale
• testo secondario: contesto (giorno/periodo)
• trend: sei sopra o sotto target

<span class=\"help-strong-dark\">Come si modificano</span>
Le tile non si modificano "a mano" direttamente dal widget: si aggiornano cambiando filtri e impostazioni disponibili nel report/settings (quando abilitate per il tuo ruolo).""",
    },

    "report_corrispettivi_ufficiali": {
        "title": "🧾 Report: sezione Corrispettivi (dati ufficiali)",
        "content": """La sezione <span class=\"help-strong-dark\">Corrispettivi</span> raccoglie i <span class=\"help-strong-dark\">dati ufficiali degli incassi</span> generati dalla cassa.

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

Alcuni pulsanti sono visibili solo a ruoli abilitati (admin/owner).""",
    },

    "report_esportazione_lettura": {
        "title": "🧠 Report: lettura dati ed esportazione",
        "content": """I report sono pensati per controllo giornaliero e analisi periodica.

Suggerimenti:
• confronta sempre periodo selezionato e giorno visualizzato
• usa i filtri per isolare categorie/operatori
• interpreta insieme KPI + dettaglio tabellare per decisioni operative

Quando disponibile, usa strumenti di esportazione/stampa in coerenza con i permessi del tuo ruolo.

Per invii amministrativi, usa sempre la vista Corrispettivi del periodo corretto prima dell'export.""",
    },

    # ========== TOOLS / SETTINGS ==========
    "tools_panorama": {
        "title": "🧰 Tools: panoramica della sezione Settings",
        "content": """La sezione Tools raccoglie le impostazioni strutturali del gestionale:

    • Operatori
    • Servizi
    • Clienti
    • Info Azienda
    • Utenti (ruoli abilitati)

    È il punto in cui si definiscono le basi operative su cui poi lavorano Agenda, Cassa, Report e, se attivi, anche i moduli opzionali.""",
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
    • <span class="help-strong-dark">Utenti</span>: creazione account e assegnazione ruolo (solo admin/owner)

    I ruoli influenzano ciò che ogni persona può vedere o fare, ad esempio in Cassa, Report e negli strumenti fiscali avanzati.""",
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
            "pacchetto_stati_dettaglio",
            "pacchetto_uso",
            "prepagata",
            "pacchetto_settings"
        ],
        "Tools": [
            "tools_panorama",
            "tools_clienti_servizi_operatori",
            "tools_info_azienda_utenti",
            "tools_touch_updates",
            "tools_workflow_consigliato",
            "client_settings",
            "service_create",
            "service_categories",
            "service_vs_products",
            "service_duration"
        ],
        "Booking via Web": [
            "booking_panorama",
            "booking_setup",
            "booking_rules",
            "booking_servizi_operatori",
            "booking_agenda_separazione"
        ],
        "WhatsApp e Marketing": [
            "whatsapp_panorama",
            "whatsapp_connect",
            "whatsapp_messaggi_template",
            "whatsapp_auto",
            "whatsapp_operatori",
            "marketing_panorama",
            "marketing_send",
            "marketing_variables",
            "marketing_filtri_template"
        ],
        "Touch": [
            "agenda_touch_mode"
        ],
    }