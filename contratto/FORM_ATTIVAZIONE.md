# Form di attivazione e firma contratto — progetto tecnico

Documento di progetto. Nulla di quanto qui descritto è ancora implementato.

---

## 1. Dove vive il form

**Dentro l'app Tosca, nella root app di `wsgi.py`, su rotta pubblica. Non su IONOS.**

`wsgi.py` monta ogni tenant su `/s/<idx>` tramite `DispatcherMiddleware`; la **root app**
(`root_app`) serve già `/owner-login`, `/owner-setup` e le API di billing. È l'unico posto che:

- conosce l'elenco dei database (`collect_db_pool()` legge `SQLALCHEMY_DATABASE_URI<N>`);
- sa creare un tenant da zero (`owner_setup_add_tenant()`, `wsgi.py:786`);
- può scrivere nel `.env` e montare il child **senza riavvio**.

Un form su IONOS dovrebbe invece esporre in rete le credenziali del PostgreSQL Azure, duplicare
i modelli e non potrebbe comunque fare il provisioning. Non ha senso.

**Ruolo di IONOS:** sito vetrina/landing. Il pulsante "Attiva TOSCA" punta a
`https://<dominio-tosca>/attiva/<token>`. Se si vuole un indirizzo pulito, un record CNAME
`attiva.<dominio>` verso l'App Service Azure e un custom domain sul servizio.

Rotte da aggiungere alla root app:

| Rotta | Metodo | Auth | Scopo |
|---|---|---|---|
| `/owner-setup/invite` | POST | owner | Genera link di attivazione per un nuovo cliente |
| `/attiva/<token>` | GET | token | Mostra il form (wizard) |
| `/attiva/<token>/step` | POST | token | Salva un passo (bozza) |
| `/attiva/<token>/pdf` | GET | token | Anteprima contratto compilato |
| `/attiva/<token>/otp` | POST | token | Invia / verifica OTP |
| `/attiva/<token>/firma` | POST | token | Registra la firma e chiude la pratica |
| `/webhook/firma` | POST | HMAC | Callback del provider di firma (opzione A) |

Il token **non deve mai** dare accesso a dati di alcun tenant: la rotta pubblica parla solo con
il registry.

---

## 2. Dove finiscono i dati

Il problema di fondo: **quando il cliente compila il form, il suo database non esiste ancora.**
Serve quindi uno store centrale, che oggi manca (i dati contratto stanno in
`owner_billing.json`, un file su disco — fragile su App Service, non transazionale, non
interrogabile).

**Proposta: un database centrale `tosca_registry`**, separato dai DB tenant, a cui le app tenant
non si connettono affatto. È la risposta più forte al requisito "campi che non verranno
visualizzati nell'app di Tosca": non è una questione di template, è un database diverso.

Bonus: è lo stesso registry che serve al piano dei 100 tenant per il login senza scansione
totale, e manda in pensione `owner_billing.json`.

```
┌────────────────────────────┐
│  tosca_registry (centrale) │  ← form pubblico, owner-setup, billing
│  tenant / invite /         │
│  contract / signature /    │
│  consent / invoice         │
└─────────────┬──────────────┘
              │ provisioning (dopo firma + incasso)
              ▼
┌────────────────────────────┐
│  DB tenant  (uno per       │  ← app Tosca: business_info, owners, clienti...
│  cliente, /s/<idx>)        │
└────────────────────────────┘
```

### Schema del registry

