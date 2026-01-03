# appl/routes/pacchetti.py
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from appl import db
from appl.models import Pacchetto, PacchettoSeduta, PacchettoRata, PacchettoScontoRegola, PacchettoPagamentoRegola, Client, Service, Operator, PacchettoStatus, ScontoTipo, SedutaStatus
from flask_wtf.csrf import generate_csrf
from sqlalchemy import or_, and_
from datetime import datetime
import json

pacchetti_bp = Blueprint('pacchetti', __name__)

@pacchetti_bp.route('/')
def pacchetti_home():
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
    
    operatori = Operator.query.filter(Operator.is_deleted == False).limit(50).all()
    operatori_data = [{
        'id': o.id,
        'nome': f"{o.user_nome} {o.user_cognome}"
    } for o in operatori]
    
    # Status disponibili per filtri
    status_options = [s.value for s in PacchettoStatus if s != PacchettoStatus.Eliminato]
    
    return render_template('pacchetti.html',
                           pacchetti=pacchetti_data,
                           clienti=clienti_data,
                           servizi=servizi_data,
                           operatori=operatori_data,
                           status_options=status_options,
                           current_filter_status=filter_status)

@pacchetti_bp.route('/api/clienti', methods=['GET'])
def api_clienti():
    # API per dropdown clienti (nome, cognome, cellulare)
    query = request.args.get('q', '').strip()
    clients = Client.query.filter(
        and_(
            Client.is_deleted == False,
            or_(
                Client.cliente_nome.ilike(f'%{query}%'),
                Client.cliente_cognome.ilike(f'%{query}%'),
                Client.cliente_cellulare.ilike(f'%{query}%')
            )
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
    
    pacchetti_query = Pacchetto.query.join(Client).filter(Pacchetto.status != PacchettoStatus.Eliminato)
    
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
    
    result = []
    for p in pacchetti:
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
            'operatori_preferiti': operatori_pref,
            'sedute': sedute_info
        })
    return jsonify(result)

@pacchetti_bp.route('/api/pacchetti', methods=['POST'])
def api_create_pacchetto():
    # Creazione pacchetto via POST (da modal)
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Dati mancanti'}), 400
    
    # Validazione base
    required = ['client_id', 'servizi', 'costo_totale', 'sconto_tipo', 'pagamento_tipo', 'nome', 'note']
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
        note=data['note'],
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
    sconto_regola = PacchettoScontoRegola(
        pacchetto_id=pacchetto.id,
        sconto_tipo=ScontoTipo[data['sconto_tipo']],
        sconto_valore=data.get('sconto_valore'),
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
    
    db.session.commit()
    return jsonify({'id': pacchetto.id, 'message': 'Pacchetto creato'}), 201

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
        pacchetto.status = PacchettoStatus[data['status']]
    if 'costo_totale_scontato' in data:
        pacchetto.costo_totale_scontato = data['costo_totale_scontato']
    
    # Aggiorna operatori preferiti (semplice replace)
    if 'operatori' in data:
        pacchetto.preferred_operators.clear()
        for op_id in data['operatori']:
            op = Operator.query.get(op_id)
            if op:
                pacchetto.preferred_operators.append(op)
    
    db.session.commit()
    return jsonify({'message': 'Pacchetto aggiornato'})

@pacchetti_bp.route('/api/pacchetti/<int:id>', methods=['DELETE'])
def api_delete_pacchetto(id):
    # Soft delete (status Eliminato)
    pacchetto = Pacchetto.query.get_or_404(id)
    pacchetto.status = PacchettoStatus.Eliminato
    db.session.commit()
    return jsonify({'message': 'Pacchetto eliminato'})

@pacchetti_bp.route('/api/pacchetti/<int:id>', methods=['GET'])
def api_get_pacchetto(id):
    # Dettagli singolo pacchetto (per edit modal)
    pacchetto = Pacchetto.query.get_or_404(id)
    sedute = [{'id': s.id, 'service_id': s.service_id, 'ordine': s.ordine, 'stato': s.stato} for s in pacchetto.sedute]
    rate = [{'id': r.id, 'importo': float(r.importo), 'is_pagata': r.is_pagata} for r in pacchetto.rate]
    operatori = [o.id for o in pacchetto.preferred_operators]
    sconto = pacchetto.sconto_regole[0] if pacchetto.sconto_regole else None
    pagamento = pacchetto.pagamento_regole[0] if pacchetto.pagamento_regole else None
    
    return jsonify({
        'id': pacchetto.id,
        'client_id': pacchetto.client_id,
        'nome': pacchetto.nome,
        'data_sottoscrizione': pacchetto.data_sottoscrizione.isoformat(),
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
    pacchetto = Pacchetto.query.get_or_404(id)

    def format_data_it(d):
        mesi = ['GEN','FEB','MAR','APR','MAG','GIU','LUG','AGO','SET','OTT','NOV','DIC']
        return f"{d.day:02d} {mesi[d.month-1]} {d.year}"

    sedute = [{'ordine': s.ordine, 'service_nome': s.service.servizio_nome, 'stato': s.stato}
              for s in pacchetto.sedute]
    rate = [{'importo': float(r.importo), 'is_pagata': r.is_pagata} for r in pacchetto.rate]
    operatori = [{'id': o.id, 'nome': f"{o.user_nome} {o.user_cognome}"} for o in pacchetto.preferred_operators]
    data_fmt = format_data_it(pacchetto.data_sottoscrizione) if pacchetto.data_sottoscrizione else ''

    return render_template('pacchetto_detail.html', pacchetto={
        'id': pacchetto.id,
        'client_id': pacchetto.client_id,
        'client_nome': f"{pacchetto.client.cliente_nome} {pacchetto.client.cliente_cognome}",
        'nome': pacchetto.nome,
        'data_sottoscrizione': data_fmt,
        'note': pacchetto.note,
        'status': pacchetto.status.value,
        'costo_totale_lordo': float(pacchetto.costo_totale_lordo),
        'costo_totale_scontato': float(pacchetto.costo_totale_scontato) if pacchetto.costo_totale_scontato else None,
        'operatori': operatori,
        'sedute': sedute,
        'rate': rate
    })