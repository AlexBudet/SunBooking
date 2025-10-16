import json
import html, re, time as pytime
from flask import Blueprint, app, render_template, jsonify, request, session, abort, current_app
from appl.models import Appointment, AppointmentStatus, BusinessInfo, Operator, Service, ServiceCategory, Client, Receipt, Subcategory, User, db
from datetime import datetime, date
import requests
from sqlalchemy import func, text
from sqlalchemy.orm import selectinload
from collections import defaultdict
from sqlalchemy.orm.attributes import flag_modified

cassa_bp = Blueprint('cassa', __name__)

@cassa_bp.route('/cassa')
def cassa():
    current_app.logger.debug("GET args in cassa: %s", request.args)
    client_id = request.args.get('client_id')
    operator_id = request.args.get('operator_id')
    client_name = request.args.get('client_name')
    operator_name = request.args.get('operator_name')
    servizi_json = request.args.get('servizi')
    appointments_json = request.args.get('appointments')
    servizi = []

    if servizi_json:
        try:
            servizi = json.loads(servizi_json)
        except:
            servizi = []

    if appointments_json:
        try:
            appointments_ids = json.loads(appointments_json)
            appointments = Appointment.query.filter(Appointment.id.in_(appointments_ids)).all()
            for appt in appointments:
                servizi.append({
                    "id": appt.service.id,
                    "nome": appt.service.servizio_nome,
                    "prezzo": appt.service.servizio_prezzo,
                    "tag": appt.service.servizio_tag,
                    "sottocategoria": appt.service.servizio_sottocategoria.nome if appt.service.servizio_sottocategoria else "",
                    "appointment_id": appt.id
                })
        except Exception as e:
            servizi = []
    elif servizi_json:
        try:
            servizi = json.loads(servizi_json)
        except Exception:
            servizi = []
    
    try:
        if client_id:
            cid = int(client_id)
            cli = db.session.get(Client, cid)
            if cli:
                client_name = f"{cli.cliente_nome or ''} {cli.cliente_cognome or ''}".strip()
        elif client_name:
            client_name = html.unescape(client_name)
    except Exception:
        if client_name:
            client_name = html.unescape(client_name)

    # Se operator_name non è passato ma operator_id sì, recupera nome e cognome dal DB
    if not operator_name and operator_id:
        op = db.session.get(Operator, operator_id)
        if op:
            operator_name = f"{op.user_nome} {op.user_cognome}"

    giorno = date.today()
    businessinfo = db.session.get(BusinessInfo, 1)

    return render_template(
        'cassa.html',
        client_id=client_id,
        operator_id=operator_id,
        client_name=client_name,
        operator_name=operator_name,
        servizi=servizi,
        giorno=giorno,
        businessinfo=businessinfo
    )

@cassa_bp.route('/cassa/api/operators')
def api_operators():
    # Restituisce la lista operatori attivi ordinati per il campo 'order'
    operators = Operator.query.filter_by(is_visible=True, is_deleted=False).order_by(Operator.order.asc()).all()
    return jsonify([
        {"id": op.id, "nome": op.user_nome, "cognome": op.user_cognome}
        for op in operators
    ])