```sql
CREATE TABLE tenant (
  id                 serial PRIMARY KEY,
  idx                integer UNIQUE,              -- indice /s/<idx>, NULL finché non provisionato
  db_uri_enc         text,                        -- cifrata a riposo (Fernet), mai in chiaro
  business_name      varchar(150) NOT NULL,
  status             varchar(20)  NOT NULL,       -- invited|signed|provisioning|active|suspended|terminated
  created_at         timestamptz  NOT NULL DEFAULT now(),
  provisioned_at     timestamptz
);

CREATE TABLE onboarding_invite (
  id            serial PRIMARY KEY,
  token_hash    varchar(64) UNIQUE NOT NULL,      -- sha256 del token; il token in chiaro sta solo nel link
  tenant_id     integer REFERENCES tenant(id) ON DELETE CASCADE,
  email         varchar(120),
  expires_at    timestamptz NOT NULL,
  opened_at     timestamptz,
  used_at       timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE contract (
  id                    serial PRIMARY KEY,
  tenant_id             integer NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
  status                varchar(20) NOT NULL DEFAULT 'draft',  -- draft|ready|signed|void
  contract_version      varchar(20) NOT NULL,                  -- es. "1.0"
  -- anagrafica (fonte di verità; copiata su business_info al provisioning)
  legal_business_name   varchar(150),
  trade_name            varchar(150),
  legal_form            varchar(50),
  vat_number            varchar(20),
  fiscal_code           varchar(16),
  rea_number            varchar(20),
  rea_province          varchar(2),
  pec                   varchar(120),
  sdi_code              varchar(7),
  -- sede legale
  legal_address         varchar(200),
  legal_cap             varchar(10),
  legal_city            varchar(100),
  legal_province        varchar(2),
  -- sede operativa (negozio)
  op_same_as_legal      boolean DEFAULT true,
  op_address            varchar(200),
  op_cap                varchar(10),
  op_city               varchar(100),
  op_province           varchar(2),
  -- contatti
  email                 varchar(120),
  phone                 varchar(30),
  mobile                varchar(30),
  website               varchar(200),
  -- firmatario
  signer_first_name     varchar(80),
  signer_last_name      varchar(80),
  signer_fiscal_code    varchar(16),
  signer_role           varchar(50),
  signer_mobile         varchar(30),              -- utenza per l'OTP
  signer_email          varchar(120),
  -- pre-configurazione dell'istanza
  opening_time          time,
  closing_time          time,
  closing_days          text,                     -- JSON, stesso formato di business_info
  vat_percentage        numeric(5,2) DEFAULT 22.0,
  operators_count       integer,
  printer_model         varchar(30),              -- rch_print_rt | rch_print_f | none
  current_software      varchar(100),
  has_data_to_migrate   boolean,
  -- moduli e condizioni economiche
  module_base           boolean DEFAULT true,
  module_web            boolean DEFAULT false,
  module_pacchetti      boolean DEFAULT false,
  module_solarium       boolean DEFAULT false,
  starter_total         numeric(10,2),
  saas_monthly_amount   numeric(10,2),
  -- SEPA: mai l'IBAN completo
  sepa_mandate_ref      varchar(64),
  sepa_iban_last4       varchar(4),
  sepa_signed_at        timestamptz,
  created_at            timestamptz NOT NULL DEFAULT now(),
  updated_at            timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE contract_consent (
  id            serial PRIMARY KEY,
  contract_id   integer NOT NULL REFERENCES contract(id) ON DELETE CASCADE,
  kind          varchar(40) NOT NULL,   -- contract | art1341 | dpa | remote_support | not_consumer
  accepted      boolean NOT NULL,
  doc_version   varchar(20),
  doc_sha256    varchar(64),
  accepted_at   timestamptz NOT NULL DEFAULT now(),
  ip            varchar(45),
  user_agent    text
);

CREATE TABLE contract_signature (
  id                 serial PRIMARY KEY,
  contract_id        integer NOT NULL REFERENCES contract(id) ON DELETE CASCADE,
  method             varchar(30) NOT NULL,   -- otp_ses | provider_fea | provider_feq
  provider           varchar(50),
  provider_envelope  varchar(120),           -- id pratica lato provider
  otp_sent_at        timestamptz,
  otp_verified_at    timestamptz,
  otp_destination    varchar(30),            -- ultime cifre del cellulare
  signed_at          timestamptz,
  ip                 varchar(45),
  user_agent         text,
  pdf_sha256         varchar(64) NOT NULL,
  pdf_bytes          bytea,                  -- oppure blob storage + URL
  audit_json         jsonb
);
```

`invoice` e `payment` migrano da `owner_billing.json` mantenendo i campi attuali
(`activation_date`, `contract_start_date`, `starter_expiry_date`, `starter_total`,
`saas_monthly_amount`, `saas_next_renewal`, `max_payment_days`, `fiscozen_contact_id`,
`revolut_account_ref`), così `_compliance_status()` continua a funzionare invariato.

---

## 3. Campi del form e destinazione

Wizard in 6 passi, salvataggio progressivo. `*` = obbligatorio.

### Passo 1 — Anagrafica azienda

| Campo | Destinazione |
|---|---|
| Ragione sociale / denominazione * | `contract.legal_business_name` → `business_info.business_name` |
| Insegna / nome commerciale | `contract.trade_name` |
| Forma giuridica * (select) | `contract.legal_form` |
| Partita IVA * | `contract.vat_number` → `business_info.vat_code` |
| Codice fiscale (se diverso) | `contract.fiscal_code` → `business_info.fiscal_code` *(nuova colonna)* |
| N. REA + provincia | `contract.rea_number`, `rea_province` |
| PEC * | `contract.pec` → `business_info.pec_code` |
| Codice destinatario SDI | `contract.sdi_code` → `business_info.sdi_code` *(nuova colonna)* |

### Passo 2 — Sedi

| Campo | Destinazione |
|---|---|
| Sede legale: indirizzo, CAP, città, prov. * | `contract.legal_*` |
| "La sede operativa coincide" (checkbox) | `contract.op_same_as_legal` |
| Sede operativa: indirizzo, CAP, città, prov. | `contract.op_*` → `business_info.address / cap / city / province` |

La sede operativa è quella che finisce in Tosca: è l'indirizzo del negozio, quello che il
cliente finale vede.

### Passo 3 — Contatti e firmatario

