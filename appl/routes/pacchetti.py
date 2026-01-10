# appl/routes/pacchetti.py
import json
from flask import Blueprint, app, render_template, request, jsonify
from appl import db
from appl.models import Pacchetto, PacchettoSeduta, PacchettoRata, PacchettoScontoRegola, PacchettoPagamentoRegola, Client, PromoPacchetto, Service, Operator, PacchettoStatus, ScontoTipo, SedutaStatus, Appointment, AppointmentStatus, BusinessInfo
from sqlalchemy import func, or_, and_
from datetime import datetime, timedelta
from sqlalchemy.orm import joinedload, selectinload
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN, ROUND_CEILING

pacchetti_bp = Blueprint('pacchetti', __name__)

def aggiungi_history(pacchetto, azione):
    """Aggiunge una voce allo storico del pacchetto"""
    try:
        history = json.loads(pacchetto.history) if pacchetto.history else []
    except:
        history = []
    
    history.append({
        "ts": datetime.now().isoformat(),
        "azione": azione
    })
    pacchetto.history = json.dumps(history)


def get_ultima_modifica(pacchetto):
    """Restituisce il datetime dell'ultima modifica dal campo history"""
    try:
        history = json.loads(pacchetto.history) if pacchetto.history else []
        if history:
            ultimo = history[-1]
            return datetime.fromisoformat(ultimo["ts"])
    except:
        pass
    # Fallback: usa data_sottoscrizione
    if pacchetto.data_sottoscrizione:
        return datetime.combine(pacchetto.data_sottoscrizione, datetime.min.time())
    return None


def aggiorna_status_pacchetto(pacchetto):
    """
    Aggiorna automaticamente lo status del pacchetto:
    - ATTIVO: se ha almeno 1 rata pagata O almeno 1 seduta effettuata
    - ABBANDONATO: se non modificato per 3 settimane (solo se era Preventivo)
    """
    if pacchetto.status == PacchettoStatus.Eliminato:
        return  # Non modificare stato eliminato
    
    # Controlla se ha rate e sedute
    ha_rate = len(pacchetto.rate) > 0
    ha_sedute = len(pacchetto.sedute) > 0
    
    # Controlla se TUTTE le rate sono pagate
    tutte_rate_pagate = ha_rate and all(r.is_pagata for r in pacchetto.rate)
    
    # Controlla se TUTTE le sedute sono effettuate
    tutte_sedute_effettuate = ha_sedute and all(s.stato == SedutaStatus.Effettuata.value for s in pacchetto.sedute)
    
    # COMPLETATO: tutte rate pagate E tutte sedute effettuate
    if tutte_rate_pagate and tutte_sedute_effettuate:
        if pacchetto.status != PacchettoStatus.Completato:
            pacchetto.status = PacchettoStatus.Completato
            aggiungi_history(pacchetto, "Pacchetto completato automaticamente")
        return
    
    # Se era Completato ma ora non lo è più, torna ad Attivo
    # Controlla se ha almeno 1 rata pagata o 1 seduta effettuata
    ha_rata_pagata = any(r.is_pagata for r in pacchetto.rate)
    ha_seduta_effettuata = any(s.stato == SedutaStatus.Effettuata.value for s in pacchetto.sedute)
    
    # ATTIVO: almeno 1 rata pagata O almeno 1 seduta effettuata
    if ha_rata_pagata or ha_seduta_effettuata:
        if pacchetto.status != PacchettoStatus.Attivo:
            pacchetto.status = PacchettoStatus.Attivo
            if pacchetto.status == PacchettoStatus.Completato:
                aggiungi_history(pacchetto, "Pacchetto riaperto (non più completato)")
        return
    
    # ABBANDONATO: inattività 3 settimane (solo se era Preventivo)
    if pacchetto.status == PacchettoStatus.Preventivo:
        ultima_modifica = get_ultima_modifica(pacchetto)
        if ultima_modifica:
            tre_settimane_fa = datetime.now() - timedelta(weeks=3)
            if ultima_modifica < tre_settimane_fa:
                pacchetto.status = PacchettoStatus.Abbandonato

def verifica_pacchetti_abbandonati():
    """
    Controlla tutti i pacchetti in stato Preventivo e li segna come Abbandonati
    se non sono stati modificati per 3 settimane.
    Da chiamare periodicamente o al caricamento della lista.
    """
    tre_settimane_fa = datetime.now() - timedelta(weeks=3)
    pacchetti_preventivo = Pacchetto.query.filter(
        Pacchetto.status == PacchettoStatus.Preventivo
    ).all()
    
    modificati = 0
    for p in pacchetti_preventivo:
        ultima_modifica = get_ultima_modifica(p)
        if ultima_modifica and ultima_modifica < tre_settimane_fa:
            p.status = PacchettoStatus.Abbandonato
            modificati += 1
    
    if modificati > 0:
        db.session.commit()
    
    return modificati

@pacchetti_bp.route('/')
def pacchetti_home():
    # Controlla pacchetti abbandonati al caricamento della pagina
    verifica_pacchetti_abbandonati()
    # Pagina principale Pacchetti - carica dati iniziali e applica filtri da query params
    # Filtri da URL: ?status=Attivo (es. Preventivo, Attivo, Completato, Abbandonato)
    filter_status = request.args.get('status', '').strip()
    
    # Query pacchetti con filtri
    pacchetti_query = Pacchetto.query.join(Client).filter(Pacchetto.status != PacchettoStatus.Eliminato)
    if filter_status and filter_status in [s.value for s in PacchettoStatus]:
        pacchetti_query = pacchetti_query.filter(Pacchetto.status == PacchettoStatus[filter_status])
    
    # Limita a 100 per caricamento iniziale (JS può caricare di più con API)
    pacchetti = pacchetti_query.limit(100).all()
    
    # Prepara dati pacchetti per template
    pacchetti_data = []
    for p in pacchetti:
        sedute_info = [{'ordine': s.ordine, 'service_nome': s.service.servizio_nome, 'stato': s.stato} for s in p.sedute]
        operatori_pref = [f"{o.user_nome} {o.user_cognome}" for o in p.preferred_operators]
        pacchetti_data.append({
            'id': p.id,
            'client_id': p.client_id,
            'client_nome': f"{p.client.cliente_nome} {p.client.cliente_cognome}",
            'nome': p.nome,
            'data_sottoscrizione': p.data_sottoscrizione.isoformat() if p.data_sottoscrizione else None,
            'note': p.note,
            'status': p.status.value,
            'costo_totale_lordo': float(p.costo_totale_lordo),
            'costo_totale_scontato': float(p.costo_totale_scontato) if p.costo_totale_scontato else None,
            'operatori_preferiti': operatori_pref,
            'sedute': sedute_info
        })
    
    # Carica dati iniziali per dropdown (primi 50, JS può cercare di più)
    clienti = Client.query.filter(Client.is_deleted == False).limit(50).all()
    clienti_data = [{
        'id': c.id,
        'nome': c.cliente_nome,
        'cognome': c.cliente_cognome,
        'cellulare': c.cliente_cellulare
    } for c in clienti]
    
    servizi = Service.query.filter(Service.is_deleted == False).limit(50).all()
    servizi_data = [{
        'id': s.id,
        'nome': s.servizio_nome,
        'categoria': s.servizio_categoria.value,
        'prezzo': s.servizio_prezzo
    } for s in servizi]
    
    operatori = Operator.query.filter(Operator.is_deleted == False, Operator.user_tipo == 'estetista', Operator.is_visible == True).limit(50).all()
    operatori_data = [{
        'id': o.id,
        'nome': f"{o.user_nome} {o.user_cognome}"
    } for o in operatori]
    
    # Status disponibili per filtri
    status_options = [s.value for s in PacchettoStatus if s != PacchettoStatus.Eliminato]
    
    # Recupera giorni abbandono da BusinessInfo
    business_info = BusinessInfo.query.first()
    giorni_abbandono = business_info.pacchetti_giorni_abbandono if business_info and business_info.pacchetti_giorni_abbandono else 90

    return render_template('pacchetti.html',
                           pacchetti=pacchetti_data,
                           clienti=clienti_data,
                           servizi=servizi_data,
                           operatori=operatori_data,
                           status_options=status_options,
                           current_filter_status=filter_status,
                           giorni_abbandono=giorni_abbandono)

