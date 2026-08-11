# Centro Assistenza — screenshot da catturare

Stato al 10/08/2026. Nel Centro Assistenza ci sono **98 topic**, di cui **49 senza immagine**.

---

## Regole di cattura (valgono per tutti)

**Misure verificate nel CSS di `appl/templates/help.html`:**

| Dove | Larghezza a video | **Esporta a** (2×) |
|---|---|---|
| Colonna del contenuto | 1060 px | — |
| Immagine di testa del topic (`"image"`) | **820 px** | **1640 px** |
| Immagine inline (`[[TESTO\|chiave]]`) | **540 px** | **1080 px** |

> Nota: la misura del topic è **820 px**, non 560. Il valore che giravamo prima era vecchio.

**Il vincolo vero è l'inquadratura, non i pixel.** Si **ritaglia**, non si rimpicciolisce: una
schermata intera rimpicciolita per stare in 820 px è illeggibile. Inquadra solo il riquadro di
cui parla il topic, con giusto un po' di contesto attorno per capire dove ci si trova.

**Nomi neutri, sempre.** Il repo è pubblico. Mai i nomi-scherzo del database di prova: usa
Rossi / Bianchi / Verdi con Mario / Laura / Giulia. Vale anche per e-mail, note cliente, nomi
operatore e numeri di telefono.

**Nome file:** `Pagina_Cosa.png`, come i 36 già presenti in `appl/static/img/help/`.

---

## 1. Da fare subito — WhatsApp (già cablate nel codice)

I due topic sono già scritti e puntano a questi file. Finché i PNG non ci sono, la guida si
mostra **senza immagine** (ho aggiunto un `onerror` che nasconde il riquadro), quindi non si
rompe nulla: appena li salvi in `appl/static/img/help/` compaiono da sole.

### `Whatsapp_QRCode.png` → topic *Collegare WhatsApp con il QR Code*

- **Dove:** Tools → WhatsApp → click su **Connetti WhatsApp**
- **Cosa inquadrare:** solo il riquadro del QR — dalla riga *"Scansiona il QR code con WhatsApp
  sul tuo telefono:"* fino a *"Annulla / In attesa di connessione…"*. Niente barra laterale,
  niente header.
- **Export:** 1640 px di larghezza

> ⚠️ **Due cautele.** Il QR è un token di sessione: dopo lo scatto clicca **Annulla**, così
> quella sessione muore e l'immagine pubblicata è inerte. E se nell'inquadratura entra un
> numero di telefono, coprilo.

### `Whatsapp_Tools_Panoramica.png` → topic *WHATSAPP: connessione, test e uso operativo*

- **Dove:** Tools → WhatsApp, **con il numero già collegato** (serve lo stato verde)
- **Cosa inquadrare:** il riquadro *Connessione WhatsApp Business* con il pallino verde, e
  sotto l'inizio della sezione *Messaggio WhatsApp manuale*, così si capisce com'è composta la
  pagina
- **Export:** 1640 px di larghezza

> ⚠️ **Il numero collegato va mascherato**: è il numero reale del negozio e finisce in un repo
> pubblico. Sostituiscilo con qualcosa tipo `+39 ••• ••• 1234`.

---

## 2. Le altre 49, in ordine di resa

Una passata per pagina: apri la pagina una volta e ritaglia tutti i pannelli che ti servono.

### Priorità alta — REPORT (10 topic, tutti pannelli visivi)

Sono la parte del programma che senza immagine si capisce peggio, e sono tutti sulla stessa
pagina: una sessione sola e li chiudi.