@cassa_bp.route('/cassa/api/services')
def api_services():
    try:
        id = request.args.get('id')
        q = request.args.get('q', '').strip()
        ultimi = request.args.get('ultimi')
        frequenti = request.args.get('frequenti')
        categoria = request.args.get('categoria')
        sottocategoria = request.args.get('sottocategoria')

        # helper: estrae id servizio supportando vari nomi/format
        def extract_sid(v):
            if not isinstance(v, dict):
                return None
            for key in ('servizio_id', 'service_id', 'id', 'servizioId', 'servizioID'):
                if key in v and v[key] not in (None, ''):
                    try:
                        return int(v[key])
                    except Exception:
                        try:
                            return int(str(v[key]).strip())
                        except Exception:
                            return None
            return None

        # base query (sempre applicata se non viene sovrascritta)
        base_query = Service.query.filter(Service.is_deleted == False)

        services = []
        # caso: ricerca per id o testo
        if id:
            query = base_query.filter(Service.id == id)
            services = query.limit(28).all()
        elif q and len(q) >= 3:
            query = base_query.filter(Service.servizio_nome.ilike(f"%{q}%"))
            services = query.limit(28).all()
        elif ultimi:
            # ULTIMI: prendi receipt recenti, estrai servizi unici nell'ordine di apparizione
            recent_receipts = Receipt.query.order_by(Receipt.created_at.desc()).limit(200).all()
            seen = set()
            ordered_ids = []
            for r in recent_receipts:
                voci = r.voci if isinstance(r.voci, list) else (json.loads(r.voci or '[]') if r.voci else [])
                for v in voci:
                    sid = extract_sid(v)
                    if sid and sid not in seen:
                        seen.add(sid)
                        ordered_ids.append(sid)
                        if len(ordered_ids) >= 28:
                            break
                if len(ordered_ids) >= 28:
                    break
            if ordered_ids:
                db_services = Service.query.filter(Service.id.in_(ordered_ids), Service.is_deleted == False).all()
                svc_map = {s.id: s for s in db_services}
                services = [svc_map[sid] for sid in ordered_ids if sid in svc_map]
            else:
                services = []
        elif frequenti:
            # FREQUENTI: conta occorrenze nei receipt e ordina per frequenza
            from collections import Counter
            all_receipts = Receipt.query.all()
            cnt = Counter()
            for r in all_receipts:
                voci = r.voci if isinstance(r.voci, list) else (json.loads(r.voci or '[]') if r.voci else [])
                for v in voci:
                    sid = extract_sid(v)
                    if sid:
                        cnt[sid] += 1
            top = [sid for sid, _ in cnt.most_common(28)]
            if top:
                db_services = Service.query.filter(Service.id.in_(top), Service.is_deleted == False).all()
                svc_map = {s.id: s for s in db_services}
                # preserva l'ordine dei top
                services = [svc_map[sid] for sid in top if sid in svc_map]
            else:
                services = []
        elif sottocategoria:
            query = base_query.join(Service.servizio_sottocategoria).filter(Subcategory.nome == sottocategoria)
            services = query.limit(28).all()
        elif categoria:
            query = base_query.filter(Service.servizio_categoria == categoria)
            services = query.limit(28).all()
        else:
            services = base_query.order_by(Service.servizio_nome).limit(28).all()

        # server-side dedup (preserva primo-occurrence) e limit finale
        seen = set()
        unique_services = []
        for s in services:
            sid = getattr(s, 'id', None)
            if sid is None or sid in seen:
                continue
            seen.add(sid)
            unique_services.append(s)
            if len(unique_services) >= 28:
                break
        services = unique_services

        return jsonify([
            {
                "id": s.id,
                "nome": s.servizio_nome,
                "tag": s.servizio_tag,
                "prezzo": s.servizio_prezzo,
                "categoria": s.servizio_categoria.value if s.servizio_categoria else "",
                "sottocategoria": s.servizio_sottocategoria.nome if s.servizio_sottocategoria else "",
                "is_prodotti": (
                    s.servizio_sottocategoria and s.servizio_sottocategoria.nome.lower() == "prodotti"
                )
            }
            for s in services
        ])
    except Exception as e:
        current_app.logger.error("Errore in /cassa/api/services: %s", str(e))
        return jsonify({"error": "Errore nel recupero dei servizi."}), 500
        
@cassa_bp.route('/cassa/api/clients')
def api_clients():
    q = request.args.get('q', '').strip()
    query = Client.query
    if q and len(q) >= 2:
        query = query.filter(
            Client.cliente_nome.ilike(f"%{q}%") | Client.cliente_cognome.ilike(f"%{q}%")
        )
    clients = query.order_by(Client.cliente_nome).limit(20).all()
    return jsonify([
        {
            "id": c.id,
            "nome": c.cliente_nome,
            "cognome": c.cliente_cognome
        }
        for c in clients
    ])