| Campo | Destinazione |
|---|---|
| Nome e cognome legale rappresentante * | `contract.signer_first_name`, `signer_last_name` |
| Codice fiscale del firmatario * | `contract.signer_fiscal_code` |
| Qualifica * (titolare / amministratore / procuratore) | `contract.signer_role` |
| Cellulare del firmatario * | `contract.signer_mobile` — **è l'utenza dell'OTP** |
| E-mail aziendale * | `contract.email` → `business_info.email` |
| Telefono negozio | `contract.phone` → `business_info.phone` |
| Cellulare negozio | `contract.mobile` → `business_info.mobile` |
| Sito web | `contract.website` → `business_info.website` |

### Passo 4 — Pre-configurazione del negozio

| Campo | Destinazione |
|---|---|
| Orario apertura * | `contract.opening_time` → `business_info.opening_time` **(NOT NULL)** |
| Orario chiusura * | `contract.closing_time` → `business_info.closing_time` **(NOT NULL)** |
| Giorni di chiusura | `contract.closing_days` → `business_info.closing_days` |
| Aliquota IVA prevalente | `contract.vat_percentage` → `business_info.vat_percentage` |
| Numero operatori * | `contract.operators_count` — dimensiona la migrazione |
| Registratore telematico (nessuno / Print!T 3.0 RT / Print F) | `contract.printer_model` → `business_info.printer_model` |
| Gestionale attuale | `contract.current_software` |
| Ha dati da migrare | `contract.has_data_to_migrate` |

I due orari sono l'unico motivo per cui oggi `owner_setup_add_tenant()` deve inventare 9:00-19:00
(`wsgi.py:841`): sono `nullable=False` senza default. Chiedendoli nel form il default sparisce.

### Passo 5 — Moduli e condizioni economiche

| Campo | Destinazione |
|---|---|
| TOSCA BASE (sempre attivo) | `contract.module_base` → `OWNER.module_base_enabled` |
| Prenotazioni online | `contract.module_web` → `OWNER.module_web_enabled` |
| Pacchetti e prepagate | `contract.module_pacchetti` → `OWNER.module_pacchetti_enabled` |
| Strumenti solarium | `contract.module_solarium` → `OWNER.module_solarium_enabled` |
| Starter 6 mesi (importo) | `contract.starter_total` → registry billing |
| Canone mensile | `contract.saas_monthly_amount` → registry billing |
| IBAN per mandato SEPA | **al PSP, non in Tosca**: si salvano solo `sepa_mandate_ref` e `sepa_iban_last4` |

Gli importi vanno precompilati dall'owner al momento dell'invito e mostrati in sola lettura al
cliente: non è il cliente a scegliersi il prezzo.

### Passo 6 — Consensi e firma

| Consenso | `contract_consent.kind` |
|---|---|
| Presa visione e accettazione del contratto e degli Allegati A, B, C | `contract` |
| Approvazione specifica clausole artt. 1341-1342 c.c. (elenco esteso, checkbox separata) | `art1341` |
| Nomina a Responsabile del trattamento (Allegato B) | `dpa` |
| Autorizzazione assistenza remota (Supremo / TeamViewer) | `remote_support` |
| Dichiarazione di agire nell'esercizio dell'attività d'impresa (non consumatore) | `not_consumer` |

Ogni riga registra `doc_version`, `doc_sha256`, `ip`, `user_agent`, `accepted_at`. La checkbox
delle clausole 1341 **deve essere separata e successiva** a quella del contratto: è il
corrispettivo digitale della doppia firma.

---

## 4. Come far firmare — e il problema dell'art. 1341

Il punto delicato. L'art. 1341 co. 2 c.c. richiede l'approvazione **specifica per iscritto** delle
clausole onerose; il contratto qui è un modulo predisposto dal Licenziante, quindi si applica in
pieno. Una firma elettronica **semplice** (spunta + OTP) ha efficacia probatoria *liberamente
valutabile dal giudice* (art. 20 CAD, art. 25 eIDAS) e con essa il requisito di forma scritta
delle clausole vessatorie è **contestabile**.

Serve un servizio di **richiesta firma**: io carico il documento, il cliente firma da remoto
**senza possedere un certificato**, il servizio lo identifica al volo con OTP e restituisce PDF
firmato più audit trail. Non serve un servizio di *firma digitale* (quelli servono a firmare i
propri documenti: il firmatario deve già avere un certificato qualificato, e imporlo a ogni
estetista è attrito insostenibile in fase di onboarding).

### Provider scelto: Certyneo — prezzi verificati il 10/08/2026

| Piano | Costo | Incluso |
|---|---|---|
| **Free** | € 0, senza scadenza | **5 buste/mese**, firma **AES eIDAS con OTP**, audit trail con timestamp, conservazione prove 10 anni, 1 utente. **API esclusa** |
| **Personal** | € 9/mese (€ 108/anno) | 25 buste/mese, AES, **API REST + webhook** |
| Standard | € 19/mese | volumi maggiori |
| Business | € 39/mese | buste illimitate |
| QES (firma qualificata) | € 9,90/firma | a consumo, se mai servisse il livello massimo |