@pacchetti_bp.route('/api/clienti', methods=['GET'])
def api_clienti():
    # API per dropdown clienti (nome, cognome, cellulare) - ricerca intelligente come in calendar
    query = request.args.get('q', '').strip()
    
    if len(query) < 2:
        return jsonify([])
    
    q = query.lower()
    parts = [p for p in q.split() if p]
    
    if len(parts) == 1:
        # Ricerca singola parola: cerca in nome, cognome o cellulare
        term = f"%{parts[0]}%"
        filters = or_(
            func.lower(Client.cliente_nome).like(term),
            func.lower(Client.cliente_cognome).like(term),
            Client.cliente_cellulare.like(term)
        )
    else:
        # Ricerca multi-parola: tutte le parole devono matchare nome O cognome
        conditions = []
        for part in parts:
            term = f"%{part}%"
            conditions.append(
                or_(
                    func.lower(Client.cliente_nome).like(term),
                    func.lower(Client.cliente_cognome).like(term)
                )
            )
        filters = and_(*conditions)
    
    clients = Client.query.filter(
        filters,
        Client.is_deleted == False,
        # Escludi clienti dummy/booking/online (case-insensitive)
        ~or_(
            and_(Client.cliente_nome.ilike('dummy'), Client.cliente_cognome.ilike('dummy')),
            and_(Client.cliente_nome.ilike('online'), Client.cliente_cognome.ilike('booking')),
            and_(Client.cliente_nome.ilike('booking'), Client.cliente_cognome.ilike('online'))
        )
    ).limit(50).all()
    
    return jsonify([{
        'id': c.id,
        'nome': c.cliente_nome,
        'cognome': c.cliente_cognome,
        'cellulare': c.cliente_cellulare
    } for c in clients])

@pacchetti_bp.route('/api/servizi', methods=['GET'])
def api_servizi():
    # API per dropdown servizi (nome, categoria, prezzo)
    query = request.args.get('q', '').strip()
    servizi = Service.query.filter(
        and_(
            Service.is_deleted == False,
            Service.servizio_nome.ilike(f'%{query}%')
        )
    ).limit(50).all()
    return jsonify([{
        'id': s.id,
        'nome': s.servizio_nome,
        'categoria': s.servizio_categoria.value,
        'prezzo': s.servizio_prezzo
    } for s in servizi])

@pacchetti_bp.route('/api/operatori', methods=['GET'])
def api_operatori():
    # API per dropdown operatori preferiti
    query = request.args.get('q', '').strip()
    operatori = Operator.query.filter(
        and_(
            Operator.is_deleted == False,
            Operator.user_tipo == 'estetista',
            Operator.is_visible == True,  # Filtro per estetiste
            or_(
                Operator.user_nome.ilike(f'%{query}%'),
                Operator.user_cognome.ilike(f'%{query}%')
            )
        )
    ).limit(50).all()
    return jsonify([{
        'id': o.id,
        'nome': f"{o.user_nome} {o.user_cognome}"
    } for o in operatori])

@pacchetti_bp.route('/api/pacchetti', methods=['GET'])
def api_pacchetti():
    
    # API per lista pacchetti con filtri (ricerca per nome, cliente, status)
    query_nome = request.args.get('nome', '').strip()
    query_cliente = request.args.get('cliente', '').strip()
    query_cliente_id = request.args.get('cliente_id', '').strip()
    query_status = request.args.get('status', '').strip()
    
    # ✅ EAGER LOADING: carica tutto in una sola query
    pacchetti_query = Pacchetto.query.join(Client).options(
        joinedload(Pacchetto.client),
        selectinload(Pacchetto.rate),
        selectinload(Pacchetto.sedute).joinedload(PacchettoSeduta.service),
        selectinload(Pacchetto.preferred_operators)
    ).filter(Pacchetto.status != PacchettoStatus.Eliminato)
    
    if query_nome:
        pacchetti_query = pacchetti_query.filter(Pacchetto.nome.ilike(f'%{query_nome}%'))
    if query_cliente_id.isdigit():
        pacchetti_query = pacchetti_query.filter(Pacchetto.client_id == int(query_cliente_id))
    elif query_cliente:
        pacchetti_query = pacchetti_query.filter(
            or_(
                Client.cliente_nome.ilike(f'%{query_cliente}%'),
                Client.cliente_cognome.ilike(f'%{query_cliente}%')
            )
        )
    if query_status:
        pacchetti_query = pacchetti_query.filter(Pacchetto.status == PacchettoStatus[query_status])
    
    pacchetti = pacchetti_query.all()

    # Controllo abbandono: aggiorna status per pacchetti Preventivo non modificati da 3 settimane
    tre_settimane_fa = datetime.now() - timedelta(weeks=3)
    pacchetti_modificati = False
    for p in pacchetti:
        if p.status == PacchettoStatus.Preventivo:
            ultima_modifica = get_ultima_modifica(p)
            if ultima_modifica and ultima_modifica < tre_settimane_fa:
                p.status = PacchettoStatus.Abbandonato
                pacchetti_modificati = True
    
    if pacchetti_modificati:
        db.session.commit()
    
    result = []
    for p in pacchetti:
        # Calcola se tutte le rate sono pagate
        tutte_rate_pagate = False
        if p.rate and len(p.rate) > 0:
            tutte_rate_pagate = all(r.is_pagata for r in p.rate)
        # ✅ MANTIENE TUTTI I CAMPI ORIGINALI
        sedute_info = [{'ordine': s.ordine, 'service_nome': s.service.servizio_nome, 'stato': s.stato} for s in p.sedute]
        operatori_pref = [f"{o.user_nome} {o.user_cognome}" for o in p.preferred_operators]
        result.append({
            'id': p.id,
            'client_id': p.client_id,
            'client_nome': f"{p.client.cliente_nome} {p.client.cliente_cognome}",
            'nome': p.nome,
            'data_sottoscrizione': p.data_sottoscrizione.isoformat() if p.data_sottoscrizione else None,
            'note': p.note,
            'status': p.status.value,
            'costo_totale_lordo': float(p.costo_totale_lordo),
            'costo_totale_scontato': float(p.costo_totale_scontato) if p.costo_totale_scontato else None,
            'operatori_preferiti': operatori_pref,  # ✅ MANTENUTO!
            'sedute': sedute_info,                   # ✅ MANTENUTO!
            'tutte_rate_pagate': tutte_rate_pagate
        })
    return jsonify(result)