@cassa_bp.route('/cassa/send-to-rch', methods=['POST'])
def send_to_rch():
    data = request.get_json(force=True)
    voci = data.get("voci", [])
    cliente_id = data.get("cliente_id")
    operatore_id = data.get("operatore_id")

    if not voci:
        return jsonify({"error": "Nessuna voce da registrare"}), 400
    
    # --- VALIDAZIONE E NORMALIZZAZIONE PREZZI: solo numeri >= 0 ---
    for idx, v in enumerate(voci, start=1):
        # ensure prezzo key exists and is numeric
        prezzo_raw = v.get("prezzo", 0)
        try:
            # accetta stringhe numeriche, numeri; vuoto -> 0
            prezzo_val = float(prezzo_raw) if prezzo_raw not in (None, "") else 0.0
        except Exception:
            return jsonify({"error": f"Prezzo non valido nella voce #{idx} ({v.get('nome') or 'sconosciuto'})."}), 400

        if prezzo_val < 0:
            return jsonify({"error": f"Prezzi negativi non consentiti nella voce #{idx} ({v.get('nome') or 'sconosciuto'})."}), 400

        # normalizza il prezzo nella voce (2 decimali)
        v["prezzo"] = round(prezzo_val, 2)

    voci_fiscali = [v for v in voci if v.get("is_fiscale", True)]
    voci_non_fiscali = [v for v in voci if not v.get("is_fiscale", True)]
    results = []
    oggi = datetime.now().date()

    # completa nomi servizi mancanti
    for v in voci:
        if not v.get("nome") and v.get("servizio_id"):
            srv = db.session.get(Service, v["servizio_id"])
            if srv:
                v["nome"] = srv.servizio_nome

    # =========================
    # 1. SCONTRINO FISCALE
    # =========================
    if voci_fiscali:
        xml_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<Service>'
        ]
        totali = {"T1": 0, "T2": 0, "T3": 0}

        for v in voci_fiscali:
            srv = db.session.get(Service, v.get("servizio_id"))
            prezzo_pieno = float(srv.servizio_prezzo) if srv else float(v.get("prezzo", 0))
            prezzo_finale = float(v.get("prezzo", prezzo_pieno))
            prezzo_cents = int(round(prezzo_finale * 100))

            desc = (v.get("nome") or (srv.servizio_nome if srv else "Servizio"))[:32]
            desc = html.escape(desc.replace(")", "").replace("(", "").replace("/", "-"))

            reparto = "R2" if getattr(srv, "servizio_sottocategoria", None) and \
                               srv.servizio_sottocategoria.nome.upper() == "PRODOTTI" else "R1"
            xml_lines.append(f'<cmd>={reparto}/${prezzo_cents}/({desc})</cmd>')

            if prezzo_pieno > 0 and prezzo_finale < prezzo_pieno:
                sconto = 100 - (prezzo_finale / prezzo_pieno * 100)
                xml_lines.append(f'<cmd>="/(Scontato del {sconto:.2f}%)</cmd>')

            metodo = v.get("metodo_pagamento", "cash")
            if metodo == "cash":
                totali["T1"] += prezzo_cents
            elif metodo == "bank":
                totali["T2"] += prezzo_cents
            elif metodo == "pos":
                totali["T3"] += prezzo_cents

        codice_lotteria = (data.get("lotteria") or "").strip().upper()
        pagamenti_digitali = any(
            v.get("metodo_pagamento", "cash") in ("pos", "bank") for v in voci_fiscali
        )
        if (
            len(codice_lotteria) == 8
            and codice_lotteria.isalnum()
            and pagamenti_digitali
        ):
            xml_lines.insert(2, f'<cmd>="/?L/$1/({codice_lotteria})</cmd>')

        if totali["T1"] == 0 and totali["T2"] == 0 and totali["T3"] == 0:
            xml_lines.append('<cmd>=T5/$0.00</cmd>')
        else:
            # Aggiungi solo per totali >0
            if totali["T1"] > 0:
                xml_lines.append(f'<cmd>=T1/${totali["T1"]}</cmd>')
            if totali["T2"] > 0:
                xml_lines.append(f'<cmd>=T2/${totali["T2"]}</cmd>')
            if totali["T3"] > 0:
                xml_lines.append(f'<cmd>=T3/${totali["T3"]}</cmd>')

        xml_lines.append('</Service>')
        payload_vendita = "\n".join(xml_lines)

        # --- STAMPA IL PAYLOAD NEL TERMINALE ---
        current_app.logger.debug("PAYLOAD XML INVIATO:\n%s", payload_vendita)

        business = BusinessInfo.query.first()
        if not business or not business.printer_ip:
            return jsonify({"error": "IP stampante RCH non configurato"}), 400
        url = f"http://{business.printer_ip}/service.cgi"
        headers = {"Content-Type": "text/xml; charset=UTF-8"}

        try:
            resp_vendita = requests.post(
                url, data=payload_vendita.encode("UTF-8"), headers=headers, timeout=10
            )
        except Exception as exc:
            current_app.logger.error("Errore di rete durante la comunicazione con RCH: %s", str(exc))
            return jsonify({"error": "Errore di comunicazione con la stampante fiscale."}), 500

        if '<errorCode>0</errorCode>' not in resp_vendita.text:
            current_app.logger.error("Errore dalla stampante RCH: %s", resp_vendita.text)
            return jsonify({"error": "La stampante fiscale ha restituito un errore."}), 500

        # ---------- lettura progressivo NR DOC ----------
        numero_progressivo = None
        numero_z = None
        for cmd in ("=C453/$0", "=DGFE/REG"):
            payload_prog = f'''<?xml version="1.0" encoding="UTF-8"?><Service><cmd>{cmd}</cmd></Service>'''
            for _ in range(6):
                pytime.sleep(0.5)
                resp = requests.post(url, data=payload_prog.encode('utf-8'), headers=headers, timeout=5)
                m_doc = (re.search(r'<lastDocF>(\d+)</lastDocF>', resp.text) or
                         re.search(r'<C453[^>]*>(\d+)</C453>', resp.text) or
                         re.search(r'<result>(\d+)</result>', resp.text))
                m_z = re.search(r'<lastZ>(\d+)</lastZ>', resp.text)
                if m_doc and m_z:
                    numero_progressivo = int(m_doc.group(1))
                    numero_z = int(m_z.group(1)) + 1
                    break
            if numero_progressivo is not None and numero_z is not None:
                break

        if numero_progressivo is None or numero_z is None:
            return jsonify({"error": "La stampante non ha restituito il progressivo"}), 500

        progressivo_completo = f"{numero_z:04d}-{numero_progressivo:04d}"

        # ---------- persiste Receipt ----------
        total_amount = round(sum(float(v.get("prezzo", 0)) for v in voci_fiscali), 2)
        nuovo_receipt = Receipt(
            created_at       = datetime.now(),
            total_amount     = total_amount,
            is_fiscale       = True,
            voci             = voci_fiscali,
            cliente_id       = cliente_id,
            operatore_id     = operatore_id,
            numero_progressivo = progressivo_completo  # <-- ora è una stringa tipo 1825-0046
        )
        db.session.add(nuovo_receipt)
        db.session.commit()

        ids_pagati = [v.get("appointment_id") for v in voci_fiscali if v.get("appointment_id")]
        if ids_pagati:
            Appointment.query.filter(Appointment.id.in_(ids_pagati)).update(
                {Appointment.stato: AppointmentStatus.PAGATO}, synchronize_session=False
            )
            db.session.commit()

        results.append({
            "message": f"Scontrino fiscale registrato (progressivo {progressivo_completo})",
            "is_fiscale": True
        })

    # =========================
    # 2. SCONTRINO NON FISCALE
    # =========================
    if voci_non_fiscali:
        ultimo = Receipt.query.filter(
            Receipt.created_at >= datetime.combine(oggi, datetime.min.time()),
            Receipt.created_at <= datetime.combine(oggi, datetime.max.time())
        ).order_by(Receipt.numero_progressivo.desc()).first()
        if not ultimo or not str(ultimo.numero_progressivo).isdigit():
            numero_progressivo = "1"
        else:
            numero_progressivo = str(int(ultimo.numero_progressivo) + 1)

        total_amount = round(sum(float(v.get("prezzo", 0)) for v in voci_non_fiscali), 2)
        nuovo_receipt = Receipt(
            created_at       = datetime.now(),
            total_amount     = total_amount,
            is_fiscale       = False,
            voci             = voci_non_fiscali,
            cliente_id       = cliente_id,
            operatore_id     = operatore_id,
            numero_progressivo = numero_progressivo
        )
        db.session.add(nuovo_receipt)
        db.session.commit()

        ids_pagati = [v.get("appointment_id") for v in voci_non_fiscali if v.get("appointment_id")]
        if ids_pagati:
            Appointment.query.filter(Appointment.id.in_(ids_pagati)).update(
                {Appointment.stato: AppointmentStatus.PAGATO}, synchronize_session=False
            )
            db.session.commit()

        results.append({
            "message": "Scontrino non fiscale registrato",
            "is_fiscale": False
        })

    return jsonify({"results": results, "reset_voci": True})