Editore francese, hosting in UE, nessuna esposizione al Cloud Act.

**Perché non gli altri:**
- **Youtrust (ex Yousign)** — Free 2 richieste/mese, One € 9/mese (10 richieste), Plus
  € 23/mese/utente. Ma la **FEA è a costo extra e solo sui piani annuali Plus/Pro**: per lo
  stesso lavoro si parte da ~€ 276/anno più il sovrapprezzo FEA.
- **cheFirma (Intesi Group)** — € 7,99/firma, FEQ vera, ma è il verso sbagliato: serve a
  firmare i *propri* documenti, non a farli firmare a terzi. Utile solo per un'eventuale
  controfirma del Licenziante.
- **Namirial / InfoCert** — QTSP italiani, più riconoscibili in giudizio, ma sensibilmente più
  cari a questi volumi.

### Come si integra Certyneo — dalle specifiche OpenAPI, verificate il 10/08/2026

Base URL `https://certyneo.com/api/v1`, autenticazione
`Authorization: Bearer sk_test_<hex>` / `sk_live_<hex>`, chiavi generate da *Settings → API* nel
dashboard.

**Il flusso completo sono quattro chiamate:**

```
1  POST /documents                     multipart, il PDF del contratto (max 50 MB)
                                       → { data: { id } }

2  POST /envelopes                     { subject, documentIds: [id],
                                         recipients: [{ email, name, phone, role:"SIGNER" }],
                                         fields: [...],                 ← posizioni firma
                                         signatureLevel: "ADVANCED",
                                         requireSmsOtp: true,
                                         expiresAt }
                                       → { id, status: "DRAFT" }

3  POST /envelopes/{id}/send           nessun body → DRAFT diventa SENT,
                                       parte l'invito al firmatario

4  webhook envelope.completed          → GET /envelopes/{id}/signed-document   (PDF firmato)
                                       → GET /envelopes/{id}/audit-trail       (PDF prove)
```

**Livello di firma.** `signatureLevel: "ADVANCED"` è la AES dell'art. 26 eIDAS e richiede
`requireSmsOtp: true` più il `phone` del firmatario in formato **E.164** (`+393331234567`).
Passare `requireSmsOtp: false` su ADVANCED restituisce errore
`ADVANCED_REQUIRES_STRONG_AUTH`. Il livello `SIMPLE` è la firma semplice, `QUALIFIED` richiede
video-identificazione e non è disponibile sul deploy base.

**Campi firma.** Due strade: posizionare i campi per coordinate
(`fieldType: "SIGNATURE"` / `"DATE_SIGNED"`, con `pageNumber`, `x`, `y`, `width`, `height`)
oppure creare un **template** dal dashboard e passare `templateId`. Per un contratto che ha
**due sottoscrizioni distinte** — corpo del contratto e blocco ex artt. 1341-1342 — il template
è più manutenibile: le coordinate vanno rifatte a ogni modifica del testo.

**Webhook.** Si registrano con `POST /webhooks` `{ url, events, active }`. Eventi utili:
`envelope.completed`, `recipient.signed`, `envelope.declined`, `envelope.expired`.

**Regalo inatteso: `POST /sepa-mandates`.** Genera il PDF del **mandato SEPA** già compilato con
creditore, debitore, IBAN e RUM, dentro una busta con i campi firma pre-posizionati. Risolve in
una chiamata il passo 5 del wizard. Attenzione però: lo schema `creditor` chiede `ics` e `siret`,
campi di impianto francese — va verificato cosa accettano per un creditore italiano (il CID
rilasciato dalla banca al posto dell'ICS).

### Un punto in cui mi ero sbagliato: l'embedded signing

**Nelle specifiche OpenAPI non esiste un endpoint di sessione incorporabile**, né un campo
`signUrl` nella risposta della busta. `POST /envelopes/{id}/send` «dispensa inviti» via
e-mail/SMS/WhatsApp: **il cliente firma sulla pagina di Certyneo**, non dentro Tosca.

Non è un problema per il requisito vero — **il contratto non viaggia mai come file** e non si
stampa niente — ma va detto chiaramente: si consegna un link, come già previsto, solo che a
inviarlo è Certyneo invece di Tosca, e la firma avviene sul loro dominio. Il ritorno su Tosca
avviene via webhook.

Se l'iframe conta davvero, è la seconda domanda da fare al loro supporto insieme a quella sul
piano: la pagina sviluppatori accennava a un `signUrl` da condividere, ma nelle specifiche non
compare.

### Firma dentro Tosca, senza invii e senza stampe

**Non serve mandare niente al cliente e non si stampa nulla.** L'API di Certyneo, creata la
busta, restituisce un **`signUrl`**: è il server di Tosca a riceverlo, quindi è Tosca a decidere
dove mandare il browser del cliente. Nessuna e-mail entra nel flusso.

```
cliente nel wizard  →  clic "Firma"
                          │
                          ▼
        Tosca: POST /envelopes  →  Certyneo restituisce signUrl
                          │
                          ▼
        browser del cliente va al signUrl (redirect o iframe)
        OTP via SMS  →  firma
                          │
                          ▼
        webhook envelope.completed  →  Tosca salva PDF + audit,
        contract.status = signed, e riporta il cliente su una
        pagina "fatto" di Tosca
```

Il pattern esiste già in casa: la connessione WhatsApp incorpora il flusso Unipile in un iframe
(`connect-iframe` in `whatsapp.html`). Stessa idea.

**Il contratto non viaggia mai come file.** L'unica cosa che si consegna al cliente è il **link**
`/attiva/<token>` — via WhatsApp, e-mail, o aperto direttamente sul PC del negozio durante
l'appuntamento di attivazione. Da lì in poi documento, lettura, firma e conferma stanno tutti
dentro il browser: nessun PDF da scaricare, allegare, stampare o rispedire.

Dopo la firma il PDF firmato viene inviato al cliente come **copia di cortesia**: non è un
passaggio del flusso, ma è buona pratica che chi firma riceva copia di ciò che ha sottoscritto.

**Unico punto aperto sul flusso:** la documentazione non dice se Certyneo consenta il framing
(`X-Frame-Options`). Il redirect al `signUrl` funziona in ogni caso e riporta il cliente su
Tosca subito dopo la firma; l'iframe, che sarebbe ancora più fluido, va testato.

### Sequenza consigliata

1. **Prova a costo zero:** piano Free, 5 buste/mese, per verificare con un contratto vero che la
   firma AES + OTP funzioni e che il PDF prodotto sia quello che vuoi — **prima** di scrivere
   l'integrazione.
2. **Poi l'integrazione** (passo 7 dell'ordine di lavoro), sul piano che include l'API.