@pacchetti_bp.route('/api/pacchetti', methods=['POST'])
def api_create_pacchetto():
    # Creazione pacchetto via POST (da modal)
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Dati mancanti'}), 400
    
    # Validazione base
    required = ['client_id', 'servizi', 'costo_totale', 'sconto_tipo', 'pagamento_tipo', 'nome']
    for r in required:
        if r not in data:
            return jsonify({'error': f'Campo {r} obbligatorio'}), 400
    
    client = Client.query.get(data['client_id'])
    if not client:
        return jsonify({'error': 'Cliente non trovato'}), 404
    
    # Crea pacchetto
    raw_status = str(data.get('status') or '').strip()
    if raw_status:
        try:
            status_enum = PacchettoStatus[raw_status]          # nome: es. "Preventivo"
        except KeyError:
            try:
                status_enum = PacchettoStatus(raw_status)      # value: es. "preventivo"
            except ValueError:
                status_enum = PacchettoStatus.Preventivo
    else:
        status_enum = PacchettoStatus.Preventivo
    if status_enum == PacchettoStatus.Eliminato:
        status_enum = PacchettoStatus.Preventivo  # non consentito in creazione

    pacchetto = Pacchetto(
        client_id=data['client_id'],
        nome=data['nome'],
        data_sottoscrizione=datetime.now().date(),
        status=status_enum,
        costo_totale_lordo=data['costo_totale'],
        costo_totale_scontato=data.get('costo_scontato')
    )
    db.session.add(pacchetto)
    db.session.flush()
    
    # Aggiungi sedute (servizi con quantità)
    ordine = 1
    for s in data['servizi']:
        service = Service.query.get(s['id'])
        if not service:
            continue
        for _ in range(s['quantita']):
            seduta = PacchettoSeduta(
                pacchetto_id=pacchetto.id,
                service_id=s['id'],
                ordine=ordine,
                stato=SedutaStatus.Presente.value
            )
            db.session.add(seduta)
            ordine += 1
    
    # Sconto regola
    sconto_tipo_raw = data.get('sconto_tipo', '')
    sconto_valore = data.get('sconto_valore')
    
    # Gestisci promo salvate (es. "promo_1" -> carica dalla tabella PromoPacchetto)
    if sconto_tipo_raw and sconto_tipo_raw.startswith('promo_'):
        promo_id = int(sconto_tipo_raw.replace('promo_', ''))
        promo = PromoPacchetto.query.get(promo_id)
        if promo:
            # Mappa il tipo promo al ScontoTipo enum
            if promo.tipo == 'percentuale':
                sconto_tipo = ScontoTipo.Percentuale
                sconto_valore = promo.percentuale
            else:
                sconto_tipo = ScontoTipo.Ogni_N_Omaggio
                sconto_valore = promo.sedute_omaggio
        else:
            sconto_tipo = None
            sconto_valore = None
    elif sconto_tipo_raw and sconto_tipo_raw in ScontoTipo.__members__:
        sconto_tipo = ScontoTipo[sconto_tipo_raw]
    else:
        sconto_tipo = None
    
    # Sconto regola - gestisce anche promo salvate (es. "promo_1")
    sconto_tipo_raw = data.get('sconto_tipo', '')
    sconto_valore = data.get('sconto_valore')
    sconto_tipo = None
    
    if sconto_tipo_raw and sconto_tipo_raw.startswith('promo_'):
        promo_id = int(sconto_tipo_raw.replace('promo_', ''))
        promo = PromoPacchetto.query.get(promo_id)
        if promo:
            if promo.tipo == 'percentuale':
                sconto_tipo = ScontoTipo.Percentuale
                sconto_valore = promo.percentuale
            else:
                sconto_tipo = ScontoTipo.Ogni_N_Omaggio
                sconto_valore = promo.sedute_omaggio
    elif sconto_tipo_raw and sconto_tipo_raw in ScontoTipo.__members__:
        sconto_tipo = ScontoTipo[sconto_tipo_raw]
    
    if sconto_tipo:
        sconto_regola = PacchettoScontoRegola(
            pacchetto_id=pacchetto.id,
            sconto_tipo=sconto_tipo,
            sconto_valore=sconto_valore,
            omaggi_extra=data.get('omaggi_extra'),
            descrizione=data.get('sconto_descrizione')
        )
        db.session.add(sconto_regola)
    
    # Pagamento regola
    pagamento_regola = PacchettoPagamentoRegola(
        pacchetto_id=pacchetto.id,
        formula_pagamenti=data['pagamento_tipo'] == 'rate',
        numero_rate=data.get('numero_rate', 1),
        descrizione=data.get('pagamento_descrizione')
    )
    db.session.add(pagamento_regola)
    
    # Rate se applicabile
    if data['pagamento_tipo'] == 'rate':
        importo_rata = data['costo_totale'] / data['numero_rate']
        for i in range(data['numero_rate']):
            rata = PacchettoRata(
                pacchetto_id=pacchetto.id,
                importo=importo_rata,
                data_scadenza=None  # Da impostare manualmente
            )
            db.session.add(rata)
    
    # Operatori preferiti
    if 'operatori' in data:
        for op_id in data['operatori']:
            op = Operator.query.get(op_id)
            if op:
                pacchetto.preferred_operators.append(op)
    
    # Assegna operatore preferito alle sedute se presente
    if pacchetto.preferred_operators:
        first_op = pacchetto.preferred_operators[0]
        sedute = PacchettoSeduta.query.filter_by(pacchetto_id=pacchetto.id).all()
        for s in sedute:
            if not s.operatore_id:
                s.operatore_id = first_op.id

    # Aggiungi voce history e aggiorna status
    aggiungi_history(pacchetto, "Creato pacchetto")
    aggiorna_status_pacchetto(pacchetto)
    
    db.session.commit()
    return jsonify({'id': pacchetto.id, 'message': 'Pacchetto creato'}), 201