@cassa_bp.route('/cassa/registro-scontrini')
def registro_scontrini():
    data_str = request.args.get('data')
    if data_str:
        try:
            giorno = datetime.strptime(data_str, "%Y-%m-%d").date()
        except ValueError:
            giorno = date.today()
    else:
        giorno = date.today()
    # --- FILTRO IN BASE AL RUOLO ---
    user_id = session.get("user_id")
    user = db.session.get(User, user_id)
    if user and user.ruolo.value == "user":
        scontrini = Receipt.query.filter(
            Receipt.is_fiscale == True,
            Receipt.created_at >= datetime.combine(giorno, datetime.min.time()),
            Receipt.created_at <= datetime.combine(giorno, datetime.max.time())
        ).order_by(Receipt.created_at.asc()).all()
    else:
        scontrini = Receipt.query.filter(
            Receipt.created_at >= datetime.combine(giorno, datetime.min.time()),
            Receipt.created_at <= datetime.combine(giorno, datetime.max.time())
        ).order_by(Receipt.created_at.asc()).all()

    for s in scontrini:
        s.is_fiscale = bool(s.is_fiscale)
        # NEW: Converti voci da stringa JSON a lista, come in api_receipt_detail
        voci = s.voci
        if isinstance(voci, str):
            try:
                s.voci = json.loads(voci)
            except Exception:
                s.voci = []
        if s.voci is None:
            s.voci = []

    # Passa il ruolo al template
    user_role = user.ruolo.value if user else None
    
    return render_template('registro_scontrini.html', scontrini=scontrini, giorno=giorno, user_role=user_role, date_today=date.today())

@cassa_bp.route('/cassa/api/receipt/<int:receipt_id>')
def api_receipt_detail(receipt_id):
    user_id = session.get("user_id")
    user = db.session.get(User, user_id)
    s = db.session.get(Receipt, receipt_id)
    if not s:
        abort(404)
    # Filtro: se user e lo scontrino NON è fiscale, blocca l'accesso
    if user and user.ruolo.value == "user" and not s.is_fiscale:
        return jsonify({"error": "Non autorizzato"}), 403

    voci = s.voci
    if isinstance(voci, str):
        try:
            voci = json.loads(voci)
        except Exception:
            voci = []
    if voci is None:
        voci = []

    for v in voci:
        if not v.get("nome") and v.get("servizio_id"):
            servizio = db.session.get(Service, v["servizio_id"])
            if servizio:
                v["nome"] = servizio.servizio_nome

    return jsonify({
        "id": s.id,
        "created_at": s.created_at.strftime('%d/%m/%Y %H:%M:%S'),
        "is_fiscale": s.is_fiscale,
        "operatore": f"{s.operatore.user_nome} {s.operatore.user_cognome}" if s.operatore else "-",
        "cliente": f"{s.cliente.cliente_nome} {s.cliente.cliente_cognome}" if s.cliente else "Generico",
        "voci": [
            {
                "nome": v.get('servizio_nome') or v.get('nome', ''),
                "prezzo": v.get('prezzo', 0),
                "metodo_pagamento": v.get('metodo_pagamento', ''),
                "is_non_fiscale": v.get('is_non_fiscale', False)
            } for v in (voci or [])
        ],
        "totale": s.total_amount,
        "totale_scontrinato": s.total_amount if s.is_fiscale else 0
    })