### Alternative italiane e modelli a consumo — verificate il 10/08/2026

| Opzione | Modello | Costo | API | Firma |
|---|---|---|---|---|
| **Certyneo Free** | SaaS | **€ 0** — 5 buste/mese | da confermare | AES |
| **Certyneo Personal** | SaaS | € 108/anno — 25 buste/mese | sì | AES |
| **InfoCert GoSign — coupon** | **a consumo** | ~€ 3,30/firma (3 firme SPID € 9,90) | **no, manuale** | AES o QES a scelta |
| **Confirmo** (Confirmo S.r.l., P.I. 08336150720) | SaaS, vincolo **12 mesi** | **da € 30/mese = € 360/anno**, più un costo proporzionale per ogni certificato AES/QES | sì | AES/QES |
| PandaDoc | SaaS | solo **Enterprise**, su richiesta | solo Enterprise | — |
| Documenso self-hosted | — | € 0 licenza + infrastruttura | sì | SES |

**Il modello a consumo esiste ed è italiano: sono i coupon GoSign di InfoCert.** Si acquista un
pacchetto di firme e si ricevono «coupon anonimi e monouso» da far usare a terzi, scegliendo in
fase di firma fra livello avanzato e qualificato. Nessun canone, QTSP italiano accreditato AgID,
massimo peso probatorio.

### I coupon: far firmare il cliente a spese proprie, senza API

**È esattamente lo scenario per cui i coupon esistono.** Dalle pagine InfoCert, testuale:

> «È possibile fare firmare i propri clienti, dipendenti e fornitori sia utilizzando le firme del
> proprio pacchetto o, in alternativa, **fornendo dei coupon di firma** per facilitare la gestione
> dei processi con **gli interlocutori che non hanno una firma digitale**.»

> «Nel caso si scelga di far utilizzare a terzi le firme, si riceverà una e-mail contenente un
> elenco di **coupon anonimi e monouso** utilizzabili nel processo di firma, in numero
> corrispondente a quello di firme acquistate.»

Si comprano N firme, si ricevono N coupon, se ne consegna uno al cliente: **paga il Licenziante,
firma il Cliente**, e il Cliente non deve possedere né acquistare nulla.

**Ma i flussi documentati sono due, e cambiano molto l'attrito per il cliente:**

| | Flusso A — coupon su Desktop | Flusso B — «Richiedi Firma» su Sign Cloud |
|---|---|---|
| Come firma il cliente | installa **InfoCert Sign Desktop**, inserisce il coupon | riceve e-mail, clicca **«Vai alla firma»**, firma **nel browser** |
| Installazioni | sì, un'applicazione | **nessuna** |
| Identificazione | **SPID** del cliente | selezione del nome; certificati qualificati se posseduti |
| Livello firma | **qualificata** (one-shot rilasciata via SPID) | firma semplice generata dalla piattaforma, salvo certificato proprio |
| Coupon utilizzabile | sì, è il suo flusso | **non documentato** |

Il flusso A dà il massimo peso probatorio — firma qualificata, che chiude ogni discussione sulle
clausole ex artt. 1341-1342 — ma chiede al cliente di installare un programma e di avere SPID,
proprio nel momento in cui si sta chiudendo la vendita. Il flusso B è quello comodo (link,
browser, niente installazioni) ma la guida non dice se accetti i coupon né a che livello firmi.