@pacchetti_bp.route('/api/pacchetti/<int:id>', methods=['DELETE'])
def api_delete_pacchetto(id):
    # Soft delete (status Eliminato)
    pacchetto = Pacchetto.query.get_or_404(id)
    pacchetto.status = PacchettoStatus.Eliminato
    db.session.commit()
    return jsonify({'message': 'Pacchetto eliminato'})

@pacchetti_bp.route('/api/pacchetti/<int:id>', methods=['PUT'])
def api_update_pacchetto(id):
    # Aggiornamento pacchetto
    pacchetto = Pacchetto.query.get_or_404(id)
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Dati mancanti'}), 400

    # Aggiorna campi base
    if 'nome' in data:
        pacchetto.nome = data['nome']
    if 'note' in data:
        pacchetto.note = data['note']
    if 'status' in data:
        raw_status = str(data['status']).strip()
        # Accetta sia nome enum (es. "Preventivo") sia value (es. "preventivo")
        try:
            pacchetto.status = PacchettoStatus[raw_status]
        except KeyError:
            try:
                pacchetto.status = PacchettoStatus(raw_status)
            except ValueError:
                pass
    if 'costo_totale_scontato' in data:
        pacchetto.costo_totale_scontato = data['costo_totale_scontato']
        
    if 'sconto_valore' in data:
        sconto = pacchetto.sconto_regole[0] if pacchetto.sconto_regole else None
        if sconto:
            raw_val = data.get('sconto_valore')
            arrotondamento = (data.get('sconto_arrotondamento') or '').lower()
            sconto.sconto_valore = Decimal(str(raw_val)) if raw_val not in (None, '') else None

            if sconto.sconto_tipo == ScontoTipo.Percentuale:
                if sconto.sconto_valore is not None:
                    lordo = Decimal(str(pacchetto.costo_totale_lordo))
                    factor = (Decimal('1') - (sconto.sconto_valore / Decimal('100')))
                    nuovo_raw = lordo * factor

                    # Arrotondamento a .00 (intero) se richiesto, altrimenti mantiene due decimali (cent)
                    if arrotondamento in ('down', 'per_difetto', 'difetto'):
                        intero = nuovo_raw.to_integral_value(rounding=ROUND_DOWN)
                        nuovo = intero.quantize(Decimal('0.01'))
                    elif arrotondamento in ('up', 'per_eccesso', 'eccesso'):
                        intero = nuovo_raw.to_integral_value(rounding=ROUND_CEILING)
                        nuovo = intero.quantize(Decimal('0.01'))
                    else:
                        # default: arrotonda a 2 decimali usando half-up
                        nuovo = nuovo_raw.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

                    pacchetto.costo_totale_scontato = nuovo
                else:
                    pacchetto.costo_totale_scontato = pacchetto.costo_totale_lordo

    if 'numero_rate' in data:
        new_num = int(data['numero_rate'])
        pagamento = pacchetto.pagamento_regole[0] if pacchetto.pagamento_regole else None
        if pagamento:
            # Recupera rate esistenti ordinate per ID
            rate_esistenti = PacchettoRata.query.filter_by(pacchetto_id=pacchetto.id).order_by(PacchettoRata.id).all()
            rate_pagate = [r for r in rate_esistenti if r.is_pagata]
            rate_non_pagate = [r for r in rate_esistenti if not r.is_pagata]
            
            totale = float(pacchetto.costo_totale_scontato or pacchetto.costo_totale_lordo)
            totale_pagato = sum(float(r.importo) for r in rate_pagate)
            rimanente = totale - totale_pagato
            
            # Calcola quante rate non pagate servono
            num_rate_non_pagate_richieste = new_num - len(rate_pagate)
            
            if num_rate_non_pagate_richieste < 0:
                # Impossibile: ci sono più rate pagate del nuovo numero richiesto
                pass  # Non fare nulla, mantieni la situazione attuale
            else:
                # Elimina solo le rate NON pagate
                for r in rate_non_pagate:
                    db.session.delete(r)
                db.session.flush()
                
                # Crea le nuove rate non pagate con il rimanente distribuito equamente
                if num_rate_non_pagate_richieste > 0:
                    importo_nuova_rata = rimanente / num_rate_non_pagate_richieste
                    for i in range(num_rate_non_pagate_richieste):
                        rata = PacchettoRata(pacchetto_id=pacchetto.id, importo=importo_nuova_rata)
                        db.session.add(rata)
                
                pagamento.numero_rate = new_num

    # Aggiorna operatori preferiti (semplice replace)
    if 'operatori' in data:
        pacchetto.preferred_operators.clear()
        for op_id in data['operatori']:
            op = Operator.query.get(op_id)
            if op:
                pacchetto.preferred_operators.append(op)

    # Aggiungi voce history e aggiorna status
    aggiungi_history(pacchetto, "Modificato pacchetto")
    aggiorna_status_pacchetto(pacchetto)

    db.session.commit()
    costo_scontato = float(pacchetto.costo_totale_scontato) if pacchetto.costo_totale_scontato else pacchetto.costo_totale_lordo
    return jsonify({'message': 'Pacchetto aggiornato', 'costo_totale_scontato': costo_scontato})