@cassa_bp.route('/cassa/api/receipt/<int:id>', methods=['DELETE'])
def api_receipt_delete(id):
    try:
        scontrino = db.session.get(Receipt, id)
        if not scontrino:
            abort(404)
        
        # Controllo ruolo: solo ADMIN/OWNER
        user_id = session.get("user_id")
        user = db.session.get(User, user_id)
        if not user or user.ruolo.value not in ["admin", "owner"]:
            return jsonify({"error": "Non autorizzato: solo amministratori possono eliminare scontrini"}), 403
        
        oggi = datetime.now().date()
        data_scontrino = scontrino.created_at.date() if scontrino.created_at else None
        
        if scontrino.is_fiscale:
            if data_scontrino != oggi:
                return jsonify({"error": "Eliminazione possibile solo per scontrini fiscali del giorno corrente"}), 400
            
            # Storna fiscalmente prima
            storno_result = stornare_scontrino_specifico(scontrino)
            if "error" in storno_result:
                return jsonify({"error": f"Storno fallito: {storno_result['error']}"}), 400
        
        # Elimina dal DB
        db.session.delete(scontrino)
        db.session.commit()
        return '', 204
    except Exception as e:
        current_app.logger.error("Errore eliminazione scontrino %s: %s", id, str(e))
        return jsonify({"error": "Errore durante l'eliminazione"}), 400
    
@cassa_bp.route('/cassa/api/receipt/<int:receipt_id>/update-metodo', methods=['POST'])
def update_metodo_pagamento(receipt_id):
    scontrino = db.session.get(Receipt, receipt_id)
    if not scontrino:
        abort(404)
    data = request.get_json()
    metodi = data.get('metodi')
    voci = scontrino.voci
    if isinstance(voci, str):
        voci = json.loads(voci)
    if not isinstance(voci, list) or not isinstance(metodi, list) or len(metodi) != len(voci):
        return jsonify({'error': 'Dati non validi'}), 400
    for idx, metodo in enumerate(metodi):
        voci[idx]['metodo_pagamento'] = metodo
    scontrino.voci = voci
    flag_modified(scontrino, "voci")
    db.session.commit()
    return jsonify({'success': True})

@cassa_bp.route('/cassa/chiusura-giornaliera', methods=['POST'])
def chiusura_giornaliera():
    business = BusinessInfo.query.first()
    if not business or not business.printer_ip:
        return jsonify({"error": "IP stampante RCH non configurato"}), 400

    url = f"http://{business.printer_ip}/service.cgi"
    # Manteniamo il content-type storico che funzionava
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    xml_payload = """<?xml version="1.0" encoding="UTF-8"?>
<Service>
<cmd>&gt;C117/$0/*1/&amp;0/[0/]0/_0/@0</cmd>
<cmd>=C3</cmd>
<cmd>=C10</cmd>
<cmd>=C1</cmd>
</Service>"""

    try:
        resp = requests.post(url, data=xml_payload.encode("UTF-8"), headers=headers, timeout=45)
        body = resp.text or ""
        masked = re.sub(r'([A-Za-z0-9_\-]{8,})', '[REDACTED]', body)
        current_app.logger.debug("Chiusura giornaliera raw (masked): %s", masked[:4000])

        # Estrai eventuali codici di esito dal body (diverse forme che la RCH può usare)
        codes = set()
        codes.update(int(m) for m in re.findall(r'<errorCode>(\d+)</errorCode>', body))
        codes.update(int(m) for m in re.findall(r'<result[^>]*>(\d+)</result>', body))
        codes.update(int(m) for m in re.findall(r'Risultat[oi]\s*:\s*(\d+)', body, flags=re.IGNORECASE))

        # Se non troviamo nulla ma la risposta è 200, assumiamo OK
        if not codes and resp.status_code == 200:
            return jsonify({"status": "ok", "code": 200, "message": "Chiusura giornaliera completata"}), 200

        # Considera 0 e 410 come non fatali (410 = nessuna richiesta codici pendente)
        non_fatali = {0, 200, 410}
        fatali = {c for c in codes if c not in non_fatali}

        if not fatali:
            # Anche se l'HTTP code non è 200, l'esito è ok: non propagare l'errore al client
            return jsonify({"status": "ok", "code": 200, "message": "Chiusura giornaliera completata"}), 200

        # Errori reali: prova best-effort di sblocco (=C1) e segnala errore
        try:
            unlock = '<?xml version="1.0" encoding="UTF-8"?><Service><cmd>=C1</cmd></Service>'
            requests.post(url, data=unlock.encode("UTF-8"), headers=headers, timeout=8)
        except Exception:
            pass
        current_app.logger.error("Chiusura giornaliera: codici fatali rilevati: %s", sorted(fatali))
        return jsonify({"error": "Errore di comunicazione con la stampante fiscale."}), 502

    except Exception as e:
        current_app.logger.error("Errore durante la chiusura giornaliera (network): %s", str(e))
        # Best-effort di sblocco
        try:
            unlock = '<?xml version="1.0" encoding="UTF-8"?><Service><cmd>=C1</cmd></Service>'
            requests.post(url, data=unlock.encode("UTF-8"), headers=headers, timeout=8)
        except Exception:
            pass
        return jsonify({"error": "Errore di comunicazione con la stampante fiscale."}), 502
 