**La domanda da fare a InfoCert è una sola e precisa:**

> *Un coupon di firma acquistato da me può essere speso dal destinatario dentro il flusso
> «Richiedi Firma» di Infocert Sign Cloud — quindi firmando dal browser, senza installare
> nulla — e con quale livello di firma?*

Se la risposta è sì, InfoCert vince su tutta la linea: € 3,30 a contratto, QTSP italiano, nessun
canone, nessuna installazione per il cliente, e nessuna API necessaria.

**Le API GoSign, invece, sono un binario commerciale separato.** Le API GoSign esistono e
sono documentate (`developers.infocert.digital/gosign/`, con Swagger, modalità Draft e Immediate,
supporto a firmatari esterni), ma il portale **non ha registrazione self-service, né sandbox
pubblica, né listino**: l'unico accesso indicato è *Contact us*. È lo stesso schema di PandaDoc —
prodotto retail a consumo da una parte, integrazione a contratto dall'altra. Non ho trovato
evidenza che i coupon a € 3,30 siano pilotabili via API, e tutti i segnali indicano di no.
**Va chiesto a InfoCert:** è una domanda sola e vale la pena farla.

### Dove vive il contratto firmato — indipendente dal provider

Qualunque strada si scelga, il PDF firmato torna indietro: con Certyneo da
`GET /envelopes/{id}/signed-document` e `/audit-trail`, con i coupon InfoCert scaricandolo a mano
una volta. **Da lì in poi la conservazione è la stessa**, e resta solo digitale.

**Copia autorevole nel registry, non nel database del tenant.**

```
contract_signature.pdf_bytes        bytea   il PDF firmato
contract_signature.pdf_sha256       varchar impronta, per provare che non è cambiato
contract_signature.audit_json       jsonb   audit trail del provider
```

Il motivo è pratico, non formale: il contratto è un documento **fra il Licenziante e il Cliente**,
e va conservato **10 anni** (art. 2220 c.c.). Se vivesse solo nel database del tenant, alla
cessazione del rapporto — quando quel database viene dismesso — sparirebbe proprio la prova del
rapporto. Il registry è anche il posto dove sta già tutto il resto della pratica.

**Copia di sola lettura nel tenant, sì.** Una volta firmato, conviene copiare lo stesso PDF nel
database del tenant e mostrarlo in Tosca (Centro Assistenza o Info Azienda) come *"Il tuo
contratto"*: il cliente se lo riscarica quando vuole senza chiederlo, e nessuno stampa niente.
La copia è ridondante per definizione, e va bene così.

Precedente in casa: `BusinessInfo.logo_image` è già un `LargeBinary` in `db.deferred` — salvare
binari nel database è pratica esistente del progetto, non una novità.

### La cosa da tenere a mente sulle cifre

A 20-50 contratti l'anno il conto è: coupon € 66-165, Certyneo Personal € 108, Certyneo Free € 0.
**Sono tutte cifre irrilevanti rispetto al canone che quei contratti generano.** La scelta non va
fatta sul prezzo ma su due criteri veri:

- **peso probatorio** — QTSP italiano accreditato AgID con possibilità di firma qualificata
  (InfoCert) contro firma avanzata di un editore francese (Certyneo);
- **automazione** — API self-service (Certyneo) contro passaggio manuale (coupon).

E soprattutto: **la scelta si può rimandare.** I passi 1-6 dell'ordine di lavoro — registry,
migrazione del billing, `provision_tenant()`, wizard, generazione del PDF — sono identici con
qualsiasi provider. Il provider entra in gioco solo al passo 7.

**Il punto di pareggio.** A ~€ 3,30 a firma, i coupon convengono **fino a circa 30 contratti
l'anno**; oltre, Certyneo Personal a € 108/anno (che ne consente 300) costa meno. Confirmo, unico
altro italiano con API trovato, parte da **più del triplo** di Certyneo e con vincolo annuale.

> ⚠️ I prezzi dei coupon InfoCert vengono da fonti terze (chitelodice.it, diritto.it), non dal
> listino ufficiale: vanno verificati su infocert.it prima di decidere. Quelli di Confirmo e
> Certyneo vengono invece dalle loro pagine.

### Se l'API di Certyneo risultasse a pagamento: alternative gratuite

Verificate il 10/08/2026, in ordine di robustezza probatoria decrescente.

| Via | Costo | API in **produzione** | Chi attesta la firma |
|---|---|---|---|
| **Certyneo Free** | € 0, 5 buste/mese, AES + OTP | da confermare | **Terzo neutrale** |
| **Documenso self-hosted** | € 0 di licenza (AGPL-3.0), API e iframe inclusi | Sì | **Tu** |
| **DocuSeal self-hosted** | € 0 di licenza, ma API, embedded e white-label sono sul Pro ($ 20/utente/mese) | solo a pagamento | **Tu** |
| **Costruita in casa** | € 0, salvo il costo degli OTP | Sì, tutto in casa | **Tu** |
| ~~PandaDoc~~ | — | ❌ **solo piano Enterprise** | — |

