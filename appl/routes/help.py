

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
    "title": "✏️ Come creare un appuntamento con CLICK SU CELLA VUOTA",
    "content": """Puoi **CLICCARE IN UNA CELLA VUOTA** del calendario e procedere nella finestra che si apre.

Una volta aperta la finestra, per creare un appuntamento clicca nel **CAMPO DI RICERCA CLIENTE**, digita le prime tre lettere o più, e poi seleziona dal dropdown il cliente per il quale vuoi prenotare (al momento del click sarà selezionato il cliente e si aprirà automaticamente il campo servizi).

Nel **CAMPO DI RICERCA SERVIZI** allo stesso modo digita le prime tre lettere o più, e poi seleziona dal dropdown il servizio per il quale vuoi creare il **MINI-BLOCCO** per l'appuntamento.

Puoi creare diversi mini-blocchi in questo modo.

Quando li avrai creati tutti clicca in basso a sinistra su **CREA APPUNTAMENTO**.

Se hai il pacchetto Web, si aprirà ancora un campo opzioni in basso che ti chiederà se vuoi inviare un **Memo Whatsapp** automatico per il cliente per il servizio o i servizi prenotati.

Subito dopo si creeranno i blocchi appuntamento in agenda, è facile!
""",
},

"calendar_appointment_navigator": {
        "title": "✏️ Come creare appuntamenti con il NAVIGATOR APPUNTAMENTI",
        "content": """Il **NAVIGATOR APPUNTAMENTI** in alto a destra sopra il calendario è più versatile e si presta a diverse esigenze.**[[NAVIGATOR APPUNTAMENTI|navigator_appuntamenti]]**

Una volta aperto il Navigator, per creare un appuntamento clicca nel **CAMPO DI RICERCA CLIENTE** e poi seleziona il servizio o i servizi. **[[CAMPO DI RICERCA CLIENTE|campo_ricerca_cliente]]**

🔍 **SELEZIONARE UN CLIENTE**
Scrivi almeno **3 lettere** del nome, cognome o telefono del cliente nel campo di ricerca: apparirà una **dropdown list** con i clienti corrispondenti presenti in database. Clicca sul cliente desiderato per selezionarlo.

💆 **SELEZIONARE UN SERVIZIO**
Allo stesso modo, nel **CAMPO DI RICERCA SERVIZI** basta scrivere **3 o più lettere** e apparirà la lista dei servizi corrispondenti. Clicca sul servizio per selezionarlo.

📦 **MINI-BLOCCHI APPUNTAMENTO**
Una volta selezionati cliente e servizio, viene creato automaticamente un **MINI-BLOCCO APPUNTAMENTO** che appare nell'area in basso del Navigator, in attesa di essere posizionato sul calendario.
Puoi creare **più mini-blocchi**: dopo aver creato il primo, cerca e seleziona un altro servizio per aggiungerne un altro!

👆 **POSIZIONAMENTO SUL CALENDARIO**
Con i mini-blocchi creati, muovi il mouse sulle **celle vuote** del calendario: vedrai un'**OMBRA** che ti mostra esattamente dove verranno posizionati i blocchi appuntamento.

☝️ **POSIZIONARE UN SOLO SERVIZIO**
Se hai creato più mini-blocchi ma vuoi posizionare solo uno specifico servizio, **clicca sul singolo mini-blocco** per selezionarlo: in questo modo verrà creato l'appuntamento relativo solo a quel servizio.
""",
    },