| File | Topic | Cosa inquadrare |
|---|---|---|
| `Report_NoShow.png` | `report_no_show` | il pannello No-show |
| `Report_Heatmap.png` | `report_heatmap` | le due heatmap affiancate |
| `Report_AndamentoAnnuale.png` | `report_andamento_annuale` | il grafico anno su anno |
| `Report_ScontrinoMedio.png` | `report_scontrino_medio` | il pannello scontrino medio |
| `Report_Saturazione.png` | `report_saturazione_agenda` | il pannello saturazione |
| `Report_PulsantiOperativi.png` | `report_pulsanti_operativi` | la barra dei pulsanti |
| `Report_TileEdit.png` | `report_previsioni_tile_edit` | un KPI in modifica |

`report_news_beauty`, `report_oroscopo` ed `report_esportazione_lettura` si possono lasciare
senza: sono pannelli di contorno.

### Priorità alta — TOOLS (7 tab)

Un ritaglio per tab, sempre inquadrando la barra dei tab in alto così si capisce dove si è.

`Tools_Operatori.png` · `Tools_Pacchetti.png` · `Tools_Marketing.png` · `Tools_InfoAzienda.png` ·
`Tools_BookingWeb.png` · `Tools_Utenti.png` · `Tools_CentroAssistenza.png`

→ topic `tools_tab_*`. Su *Info Azienda* e *Utenti* attenzione ai dati reali: partita IVA,
indirizzo, username.

I quattro `tools_clienti_servizi_operatori`, `tools_info_azienda_utenti`, `tools_users_ruoli`,
`tools_workflow_consigliato` sono topic di raccordo: rimandano ad altri, non serve immagine.

### Priorità media

| Gruppo | Topic | Note |
|---|---|---|
| **BOOKING** (7) | `booking_setup`, `booking_rules`, `booking_agenda_separazione` | gli altri 4 sono concettuali; `booking1.png`/`booking2.png` esistono già e sono usate altrove |
| **WHATSAPP** (5 restanti) | `whatsapp_messaggi_template`, `whatsapp_auto`, `whatsapp_operatori`, `whatsapp_memo_clienti_mattino` | tutte sezioni della stessa pagina Tools → WhatsApp: le ritagli nella stessa passata dei due scatti del punto 1 |
| **MARKETING** (4) | `marketing_send`, `marketing_filtri_template` | `marketing_panorama` e `marketing_variables` sono testuali |
| **PACCHETTI/PREPAGATE** (6) | `pacchetto_pagamento`, `pacchetto_memo`, `prepagata_uso` | qui i nomi cliente sono ovunque: massima attenzione |
| **CASSA** (1) | `cassa_strumenti_fiscali_rch` | la colonna strumenti fiscali a destra |

### Priorità bassa / da valutare

- **MOBILE** (2): `mobile_uso_agenda`, `mobile_installa_app` — servono scatti da telefono, con
  proporzioni verticali che nel riquadro da 820 px rendono male. Valuta se non convenga un
  ritaglio stretto centrato.
- **GENERALI** (2): puramente testuali, l'immagine non aggiunge niente.

---

## 3. Immagini già presenti ma non usate

| File | Situazione |
|---|---|
| `Cassa_PulsantiServizio.png` | **orfana** — nessun topic la usa. Candidata naturale: `cassa_crea_scontrino`, il cui passo 2️⃣ parla proprio dei filtri e dei pulsanti servizio. Oggi quel topic mostra `Cassa_Panoramica.png` (schermata intera). Da decidere. |
| `NavigatorAppuntamenti_Chiuso.png`, `NavigatorAppuntamenti_CercaCliente.png` | regolari: sono usate come immagini **inline** tramite `HELP_IMAGES`, non come immagine di testa |
| `freccia_corta.png`, `freccia_lunga.png` | asset decorativi |

---

## 4. Dopo aver aggiunto i file

Basta copiarli in `appl/static/img/help/`. **Non serve toccare il codice** per le due WhatsApp:
i nomi sono già cablati. Per le altre va aggiunta la terna `"image"` / `"image_caption"` /
`"image_path"` nel topic dentro `appl/routes/help.py`.

E ricorda: **dopo ogni modifica a `help.py` o ai template va riavviata l'app**, il reload della
pagina non basta.