### PandaDoc: escluso per l'integrazione, verificato sulle loro pagine

Tecnicamente sarebbe perfetto — l'embedded signing è documentato per bene:
`POST /public/v1/documents/{id}/session` crea la sessione, la libreria `pandadoc-signing`
la incorpora nella pagina, e l'invio con `"silent": true` **salta del tutto le notifiche e-mail**.
Eventi `document.completed` e webhook inclusi.

Il problema è l'accesso. Dalla loro documentazione di supporto, testuale:

> «You must have an active **Enterprise** plan to access the Production API.»
> «Contact our Sales team to get access to the Production API key.»

Il **Sandbox** è gratuito ma inservibile per contratti veri: PDF con watermark, prefisso `[DEV]`
sui documenti, e soprattutto **si può inviare solo a indirizzi del proprio dominio** (il sistema
confronta il dominio di mittente e destinatario). Serve a costruire un proof of concept, non a
far firmare le clienti.

I «60 documenti/anno con API gratuita» che circolano in rete vengono da blog di **concorrenti**
(eversign, SignWell, Verdocs, bindlegal), non da PandaDoc: quel numero riguarda il piano
**Free eSign via interfaccia web**, non l'API. PandaDoc resta quindi utilizzabile **a mano** —
carichi il contratto e lo mandi dal loro sito — ma non integrabile in Tosca senza Enterprise, il
cui prezzo è solo su richiesta commerciale.

**Ne segue che Certyneo torna il candidato principale**, e la domanda «da quale piano parte
l'API» diventa la sola cosa che decide.

**Sul self-hosted, due avvertenze che contano più del prezzo:**

1. **Sei tu il custode della prova.** Generi il documento, gestisci l'OTP, scrivi l'audit trail e
   lo conservi. Se un cliente contesta la firma, sei giudice e parte. Quello che si compra con i
   9-40 €/mese di un provider non è la tecnologia: è **un terzo neutrale che attesta il processo**.
   Su un contratto che contiene limitazioni di responsabilità e foro esclusivo, non è un dettaglio.
2. **Self-hosted non vuol dire gratis.** Documenso o DocuSeal sono un altro servizio da far
   girare, con il suo database, sulla stessa infrastruttura Azure che è **già al limite**
   (PostgreSQL B1ms, cfr. piano 100 tenant). Il costo si sposta da licenza a infrastruttura e
   manutenzione, e cresce proprio quando cresci tu.

Il livello di firma ottenibile in self-hosted o in casa è comunque **firma elettronica semplice**,
non AES: è l'opzione debole sulle clausole ex art. 1341 già segnalata sopra.

### Da verificare prima di impegnarsi — bloccante sul costo

**Non è chiaro da quale piano parta l'API**, e le fonti si contraddicono tre volte: una dà l'API
inclusa nel Free, la pagina del piano gratuito dice che «API REST, webhook, SSO, integrazioni
sono riservate ai piani a pagamento», la guida comparativa la dà **dal piano Business**. La
pagina sviluppatori non lo specifica.

La differenza è fra **€ 0, € 108/anno e € 468/anno**: è la prima domanda da fare a Certyneo,
prima di qualsiasi decisione. Da chiedere insieme: se il `signUrl` sia incorporabile in iframe.

Documentazione OpenAPI: `https://certyneo.com/api/v1/openapi` — webhook `envelope.created`,
`envelope.completed`, `envelope.declined`, firmati HMAC SHA-256.

Resta da chiarire con l'avvocato se la AES con OTP sia sufficiente per l'approvazione specifica
delle clausole ex art. 1341 co. 2 c.c., o se per quel solo blocco convenga la QES a consumo.

---

## 5. Flusso completo

```
 owner                      cliente                        sistema
   │                           │                              │
   ├─ /owner-setup            │                              │
   │  "Nuovo cliente" ────────────────────────────────────►  crea tenant(status=invited)
   │  (nome, email, importi)  │                              crea contract(status=draft)
   │                           │                              genera token, salva token_hash
   │  ◄── link da inviare ─────┼──────────────────────────────┘
   │                           │
   │      link via mail/WA ───►│
   │                           ├─ GET /attiva/<token> ──────► valida token (scadenza, non usato)
   │                           ├─ passi 1..5 ───────────────► UPDATE contract (bozza)
   │                           ├─ anteprima PDF ────────────► render contratto compilato
   │                           ├─ passo 6: consensi ────────► INSERT contract_consent
   │                           ├─ firma ────────────────────► provider FEA / OTP
   │                           │                              INSERT contract_signature
   │                           │                              contract.status = signed
   │                           │                              tenant.status  = signed
   │                           │                              invite.used_at = now()
   │  ◄── notifica firma ──────┼──────────────────────────────┤
   │                           │  ◄── PDF firmato via mail ───┤
   │                           │                              │
   ├─ incasso Starter          │                              │
   ├─ "Attiva" ───────────────────────────────────────────►  provision_tenant(contract)
   │                           │                              ├ CREATE DATABASE + utente
   │                           │                              ├ create_app(uri) + db.create_all()
   │                           │                              ├ BusinessInfo dai dati del form
   │                           │                              ├ OWNER dai moduli firmati
   │                           │                              ├ utente owner copiato
   │                           │                              ├ _write_env_var(...)
   │                           │                              └ mount /s/<idx>  (no restart)
   │  ◄── credenziali ─────────┼──────────────────────────────┘
```