"calendar_drag": {
    "title": "🖱️ Spostare un appuntamento? Facilissimo!",
    "content": """Funziona come sul telefono: tocca, tieni premuto e trascina! 

📍 **Per spostare:** clicca sulla parte alta dell'appuntamento, sulla **BARRA DI TRASCINAMENTO** (la riconosci perché passandoci sopra col mouse il puntatore diventa una manina) e trascinalo dove vuoi

⏱️ **Per allungare/accorciare:** afferra il bordo in basso, la **BARRA DELLA DURATA** e tira su o giù di un quarto d'ora

👥 **Cambiare operatore:** trascina semplicemente l'appuntamento in un'altra colonna per assegnarlo ad un altro operatore

È tutto automatico, non devi salvare nulla! Nella versione web ad ogni spostamento dovrai confermare se inviare o meno un memo Whatsapp al cliente ✨""",
},

    "calendar_status": {
        "title": "🎨 I colori dei blocchi appuntamento - cosa significano",
        "content": """Ogni colore ti dice subito lo stato del blocco appunbtamento:

🟢🟤🔴🟡 **Colorato** → L'appuntamento è programmato (il colore si può modificare)
⚪ **Grigio chiaro, scritta in grigio** → Tutto fatto e pagato ✓
🔘  **Grigio a puntini, scritta in nero** → Blocco OFF, non prenotabile!
⚫ **Nero a puntini, scritta in bianco** → Il cliente non si è presentato: No-Show! 😢
🔵 **Blu** → Colore di default di un appuntamento preso da Booking Online

**Per cambiare stato ad un blocco appuntamento prosegui nella lettura per vedere le funzioni nascoste di ogni blocco...""",
    },

"calendar_block_buttons": {
    "title": "⬆️ Pulsanti sopra al blocco appuntamento",
    "content": """I **PULSANTI** che appaiono sopra al blocco appuntamento al passaggio del mouse sono fondamentali per gestire gli appuntamenti in modo rapido ed efficiente!

• ✂️ **TOGLI E SPOSTA** → Taglia il blocco e lo mette nel Navigator per spostarlo altrove, perfetto per spostare un appuntamento ad un altro giorno
• 📋 **COPIA BLOCCO** → Copia il blocco nel Navigator per duplicarlo e posizionare lo stesso appuntamento in un'altra parte del calendario, principalmente usato per prenotare gli stessi servizi allo stesso cliente in altre date
• 🎨 **IMPOSTA COLORE** → Cambia il colore del blocco appuntamento. Se usi uno sfondo molto chiaro le lettere del blocco diventeranno scure, non c'è pericolo... sbizzarrisciti! 👩‍🎨
• ➕ **AGGIUNGI (Aggiungi Servizi)**
 **AGGIUNGI SERVIZI** → Aggiunge altri servizi per lo stesso cliente, da Navigator in alto a destra sopra il calendario
• 📝 **NOTA APPUNTAMENTO** → Aggiunge o modifica una nota per questo appuntamento (occhio a non confondere le **note cliente** che rimangono fisse e visibili per ogni appuntamento prenotato dal cliente, con le **note appuntamento** che si impostano da qui, e sono visibili solo per quel singolo blocco appuntamento)
•  **€** **PORTA IN CASSA** → Porta il servizio relativo al blocco e gli altri contigui per quel cliente in cassa per il pagamento. A pagamento effettuato il blocco diventerà grigio chiaro con scritte in grigio, vuol dire che il pagamento per quei servizi è stato effettuato! ps: funzione disponibile solo su versione installata, non per versione web!
e inoltre...
📱 **Pulsante a lato del blocco**
• 💬 **INVIA WHATSAPP** → Invia un **promemoria WhatsApp** al cliente
""",
},