@pacchetti_bp.route('/api/pacchetti/<int:id>', methods=['GET'])
def api_get_pacchetto(id):
    # Dettagli singolo pacchetto (per edit modal / detail page)
    pacchetto = Pacchetto.query.get_or_404(id)

    sedute = []
    for s in pacchetto.sedute:
        operatore_nome = None
        if getattr(s, 'operatore_id', None):
            op = Operator.query.get(s.operatore_id)
            if op:
                operatore_nome = f"{op.user_nome} {op.user_cognome}"
        sedute.append({
            'id': s.id,
            'service_id': s.service_id,
            'service_nome': s.service.servizio_nome if s.service else None,
            'ordine': s.ordine,
            'stato': s.stato,
            'data_trattamento': s.data_trattamento.isoformat() if getattr(s, 'data_trattamento', None) else None,
            'operatore_id': getattr(s, 'operatore_id', None),
            'operatore_nome': operatore_nome
        })

    # Ordina rate: prima le pagate (per data_pagamento), poi le non pagate (per id)
    rate_ordinate = sorted(pacchetto.rate, key=lambda r: (
        0 if r.is_pagata else 1,
        r.data_pagamento or datetime.max if r.is_pagata else datetime.max,
        r.id
    ))
    rate = [{'id': r.id, 'importo': float(r.importo), 'is_pagata': r.is_pagata} for r in rate_ordinate]
    operatori = [o.id for o in pacchetto.preferred_operators]
    sconto = pacchetto.sconto_regole[0] if pacchetto.sconto_regole else None
    pagamento = pacchetto.pagamento_regole[0] if pacchetto.pagamento_regole else None

    client_nome_completo = f"{pacchetto.client.cliente_nome} {pacchetto.client.cliente_cognome}" if pacchetto.client else None
    client_cellulare = pacchetto.client.cliente_cellulare if pacchetto.client else None

    return jsonify({
        'id': pacchetto.id,
        'client_id': pacchetto.client_id,
        'client_nome_completo': client_nome_completo,
        'client_cellulare': client_cellulare,
        'nome': pacchetto.nome,
        'data_sottoscrizione': pacchetto.data_sottoscrizione.isoformat() if pacchetto.data_sottoscrizione else None,
        'note': pacchetto.note,
        'status': pacchetto.status.value,
        'costo_totale_lordo': float(pacchetto.costo_totale_lordo),
        'costo_totale_scontato': float(pacchetto.costo_totale_scontato) if pacchetto.costo_totale_scontato else None,
        'sedute': sedute,
        'rate': rate,
        'operatori': operatori,
        'sconto': {
            'tipo': sconto.sconto_tipo.value if sconto else None,
            'valore': float(sconto.sconto_valore) if sconto and sconto.sconto_valore else None,
            'omaggi': sconto.omaggi_extra if sconto else None
        } if sconto else None,
        'pagamento': {
            'tipo': 'rate' if pagamento and pagamento.formula_pagamenti else 'saldo',
            'numero_rate': pagamento.numero_rate if pagamento else 1
        } if pagamento else None
    })

@pacchetti_bp.route('/detail/<int:id>', methods=['GET'])
def pacchetto_detail(id):
    # EAGER LOADING: carica tutto in UNA sola query
    pacchetto = Pacchetto.query.options(
        joinedload(Pacchetto.client),
        selectinload(Pacchetto.rate),
        selectinload(Pacchetto.sedute).joinedload(PacchettoSeduta.service),
        selectinload(Pacchetto.preferred_operators),
        selectinload(Pacchetto.sconto_regole),
        selectinload(Pacchetto.pagamento_regole)
    ).get_or_404(id)

    # Aggiorna lo status del pacchetto prima di mostrare la pagina
    aggiorna_status_pacchetto(pacchetto)
    db.session.commit()

    def format_data_it(d):
        mesi = ['GEN','FEB','MAR','APR','MAG','GIU','LUG','AGO','SET','OTT','NOV','DIC']
        return f"{d.day:02d} {mesi[d.month-1]} {d.year}"

    # Carica tutti gli operatori in una sola query (invece di N query)
    # Raccogli gli ID operatore usati nelle sedute
    operatore_ids = set()
    for s in pacchetto.sedute:
        if s.operatore_id:
            operatore_ids.add(s.operatore_id)
    
    # Carica tutti gli operatori necessari in una query
    operatori_map = {}
    if operatore_ids:
        operatori_db = Operator.query.filter(Operator.id.in_(operatore_ids)).all()
        operatori_map = {o.id: f"{o.user_nome} {o.user_cognome}" for o in operatori_db}

    # Costruisci sedute usando i dati già caricati (zero query aggiuntive)
    sedute_ordinate = sorted(pacchetto.sedute, key=lambda s: s.ordine or 0)
    sedute = []
    for s in sedute_ordinate:
        sedute.append({
            'id': s.id,
            'ordine': s.ordine,
            'service_id': s.service_id,
            'service_nome': s.service.servizio_nome if s.service else None,
            'service_tag': s.service.servizio_tag if s.service else None,
            'service_duration': s.service.servizio_durata if s.service else None,
            'stato': s.stato,
            'data_trattamento': s.data_trattamento.strftime('%Y-%m-%d') if s.data_trattamento else None,
            'operatore_id': s.operatore_id,
            'operatore_nome': operatori_map.get(s.operatore_id) if s.operatore_id else None
        })

    # Ordina rate: prima le pagate (per data_pagamento), poi le non pagate (per id)
    rate_ordinate = sorted(pacchetto.rate, key=lambda r: (
        0 if r.is_pagata else 1,
        r.data_pagamento or datetime.max if r.is_pagata else datetime.max,
        r.id
    ))
    rate = [{'id': r.id, 'importo': float(r.importo), 'is_pagata': r.is_pagata, 'data_scadenza': r.data_scadenza.isoformat() if r.data_scadenza else None, 'data_pagamento': r.data_pagamento} for r in rate_ordinate]

    totale_pacchetto = float(pacchetto.costo_totale_scontato) if pacchetto.costo_totale_scontato else float(pacchetto.costo_totale_lordo)
    totale_rate_pagate = sum(float(r.importo) for r in pacchetto.rate if r.is_pagata)
    totale_rate_non_pagate = sum(float(r.importo) for r in pacchetto.rate if not r.is_pagata)
    totale_rate = totale_rate_pagate + totale_rate_non_pagate
    
    # Verifica se c'è disallineamento (con tolleranza di 0.01€)
    rate_disallineate = abs(totale_rate - totale_pacchetto) > 0.01
    differenza_rate = round(totale_pacchetto - totale_rate, 2)

    # Usa i dati già caricati (zero query aggiuntive)
    operatori = [{'id': o.id, 'nome': f"{o.user_nome} {o.user_cognome}"} for o in pacchetto.preferred_operators]
    
    all_operatori = [{'id': o.id, 'nome': f"{o.user_nome} {o.user_cognome}"} for o in Operator.query.filter(Operator.is_deleted == False, Operator.user_tipo == 'estetista', Operator.is_visible == True).all()]
    
    data_fmt = format_data_it(pacchetto.data_sottoscrizione) if pacchetto.data_sottoscrizione else ''
    
    # Usa i dati già caricati
    sconto = pacchetto.sconto_regole[0] if pacchetto.sconto_regole else None
    sconto_dict = {
        'tipo': sconto.sconto_tipo.value if sconto else None,
        'valore': float(sconto.sconto_valore) if sconto and sconto.sconto_valore else None,
        'omaggi': sconto.omaggi_extra if sconto else None
    } if sconto else None
    
    pagamento = pacchetto.pagamento_regole[0] if pacchetto.pagamento_regole else None
    pagamento_dict = {
        'tipo': 'rate' if pagamento and pagamento.formula_pagamenti else 'saldo',
        'numero_rate': pagamento.numero_rate if pagamento else 1
    } if pagamento else None

    return render_template('pacchetto_detail.html', pacchetto={
        'id': pacchetto.id,
        'client_id': pacchetto.client_id,
        'client_nome': f"{pacchetto.client.cliente_nome} {pacchetto.client.cliente_cognome}" if pacchetto.client else '',
        'client_cellulare': pacchetto.client.cliente_cellulare if pacchetto.client else '',
        'nome': pacchetto.nome,
        'data_sottoscrizione': data_fmt,
        'note': pacchetto.note,
        'status': pacchetto.status.value,
        'costo_totale_lordo': float(pacchetto.costo_totale_lordo),
        'costo_totale_scontato': float(pacchetto.costo_totale_scontato) if pacchetto.costo_totale_scontato else None,
        'totale_rate_pagate': totale_rate_pagate,
        'totale_rate_non_pagate': totale_rate_non_pagate,
        'rate_disallineate': rate_disallineate,
        'differenza_rate': differenza_rate,
        'operatori': operatori,
        'all_operatori': all_operatori,
        'sedute': sedute,
        'rate': rate,
        'sconto': sconto_dict,
        'pagamento': pagamento_dict
    })

