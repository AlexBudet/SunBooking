SunBooking - Gestionale Online
Applicazione Flask per gestione appuntamenti e reporstistica centro estetico

Requisiti
Python 3.9+
Azure Web App (App Service)
Database PostgreSQL su Azure
Installazione

Clona il repository

Installa le dipendenze

Configura le variabili d'ambiente

Deploy su Azure

Carica tutti i file del progetto su Azure Web App

Imposta le variabili d'ambiente dal portale Azure

Assicurati che il database sia accessibile dagli IP di uscita della Web App

Il file principale è wsgi.py

SunBooking/<br>
│<br>
├── .env<br>
├── cert.pem<br>
├── key.pem<br>
├── main.py<br>
├── requirements.txt<br>
├── __init__.py<br>
│<br>
├── appl/<br>
│   ├── __init__.py<br>
│   ├── forms.py<br>
│   ├── models.py<br>
│<br>
│   ├── routes/<br>
│   │   ├── __init__.py<br>
│   │   ├── calendar.py<br>
│   │   ├── cassa.py<br>
│   │   ├── clients.py<br>
│   │   ├── main_routes.py<br>
│   │   ├── operators.py<br>
│   │   ├── report.py<br>
│   │   ├── services.py<br>
│   │   ├── settings.py<br>
│<br>
│   ├── static/<br>
│   │   ├── css/<br>
│   │   │   ├── print_agenda.css<br>
│   │   │   └── styles.css<br>
│   │   ├── img/<br>
│   │   └── js/<br>
│   │       ├── calendar.js<br>
│   │       ├── cassa.js<br>
│   │       ├── palette-stagionale.json<br>
│   │       ├── settings.js<br>
│   │       └── touch-ui.js<br>
│<br>
│   ├── templates/<br>
│       ├── agenda_print.html<br>
│       ├── base.html<br>
│       ├── business_info.html<br>
│       ├── calendar.html<br>
│       ├── cassa.html<br>
│       ├── change_password.html<br>
│       ├── clients.html<br>
│       ├── edit_client.html<br>
│       ├── edit_operator.html<br>
│       ├── edit_service.html<br>
│       ├── landing.html<br>
│       ├── operators.html<br>
│       ├── registro_scontrini.html<br>
│       ├── report.html<br>
│       ├── services.html<br>
│       ├── set_booking.html<br>
│       ├── settings.html<br>
│       ├── users.html<br>
│       └── whatsapp.html<br>
│<br>
├── build/<br>
│   ├── start/<br>
│   └── wsgi/<br>
│<br>
├── psql/<br>
└── py/<br>
<br>

Note
Tutte le chiavi e password devono essere gestite tramite variabili d'ambiente.
