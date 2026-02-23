

"""
Contenuti Help per SunBooking.
Modifica questo file per aggiornare i testi di aiuto nell'app.
"""
HELP_IMAGES = {
    "navigator_appuntamenti": ["NavigatorAppuntamenti_Chiuso.png", "NavigatorAppuntamenti_Aperto.png", "NavigatorAppuntamenti_dropdownClienti.png", "NavigatorAppuntamenti_dropdownServizi.png"] 
}
HELP_TOPICS = {
    
    # ========== CALENDARIO ==========
    "calendar_new": {
        "title": "✏️ Come creare un appuntamento",
        "content": """Puoi **CLICCARE IN UNA CELLA VUOTA** del calendario e procedere nella finestra che si apre.<br><br>Oppure usare il **CAMPO DI RICERCA CLIENTE** in alto a destra sopra il calendario, e poi selezionare il servizio o i servizi.

In entrambi i casi, dovrai:
1. Cercare e selezionare il **CLIENTE** (puoi anche crearne uno nuovo al volo cliccando su "**+**" a lato del campo di ricerca)
2. Scegliere il **SERVIZIO**
3. Confermare **DATA E ORA**

Il click su cella vuota è più comodo se il cliente ha chiesto un particolare orario, oppure se devi trascrivere gli appuntamenti per quella giornata da appunti cartacei o altro.

Il [[Navigator Appuntamenti|navigator_appuntamenti]] in alto a destra sopra il calendario è più versatile e si presta a diverse esigenze.

L'appuntamento verrà creato automaticamente con la durata del servizio scelto.""",
        "video": None
    },

"calendar_drag": {
    "title": "🖱️ Spostare un appuntamento? Facilissimo!",
    "content": """Funziona come sul telefono: tocca, tieni premuto e trascina! 

📍 **Per spostare:** clicca sull'appuntamento e trascinalo dove vuoi

⏱️ **Per allungare/accorciare:** afferra il bordo in basso e tira su o giù

👥 **Cambiare operatore:** trascina l'appuntamento nella colonna di un altro operatore

È tutto automatico, non devi salvare nulla! ✨""",
    "image": "calendar_drag.gif",
    "video": None
},

    "calendar_status": {
        "title": "🎨 I colori dei blocchi appuntamento - cosa significano",
        "content": """Ogni colore ti dice subito lo stato del blocco appunbtamento:

🟢🟤🟣 **Colorato** → L'appuntamento è programmato (il colore si può modificare)
⚪ **Grigio chiaro, scritta in bianco** → Tutto fatto e pagato ✓
⚫ **Nero a puntini** → Il cliente non si è presentato: No-Show! 😢
🔵 **Blu** → Colore di default di un appuntamento preso da Booking Online

**Per cambiare stato:**prosegui nella lettura per vedere le funzioni nascoste di ogni blocco appuntamento...""",
        "image": "calendar_colors.png",
        "video": None
    },

    "calendar_block": {
        "title": "📋 Il blocco appuntamento - tutte le funzioni",
        "content": """Ogni blocco appuntamento ha tante funzioni nascoste! Ecco cosa puoi fare:

⬆️ **PULSANTI SOPRA AL BLOCCO** (appaiono al passaggio del mouse)
• ✂️ **Togli e Sposta** → Taglia il blocco e lo mette nel Navigator per spostarlo altrove
• 📋 **Copia Blocco** → Copia il blocco nel Navigator per duplicarlo e posizionare lo stesso appuntamento su altra data
• 🎨 **Imposta Colore** → Cambia il colore del blocco appuntamento
•  **+** **Aggiungi Servizi** → Aggiunge altri servizi per lo stesso cliente, da Navigator in alto a destra sopra il calendario
• 📝 **Nota Appuntamento** → Aggiunge o modifica una nota per questo appuntamento
•  **€** **Porta in Cassa** → Porta il servizio relativo al blocco e gli altri contigui per quel cliente, direttamente in cassa per il pagamento
e inoltre...
📱 **PULSANTE A LATO DEL BLOCCO**
• 💬 **Invia WhatsApp** → Invia un promemoria WhatsApp al cliente  

🖱️ **PASSANDO IL MOUSE/PUNTATORE SUL NOME CLIENTE**
Passa il mouse sul nome del cliente e appare un **TOOLTIP CON INFORMAZIONI** con:
• 🕰️ Data e ora di creazione (ed eventualmente di ultima modifica) di quel blocco appuntamento
• 👤 Nome e Cognome del cliente associato
• 📝 Note Cliente (se presenti)
• 📞 Numero di telefono
• 📅 Data e ora dell'appuntamento
• 💇 Servizio associato al blocco appuntamento
• 📝 Note Appuntamento (se presenti)

🖱️ **CLICK DENTRO BLOCCO**
• 🗑️ **Cestino** (in alto a sinistra) → Apre una finestra con diverse opzioni:
   - **ELIMINA** il singolo blocco
   - Elimina tutto il gruppo di blocchi appuntamento per quel cliente in quella data (se più di uno)
   - Imposta **NO-SHOW** (il cliente non si è presentato!)
   - **ANNULLA** se si vuole uscire senza fare modifiche
•  ◯ **Cliente in Istituto** (in alto a destra) → Indica che il cliente è arrivato ed è attualmente in istituto
• 👤 **Nome Cliente** (al centro) → Cliccando sul nome si apre la finestra per assegnare quell'appuntamento (e gli altri della stessa data) ad un altro cliente

🔔 **SPIE LAMPEGGIANTI**
• 🟡 **Spia gialla** → Il cliente è in istituto, tutto ok!
• 🔴 **Spia rossa** → Il cliente è in istituto ma siamo in ritardo!""",
        "image": None,
        "video": None
    },

    # ========== CASSA ==========
    "cassa_crea_scontrino": {
        "title": "🧾 Creare uno scontrino",
        "content": """Creare uno scontrino è semplicissimo!

1️⃣ Vai nella sezione **Cassa**
2️⃣ Cerca i Servizi o Prodotti venduti, oppure muoviti con i tab in alto ("Frequenti", "Ultimi", ecc.)
3️⃣ Seleziona l'operatore o il cliente (opzionale)
4️⃣ Modifica il metodo di pagamento per una o per tutte le voci (con i tasti in fondo: "cash", "pos", "bank")
5️⃣ Conferma cliccando su "Avanti" oppure annulla
6️⃣ Infine stampa lo scontrino cliccando su "Stampa"

Lo scontrino viene creato e salvato automaticamente! 🎉""",
        "image": None,
        "video": None
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
        "image": None,
        "video": None
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
        "image": None,
        "video": None
    },
    
    # ========== CLIENTI ==========
    "client_search": {
        "title": "🔍 Trovare un cliente",
        "content": """Inizia a scrivere e... magia! ✨

Puoi cercare per:
• Nome (es: "Maria")
• Cognome (es: "Rossi")  
• Telefono (es: "333")

Bastano 3 lettere e i risultati corrispondenti appaiono subito sotto!

**Trucco:** cerca solo con le prime lettere e scrivine altre solo se non vedi ancora il risultato che cercavi, è più veloce 😉""",
        "image": None,
        "video": None
    },
    
    "client_history": {
        "title": "📊 Vedere lo storico cliente",
        "content": """Vuoi sapere tutto di un cliente? Ecco come!

Clicca sull'icona "**i**" a fianco ai risultati della ricerca cliente, oppure vai in Impostazioni → Clienti, cerca il cliente e clicca su "**STORICO**":

📅 Tutti gli appuntamenti passati, con la data in cui sono stati registrati in istituto
💰 Quanto ha speso in totale
💆 Gli operatori associati
📝 I dati cliente e le note che hai salvato

Perfetto per capire le abitudini dei tuoi clienti! 🎯""",
        "image": "client_history.png",
        "video": None
    },
    
    "client_new": {
        "title": "👤 Aggiungere un nuovo cliente",
        "content": """Nuovo cliente? Lo aggiungi in 30 secondi!

1️⃣ Vai in **Impostazioni → Clienti** e clicca **"Nuovo Cliente"**, oppure usa il tasto "**+**" accanto al campo di ricerca cliente nel calendario
2️⃣ Inserisci nome, cognome e cellulare (attenzione, ogni numero di cellulare può essere associato a un solo cliente, ed è obbligatorio se vuoi salvare il cliente)
3️⃣ Clicca su "Salva" e il cliente è pronto all'uso!

Il sesso viene capito automaticamente dal nome (ma puoi correggerlo)!

**Consiglio:** verifica sempre il cellulare per i promemoria WhatsApp 📱, e fai in modo che il numero di cellulare sia associato al suo effettivo proprietario!""",
        "image": None,
        "video": None
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
        "image": "pacchetto_create.png",
        "video": "pacchetti"
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
        "image": None,
        "video": None
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
        "image": None,
        "video": None
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
        "image": "whatsapp_qr.png",
        "video": "whatsapp"
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
        "image": None,
        "video": None
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

**Consiglio:** non esagerare, 1-2 messaggi al mese per cliente 👍""",
        "image": None,
        "video": None
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
        "image": None,
        "video": None
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
        "image": "booking_link.png",
        "video": "booking"
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
        "image": None,
        "video": None
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

**Trucco:** crea preset per i turni più comuni, risparmi tempo 🚀""",
        "image": None,
        "video": None
    },

    # ========== SERVIZI ==========
    "service_create": {
        "title": "💆 Creare un servizio",
        "content": """Aggiungi i tuoi trattamenti in pochi click!

1️⃣ Vai in **Impostazioni → Servizi**
2️⃣ Clicca **"Nuovo Servizio"**
3️⃣ Compila: nome, durata, prezzo, categoria
4️⃣ Scegli chi può farlo (operatori)
5️⃣ Salva!

Il servizio appare subito nel menu appuntamenti 🎉

**Consiglio:** usa nomi chiari che anche i clienti capiscono (per il booking online)""",
        "image": None,
        "video": None
    },
}


def get_help(topic):
    """Restituisce il contenuto help per un argomento specifico"""
    return HELP_TOPICS.get(topic, {
        "title": "🤔 Aiuto",
        "content": "Contenuto non disponibile per questo argomento. Contatta il supporto!",
        "image": None,
        "video": None
    })


def get_all_topics():
    """Restituisce tutti gli argomenti help"""
    return HELP_TOPICS


def get_topics_by_category():
    """Restituisce gli argomenti organizzati per categoria"""
    return {
        "Calendario": ["calendar_new", "calendar_drag", "calendar_status", "calendar_block"],
        "Cassa": ["cassa_crea_scontrino", "cassa_pagamento", "cassa_blocchi_appuntamento"],
        "Clienti": ["client_new", "client_search", "client_history"],
        "Pacchetti": ["pacchetto_create", "pacchetto_uso", "prepagata"],
        "WhatsApp": ["whatsapp_connect", "whatsapp_auto"],
        "Marketing": ["marketing_send", "marketing_variables"],
        "Prenotazioni Online": ["booking_setup", "booking_rules"],
        "Operatori": ["operator_shifts"],
        "Servizi": ["service_create"],
    }