**Il provisioning avviene dopo la firma e l'incasso, non prima.** Due ragioni: un DB creato per
una trattativa non chiusa resta lì a consumare connessioni (e il PostgreSQL B1ms è già al
limite, cfr. piano 100 tenant), e l'art. 7.1 fa decorrere il contratto dal pagamento.

Il refactor concreto: estrarre da `owner_setup_add_tenant()` (`wsgi.py:786-921`) una funzione
`provision_tenant(contract) -> idx`. La rotta owner esistente diventa un chiamante che costruisce
un `contract` al volo; il flusso da form ne diventa il secondo chiamante. Nessuna logica
duplicata.

---

## 6. Sicurezza della rotta pubblica

| Rischio | Contromisura |
|---|---|
| Enumerazione token | Token 32 byte da `secrets.token_urlsafe`, in DB solo lo SHA-256, 404 generico su token non valido/scaduto/usato |
| Riuso del link | `used_at` valorizzato alla firma; dopo, il link mostra solo la ricevuta |
| Brute force OTP | Max 5 tentativi, OTP a 6 cifre valido 10 minuti, nuovo invio con cooldown 60 s |
| Spam / bot | Rate limit per IP (riusare lo schema di `_owner_login_check_rate`, `wsgi.py:465`) + honeypot |
| CSRF | Token CSRF sui POST del wizard |
| Manomissione importi | `starter_total` e `saas_monthly_amount` in sola lettura, impostati dall'owner all'invito e mai accettati dal client |
| Dati in transito | Solo HTTPS, HSTS |
| IBAN | Mai salvato in chiaro: va al PSP, in DB restano `mandate_ref` e ultime 4 cifre |
| Accesso ai tenant | La rotta pubblica non apre nessuna sessione applicativa e non tocca i DB tenant |

---

## 7. Modifiche a `models.py`

Tre sole colonne nuove in `business_info`, tutte per dati che l'app usa davvero in fattura e
nei documenti; tutto il resto del contratto sta nel registry.

```python
    legal_business_name = db.Column(String(150), nullable=True)  # ragione sociale completa
    fiscal_code         = db.Column(String(16),  nullable=True)  # CF, distinto da vat_code (P.IVA)
    sdi_code            = db.Column(String(7),   nullable=True)  # codice destinatario, distinto da PEC
```

Query di allineamento da eseguire **su ciascuno dei tre tenant** (`suncity`, `sunexp3`,
`sunbookingdb`), da finestra psql:

```sql
ALTER TABLE business_info ADD COLUMN IF NOT EXISTS legal_business_name varchar(150);
ALTER TABLE business_info ADD COLUMN IF NOT EXISTS fiscal_code         varchar(16);
ALTER TABLE business_info ADD COLUMN IF NOT EXISTS sdi_code            varchar(7);
```

Nessuna modifica a `OWNER`: i quattro flag `module_*` e le date di attivazione coprono già
quanto serve al contratto.

---

## 8. Ordine di lavoro proposto

0. **Account Certyneo**: registrarsi, chiarire da quale piano parte l'API, generare una chiave
   `sk_test_`, provare a mano un contratto vero dal dashboard. Zero codice, e chiude le due
   incognite (piano e iframe) prima di investire tempo.
1. Validazione legale del contratto e conferma del livello di firma (ADVANCED / AES).
2. Creazione del database `tosca_registry` e dei modelli (`appl/registry_models.py`, binding
   separato — le app tenant non devono vederlo).
3. Migrazione di `owner_billing.json` nel registry, con `_compliance_status()` invariato.
4. Estrazione di `provision_tenant()` da `owner_setup_add_tenant()`.
5. Generazione invito da `/owner-setup` + rotta `/attiva/<token>` con il wizard.
6. Generazione PDF del contratto compilato (template + WeasyPrint o equivalente). È il
   prerequisito della firma: oggi il contratto esiste in Markdown e HTML, non in PDF.
7. Integrazione Certyneo: `POST /documents` → `POST /envelopes` → `POST /envelopes/{id}/send`,
   più la rotta pubblica che riceve i webhook (verifica HMAC) e archivia PDF firmato e audit
   trail in `contract_signature`.
8. Pulsante "Attiva" nel pannello owner che chiama `provision_tenant()`.
9. Le tre colonne nuove in `business_info` e le query sui tre tenant.

Passi 1-4 sono indipendenti dal form e si possono fare subito: il registry serve comunque, con o
senza contratto online.