@cassa_bp.route('/cassa/api/dgfe', methods=['POST'])
def api_dgfe():
    data = request.get_json(force=True) or {}
    current_app.logger.debug("DEBUG /cassa/api/dgfe: %s", {"date": data.get("date"), "ip": ("[REDACTED]" if data.get("ip") else None)})

    ip = data.get("ip") if isinstance(data.get("ip"), str) else None
    date_str = data.get("date") if isinstance(data.get("date"), str) else None

    if not ip or not date_str:
        return jsonify({"error": "IP e data obbligatori"}), 400

    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        return jsonify({"error": "Formato data non valido"}), 400

    if not re.match(r'^(?:\d{1,3}\.){3}\d{1,3}$', ip) or any(int(p) > 255 for p in ip.split('.')):
        return jsonify({"error": "IP non valido"}), 400

    if not ip or not date_str:
        return jsonify({"error": "IP e data obbligatori"}), 400

    url = f'http://{ip}/service.cgi'
    headers = {'Content-Type': 'text/xml; charset=iso-8859-1'}
    timeout_short = 5
    timeout_mid = 10

    try:
        with requests.Session() as s:
            s.headers.update({'Connection': 'close'})
            xml_c3 = '<?xml version="1.0" encoding="UTF-8"?><Service><cmd>=C3</cmd></Service>'
            s.post(url, data=xml_c3.encode('iso-8859-1'), headers=headers, timeout=timeout_short, allow_redirects=False)

            d = datetime.strptime(date_str, '%Y-%m-%d')
            d_str = d.strftime('%d%m%y')
            xml_c452 = '<?xml version="1.0" encoding="UTF-8"?><Service>' \
                       f'<cmd>=C452/$0/&{d_str}/[1/]9999</cmd>' \
                       '</Service>'
            resp2 = s.post(url, data=xml_c452.encode('iso-8859-1'), headers=headers, timeout=timeout_mid, allow_redirects=False)

            xml_c1 = '<?xml version="1.0" encoding="UTF-8"?><Service><cmd>=C1</cmd></Service>'
            s.post(url, data=xml_c1.encode('iso-8859-1'), headers=headers, timeout=timeout_short, allow_redirects=False)
    except requests.exceptions.RequestException as e:
        current_app.logger.error("Errore durante la richiesta DGFE (network): %s", str(e))
        return jsonify({"error": "Errore di comunicazione con la stampante fiscale."}), 502

    ej_match = re.search(r"<EJ[^>]*>(.*?)</EJ>", resp2.text, re.DOTALL)
    dgfe_text = ej_match.group(1).strip() if ej_match else ""

    scontrini = []
    for blocco in dgfe_text.split('\n\n'):
        lines = blocco.strip().splitlines()
        if not lines:
            continue
        progressivo = re.search(r'PROGR:\s*(\d+)', blocco)
        dataora = re.search(r'DATA:\s*(\d{2}/\d{2}/\d{4} \d{2}:\d{2})', blocco)
        servizi = re.findall(r'SERVIZIO:\s*(.*?)\s*PREZZO:\s*([\d,.]+)', blocco)
        metodo = re.search(r'PAGAMENTO:\s*(\w+)', blocco)
        totale = re.search(r'TOTALE:\s*([\d,.]+)', blocco)
        if progressivo and dataora and servizi and metodo and totale:
            scontrini.append({
                "progressivo": progressivo.group(1),
                "dataora": dataora.group(1),
                "servizi": [{"nome": s[0], "prezzo": s[1]} for s in servizi],
                "metodo": metodo.group(1),
                "totale": totale.group(1)
            })

    return jsonify({
        "dgfe_text": dgfe_text or "Nessun dato DGFE trovato.",
        "scontrini": scontrini,
        "raw_xml": resp2.text
    })
    
@cassa_bp.route('/cassa/api/myspia')
def api_myspia():
    try:
        # Limite: solo appuntamenti IN_ISTITUTO della data corrente
        today = datetime.now().date()
        day_start = datetime.combine(today, datetime.min.time())
        day_end = datetime.combine(today, datetime.max.time())

        apps = Appointment.query.filter(
            Appointment.stato == AppointmentStatus.IN_ISTITUTO,
            Appointment.start_time >= day_start,
            Appointment.start_time <= day_end
        ).options(selectinload(Appointment.client), selectinload(Appointment.service), selectinload(Appointment.operator)).all()

        # Raggruppa per cliente
        gruppi = {}
        for app in apps:
            if not app.client:
                continue
            key = (app.client.id, app.client.cliente_nome, app.client.cliente_cognome)
            gruppi.setdefault(key, []).append(app)

        result = []
        for (client_id, nome, cognome), apps in gruppi.items():
            result.append({
                "cliente_id": client_id,
                "cliente_nome": nome,
                "cliente_cognome": cognome,
                "ids": [a.id for a in apps],
                "appuntamenti": [
                    {
                        "servizio_nome": a.service.servizio_nome if a.service else "",
                        "durata": a._duration,
                        "prezzo": a.service.servizio_prezzo if a.service else 0,
                        "bg_color": a.colore or "#fff",
                        "font_color": a.colore_font or "#000",
                        "data": a.start_time.strftime("%Y-%m-%d") if a.start_time else "",
                        "start_time": a.start_time.strftime("%H:%M") if a.start_time else "",
                        "operator_nome": f"{a.operator.user_nome} {a.operator.user_cognome}" if a.operator else ""
                    } for a in apps
                ]
            })
        return jsonify(result)
    except Exception as e:
        current_app.logger.exception("api_myspia error")
        return jsonify([]), 500

