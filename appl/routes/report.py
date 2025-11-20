import json
from flask import Blueprint, current_app, request, jsonify, render_template, send_file, session
from sqlalchemy.orm import joinedload
import requests
from sqlalchemy import func, cast, Date
from appl.models import Appointment, AppointmentStatus, Operator, Client, AppointmentSource, BusinessInfo, Receipt, Service, ServiceCategory, Subcategory, User
from appl import db
import pandas as pd
import os
import re
from pytz import timezone as pytz_timezone
import random
from datetime import date, datetime, timedelta, time
from itertools import groupby
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')  # leggi da .env

def to_rome(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(pytz_timezone('Europe/Rome'))

# Helpers condivisi per lettura voci e classificazione prodotti
def _to_list(voci):
    if isinstance(voci, list):
        return voci
    if isinstance(voci, str):
        try:
            data = json.loads(voci)
            return data if isinstance(data, list) else []
        except Exception:
            return []
    return []

def _norm_name(n):
    return (n or "").strip().lower()

def _parse_sid(voce):
    sid = voce.get('servizio_id') or voce.get('service_id')
    if sid in (None, ''):
        return None
    try:
        return int(str(sid).strip())
    except Exception:
        return None

def _build_product_maps(receipts):
    # Raccoglie ids/nomi dai receipts e costruisce:
    # - id_is_product: {service_id -> bool} SOLO in base alla sottocategoria del Service ("prodotti")
    # - name_is_product: lasciata vuota per evitare fallback basati sul nome
    # - services_by_id: {service_id -> Service}, utile in /api/report_day per categorie
    servizio_ids, names_lower = set(), set()
    for r in receipts:
        for v in _to_list(r.voci):
            sid = _parse_sid(v)
            if sid:
                servizio_ids.add(sid)
            # non useremo più i nomi per classificare, li lasciamo comunque raccolti se servono altrove
            n = _norm_name(v.get('nome'))
            if n:
                names_lower.add(n)

    id_is_product, name_is_product, services_by_id = {}, {}, {}

    if servizio_ids:
        svcs = (Service.query.options(joinedload(Service.servizio_sottocategoria))
                .filter(Service.id.in_(list(servizio_ids))).all())
        for s in svcs:
            services_by_id[s.id] = s
            sub_l = _norm_name(s.servizio_sottocategoria.nome) if s.servizio_sottocategoria else ""
            # SOLO sottocategoria: prodotto se la sottocategoria contiene "prod"
            id_is_product[s.id] = ('prod' in sub_l)

    # Intenzionalmente NON popoliamo name_is_product: niente fallback su nome
    return id_is_product, name_is_product, services_by_id

CITAZIONI = [
    ("Coco Chanel", "Non esistono donne brutte, solo donne pigre."),
    ("Giorgio Armani", "L’eleganza è la risultante di una naturale semplicità."),
    ("Sophia Loren", "Non mi pento mai di nulla. Ciò che sono oggi è grazie alle mie esperienze."),
    ("Audrey Hepburn", "Per avere uno sguardo luminoso, cerca sempre il buono nelle persone."),
    ("Marilyn Monroe", "Un sorriso è il miglior trucco che una ragazza possa indossare."),
    ("Elizabeth Taylor", "Penso che il glamour sia qualcosa che deve venire da dentro di te."),
    ("Helena Rubinstein", "Non ci sono donne brutte, solo donne pigre."),
    ("Estée Lauder", "La bellezza è un’attitudine."),
    ("Oscar Wilde", "Amare sé stessi è l’inizio di una storia d’amore lunga tutta la vita."),
    ("Yves Saint Laurent", "Senza eleganza nel cuore, non c’è eleganza."),
    ("Diana Vreeland", "La bellezza è dove la trovi."),
    ("Anna Magnani", "Lasciami tutte le rughe, non togliermene nemmeno una. Le ho pagate tutte care."),
    ("Diane von Furstenberg", "Sentirsi belli è una decisione che si prende ogni mattina."),
    ("Twiggy", "Non ho mai pensato di essere bella, mi sentivo solo diversa."),
    ("Donatella Versace", "La moda è un’arma che puoi usare quando ne hai bisogno."),
    ("Miuccia Prada", "Non è importante essere alla moda, è importante avere stile."),
    ("Jean Paul Gaultier", "Tutti abbiamo qualcosa di unico, bisogna solo saperlo esprimere."),
    ("Sophia Loren", "L’acqua, la pasta e un sorriso sono i segreti della mia bellezza."),
    ("Anna Wintour", "Se ti senti bene con quello che indossi, trasmetti una sicurezza che gli altri percepiscono."),
    ("Karl Lagerfeld", "Chi indossa i jeans è sempre moderno."),
    ("Vera Wang", "La moda riguarda la vita quotidiana di tutti noi."),
    ("Gianni Versace", "La cosa più importante che puoi indossare è la personalità."),
    ("Audrey Hepburn", "La felicità è la salute e una cattiva memoria."),
    ("David Bowie", "La mia autostima viene dal fatto che sono diverso."),
    ("Salma Hayek", "Non mi interessa essere perfetta, voglio essere reale."),
    ("Jane Birkin", "Una piccola imperfezione è spesso il vero segno della bellezza."),
    ("Catherine Deneuve", "Se sai vestire bene, puoi vivere ovunque."),
    ("Oscar de la Renta", "La moda è un trend, lo stile vive dentro di te."),
    ("Gisele Bündchen", "La salute è la chiave della bellezza."),
    ("Immanuel Kant", "Il sublime ci eleva, il bello ci fa sentire vivi."),
    ("Coco Chanel", "La bellezza serve a noi donne per essere amate dagli uomini, la stupidità per amare gli uomini."),
    ("Vivienne Westwood", "Compra meno, scegli bene, fallo durare."),
    ("Dita Von Teese", "Puoi essere la pesca più matura e succosa del mondo e ci sarà sempre qualcuno a cui non piacciono le pesche."),
    ("Iris Apfel", "Più sei te stessa, meno sembri qualcun altro."),
    ("Sonia Rykiel", "La moda è come una dieta: non devi seguirla troppo seriamente."),
    ("Marisa Berenson", "La bellezza è un dono che dobbiamo rispettare."),
    ("Raquel Welch", "Il mio miglior trattamento di bellezza è dormire e sorridere molto."),
    ("Linda Evangelista", "Non mi alzo dal letto per meno di 10.000 dollari al giorno."),
    ("Naomi Campbell", "La bellezza è potere. Un sorriso è la sua spada."),
    ("Kate Moss", "Nulla ha un aspetto migliore di quanto ti senti davvero a tuo agio."),
    ("Frida Kahlo", "Piedi, a cosa mi servite se ho ali per volare?"),
    ("Brigitte Bardot", "Sono come sono. Mi piace essere naturale."),
    ("Marlene Dietrich", "Essere un po' misteriosa fa parte del fascino."),
    ("Madonna", "Mi sono reinventata molte volte. Questo è il segreto della mia longevità."),
    ("Christy Turlington", "La vera bellezza è essere curiosi."),
    ("Cleopatra", "Il benessere è il miglior ornamento della donna."),
    ("Charlotte Gainsbourg", "Lo stile è come ti muovi nel mondo, non come ti vesti."),
    ("Marina Abramovic", "La vera trasformazione parte dal corpo."),
    ("Serena Williams", "Nessuno può definire i tuoi limiti, solo tu stessa."),
    ("Cate Blanchett", "L’autenticità è la nuova bellezza."),
    ("Oprah Winfrey", "L’unico vero lusso nella vita è prendersi cura di sé stessi."),
    ("Arianna Huffington", "Il benessere non è un lusso, è una priorità."),
    ("Emma Watson", "La forza è accettare la propria vulnerabilità."),
    ("Giulia Gam", "Non c’è nulla di più bello che prendersi cura di sé."),
    ("Maya Angelou", "Se hai solo un sorriso, donalo alle persone che ami."),
    ("Carla Bruni", "La vera eleganza è la naturalezza, la salute."),
    ("Mae West", "Potrei resistere a tutto tranne che alle tentazioni."),
    ("Ru Paul", "Se non ami te stesso, come diavolo pretendi che qualcuno ti ami?"),
    ("Ashley Graham", "Il mio corpo è una rivoluzione."),
    ("Winnie Harlow", "La mia pelle racconta la mia storia, non la tua."),
    ("Lucille Ball", "Mi prendo molto poco sul serio. Sorrido ai miei difetti, li indosso come medaglie."),
    ("Ricky Gervais", "L’autostima non significa essere perfetti, ma saper ridere dei propri difetti."),
    ("Huda Kattan", "Non permettere a nessuno di decidere cosa ti rende bella."),
    ("Bebe Vio", "Il mio corpo non ha limiti, li ha solo la testa."),
    ("Ellen DeGeneres", "La mia dieta preferita è quella che mi fa felice."),
    ("Serena Williams", "Le mie braccia forti sono il segno delle mie vittorie."),
    ("Frida Kahlo", "Mi dipingo perché sono spesso sola e sono il soggetto che conosco meglio."),
    ("Lady Gaga", "Una volta che ami davvero chi sei, nessuno può fermarti."),
    ("Amy Schumer", "La perfezione è noiosa. Meglio essere veri, e riderci sopra."),
    ("Drew Barrymore", "Sono fiera delle mie imperfezioni. Sono parte di me."),
    ("Adele", "Non mi interessa ciò che pensano gli altri del mio corpo. È il mio."),
    ("Chrissy Teigen", "Non ho paura di mostrare la mia pancia. È la vita."),
    ("Lizzo", "Se vuoi vedere il mio corpo, preparati a vedere anche la mia anima."),
    ("Simonetta Agnello Hornby", "La vita è troppo breve per non mangiare dolci."),
    ("Paolo Poli", "Ogni ruga è una medaglia per essere sopravvissuti con ironia."),
    ("Jovanotti", "La vita è una figata. E anche il corpo che la vive."),
    ("Rosalind Franklin", "I segreti più profondi sono nascosti nella materia. E nel sorriso di chi osserva."),
    ("Luciano De Crescenzo", "Siamo angeli con un’ala soltanto: possiamo volare solo abbracciandoci."),
    ("Francesca Michielin", "La mia forza è la mia autenticità, non la mia forma."),
    ("Shonda Rhimes", "Fermati a respirare, a sentire il corpo: la felicità è qui."),
    ("Emanuela Grimalda", "Più ti vuoi bene, più le rughe spariscono dietro un sorriso."),
    ("Melissa McCarthy", "A volte il mio look urla, ma è solo un modo per ricordare a tutti che ci sono."),
    ("Vasco Rossi", "Ognuno col suo corpo e la sua testa, la sua festa."),
    ("Diletta Leotta", "L’attività fisica non serve solo per l’aspetto, ma per sentirsi bene."),
    ("Rita Levi-Montalcini", "Non temete le difficoltà del corpo: vi serviranno per rafforzare la mente."),
    ("Mara Maionchi", "Io mi piaccio così, con la mia voce roca e la mia risata rumorosa.")
]

report_bp = Blueprint('report', __name__)

@report_bp.route('/api/registro_corrispettivi')
def registro_corrispettivi():
    date_from = request.args.get('dateFrom')
    date_to = request.args.get('dateTo')
    if not date_from or not date_to:
        return jsonify({'error': 'Date non valide'}), 400

    try:
        start = datetime.strptime(date_from, "%Y-%m-%d")
        end = datetime.strptime(date_to, "%Y-%m-%d")
    except ValueError:
        return jsonify({'error': 'Formato data non valido. Usa YYYY-MM-DD.'}), 400

    receipts = (
        Receipt.query.filter(
            Receipt.created_at >= start,
            Receipt.created_at < end + timedelta(days=1),
            Receipt.is_fiscale == True
        ).all()
    )

    # Build mappe prodotto una sola volta
    id_is_product, name_is_product, _ = _build_product_maps(receipts)

    # Aggregazione
    agg = {}
    def ensure(day):
        if day not in agg:
            agg[day] = {'totale': 0.0, 'prodotti': 0.0, 'cash': 0.0, 'digitali': 0.0, 'altro': 0.0}
        return agg[day]

    for r in receipts:
        day = r.created_at.date()
        row = ensure(day)
        row['totale'] += float(r.total_amount or 0.0)

        for voce in _to_list(r.voci):
            prezzo_raw = voce.get('prezzo') if 'prezzo' in voce else voce.get('importo')
            try:
                importo = float(prezzo_raw or 0.0)
            except Exception:
                importo = 0.0

            # SOLO se la voce ha un service_id che mappa a sottocategoria "prodotti"
            sid = _parse_sid(voce)
            is_prod = bool(sid and id_is_product.get(sid, False))

            if is_prod:
                row['prodotti'] += importo

            metodo = (voce.get('metodo_pagamento') or voce.get('metodo') or '').strip().lower()
            if metodo == 'cash':
                row['cash'] += importo
            elif metodo in ('pos', 'digital', 'carta', 'bancomat'):
                row['digitali'] += importo
            elif metodo in ('bank', 'assegno', 'altro'):
                row['altro'] += importo

    giorni_settimana = {
        'Monday': 'Lunedì', 'Tuesday': 'Martedì', 'Wednesday': 'Mercoledì',
        'Thursday': 'Giovedì', 'Friday': 'Venerdì', 'Saturday': 'Sabato', 'Sunday': 'Domenica'
    }

    rows = []
    cur = start.date()
    last = end.date()
    while cur <= last:
        data_row = agg.get(cur, {'totale': 0.0, 'prodotti': 0.0, 'cash': 0.0, 'digitali': 0.0, 'altro': 0.0})
        totale = data_row['totale']
        prodotti = data_row['prodotti']
        servizi = max(0.0, totale - prodotti)
        rows.append({
            'data': cur.strftime('%d-%m-%Y'),
            'giorno': giorni_settimana[cur.strftime('%A')],
            'totale': round(totale, 2),
            'servizi': round(servizi, 2),
            'prodotti': round(prodotti, 2),
            'cash': round(data_row['cash'], 2),
            'digitali': round(data_row['digitali'], 2),
            'altro': round(data_row['altro'], 2),
        })
        cur += timedelta(days=1)

    totali = {
        'totale': round(sum(r['totale'] for r in rows), 2),
        'servizi': round(sum(r['servizi'] for r in rows), 2),
        'prodotti': round(sum(r['prodotti'] for r in rows), 2),
        'cash': round(sum(r['cash'] for r in rows), 2),
        'digitali': round(sum(r['digitali'] for r in rows), 2),
        'altro': round(sum(r['altro'] for r in rows), 2),
    }
    return jsonify({'rows': rows, 'totali': totali})

@report_bp.route('/report')
def report():
    oggi = date.today()
    user_id = session.get("user_id")
    user = db.session.get(User, user_id)

    start_day = datetime.combine(oggi, datetime.min.time())
    end_day = datetime.combine(oggi, datetime.max.time())

    if user and user.ruolo.value == "user":
        scontrini_fiscali = Receipt.query.filter(
            Receipt.created_at >= start_day,
            Receipt.created_at <= end_day,
            Receipt.is_fiscale == True
        ).all()
        scontrini_test = []
    else:
        scontrini_fiscali = Receipt.query.filter(
            Receipt.created_at >= start_day,
            Receipt.created_at <= end_day,
            Receipt.is_fiscale == True
        ).all()
        scontrini_test = Receipt.query.filter(
            Receipt.created_at >= start_day,
            Receipt.created_at <= end_day,
            Receipt.is_fiscale == False
        ).all()

    tutti = scontrini_fiscali + scontrini_test
    id_is_product, name_is_product, _ = _build_product_maps(tutti)

    totale_fiscale = sum(float(s.total_amount or 0) for s in scontrini_fiscali)
    totale_test = sum(float(s.total_amount or 0) for s in scontrini_test)
    totale = totale_fiscale + totale_test

    totale_prodotti = 0.0
    totale_servizi = 0.0
    totale_cash = 0.0
    totale_pos = 0.0
    totale_altro = 0.0

    for s in tutti:
        for voce in _to_list(s.voci):
            try:
                prezzo = float(voce.get('prezzo') if 'prezzo' in voce else (voce.get('importo') or 0.0))
            except Exception:
                prezzo = 0.0

            sid = _parse_sid(voce)
            is_prod = bool(sid and id_is_product.get(sid, False))

            if is_prod:
                totale_prodotti += prezzo
            else:
                totale_servizi += prezzo

            metodo = (voce.get('metodo_pagamento') or voce.get('metodo') or '').strip().lower()
            if metodo == 'cash':
                totale_cash += prezzo
            elif metodo == 'pos' or metodo in ('digital', 'carta', 'bancomat'):
                totale_pos += prezzo
            elif metodo:
                totale_altro += prezzo

    appuntamenti = Appointment.query.filter(func.date(Appointment.start_time) == oggi).all()
    totali = len(appuntamenti)
    completati = len([a for a in appuntamenti if a.stato in (
        AppointmentStatus.IN_ISTITUTO, AppointmentStatus.PAGATO, AppointmentStatus.NON_ARRIVATO
    )])
    noshow = len([a for a in appuntamenti if a.stato == AppointmentStatus.NON_ARRIVATO])

    business_info = BusinessInfo.query.first()

    return render_template(
        "report.html",
        totale=round(totale, 2),
        totale_servizi=round(totale_servizi, 2),
        totale_prodotti=round(totale_prodotti, 2),
        totale_cash=round(totale_cash, 2),
        totale_pos=round(totale_pos, 2),
        totale_altro=round(totale_altro, 2),
        completati=completati,
        totali=totali,
        noshow=noshow,
        business_info=business_info,
        current_user=user
    )

@report_bp.route('/api/report_day')
def report_day():
    date_str = request.args.get('date')
    if not date_str:
        return jsonify({'error': 'Data non valida'}), 400
    giorno = datetime.strptime(date_str, "%Y-%m-%d").date()

    user_id = session.get("user_id")
    user = db.session.get(User, user_id)

    start_day = datetime.combine(giorno, datetime.min.time())
    end_day = datetime.combine(giorno, datetime.max.time())

    receipts_query = Receipt.query.filter(
        Receipt.created_at >= start_day,
        Receipt.created_at <= end_day
    )
    if user and user.ruolo.value == "user":
        scontrini_fiscali = receipts_query.filter(Receipt.is_fiscale == True).all()
        scontrini_test = []
    else:
        scontrini_fiscali = receipts_query.filter(Receipt.is_fiscale == True).all()
        scontrini_test = receipts_query.filter(Receipt.is_fiscale == False).all()

    passaggi_cassa = len(scontrini_fiscali) + len(scontrini_test)

    tutti = scontrini_fiscali + scontrini_test
    id_is_product, name_is_product, services_by_id = _build_product_maps(tutti)

    totale_fiscale = sum(float(s.total_amount or 0) for s in scontrini_fiscali)
    totale_test = sum(float(s.total_amount or 0) for s in scontrini_test)
    totale = totale_fiscale + totale_test

    totale_prodotti = 0.0
    totale_servizi = 0.0
    totale_cash = 0.0
    totale_pos = 0.0
    totale_altro = 0.0

    cash_fiscale = 0.0
    pos_fiscale = 0.0
    altro_fiscale = 0.0
    cash_test = 0.0
    pos_test = 0.0
    altro_test = 0.0

    estetica_fiscale = 0.0
    estetica_test = 0.0
    solarium_fiscale = 0.0
    solarium_test = 0.0

    # Nuove variabili per breakdown metodi e categorie
    cash_servizi = 0.0
    cash_prodotti = 0.0
    pos_servizi = 0.0
    pos_prodotti = 0.0
    altro_servizi = 0.0
    altro_prodotti = 0.0
    estetica_servizi = 0.0
    estetica_prodotti = 0.0
    solarium_servizi = 0.0
    solarium_prodotti = 0.0

    for s in tutti:
        is_fisc = bool(s.is_fiscale)
        for voce in _to_list(s.voci):
            try:
                prezzo = float(voce.get('prezzo') if 'prezzo' in voce else (voce.get('importo') or 0.0))
            except Exception:
                prezzo = 0.0

            sid = _parse_sid(voce)
            is_prod = bool(sid and id_is_product.get(sid, False))

            if is_prod:
                totale_prodotti += prezzo
            else:
                totale_servizi += prezzo

            metodo = (voce.get('metodo_pagamento') or voce.get('metodo') or '').strip().lower()
            if metodo == 'cash':
                totale_cash += prezzo
                if is_fisc: cash_fiscale += prezzo
                else:       cash_test += prezzo
                if is_prod:
                    cash_prodotti += prezzo
                else:
                    cash_servizi += prezzo
            elif metodo in ('pos', 'digital', 'carta', 'bancomat'):
                totale_pos += prezzo
                if is_fisc: pos_fiscale += prezzo
                else:       pos_test += prezzo
                if is_prod:
                    pos_prodotti += prezzo
                else:
                    pos_servizi += prezzo
            elif metodo:
                totale_altro += prezzo
                if is_fisc: altro_fiscale += prezzo
                else:       altro_test += prezzo
                if is_prod:
                    altro_prodotti += prezzo
                else:
                    altro_servizi += prezzo

            svc = services_by_id.get(sid) if sid else None
            if svc and svc.servizio_categoria == ServiceCategory.Estetica:
                if is_fisc: estetica_fiscale += prezzo
                else:       estetica_test += prezzo
                if is_prod:
                    estetica_prodotti += prezzo
                else:
                    estetica_servizi += prezzo
            elif svc and svc.servizio_categoria == ServiceCategory.Solarium:
                if is_fisc: solarium_fiscale += prezzo
                else:       solarium_test += prezzo
                if is_prod:
                    solarium_prodotti += prezzo
                else:
                    solarium_servizi += prezzo

    # Appuntamenti del giorno (mantieni logica esistente)
    appuntamenti = Appointment.query.filter(
        func.date(Appointment.start_time) == giorno
    ).join(Client, Appointment.client_id == Client.id).join(Service, Appointment.service_id == Service.id).filter(
        Client.cliente_nome.ilike('%dummy%') == False,
        Client.cliente_cognome.ilike('%dummy%') == False,
        Service.servizio_nome.ilike('%dummy%') == False
    ).all()

    appuntamenti_validi = appuntamenti

    # Gruppi per cliente
    gruppi = []
    for key, group in groupby(appuntamenti_validi, key=lambda a: a.client.cliente_nome if a.client else None):
        gruppi.append(list(group))
    totali = len(gruppi)

    completati = sum(
        all(a.stato == AppointmentStatus.PAGATO for a in gruppo)
        for gruppo in gruppi
    )

    # Incasso stimato
    incasso_stimato_totale = 0.0
    incasso_stimato_solarium = 0.0
    incasso_stimato_estetica = 0.0
    for a in appuntamenti_validi:
        prezzo = a.service.servizio_prezzo if a.service else 0
        incasso_stimato_totale += prezzo
        if a.service and a.service.servizio_categoria == ServiceCategory.Solarium:
            incasso_stimato_solarium += prezzo
        elif a.service and a.service.servizio_categoria == ServiceCategory.Estetica:
            incasso_stimato_estetica += prezzo

    # Passaggi cassa calendario
    passaggi_cassa_calendario = len(set(
        a.client.cliente_nome
        for a in appuntamenti_validi
        if a.client and a.stato == AppointmentStatus.PAGATO
    ))

    # Completati e noshow per cliente
    completati = 0
    noshow = 0
    clienti_unici = set(a.client.cliente_nome for a in appuntamenti_validi if a.client)
    for nome_cliente in clienti_unici:
        appuntamenti_cliente = [a for a in appuntamenti_validi if a.client and a.client.cliente_nome == nome_cliente]
        if all(a.stato == AppointmentStatus.PAGATO for a in appuntamenti_cliente):
            completati += 1
        if any(a.stato == AppointmentStatus.NON_ARRIVATO for a in appuntamenti_cliente):
            noshow += 1
    totali = len(clienti_unici)

    # KPI mese (come versione attuale)
    primo_giorno_mese = giorno.replace(day=1)
    if giorno.month == 12:
        primo_giorno_mese_prox = giorno.replace(year=giorno.year + 1, month=1, day=1)
    else:
        primo_giorno_mese_prox = giorno.replace(month=giorno.month + 1, day=1)
    ultimo_giorno_mese = primo_giorno_mese_prox - timedelta(days=1)

    totale_mese = db.session.query(func.sum(Receipt.total_amount)).filter(
        Receipt.created_at >= datetime.combine(primo_giorno_mese, datetime.min.time()),
        Receipt.created_at <= datetime.combine(ultimo_giorno_mese, datetime.max.time())
    ).scalar() or 0

    giorni_mese = (ultimo_giorno_mese - primo_giorno_mese).days + 1
    media_mese_ricavi = (totale_mese / giorni_mese) if giorni_mese else 0

    medie_giornaliere_fisse = [600, 500, 700, 800, 900, 1000, 1000, 1000, 900, 700, 500, 800]
    media_giornaliera_riferimento = medie_giornaliere_fisse[giorno.month - 1]

    appuntamenti_mese = Appointment.query.filter(
        func.date(Appointment.start_time) >= primo_giorno_mese,
        func.date(Appointment.start_time) <= ultimo_giorno_mese
    ).join(Client, Appointment.client_id == Client.id).join(Service, Appointment.service_id == Service.id).filter(
        Client.cliente_nome.ilike('%dummy%') == False,
        Client.cliente_cognome.ilike('%dummy%') == False,
        Service.servizio_nome.ilike('%dummy%') == False
    ).all()

    clienti_serviti_per_giorno = defaultdict(set)
    noshow_per_giorno = defaultdict(int)
    totali_per_giorno = defaultdict(set)
    for a in appuntamenti_mese:
        g = a.start_time.date()
        totali_per_giorno[g].add(a.client_id)
        if a.stato == AppointmentStatus.PAGATO:
            clienti_serviti_per_giorno[g].add(a.client_id)
        if a.stato == AppointmentStatus.NON_ARRIVATO:
            noshow_per_giorno[g] += 1

    media_mese_clienti = (sum(len(v) for v in clienti_serviti_per_giorno.values()) / giorni_mese) if giorni_mese else 0
    media_mese_noshow = (sum(noshow_per_giorno.values()) / giorni_mese) if giorni_mese else 0
    media_mese_completamento = (
        sum(
            (len(clienti_serviti_per_giorno[g]) / len(totali_per_giorno[g]) * 100) if len(totali_per_giorno[g]) > 0 else 0
            for g in totali_per_giorno
        ) / giorni_mese if giorni_mese else 0
    )

    return jsonify({
        "totale": round(totale, 2),
        "totale_servizi": round(totale_servizi, 2),
        "totale_prodotti": round(totale_prodotti, 2),
        "totale_cash": round(totale_cash, 2),
        "totale_pos": round(totale_pos, 2),
        "totale_altro": round(totale_altro, 2),
        "totale_test": round(totale_test, 2),
        "totale_fiscale": round(totale_fiscale, 2),
        "completati": completati,
        "totali": totali,
        "noshow": noshow,
        "cash_fiscale": round(cash_fiscale, 2),
        "pos_fiscale": round(pos_fiscale, 2),
        "altro_fiscale": round(altro_fiscale, 2),
        "cash_test": round(cash_test, 2),
        "pos_test": round(pos_test, 2),
        "altro_test": round(altro_test, 2),
        "estetica_fiscale": round(estetica_fiscale, 2),
        "estetica_test": round(estetica_test, 2),
        "solarium_fiscale": round(solarium_fiscale, 2),
        "solarium_test": round(solarium_test, 2),
        "media_mese_ricavi": round(media_mese_ricavi, 2),
        "media_mese_clienti": round(media_mese_clienti, 2),
        "media_mese_noshow": round(media_mese_noshow, 2),
        "media_mese_completamento": round(media_mese_completamento, 2),
        "media_giornaliera_riferimento": media_giornaliera_riferimento,
        "passaggi_cassa": passaggi_cassa,
        "passaggi_cassa_calendario": passaggi_cassa_calendario,
        "incasso_stimato_totale": round(incasso_stimato_totale, 2),
        "incasso_stimato_solarium": round(incasso_stimato_solarium, 2),
        "incasso_stimato_estetica": round(incasso_stimato_estetica, 2),
        "cash_servizi": round(cash_servizi, 2),
        "cash_prodotti": round(cash_prodotti, 2),
        "pos_servizi": round(pos_servizi, 2),
        "pos_prodotti": round(pos_prodotti, 2),
        "altro_servizi": round(altro_servizi, 2),
        "altro_prodotti": round(altro_prodotti, 2),
        "estetica_servizi": round(estetica_servizi, 2),
        "estetica_prodotti": round(estetica_prodotti, 2),
        "solarium_servizi": round(solarium_servizi, 2),
        "solarium_prodotti": round(solarium_prodotti, 2),
    })

@report_bp.route('/api/appuntamenti_presi_oggi')
def appuntamenti_presi_oggi():
    oggi = date.today()
    inizio = datetime.combine(oggi, datetime.min.time())
    fine = datetime.combine(oggi, datetime.max.time())

    totale = Appointment.query.filter(
        Appointment.created_at >= inizio,
        Appointment.created_at <= fine
    ).count()

    gestionale = Appointment.query.filter(
        Appointment.created_at >= inizio,
        Appointment.created_at <= fine,
        Appointment.source == AppointmentSource.gestionale
    ).count()

    web = Appointment.query.filter(
        Appointment.created_at >= inizio,
        Appointment.created_at <= fine,
        Appointment.source == AppointmentSource.web
    ).count()

    return jsonify({
        "presi_totale": totale,
        "presi_gestionale": gestionale,
        "presi_web": web
    })

@report_bp.route('/api/incasso_stimato_oggi')
def incasso_stimato_oggi():
    oggi = date.today()
    inizio = datetime.combine(oggi, datetime.min.time())
    fine = datetime.combine(oggi, datetime.max.time())

    appointments = Appointment.query.filter(
        Appointment.start_time >= inizio,
        Appointment.start_time <= fine
    ).all()

    totale = 0
    solarium = 0
    estetica = 0

    for app in appointments:
        prezzo = app.service.servizio_prezzo if app.service else 0
        totale += prezzo
        if app.service and app.service.servizio_categoria == ServiceCategory.Solarium:
            solarium += prezzo
        elif app.service and app.service.servizio_categoria == ServiceCategory.Estetica:
            estetica += prezzo

    return jsonify({
        "totale": totale,
        "solarium": solarium,
        "estetica": estetica
    })

@report_bp.route('/api/top_clienti_anno')
def top_clienti_anno():
    year = request.args.get('year', default=date.today().year, type=int)

    # Prima calcola la spesa totale per ogni cliente nell'anno
    subq = (
        db.session.query(
            Receipt.cliente_id.label('client_id'),
            func.sum(Receipt.total_amount).label('totale_speso')
        )
        .filter(func.extract('year', Receipt.created_at) == year)
        .group_by(Receipt.cliente_id)
    ).subquery()

    appointments = (
        db.session.query(
            Appointment.client_id,
            func.count(Appointment.id).label('num_app'),
            func.sum(Appointment._duration).label('tot_minuti'),
            subq.c.totale_speso
        )
        .join(subq, Appointment.client_id == subq.c.client_id)
        .filter(func.extract('year', Appointment.start_time) == year)
        .group_by(Appointment.client_id, subq.c.totale_speso)
        .order_by(subq.c.totale_speso.desc())
        .limit(10)
        .all()
    )

    result = []
    for client_id, num_app, tot_minuti, totale_speso in appointments:
        client = db.session.get(Client, client_id)
        if not client:
            continue
        result.append({
            "id": client_id,
            "nome": getattr(client, "cliente_nome", ""),
            "cognome": getattr(client, "cliente_cognome", ""),
            "num_app": num_app,
            "tot_minuti": tot_minuti,
            "totale_speso": totale_speso or 0
        })
    return jsonify(result)

@report_bp.route('/api/appuntamenti_giorno')
def appuntamenti_giorno():
    date_str = request.args.get('date')
    if not date_str:
        return jsonify({'error': 'Data non valida'}), 400
    giorno = datetime.strptime(date_str, "%Y-%m-%d").date()
    appuntamenti = Appointment.query.filter(
        func.date(Appointment.start_time) == giorno
    ).all()
    # Restituisci solo gli id dei clienti
    return jsonify([
        {"client_id": a.client_id, "id": a.id} for a in appuntamenti if a.client_id
    ])

@report_bp.route('/api/heatmap_appuntamenti')
def heatmap_appuntamenti():
    data_rif = request.args.get("data_rif")
    if data_rif:
        data_rif = datetime.strptime(data_rif, "%Y-%m-%d")
    else:
        data_rif = datetime.today()

    giorni = [data_rif - timedelta(days=i) for i in reversed(range(10))]
    giorni_label = [g.strftime('%d/%m') for g in giorni]
    ore = [f"{h:02d}" for h in range(8, 21)]

    # FILTRA: escludi appuntamenti OFF (client/service null o dummy)
    results = (
        db.session.query(
            func.date(Appointment.start_time).label('giorno'),
            func.extract('hour', Appointment.start_time).label('ora'),
            func.count(Appointment.id).label('count')
        )
        .join(Client, Appointment.client_id == Client.id)
        .join(Service, Appointment.service_id == Service.id)
        .filter(
            Appointment.start_time >= data_rif - timedelta(days=10),
            Appointment.start_time <= data_rif,
            Client.cliente_nome.isnot(None),
            Client.cliente_cognome.isnot(None),
            Service.servizio_nome.isnot(None),
            func.lower(Client.cliente_nome) != 'dummy',
            func.lower(Client.cliente_cognome) != 'dummy',
            func.lower(Service.servizio_nome) != 'dummy'
        )
        .group_by(
            func.date(Appointment.start_time),
            func.extract('hour', Appointment.start_time)
        )
        .all()
    )

    valori = []
    for row in results:
        y = (data_rif.date() - row.giorno).days
        x = int(row.ora) - 8
        if 0 <= x < len(ore):
            valori.append({'x': x, 'y': y, 'v': row.count})

    operatori_totali = Operator.query.filter_by(is_deleted=False, is_visible=True).count()

    return jsonify({
        'giorni': giorni_label,
        'ore': ore,
        'valori': valori,
        'max_legend': operatori_totali + 1
    })

@report_bp.route('/api/heatmap_incassi')
def heatmap_incassi():

    data_rif = request.args.get("data_rif")
    if data_rif:
        data_rif = datetime.strptime(data_rif, "%Y-%m-%d")
    else:
        data_rif = datetime.today()

    user_id = session.get("user_id")
    user = db.session.get(User, user_id)

    giorni = [data_rif - timedelta(days=i) for i in reversed(range(10))]
    giorni_label = [g.strftime('%d/%m') for g in giorni]
    ore = [f"{h:02d}" for h in range(8, 21)]  # es: 08-20

    valori = []
    max_incasso = 0
    for y, giorno in enumerate(giorni):
        for x, ora in enumerate(ore):
            start = datetime.combine(giorno, datetime.min.time()).replace(hour=int(ora))
            end = start + timedelta(hours=1)
            query = db.session.query(func.sum(Receipt.total_amount)).filter(
                Receipt.created_at >= start,
                Receipt.created_at < end
            )
            # Filtro fiscale solo per user
            if user and user.ruolo.value == "user":
                query = query.filter(Receipt.is_fiscale == True)
            incasso = query.scalar() or 0
            valori.append({'x': x, 'y': y, 'v': float(incasso)})
            if incasso > max_incasso:
                max_incasso = incasso

    return jsonify({
        'giorni': giorni_label,
        'ore': ore,
        'valori': valori,
        'max_legend': max_incasso
    })

@report_bp.route('/api/next_appointments')
def next_appointments():
    now = datetime.now()
    appointments = (
        Appointment.query
        .filter(Appointment.start_time >= now)
        .order_by(Appointment.start_time.asc())
        .limit(6)  # Modifica qui il limite se vuoi più/meno appuntamenti
        .all()
    )

    # FILTRO IDENTICO AL PDF
    appointments = [
        a for a in appointments
        if a.client is not None and getattr(a.client, "cliente_nome", "").lower() != "dummy"
        and a.service is not None and getattr(a.service, "servizio_nome", "").lower() != "dummy"
    ]

    result = []
    for appt in appointments:
        # Rileva blocco OFF (client/service mancanti o "dummy")
        is_off = (
            appt.client is None or
            getattr(appt.client, "cliente_nome", "").lower() in ["dummy"] or
            getattr(appt.client, "cliente_cognome", "").lower() in ["dummy"] or
            appt.service is None or
            getattr(appt.service, "servizio_nome", "").lower() == "dummy"
        )

        operator_name = ""
        try:
            # Se hai nome e cognome disponibili, usa entrambi
            operator_name = f"{appt.operator.user_nome} {appt.operator.user_cognome}".strip() if appt.operator else ""
        except Exception:
            operator_name = appt.operator.user_nome if getattr(appt, "operator", None) else ""

        result.append({
            "id": appt.id,
            "start_time": appt.start_time.strftime("%H:%M"),
            "date": appt.start_time.strftime("%d/%m/%Y"),
            "client": "OFF" if is_off else (f"{appt.client.cliente_nome} {appt.client.cliente_cognome}" if appt.client else ""),
            "service": "" if is_off else (appt.service.servizio_nome if appt.service else ""),
            "operator": operator_name,
            "is_off": is_off,
            "note": (appt.note or "").strip() if is_off else ""   # <--- nota solo se OFF
        })

    return jsonify(result)
                                            
@report_bp.route('/api/agenda_data')
def agenda_data():
    date = request.args.get('date')
    appointments = Appointment.query.filter(
        db.func.date(Appointment.start_time) == date
    ).order_by(Appointment.start_time).all()

    # Filtra in Python i blocchi OFF/dummy
    appointments = [
        a for a in appointments
        if a.client is not None and getattr(a.client, "cliente_nome", "").lower() != "dummy"
        and a.service is not None and getattr(a.service, "servizio_nome", "").lower() != "dummy"
    ]

    result = []
    for appt in appointments:
        operator_name = ""
        try:
            operator_name = f"{appt.operator.user_nome} {appt.operator.user_cognome}".strip() if appt.operator else ""
        except Exception:
            operator_name = appt.operator.user_nome if getattr(appt, "operator", None) else ""

        result.append({
            "id": appt.id,
            "start_time": appt.start_time.strftime("%H:%M"),
            "date": appt.start_time.strftime("%d/%m/%Y"),
            "client": f"{appt.client.cliente_nome} {appt.client.cliente_cognome}" if appt.client else "",
            "service": appt.service.servizio_nome if appt.service else "",
            "operator": operator_name,
            "note": (appt.note or "").strip()
        })

    return jsonify(result)

@report_bp.route('/api/business_city')
def business_city():
    info = BusinessInfo.query.first()
    city = info.city.strip() if info and info.city else "Milano"
    province = info.province.strip() if info and info.province else ""
    return jsonify({"city": city, "province": province})

@report_bp.route('/api/appuntamenti_presi_giorno')
def appuntamenti_presi_giorno():
    date_str = request.args.get('date')
    if not date_str:
        return jsonify({'error': 'Data non valida'}), 400
    
    giorno = datetime.strptime(date_str, "%Y-%m-%d").date()
    
    # Query per appuntamenti creati in quel giorno specifico
    appuntamenti_totali = Appointment.query.filter(
        func.date(Appointment.created_at) == giorno
    ).count()
    
    # Appuntamenti creati manualmente (source è null o vuoto)
    appuntamenti_gestionale = Appointment.query.filter(
        func.date(Appointment.created_at) == giorno,
        Appointment.source == AppointmentSource.gestionale
    ).count()
    
    # Appuntamenti creati via web booking
    appuntamenti_web = Appointment.query.filter(
        func.date(Appointment.created_at) == giorno,
        Appointment.source == AppointmentSource.web
    ).count()
    
    return jsonify({
        'presi_totale': appuntamenti_totali,
        'presi_gestionale': appuntamenti_gestionale,
        'presi_web': appuntamenti_web
    })

@report_bp.route('/api/oroscopo_giornaliero')
def oroscopo_giornaliero():
    if not GEMINI_API_KEY:
        current_app.logger.warning("GEMINI_API_KEY non impostata: API Gemini saltata.")
        return jsonify({
            "previsione": "Previsione non disponibile al momento.",
            "citazione": "",
            "consiglio": ""
        })
    
    prompt = (
        "Scrivi una breve previsione oroscopo generale per il centro estetico con tono positivo, massimo 3 frasi in italiano, iniziando con un simbolo astrologico come 🔮, 🪐, ⭐ o 🌟.\n"
        "Poi a capo scrivi un consiglio del giorno per il centro estetico, iniziando con 💡 e senza inserire 'consiglio del giorno' nel testo."
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    body = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }
    try:
        response = requests.post(url, json=body, headers={"Content-Type": "application/json"}, timeout=10)
        data = response.json()
        testo = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        if not testo:
            previsione = "Previsione non disponibile al momento."
            citazione = ""
            consiglio = ""
        else:
            # Divide il testo in base alle righe
            righe = [r.strip() for r in testo.split('\n') if r.strip()]
            # Cerca le parti
            previsione = next((r for r in righe if r.startswith("♈") or r.startswith("🔮") or r.startswith("🪐") or r.startswith("⭐") or r.startswith("🌟")), "")
            autore, cit = random.choice(CITAZIONI)
            citazione = f"💄 {cit} ({autore})"
            consiglio = next((r for r in righe if r.startswith("💡")), "")
            # Se non trova, fallback
            if not previsione and righe:
                previsione = righe[0]
            if not citazione and len(righe) > 1:
                citazione = righe[1]
            if not consiglio and len(righe) > 2:
                consiglio = righe[2]
    except Exception as e:
        current_app.logger.error("Errore durante la chiamata all'API Gemini per l'oroscopo: %s", str(e))
        previsione = "Previsione non disponibile al momento."
        citazione = ""
        consiglio = ""

    return jsonify({
        "previsione": previsione,
        "citazione": citazione,
        "consiglio": consiglio
    })

@report_bp.route('/api/report_incasso_sottocategorie')
def report_incasso_sottocategorie():
    try:
        categoria = request.args.get('categoria')
        date_from = request.args.get('dateFrom')
        date_to = request.args.get('dateTo')

        if not categoria or not date_from or not date_to:
            return jsonify({'error': 'Parametri mancanti'}), 400

        try:
            categoria_enum = ServiceCategory[categoria.capitalize()]
        except KeyError:
            return jsonify({'error': 'Categoria non valida'}), 400

        user_id = session.get("user_id")
        user = db.session.get(User, user_id)
        filtro_fiscale = True if (user and user.ruolo.value == "user") else None

        start = datetime.strptime(date_from, "%Y-%m-%d")
        end = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
        receipts_q = Receipt.query.filter(
            Receipt.created_at >= start,
            Receipt.created_at < end
        )
        if filtro_fiscale is not None:
            receipts_q = receipts_q.filter(Receipt.is_fiscale == filtro_fiscale)
        receipts = receipts_q.all()

        # Colleziona tutti i service_id per un fetch unico
        servizio_ids = set()
        for r in receipts:
            for voce in _to_list(r.voci):
                sid = _parse_sid(voce)
                if sid:
                    servizio_ids.add(sid)

        services = {}
        if servizio_ids:
            svc_list = Service.query.filter(Service.id.in_(list(servizio_ids)))\
                                    .options(joinedload(Service.servizio_sottocategoria)).all()
            services = {s.id: s for s in svc_list}

        # Aggrega per sottocategoria
        sottocategorie_map = {}
        for r in receipts:
            for voce in _to_list(r.voci):
                sid = _parse_sid(voce)
                if not sid:
                    continue
                servizio = services.get(sid)
                if not servizio or servizio.servizio_categoria != categoria_enum:
                    continue

                sottocategoria_id = servizio.servizio_sottocategoria_id
                if not sottocategoria_id:
                    continue

                sottocategoria_nome = "Senza sottocategoria"
                if servizio.servizio_sottocategoria:
                    sc = servizio.servizio_sottocategoria
                    sottocategoria_nome = getattr(sc, 'nome', None) or "Senza sottocategoria"

                try:
                    importo = float(voce.get('prezzo') or 0)
                except Exception:
                    importo = 0.0

                rec = sottocategorie_map.setdefault(
                    sottocategoria_id,
                    {'nome': sottocategoria_nome, 'totale': 0.0, 'passaggi_cassa': 0}
                )
                rec['totale'] += importo
                rec['passaggi_cassa'] += 1

        sottocategorie_result = [
            {
                'id': sid,
                'nome': dati['nome'],
                'totale': round(dati['totale'], 2),
                'passaggi_cassa': dati['passaggi_cassa']
            }
            for sid, dati in sottocategorie_map.items()
        ]

        return jsonify(sottocategorie_result)
    except Exception as e:
        current_app.logger.error(f"Errore in report_incasso_sottocategorie: {e}")
        return jsonify({'error': 'Errore interno del server'}), 500
    
@report_bp.route('/api/report_incasso_servizi')
def report_incasso_servizi():
    categoria = request.args.get('categoria')
    sottocategoria_id = request.args.get('sottocategoria_id')
    date_from = request.args.get('dateFrom')
    date_to = request.args.get('dateTo')

    if not categoria or not date_from or not date_to:
        return jsonify({'error': 'Parametri mancanti'}), 400

    try:
        categoria_enum = ServiceCategory[categoria.capitalize()]
    except KeyError:
        return jsonify({'error': 'Categoria non valida'}), 400

    user_id = session.get("user_id")
    user = db.session.get(User, user_id)
    filtro_fiscale = True if (user and user.ruolo.value == "user") else None

    start = datetime.strptime(date_from, "%Y-%m-%d")
    end = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
    receipts_q = Receipt.query.filter(
        Receipt.created_at >= start,
        Receipt.created_at < end
    )
    if filtro_fiscale is not None:
        receipts_q = receipts_q.filter(Receipt.is_fiscale == filtro_fiscale)
    receipts = receipts_q.all()

    # Colleziona tutti i service_id per un fetch unico
    servizio_ids = set()
    for r in receipts:
        for voce in _to_list(r.voci):
            sid = _parse_sid(voce)
            if sid:
                servizio_ids.add(sid)

    services = {}
    if servizio_ids:
        svc_list = Service.query.filter(Service.id.in_(list(servizio_ids))).all()
        services = {s.id: s for s in svc_list}

    # Aggrega per servizio
    servizi_map = {}
    for r in receipts:
        for voce in _to_list(r.voci):
            sid = _parse_sid(voce)
            if not sid:
                continue
            servizio = services.get(sid)
            if not servizio or servizio.servizio_categoria != categoria_enum:
                continue

            if sottocategoria_id and sottocategoria_id not in ("undefined", "null", ""):
                try:
                    sottocategoria_id_int = int(sottocategoria_id)
                except (ValueError, TypeError):
                    continue
                if servizio.servizio_sottocategoria_id != sottocategoria_id_int:
                    continue

            try:
                importo = float(voce.get('prezzo') or 0)
            except Exception:
                importo = 0.0

            rec = servizi_map.setdefault(sid, {'nome': servizio.servizio_nome, 'totale': 0.0, 'passaggi_cassa': 0})
            rec['totale'] += importo
            rec['passaggi_cassa'] += 1

    servizi_result = [
        {
            'id': sid,
            'nome': dati['nome'],
            'totale': round(dati['totale'], 2),
            'passaggi_cassa': dati['passaggi_cassa']
        }
        for sid, dati in servizi_map.items()
    ]

    return jsonify(servizi_result)

@report_bp.route('/api/report_passaggi_cassa')
def report_passaggi_cassa():
    date_from = request.args.get('dateFrom')
    date_to = request.args.get('dateTo')
    if not date_from or not date_to:
        return jsonify({'error': 'Date non valide'}), 400

    start = datetime.strptime(date_from, "%Y-%m-%d")
    end = datetime.strptime(date_to, "%Y-%m-%d")

    receipts = Receipt.query.filter(
        Receipt.created_at >= start,
        Receipt.created_at < end + timedelta(days=1)
    ).all()

    rows = []
    for r in receipts:
        giorno = r.created_at.date()
        is_fiscale = r.is_fiscale
        client = r.cliente
        sesso = getattr(client, "cliente_sesso", "").lower() if client else ""
        rows.append({
            'data': giorno,
            'fiscale': is_fiscale,
            'uomo': 1 if sesso == "m" else 0,
            'donna': 1 if sesso == "f" else 0
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.groupby('data').agg(
            totali=('fiscale', 'count'),
            fiscali=('fiscale', 'sum'),
            uomo=('uomo', 'sum'),
            donna=('donna', 'sum')
        ).reset_index()
    else:
        df = pd.DataFrame(columns=['data', 'totali', 'fiscali', 'uomo', 'donna'])

    all_days = pd.date_range(start=start, end=end)
    df_all = pd.DataFrame({'data': all_days.date})
    df = df_all.merge(df, on='data', how='left').fillna(0)

    giorni_settimana = {
        'Monday': 'Lunedì',
        'Tuesday': 'Martedì',
        'Wednesday': 'Mercoledì',
        'Thursday': 'Giovedì',
        'Friday': 'Venerdì',
        'Saturday': 'Sabato',
        'Sunday': 'Domenica'
    }
    df['giorno'] = df['data'].apply(lambda d: giorni_settimana[d.strftime('%A')])
    df['data'] = df['data'].apply(lambda d: d.strftime('%d-%m-%Y'))
    df = df[['data', 'giorno', 'totali', 'fiscali', 'uomo', 'donna']]

    totali = df[['totali', 'fiscali', 'uomo', 'donna']].sum().astype(int).to_dict()
    return jsonify({
        'rows': df.to_dict(orient='records'),
        'totali': totali
    })

@report_bp.route('/api/report_clienti')
def report_clienti():

    date_from = request.args.get('dateFrom')
    date_to = request.args.get('dateTo')
    if not date_from or not date_to:
        return jsonify({'error': 'Date non valide'}), 400

    start = datetime.strptime(date_from, "%Y-%m-%d")
    end = datetime.strptime(date_to, "%Y-%m-%d")

    receipts = Receipt.query.filter(
        Receipt.created_at >= start,
        Receipt.created_at < end + timedelta(days=1)
    ).all()

    # Raggruppa per cliente
    clienti = {}
    for r in receipts:
        if not r.cliente: continue
        cid = r.cliente.id
        nome = f"{r.cliente.cliente_nome} {r.cliente.cliente_cognome}"
        data_pass = r.created_at.strftime('%d-%m-%Y')
        if cid not in clienti:
            clienti[cid] = {
                'nome': nome,
                'passaggi': 0,
                'ultimo': data_pass,
                'date_list': []
            }
        clienti[cid]['passaggi'] += 1
        clienti[cid]['date_list'].append(r.created_at.date())
        # Aggiorna ultimo passaggio se più recente
        if r.created_at.strftime('%d-%m-%Y') > clienti[cid]['ultimo']:
            clienti[cid]['ultimo'] = r.created_at.strftime('%d-%m-%Y')

    # Calcola frequenza
    def calcola_frequenza(date_list, start, end):
        if not date_list: return "occasionale", 4
        giorni = (end - start).days + 1
        n_pass = len(date_list)
        if giorni < 7:
            return "occasionale", 4
        sett = giorni / 7
        freq = n_pass / sett
        if freq > 2:
            return "giornaliera", 0
        elif freq > 1:
            return "settimanale", 1
        elif freq > 0.5:
            return "bi-settimanale", 2
        elif freq > 0.2:
            return "mensile", 3
        else:
            return "occasionale", 4

    rows = []
    for c in clienti.values():
        freq, freq_idx = calcola_frequenza(c['date_list'], start, end)
        rows.append({
            'nome': c['nome'],
            'passaggi': c['passaggi'],
            'ultimo': c['ultimo'],
            'frequenza': freq,
            'frequenza_idx': freq_idx
        })

    return jsonify({'rows': rows})

@report_bp.route('/api/report_incasso_categoria_totali')
def report_incasso_categoria_totali():

    date_from = request.args.get('dateFrom')
    date_to = request.args.get('dateTo')
    if not date_from or not date_to:
        return jsonify({'error': 'Date non valide'}), 400

    start = datetime.strptime(date_from, "%Y-%m-%d")
    end = datetime.strptime(date_to, "%Y-%m-%d")

    receipts = Receipt.query.filter(
        Receipt.created_at >= start,
        Receipt.created_at < end + timedelta(days=1)
    ).all()

    totale = 0
    estetica = 0
    solarium = 0
    passaggi_estetica = 0
    passaggi_solarium = 0

    for r in receipts:
        ha_estetica = False
        ha_solarium = False
        for voce in _to_list(r.voci):
            try:
                prezzo = float(voce.get('prezzo') if 'prezzo' in voce else (voce.get('importo') or 0))
            except Exception:
                prezzo = 0.0

            categoria_val = (voce.get("categoria") or "").strip()
            if not categoria_val:
                sid = _parse_sid(voce)
                servizio = db.session.get(Service, sid) if sid else None
                if servizio and servizio.servizio_categoria:
                    categoria_val = servizio.servizio_categoria.value

            totale += prezzo
            if categoria_val in ["Estetica", "Prodotti Estetica", "Servizi Estetica"]:
                estetica += prezzo
                ha_estetica = True
            elif categoria_val in ["Solarium", "Prodotti Solarium", "Servizi Solarium"]:
                solarium += prezzo
                ha_solarium = True

        if ha_estetica:
            passaggi_estetica += 1
        if ha_solarium:
            passaggi_solarium += 1

    estetica_pct = round((estetica / totale * 100), 1) if totale else 0
    solarium_pct = round((solarium / totale * 100), 1) if totale else 0

    return jsonify({
        'totale': round(totale, 2),
        'estetica': round(estetica, 2),
        'solarium': round(solarium, 2),
        'estetica_pct': estetica_pct,
        'solarium_pct': solarium_pct,
        'passaggi_estetica': passaggi_estetica,
        'passaggi_solarium': passaggi_solarium
    })

@report_bp.route('/api/report_operatori')
def report_operatori():

    date_from = request.args.get('dateFrom')
    date_to = request.args.get('dateTo')
    if not date_from or not date_to:
        return jsonify({'error': 'Date non valide'}), 400

    start = datetime.strptime(date_from, "%Y-%m-%d")
    end = datetime.strptime(date_to, "%Y-%m-%d")

    # Recupera operatori visibili
    operatori = Operator.query.filter_by(is_visible=True, is_deleted=False).order_by(Operator.order.asc()).all()
    operatori_ids = [op.id for op in operatori]
    operatori_nomi = [f"{op.user_nome} {op.user_cognome}" for op in operatori]

    # Query aggregata: somma per operatore e giorno
    results = (
        db.session.query(
            cast(Receipt.created_at, Date).label('data'),
            Receipt.operatore_id,
            func.sum(Receipt.total_amount).label('totale')
        )
        .filter(
            Receipt.created_at >= start,
            Receipt.created_at < end + timedelta(days=1),
            Receipt.operatore_id.in_(operatori_ids),
            Receipt.is_fiscale == True  # togli se vuoi anche i non fiscali
        )
        .group_by(cast(Receipt.created_at, Date), Receipt.operatore_id)
        .all()
    )

    # Prepara struttura dati: {data: {operatore_id: incasso}}
    giorni = []
    current = start
    while current <= end:
        giorni.append(current)
        current += timedelta(days=1)

    # Mappa risultati: {(data, operatore_id): totale}
    incassi_map = {}
    for row in results:
        key = (row.data, row.operatore_id)
        incassi_map[key] = float(row.totale or 0)

    stats = []
    for giorno in giorni:
        row = {'data': giorno.strftime('%d/%m/%Y')}
        totale_giorno = 0
        for op in operatori:
            incasso = incassi_map.get((giorno.date(), op.id), 0)
            row[str(op.id)] = incasso
            totale_giorno += incasso
        row['totale'] = totale_giorno
        stats.append(row)

    # Calcola totali per ogni operatore
    totali_operatori = {}
    for op in operatori:
        tot = sum(r[str(op.id)] for r in stats)
        totali_operatori[str(op.id)] = float(tot)

    totale_periodo = sum(r['totale'] for r in stats)

    return jsonify({
        'operatori': [{'id': op.id, 'nome': f"{op.user_nome} {op.user_cognome}"} for op in operatori],
        'rows': stats,
        'totali_operatori': totali_operatori,
        'totale_periodo': totale_periodo
    })

def estrai_nome_cognome(note):
    nome = cognome = ""
    if note:
        m_nome = re.search(r'Nome:\s*([^,]+)', note, re.IGNORECASE)
        m_cognome = re.search(r'Cognome:\s*([^,]+)', note, re.IGNORECASE)
        if m_nome:
            nome = m_nome.group(1).strip()
        if m_cognome:
            cognome = m_cognome.group(1).strip()
    return nome, cognome

@report_bp.route('/api/booking_online_giorno')
def booking_online_giorno():
    date_str = request.args.get('date')
    if not date_str:
        return jsonify({'error': 'Data non valida'}), 400
    giorno = datetime.strptime(date_str, "%Y-%m-%d").date()
    inizio = datetime.combine(giorno, datetime.min.time())
    fine = datetime.combine(giorno, datetime.max.time())
    appointments = Appointment.query.filter(
        Appointment.created_at >= inizio,
        Appointment.created_at <= fine,
        Appointment.source == AppointmentSource.web
    ).order_by(Appointment.created_at.asc()).all()
    result = []
    for a in appointments:
        nome, cognome = estrai_nome_cognome(a.note or "")
        result.append({
            "id": a.id,
            "ora": to_rome(a.created_at).strftime("%H:%M"),
            "nome_cliente": nome,
            "cognome_cliente": cognome,
            "servizio": a.service.servizio_nome if a.service else "",
            "note": a.note or ""
        })
    return jsonify({
        "data": giorno.strftime("%d/%m/%Y"),
        "prenotazioni": result
    })