@pacchetti_bp.route('/api/pacchetti/<int:id>/sedute/ordine', methods=['POST'])
def api_update_sedute_ordine(id):
    # Aggiorna l'ordine delle sedute via lista di ID in nuovo ordine
    pacchetto = Pacchetto.query.get_or_404(id)
    payload = request.get_json() or {}
    order_list = payload.get('ordine') or payload.get('order')

    if not isinstance(order_list, list) or not order_list:
        return jsonify({'error': 'Ordine non valido: atteso array di ID'}), 400

    sedute = PacchettoSeduta.query.filter_by(pacchetto_id=pacchetto.id).order_by(PacchettoSeduta.ordine.asc()).all()
    sedute_ids = {s.id for s in sedute}
    if set(order_list) != sedute_ids:
        return jsonify({'error': 'La lista di ID sedute non coincide con quelle del pacchetto'}), 400

    # Applica nuovo ordine
    id_to_seduta = {s.id: s for s in sedute}
    for idx, seduta_id in enumerate(order_list, start=1):
        id_to_seduta[seduta_id].ordine = idx

    # Aggiungi voce history e aggiorna status
    aggiungi_history(pacchetto, "Riordinato sedute")
    aggiorna_status_pacchetto(pacchetto)

    db.session.commit()
    return jsonify({'message': 'Ordine sedute aggiornato'})

@pacchetti_bp.route('/api/pacchetti/<int:id>/note', methods=['PUT'])
def api_update_pacchetto_note(id):
    # Aggiorna le note del pacchetto (salvataggio diretto dalla pagina di dettaglio)
    pacchetto = Pacchetto.query.get_or_404(id)
    payload = request.get_json() or {}
    note = payload.get('note', '')
    pacchetto.note = note

    # Aggiungi voce history e aggiorna status
    aggiungi_history(pacchetto, "Modificate note")
    aggiorna_status_pacchetto(pacchetto)

    db.session.commit()
    return jsonify({'message': 'Note aggiornate', 'note': pacchetto.note})

@pacchetti_bp.route('/api/pacchetti/<int:id>/sedute/<int:seduta_id>', methods=['PUT'])
def api_update_seduta(id, seduta_id):
    seduta = PacchettoSeduta.query.filter_by(id=seduta_id, pacchetto_id=id).first_or_404()
    pacchetto = Pacchetto.query.get(id)
    data = request.get_json() or {}

    if 'operatore_id' in data:
        seduta.operatore_id = data['operatore_id'] or None

    if 'data_trattamento' in data:
        raw = data['data_trattamento']
        if raw in (None, '', '—'):
            seduta.data_trattamento = None
        else:
            try:
                # Prova prima DateTime completo, poi fallback a solo data
                try:
                    # Formato DateTime completo ISO: "2026-01-09T14:30:00.000Z"
                    seduta.data_trattamento = datetime.strptime(raw, '%Y-%m-%dT%H:%M:%S.%fZ')
                except ValueError:
                    # Fallback: solo data "YYYY-MM-DD"
                    base = str(raw).strip()[:10]
                    seduta.data_trattamento = datetime.strptime(base, '%Y-%m-%d')
            except Exception:
                return jsonify({'error': 'Formato data non valido'}), 400

    if 'stato' in data:
        seduta.stato = data['stato']

    # Aggiungi voce history con dettaglio azione
    if 'stato' in data and data['stato'] == SedutaStatus.Effettuata.value:
        aggiungi_history(pacchetto, f"Seduta {seduta.ordine} effettuata")
        
        # Cerca l'appuntamento che ha pacchetto_seduta_id = seduta.id
        appointment = Appointment.query.filter_by(pacchetto_seduta_id=seduta.id).first()
        if appointment:
            appointment.stato = AppointmentStatus.PAGATO
    else:
        aggiungi_history(pacchetto, f"Modificata seduta {seduta.ordine}")
    aggiorna_status_pacchetto(pacchetto)

    db.session.commit()
    return jsonify({'message': 'Seduta aggiornata'})

@pacchetti_bp.route('/api/rate/<int:rata_id>', methods=['PUT'])