@cassa_bp.route('/cassa/annulla-ultimo-scontrino', methods=['POST'])
def annulla_ultimo_scontrino():
    ultimo = Receipt.query.filter(Receipt.is_fiscale == True).order_by(Receipt.created_at.desc()).first()
    if not ultimo or not ultimo.numero_progressivo:
        return jsonify({"error": "Nessuno scontrino fiscale da annullare"}), 404
    try:
        progressivo_str = str(ultimo.numero_progressivo)
        progressivo_sx, progressivo_dx = progressivo_str.split('-')
        progressivo_sx = progressivo_sx.zfill(4)
        progressivo_dx = str(int(progressivo_dx))
    except Exception as e:
        current_app.logger.error("Errore durante l'annullamento dell'ultimo scontrino: %s", str(e))
        return jsonify({"error": "Errore durante l'annullamento."}), 500
    data_scontrino = ultimo.created_at if ultimo.created_at else datetime.now()
    data_str = data_scontrino.strftime("%d%m%y")
    cmd = f"=k/&{data_str}/[{progressivo_sx}/]{progressivo_dx}"
    xml = f"""<?xml version="1.0" encoding="UTF-8" ?>
    <Service>
    <cmd>{cmd}</cmd>
    </Service>"""
    business = BusinessInfo.query.first()
    if not business or not business.printer_ip:
        return jsonify({"error": "IP stampante RCH non configurato"}), 400
    url = f"http://{business.printer_ip}/service.cgi"
    headers = {"Content-Type": "text/xml; charset=UTF-8"}
    try:
        resp = requests.post(url, data=xml.encode("UTF-8"), headers=headers, timeout=10)
        numero_progressivo = None
        numero_z = None
        for cmd in ("=C453/$0", "=DGFE/REG"):
            payload_prog = f'''<?xml version="1.0" encoding="UTF-8"?><Service><cmd>{cmd}</cmd></Service>'''
            for _ in range(6):
                pytime.sleep(0.5)
                resp2 = requests.post(url, data=payload_prog.encode('utf-8'), headers=headers, timeout=5)
                m_doc = (re.search(r'<lastDocF>(\d+)</lastDocF>', resp2.text) or
                        re.search(r'<C453[^>]*>(\d+)</C453>', resp2.text) or
                        re.search(r'<result>(\d+)</result>', resp2.text))
                m_z = re.search(r'<lastZ>(\d+)</lastZ>', resp2.text)
                if m_doc and m_z:
                    numero_progressivo = int(m_doc.group(1))
                    numero_z = int(m_z.group(1)) + 1
                    break
            if numero_progressivo is not None and numero_z is not None:
                break
        if numero_progressivo is None or numero_z is None:
            return jsonify({"error": "La stampante non ha restituito il progressivo"}), 500
        progressivo_completo = f"{numero_z:04d}-{numero_progressivo:04d}"
        voci_storno = []
        for v in ultimo.voci:
            voce = v.copy()
            try:
                voce['prezzo'] = -abs(float(voce.get('prezzo', 0)))
            except Exception:
                voce['prezzo'] = -0.0
            voce['nome'] = voce.get('nome') or voce.get('servizio_nome') or "STORNO"
            voci_storno.append(voce)
        nuovo_receipt = Receipt(
            created_at       = datetime.now(),
            total_amount     = -abs(ultimo.total_amount),
            is_fiscale       = True,
            voci             = voci_storno,
            cliente_id       = ultimo.cliente_id,
            operatore_id     = ultimo.operatore_id,
            numero_progressivo = progressivo_completo
        )
        db.session.add(nuovo_receipt)
        db.session.commit()
    except Exception as e:
        current_app.logger.error("Errore di rete durante l'annullamento: %s", str(e))
        return jsonify({"error": "Errore di rete durante l'annullamento."}), 500
    raw = resp.text or ""
    masked = re.sub(r'([A-Za-z0-9_\-]{8,})', '[REDACTED]', raw)
    current_app.logger.debug("Annullo raw (masked): %s", masked[:2000])
    return jsonify({"status": "ok" if resp.status_code == 200 else "error", "code": resp.status_code, "progressivo": progressivo_completo}), resp.status_code

@cassa_bp.route('/cassa/api/myspia/dettagli', methods=['POST'])
def myspia_dettagli():
    try:
        data = request.get_json(force=True) or {}
        ids = data.get('ids') or []
        if isinstance(ids, str):
            ids = [x for x in re.split(r'[,\s]+', ids) if x]
        ids = [int(x) for x in ids if str(x).isdigit()]
        if not ids:
            return jsonify({"success": False, "error": "Nessun id appuntamento"}), 400

        apps = (Appointment.query
                .filter(Appointment.id.in_(ids))
                .options(selectinload(Appointment.client),
                         selectinload(Appointment.service),
                         selectinload(Appointment.operator))
                .all())
        if not apps:
            return jsonify({"success": False, "error": "Appuntamenti non trovati"}), 404

        apps.sort(key=lambda a: a.start_time or datetime.min)

        cli = next((a.client for a in apps if a.client), None)
        op = next((a.operator for a in apps if a.operator), None)

        result = {
            "success": True,
            "cliente_id": cli.id if cli else None,
            "cliente_nome": (cli.cliente_nome if cli else "") or "",
            "cliente_cognome": (cli.cliente_cognome if cli else "") or "",
            "operatore_id": op.id if op else None,
            "operatore_nome": (f"{op.user_nome} {op.user_cognome}".strip() if op else ""),
            "appuntamenti": []
        }

        for a in apps:
            s = a.service
            result["appuntamenti"].append({
                "id": s.id if s else None,
                "nome": s.servizio_nome if s else "",
                "prezzo": s.servizio_prezzo if s else 0,
                "tag": s.servizio_tag if s else "",
                "sottocategoria": s.servizio_sottocategoria.nome if (s and s.servizio_sottocategoria) else "",
                "appointment_id": a.id
            })

        return jsonify(result)
    except Exception as e:
        current_app.logger.exception("Errore /cassa/api/myspia/dettagli")
        return jsonify({"success": False, "error": "Errore interno"}), 500
    