"calendar_block_tooltip": {
    "title": "🖱️ Tooltip sul nome cliente",
    "content": """Passa il mouse sul nome del cliente e appare un **TOOLTIP CON INFORMAZIONI** con:
• 🕰️ Data e ora di creazione (ed eventualmente di ultima modifica) di quel blocco appuntamento
• 👤 Nome e Cognome del cliente associato
• 📝 Note Cliente (se presenti)
• 📞 Numero di telefono
• 📅 Data e ora dell'appuntamento
• 💇 Servizio associato al blocco appuntamento
• 📝 Note Appuntamento (se presenti)
""",
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

✂️ **TAGLIA (Togli e Sposta)**
Cliccando su questo pulsante, i blocchi appuntamento **scompaiono** dal calendario (lasciando un'ombra al loro posto) e vengono trasformati in **mini-blocchi** visibili nel **Navigator Appuntamenti** in alto a destra.
Da lì puoi riposizionarli dove preferisci: basta muovere il mouse su una cella vuota del calendario e cliccare per confermare la nuova posizione.
Puoi tagliare anche più blocchi appuntamento e spostarli tutti con un click in agenda! Vedrai un'**ombra** sulle celle di calendario in prossimità del puntatore dove verranno creati i blocchi, e un'ombra sulle celle da cui sono stati tagliati i blocchi. Se annulli l'operazione (per es. con SVUOTA da Navigator Appuntamenti) i blocchi appuntamento torneranno al loro posto originario!

📋 **COPIA (Copia Blocco)**
Funziona in modo simile a "Taglia", ma **lascia i blocchi originali al loro posto**!
I blocchi vengono copiati come mini-blocchi nel Navigator Appuntamenti, pronti per essere posizionati su un'altra data.
**Esempio pratico:** un cliente vuole prenotare lo stesso trattamento una volta al mese per diversi mesi? Copia il blocco e posizionalo velocemente sulle date successive. Fatto in pochi secondi! 🚀

➕ **AGGIUNGI (Aggiungi Servizi)**
Cliccando su "Aggiungi", si apre il **Navigator Appuntamenti** già **pre-caricato con il nome del cliente** del blocco da cui hai cliccato.
In questo modo puoi aggiungere altri servizi allo stesso cliente per lo stesso appuntamento, senza doverlo cercare di nuovo.
Ideale quando il cliente decide di aggiungere un trattamento extra! 💆""",
    },

    "calendar_note": {
        "title": "📝 Le note: cliente e appuntamento",
        "content": """In Tosca puoi aggiungere due tipi di note, entrambe visibili nel tooltip informativo del blocco appuntamento!

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
• 🌐 **Prenotazioni da Booking Online:** mostrano informazioni sulla prenotazione web (dettagli del cliente, eventuale operatore selezionato)
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
        "title": "🔍 Trovare un cliente",
        "content": """Inizia a scrivere e... magia! ✨

Nei campi di ricerca cliente, puoi cercare cliente per
• Nome (es: "Maria")
• Cognome (es: "Rossi")  
• Telefono (es: "333")

Bastano 3 lettere (o i primi 3 numeri del cellulare) e i risultati corrispondenti appaiono subito sotto!

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Cerca solo con le prime lettere e scrivine altre solo se non vedi ancora il risultato che cercavi... è più veloce! 😉</span>
</div>""",
    },
    
"client_new": {
    "title": "👤 Aggiungere un nuovo cliente",
    "content": """Il modo più veloce per aggiungere un nuovo cliente è usare il **TASTO +** accanto al campo di ricerca cliente nella finestra di creazione appuntamento o nel Navigator Appuntamenti in Agenda!

Da lì, basta scrivere **NOME, COGNOME e CELLULARE**: il cliente viene subito aggiunto alla tua rubrica clienti!

Se il cellulare è già presente per un altro cliente, vieni avvisato con un messaggio (non è ammesso lo stesso numero di cellulare per più clienti!).

Il **SESSO** viene capito automaticamente dal nome (ma puoi correggerlo nelle impostazioni)

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Verifica sempre il cellulare per i promemoria WhatsApp 📱, e fai in modo che il numero sia associato al suo effettivo proprietario!</span>
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
        "title": "📊 Vedere lo storico cliente",
        "content": """Vuoi sapere tutto di un cliente? Ecco come!

Vai in **Impostazioni → Clienti**, cerca il cliente e clicca su "**STORICO**":

📅 Tutti gli appuntamenti passati, con la data in cui sono stati registrati in istituto
💰 Quanto ha speso in totale
💆 Gli operatori associati
📝 I dati cliente e le note che hai salvato

Perfetto per capire le abitudini dei tuoi clienti! 🎯""",
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

🔘 **TASTI AZIONE**
Per ogni cliente hai a disposizione questi pulsanti:
• **MODIFICA** → Apre una finestra per modificare i dati anagrafici del cliente
• **NOTE** → Apre una finestra per creare, visualizzare o modificare la nota per quel cliente
• **STORICO** → Apre lo storico completo del cliente (appuntamenti, spese, ecc.)
• **ELIMINA** → Elimina il cliente dalla rubrica (attenzione, operazione irreversibile!)

Qui hai il controllo totale sulla tua rubrica clienti! 📋""",
    },
    
    # ========== PACCHETTI ==========
    "pacchetto_create": {
        "title": "📦 Creare un pacchetto",
        "content": """I pacchetti fanno felici i clienti E te! Ecco come crearli:

1️⃣ Vai nella sezione **Pacchetti**
2️⃣ Clicca **"Nuovo Pacchetto"**
3️⃣ Seleziona: **Pacchetto Servizi** o **Carta Prepagata**
4️⃣ Scegli il cliente
5️⃣ Configura servizi, sedute e prezzo
6️⃣ Salva!

Il pacchetto è subito pronto all'uso 🚀""",
    },
    
    "pacchetto_uso": {
        "title": "✂️ Usare un pacchetto",
        "content": """Scalare le sedute è automatico!

Quando crei un appuntamento:
1️⃣ Seleziona il cliente (verrà mostrato se ha pacchetti attivi)
2️⃣ Scegli un servizio incluso nel pacchetto
3️⃣ Il sistema chiede: "Scalare dal pacchetto?" → Sì!

Le sedute si scalano da sole quando completi l'appuntamento 🎯

**Niente calcoli manuali, pensa a tutto l'app!**""",
    },
    
    "prepagata": {
        "title": "💳 Carta prepagata",
        "content": """È come un borsellino digitale per i tuoi clienti!

**Come funziona:**
1️⃣ Il cliente carica un importo (es: 200€)
2️⃣ Ad ogni visita, il costo viene scalato
3️⃣ Tu vedi sempre il saldo rimanente

**Perfetta per:**
• Clienti abituali che vogliono pagare in anticipo
• Chi vuole evitare di pagare ogni volta
• Regali 🎁

Il saldo è sempre visibile nella scheda cliente!""",
    },
    
    # ========== WHATSAPP ==========
    "whatsapp_connect": {
        "title": "📱 Collegare WhatsApp",
        "content": """Collega WhatsApp in 1 minuto!

1️⃣ Vai in **Impostazioni → WhatsApp**
2️⃣ Clicca **"Connetti WhatsApp"**
3️⃣ Appare un QR code sullo schermo
4️⃣ Prendi il telefono, apri WhatsApp
5️⃣ Vai in **Impostazioni → Dispositivi collegati**
6️⃣ Scansiona il QR code

Quando diventa 🟢 **verde** = sei connesso! 

**Nota:** il telefono deve restare connesso a internet""",
    },
    
    "whatsapp_auto": {
        "title": "⏰ Promemoria automatici",
        "content": """Mai più clienti che dimenticano l'appuntamento!

Una volta collegato WhatsApp:
1️⃣ Attiva i **promemoria automatici**
2️⃣ Scegli **quando inviarli** (es: ore 18:00 del giorno prima)
3️⃣ Personalizza il **messaggio**

Il sistema invia tutto da solo! 🤖

**Variabili utili:**
• {{nome}} → Nome del cliente
• {{servizio}} → Nome del trattamento
• {{data}} → Data appuntamento
• {{ora}} → Orario appuntamento""",
    },
    
    # ========== MARKETING ==========
    "marketing_send": {
        "title": "📣 Inviare messaggi marketing",
        "content": """Raggiungi i tuoi clienti in pochi click!

1️⃣ Usa i **filtri** per scegliere chi contattare
   (es: "clienti che non vengono da 30 giorni")
2️⃣ Scrivi il messaggio o usa un **template**
3️⃣ Controlla l'**anteprima**
4️⃣ Clicca **"Invia"**

⚠️ **Attenzione:** rispetta il limite giornaliero per evitare blocchi da WhatsApp!

<div class="help-hint-box">
<span class="help-hint-label">Consiglio:</span>
<span class="help-hint-text">Non esagerare, 1-2 messaggi al mese per cliente 👍</span>
</div>""",
    },
    
    "marketing_variables": {
        "title": "✨ Personalizzare i messaggi",
        "content": """Fai sentire speciale ogni cliente con le variabili!

**Scrivi così:**
"Ciao {{nome}}, sono passati {{giorni_assenza}} giorni..."

**Il cliente riceve:**
"Ciao Maria, sono passati 45 giorni..."

**Variabili disponibili:**
• {{nome}} → Nome
• {{cognome}} → Cognome
• {{centro}} → Nome del tuo centro
• {{giorni_assenza}} → Giorni dall'ultima visita
• {{totale_visite}} → Numero visite totali

Ogni messaggio diventa unico! 💌""",
    },
    
    # ========== BOOKING ONLINE ==========
    "booking_setup": {
        "title": "🌐 Prenotazioni online",
        "content": """Fai prenotare i clienti 24 ore su 24!

1️⃣ Vai in **Impostazioni → Booking Web**
2️⃣ **Attiva** i servizi prenotabili online
3️⃣ **Assegna** gli operatori a ogni servizio
4️⃣ Configura le **regole** che vuoi siano mostrate sulla tua pagina prenotazioni(anticipo, durata max, ecc.)
5️⃣ **Copia il link** e condividilo!

Metti il link su:
• Instagram bio 📸
• Facebook 👍
• Google My Business 🗺️
• Messaggi Whatsapp 📱
• Biglietti da visita e altra grafica per il tuo negozio 🖼️

I clienti prenotano da soli, anche di notte! 🌙""",
    },
    
    "booking_rules": {
        "title": "⚙️ Regole prenotazione online",
        "content": """Proteggi il tuo calendario con le regole giuste!

**Puoi impostare:**
• ⏱️ **Durata massima:** es. max 90 minuti per prenotazione
• 💰 **Prezzo massimo:** es. max 100€
In entrambi i casi puoi decidere se pubblicare solo un avviso o bloccare completamente la prenotazione.

**Perché servono?**
• Eviti che nelle ore di punta il telefono sia congestionato
• Puoi rindirizzare i clienti più complicati, gli **indecisi** che ti tengono sull'agenda delle mezz'ore e non si decidono mai!
• Dà un'immagine più professionale, mostrando che hai regole chiare per il tuo servizio
Trova il tuo equilibrio! ⚖️""",
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
<span class="help-hint-text">Usa nomi chiari che anche i clienti capiscono (per il booking online), e abbreviazioni intuitive per te e il tuo staff!</span>
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
        "Calendario": [
            "calendar_create_appointment",
            "calendar_appointment_navigator",
            "calendar_drag",
            "calendar_status",
            "calendar_block_buttons",
            "calendar_block_tooltip",
            "calendar_block_click",
            "funzioni_blocchi",
            "calendar_note",
            "calendar_paid_block",
            "calendar_off_block"
        ],
        "Cassa": [
            "cassa_crea_scontrino",
            "cassa_pagamento",
            "cassa_blocchi_appuntamento"
        ],
        "Clienti": [
            "client_new",
            "client_search",
            "client_info_window",
            "client_history",
            "client_settings"
        ],
        "Servizi": [
            "service_create",
            "service_categories",
            "service_vs_products",
            "service_duration"
        ],
        "Pacchetti": [
            "pacchetto_create",
            "pacchetto_uso",
            "prepagata"
        ],
        "WhatsApp": [
            "whatsapp_connect",
            "whatsapp_auto"
        ],
        "Marketing": [
            "marketing_send",
            "marketing_variables"
        ],
        "Prenotazioni Online": [
            "booking_setup",
            "booking_rules"
        ],
        "Operatori": [
            "operator_shifts"
        ],
    }