def api_update_rata(rata_id):
    rata = PacchettoRata.query.get_or_404(rata_id)
    data = request.get_json() or {}

    # Verifica se la rata è già pagata (non modificabile)
    if rata.is_pagata and 'importo' in data:
        return jsonify({'error': 'Non è possibile modificare l\'importo di una rata già pagata'}), 400

    if 'is_pagata' in data:
        rata.is_pagata = data['is_pagata']
    
    if 'data_scadenza' in data:
        raw = data['data_scadenza']
        if raw:
            try:
                rata.data_scadenza = datetime.strptime(raw, '%Y-%m-%d').date()
            except Exception:
                return jsonify({'error': 'Formato data non valido'}), 400
        else:
            rata.data_scadenza = None
    
    if 'importo' in data:
        try:
            nuovo_importo = float(data['importo'])
        except Exception:
            return jsonify({'error': 'Importo non valido'}), 400

        # Se skip_redistribution è true, setta solo l'importo senza ridistribuire
        if data.get('skip_redistribution'):
            rata.importo = nuovo_importo
        else:
            # Carica il pacchetto e le rate ordinate per ID
            pacchetto = Pacchetto.query.get(rata.pacchetto_id)
            rate = PacchettoRata.query.filter_by(pacchetto_id=rata.pacchetto_id).order_by(PacchettoRata.id).all()
            costo_scontato = float(pacchetto.costo_totale_scontato or pacchetto.costo_totale_lordo)

            # Separa rate pagate e non pagate
            rate_pagate = [r for r in rate if r.is_pagata]
            rate_non_pagate = [r for r in rate if not r.is_pagata]
            
            # Trova la rata corrente tra quelle non pagate
            if rata not in rate_non_pagate:
                return jsonify({'error': 'Rata già pagata, non modificabile'}), 400
            
            # Calcola la somma delle rate già pagate (fissa)
            somma_pagate = sum(float(r.importo) for r in rate_pagate)
            
            # Importo disponibile per le rate non pagate
            importo_disponibile = costo_scontato - somma_pagate
            
            # Calcola la differenza tra nuovo e vecchio importo
            vecchio_importo = float(rata.importo)
            differenza = nuovo_importo - vecchio_importo
            
            # Le altre rate non pagate (esclusa quella modificata)
            altre_rate_non_pagate = [r for r in rate_non_pagate if r.id != rata.id]
            
            if len(altre_rate_non_pagate) == 0:
                # Se è l'unica rata non pagata, verifica solo che non superi il disponibile
                if nuovo_importo > importo_disponibile:
                    return jsonify({'error': f'Importo troppo alto. Massimo disponibile: €{importo_disponibile:.2f}'}), 400
                rata.importo = nuovo_importo
            else:
                # Calcola il rimanente da distribuire sulle altre rate
                rimanente_per_altre = importo_disponibile - nuovo_importo
                
                # Verifica che il rimanente non sia negativo
                if rimanente_per_altre < 0:
                    return jsonify({'error': f'Importo troppo alto. Massimo disponibile: €{importo_disponibile:.2f}'}), 400
                
                # Arrotonda a numeri interi: calcola base e resto
                num_altre = len(altre_rate_non_pagate)
                importo_base = int(rimanente_per_altre // num_altre)  # parte intera
                resto_euro = int(round(rimanente_per_altre - (importo_base * num_altre)))  # euro da distribuire
                
                # Verifica che nessuna rata diventi negativa
                if importo_base < 0:
                    return jsonify({'error': 'Impossibile: l\'aumento genererebbe rate negative'}), 400
                
                # Applica le modifiche: rata modificata
                rata.importo = nuovo_importo
                
                # Distribuisci sulle altre rate: le prime 'resto_euro' ricevono 1€ in più
                for i, r in enumerate(altre_rate_non_pagate):
                    if i < resto_euro:
                        r.importo = float(importo_base + 1)
                    else:
                        r.importo = float(importo_base)

    # Aggiungi voce history e aggiorna status
    pacchetto = Pacchetto.query.get(rata.pacchetto_id)
    rata_num = next((i+1 for i, r in enumerate(pacchetto.rate) if r.id == rata.id), 0)
    aggiungi_history(pacchetto, f"Modificata rata {rata_num}")
    aggiorna_status_pacchetto(pacchetto)

    db.session.commit()
    return jsonify({'success': True, 'message': 'Rata aggiornata'})

@pacchetti_bp.route('/api/pacchetti/<int:id>/check_rate_pagate', methods=['GET'])
def api_check_rate_pagate(id):
    """Verifica se ci sono rate già pagate per il pacchetto"""
    pacchetto = Pacchetto.query.get_or_404(id)
    rate_pagate = [r for r in pacchetto.rate if r.is_pagata]
    return jsonify({
        'has_rate_pagate': len(rate_pagate) > 0,
        'count': len(rate_pagate),
        'totale_pagato': sum(float(r.importo) for r in rate_pagate)
    })

@pacchetti_bp.route('/api/pacchetti/<int:id>/ridistribuisci_rate', methods=['POST'])
def api_ridistribuisci_rate(id):
    """Ridistribuisce equamente l'importo rimanente su tutte le rate non pagate"""
    pacchetto = Pacchetto.query.get_or_404(id)
    data = request.get_json() or {}
    
    # Calcola totale pacchetto
    costo_totale = float(pacchetto.costo_totale_scontato or pacchetto.costo_totale_lordo)
    
    # Separa rate pagate e non pagate
    rate_pagate = [r for r in pacchetto.rate if r.is_pagata]
    rate_non_pagate = [r for r in pacchetto.rate if not r.is_pagata]
    
    if not rate_non_pagate:
        return jsonify({'error': 'Nessuna rata non pagata da ridistribuire'}), 400
    
    # Calcola importo già pagato
    totale_pagato = sum(float(r.importo) for r in rate_pagate)
    
    # Importo da distribuire sulle rate non pagate
    importo_rimanente = costo_totale - totale_pagato
    
    # Arrotonda a numeri interi: calcola base e resto
    num_rate_non_pagate = len(rate_non_pagate)
    importo_base = int(importo_rimanente // num_rate_non_pagate)  # parte intera
    resto_euro = int(round(importo_rimanente - (importo_base * num_rate_non_pagate)))  # euro da distribuire
    
    # Aggiorna tutte le rate non pagate
    for i, rata in enumerate(rate_non_pagate):
        if i < resto_euro:
            # Le prime 'resto_euro' rate ricevono 1€ in più
            rata.importo = float(importo_base + 1)
        else:
            rata.importo = float(importo_base)
    
    # Aggiungi history
    aggiungi_history(pacchetto, f"Ridistribuite {num_rate_non_pagate} rate (€{importo_base}.00 base)")
    
    db.session.commit()
    
    return jsonify({
        'message': 'Rate ridistribuite con successo',
        'importo_per_rata': importo_base,
        'num_rate': num_rate_non_pagate,
        'totale_rimanente': importo_rimanente
    })
    
@pacchetti_bp.route('/api/check-disponibili', methods=['POST'])
def check_pacchetti_disponibili():
    """
    Verifica se un cliente ha pacchetti con sedute disponibili per i servizi selezionati.
    
    Request JSON:
        {
            "client_id": int,
            "service_ids": [int, int, ...]
        }
    
    Response JSON:
        [
            {
                "pacchetto_id": int,
                "pacchetto_nome": str,
                "client_nome": str,
                "status": str,
                "sedute_disponibili": [
                    {
                        "seduta_id": int,
                        "service_id": int,
                        "service_nome": str,
                        "ordine": int
                    },
                    ...
                ],
                "sedute_totali": int,
                "sedute_effettuate": int
            },
            ...
        ]
    """
    try:
        data = request.get_json()
        client_id = data.get('client_id')
        service_ids = data.get('service_ids', [])
        
        if not client_id or not service_ids:
            return jsonify([]), 200
        
        # Trova tutti i pacchetti del cliente con status Preventivo o Attivo
        pacchetti = Pacchetto.query.filter(
            and_(
                Pacchetto.client_id == client_id,
                Pacchetto.status.in_([PacchettoStatus.Preventivo, PacchettoStatus.Attivo])
            )
        ).all()
        
        risultati = []
        
        for pacchetto in pacchetti:
            print(f"DEBUG: Pacchetto {pacchetto.id} - {pacchetto.nome}")
            print(f"DEBUG: Sedute totali: {len(pacchetto.sedute)}")
            
            sedute_disponibili = []
            for seduta in pacchetto.sedute:
                print(f"  - Seduta {seduta.id}: service_id={seduta.service_id}, stato={seduta.stato} (tipo: {type(seduta.stato)})")
                print(f"    Confronto: {seduta.service_id} in {service_ids} = {seduta.service_id in service_ids}")
                print(f"    Stato != Effettuata: {seduta.stato} != {SedutaStatus.Effettuata} = {seduta.stato != SedutaStatus.Effettuata}")
                # Converti service_ids in interi per confronto corretto
                service_ids_int = [int(sid) for sid in service_ids]
                if seduta.service_id in service_ids_int and seduta.stato != SedutaStatus.Effettuata:
                    sedute_disponibili.append({
                        'seduta_id': seduta.id,
                        'service_id': seduta.service_id,
                        'service_nome': seduta.service.servizio_nome if seduta.service else 'Servizio',
                        'ordine': seduta.ordine
                    })
            
            if sedute_disponibili:
                risultati.append({
                    'pacchetto_id': pacchetto.id,
                    'pacchetto_nome': pacchetto.nome,
                    'client_nome': f"{pacchetto.client.cliente_nome} {pacchetto.client.cliente_cognome}",
                    'status': pacchetto.status.value,
                    'sedute_disponibili': sedute_disponibili,
                    'sedute_totali': len(pacchetto.sedute),
                    'sedute_effettuate': len([s for s in pacchetto.sedute if s.stato == SedutaStatus.Effettuata.value])
                })
        
        return jsonify(risultati), 200
        
    except Exception as e:
        print(f"Errore check_pacchetti_disponibili: {str(e)}")
        return jsonify([]), 500
    
@pacchetti_bp.route('/api/sedute/<int:seduta_id>/update-data', methods=['POST'])
def update_seduta_data(seduta_id):
    """Aggiorna la data_trattamento di una seduta specifica"""
    try:
        data = request.get_json()
        data_trattamento = data.get('data_trattamento')
        operatore_id = data.get('operatore_id')

        print(f"DEBUG update_seduta_data: seduta_id={seduta_id}, data_trattamento={data_trattamento}")
        
        if not data_trattamento:
            return jsonify({'error': 'data_trattamento mancante'}), 400
        
        # Trova la seduta
        seduta = PacchettoSeduta.query.get(seduta_id)
        if not seduta:
            return jsonify({'error': 'Seduta non trovata'}), 404
        
        # ✅ FIX: Parsing robusto - rimuovi timezone per evitare problemi con SQLite
        try:
            # Rimuovi 'Z' e qualsiasi timezone, poi parsa
            clean_date = data_trattamento.replace('Z', '').replace('+00:00', '')
            # Rimuovi anche millisecondi se presenti
            if '.' in clean_date:
                clean_date = clean_date.split('.')[0]
            # Ora parsa come datetime naive
            seduta.data_trattamento = datetime.strptime(clean_date, '%Y-%m-%dT%H:%M:%S')
        except ValueError:
            # Fallback: prova solo data
            try:
                seduta.data_trattamento = datetime.strptime(data_trattamento[:10], '%Y-%m-%d')
            except:
                return jsonify({'error': f'Formato data non valido: {data_trattamento}'}), 400
            
        # ✅ NUOVO: Aggiorna operatore se fornito e diverso
        if operatore_id is not None:
            operatore_id_int = int(operatore_id) if operatore_id else None
            if seduta.operatore_id != operatore_id_int:
                print(f"DEBUG: Cambio operatore da {seduta.operatore_id} a {operatore_id_int}")
                seduta.operatore_id = operatore_id_int
        
        print(f"DEBUG: Salvando seduta.data_trattamento = {seduta.data_trattamento}")
        db.session.commit()
        print(f"DEBUG: Commit completato!")
        
        return jsonify({
            'success': True,
            'seduta_id': seduta_id,
            'data_trattamento': str(seduta.data_trattamento),
            'operatore_id': seduta.operatore_id
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Errore update_seduta_data: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    
# Aggiungi questo endpoint dopo check_pacchetti_disponibili (circa riga 1078):

@pacchetti_bp.route('/api/sedute-disponibili/<int:pacchetto_id>', methods=['GET'])
def get_sedute_disponibili(pacchetto_id):
    """
    Restituisce le sedute disponibili (non pianificate/non effettuate) per un pacchetto specifico.
    
    Query params:
        - client_id (opzionale): per verifica di sicurezza
        
    Response JSON:
        [
            {
                "seduta_id": int,
                "service_id": int,
                "service_nome": str,
                "numero_seduta": int,
                "ordine": int,
                "data_trattamento": str|null,
                "stato": str
            },
            ...
        ]
    """
    try:
        client_id = request.args.get('client_id', type=int)
        
        pacchetto = Pacchetto.query.filter(
            Pacchetto.id == pacchetto_id,
            Pacchetto.status.in_([PacchettoStatus.Preventivo, PacchettoStatus.Attivo])
        ).first()
        
        if not pacchetto:
            return jsonify([]), 404
        
        # Verifica che il pacchetto appartenga al cliente (se specificato)
        if client_id and pacchetto.client_id != client_id:
            return jsonify([]), 403
        
        sedute_disponibili = []
        for seduta in pacchetto.sedute:
            # Includi tutte le sedute che non sono ancora effettuate
            if seduta.stato != SedutaStatus.Effettuata:
                sedute_disponibili.append({
                    'seduta_id': seduta.id,
                    'service_id': seduta.service_id,
                    'service_nome': seduta.service.servizio_nome if seduta.service else 'Servizio',
                    'servizio_tag': seduta.service.servizio_tag if seduta.service else '',
                    'numero_seduta': seduta.ordine + 1,  # 1-based per display
                    'ordine': seduta.ordine,
                    'data_trattamento': seduta.data_trattamento.isoformat() if seduta.data_trattamento else None,
                    'stato': seduta.stato.value if hasattr(seduta.stato, 'value') else str(seduta.stato)
                })
        
        return jsonify(sedute_disponibili), 200
        
    except Exception as e:
        print(f"Errore get_sedute_disponibili: {str(e)}")
        return jsonify([]), 500