# Helper per stornare uno scontrino specifico (del giorno corrente)
def stornare_scontrino_specifico(scontrino):
    if not scontrino.is_fiscale or not scontrino.numero_progressivo:
        return {"error": "Scontrino non fiscale o senza progressivo"}
    
    try:
        progressivo_str = str(scontrino.numero_progressivo)
        progressivo_sx, progressivo_dx = progressivo_str.split('-')
        progressivo_sx = progressivo_sx.zfill(4)
        progressivo_dx = str(int(progressivo_dx))
    except Exception as e:
        return {"error": "Progressivo non valido"}
    
    data_scontrino = scontrino.created_at.date() if scontrino.created_at else datetime.now().date()
    oggi = datetime.now().date()
    if data_scontrino != oggi:
        return {"error": "Storno possibile solo per scontrini del giorno corrente"}
    
    data_str = data_scontrino.strftime("%d%m%y")
    cmd = f"=k/&{data_str}/[{progressivo_sx}/]{progressivo_dx}"
    xml = f"""<?xml version="1.0" encoding="UTF-8" ?>
    <Service>
    <cmd>{cmd}</cmd>
    </Service>"""
    
    business = BusinessInfo.query.first()
    if not business or not business.printer_ip:
        return {"error": "IP stampante RCH non configurato"}
    
    url = f"http://{business.printer_ip}/service.cgi"
    headers = {"Content-Type": "text/xml; charset=UTF-8"}
    
    try:
        resp = requests.post(url, data=xml.encode("UTF-8"), headers=headers, timeout=None)
        current_app.logger.info("Risposta RCH storno: %s", resp.text)
        
        # Leggi nuovo progressivo post-storno (come in annulla_ultimo_scontrino)
        numero_progressivo = None
        numero_z = None
        for cmd in ("=C453/$0", "=DGFE/REG"):
            payload_prog = f'''<?xml version="1.0" encoding="UTF-8"?><Service><cmd>{cmd}</cmd></Service>'''
            for _ in range(6):
                pytime.sleep(0.5)
                resp2 = requests.post(url, data=payload_prog.encode('utf-8'), headers=headers, timeout=None)
                m_doc = (re.search(r'<lastDocF>(\d+)</lastDocF>', resp2.text) or
                         re.search(r'<C453[^>]*>(\d+)</C453>', resp2.text) or
                         re.search(r'<result>(\d+)</result>', resp2.text))
                m_z = re.search(r'<lastZ>(\d+)</lastZ>', resp2.text)
                if m_doc and m_z:
                    numero_progressivo = int(m_doc.group(1))
                    numero_z = int(m_z.group(1)) + 1
                    break
            if numero_progressivo is not None and numero_z is not None:
                break
        
        if numero_progressivo is None or numero_z is None:
            return {"error": "Impossibile leggere progressivo post-storno"}
        
        progressivo_completo = f"{numero_z:04d}-{numero_progressivo:04d}"
        
        # Crea sempre scontrino di storno nel DB (come in annulla_ultimo_scontrino)
        voci_storno = []
        for v in scontrino.voci:
            voce = v.copy()
            try:
                voce['prezzo'] = -abs(float(voce.get('prezzo', 0)))
            except Exception:
                voce['prezzo'] = -0.0
            voce['nome'] = voce.get('nome') or voce.get('servizio_nome') or "STORNO"
            voci_storno.append(voce)
        
        nuovo_receipt = Receipt(
            created_at       = datetime.now(),
            total_amount     = -abs(scontrino.total_amount),
            is_fiscale       = True,
            voci             = voci_storno,
            cliente_id       = scontrino.cliente_id,
            operatore_id     = scontrino.operatore_id,
            numero_progressivo = progressivo_completo
        )
        db.session.add(nuovo_receipt)
        db.session.commit()
        
        # Restituisci flag rch_ok basato su HTTP status (come in annulla_ultimo_scontrino)
        rch_ok = resp.status_code == 200
        return {"success": True, "progressivo_storno": progressivo_completo, "rch_ok": rch_ok}
    except Exception as e:
        current_app.logger.error("Errore storno specifico: %s", str(e))
        return {"error": "Errore durante lo storno"}
    
@cassa_bp.route('/api/user-role')
def api_user_role():
    user_id = session.get("user_id")
    user = db.session.get(User, user_id)
    return jsonify({"role": user.ruolo.value if user else None})