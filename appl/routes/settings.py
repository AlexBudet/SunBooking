# app/routes/settings.py
import re
import gender_guesser.detector as gender
from sqlalchemy import and_
from sqlalchemy.orm import joinedload, selectinload, load_only
from werkzeug.security import generate_password_hash, check_password_hash
from collections import defaultdict
from gender_guesser.detector import Detector
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session, abort, current_app
from flask import current_app as app
from datetime import datetime, timedelta
import os, ipaddress, time, requests
import threading
from sqlalchemy.sql import func, or_
from .. import db
from ..models import Appointment, AppointmentStatus, Operator, OperatorShift, Receipt, Service, Client, BusinessInfo, ServiceCategory, Subcategory, WeekDay, User, RuoloUtente
from wbiztool_client import WbizToolClient
from pytz import timezone

# Blueprint per le rotte delle impostazioni
settings_bp = Blueprint('settings', __name__, template_folder='../templates')

# semplice rate limiter in memoria (per processo)
_ping_printer_rl = {}

def format_name(name):
    """
    Normalizza il nome:
    - trim
    - minuscolo globale
    - capitalizza ogni parola
    - capitalizza dopo apostrofi tipografici (', ’, ′) e trattini: d’adamo -> D’Adamo, anna-maria -> Anna-Maria
    - decodifica entità HTML (es. &#39;)
    """
    if not name:
        return ""
    # Decodifica entità HTML e normalizza apostrofi tipografici in apostrofo ASCII
    try:
      import html as _html
      s = _html.unescape(str(name).strip())
    except Exception:
      s = str(name).strip()
    # Unifica tutti i tipi di apostrofo al carattere ASCII '
    s = (s.replace("\u2019", "'")   # ’
           .replace("\u02BC", "'")  # ʼ
           .replace("\u2032", "'")) # ′
    # Porta tutto in minuscolo per poi capitalizzare selettivamente
    s = s.lower()

    # Regola: rendi maiuscola la prima lettera della stringa, e ogni lettera dopo apostrofo o trattino
    # (gestisce anche lettere accentate)
    import re as _re
    def _upper(m):
        sep, ch = m.group(1), m.group(2)
        return (sep or "") + ch.upper()

    # (^|['-]) -> inizio stringa oppure dopo apostrofo o trattino
    s = _re.sub(r"(^|['-])([a-zà-öø-ÿ])", _upper, s)

    # Se vuoi mantenere l’apostrofo tipografico, ricambia l'ASCII in ’:
    # s = s.replace("'", "’")

    return s

# ===================== HOME =====================
@settings_bp.route('/settings', methods=['GET'])
def settings_home():
    """Pagina principale delle impostazioni."""
    # Qui puoi renderizzare una pagina di benvenuto o reindirizzare a una pagina predefinita
    return redirect(url_for('settings.clients'))

# ===================== BUSINESS INFO =====================
@settings_bp.route('/ping_printer', methods=['POST'])
def ping_printer():
    # 1) Recupera IP: prima da payload client (campo "ip"), altrimenti da DB
    payload = request.get_json(silent=True) or {}
    ip_from_client = (payload.get('ip') or '').strip()

    if ip_from_client:
        printer_ip = ip_from_client
    else:
        business = BusinessInfo.query.first()
        printer_ip = (getattr(business, 'printer_ip', None) or '').strip()

    if not printer_ip:
        return jsonify({"error": "IP stampante non configurato"}), 400

    # 2) Validazione IP minima (solo IPv4 non loopback)
    try:
        ip_addr = ipaddress.ip_address(printer_ip)
    except ValueError:
        current_app.logger.warning("ping_printer: printer_ip non è un indirizzo IP valido: %s", printer_ip)
        return jsonify({"error": "IP stampante non valido"}), 400

    if ip_addr.version != 4 or ip_addr.is_loopback:
        current_app.logger.warning("ping_printer: IP non ammesso (IPv6/loopback): %s", printer_ip)
        return jsonify({"error": "IP stampante non ammesso"}), 400

    # 3) Unico test: semplice GET HTTP verso la porta configurata, timeout ~20 secondi
    remote = request.remote_addr or 'unknown'
    port_env = os.getenv('PRINTER_HTTP_PORT', '80')
    try:
        port_int = int(port_env)
    except ValueError:
        port_int = 80

    url = f"http://{printer_ip}:{port_int}/"
    # timeout totale 20 secondi (connect, read)
    timeout = (10, 10)

    try:
        resp = requests.get(url, timeout=timeout, allow_redirects=False)
        current_app.logger.info("ping_printer: %s -> %s (status %s)", remote, url, resp.status_code)
        return jsonify({
            "ok": True,
            "status_code": resp.status_code,
            "text_snippet": (resp.text[:200] + '...') if isinstance(resp.text, str) else ""
        }), 200
    except requests.exceptions.Timeout:
        current_app.logger.error("ping_printer: timeout verso %s", url)
        return jsonify({"error": "Timeout connessione stampante (nessuna risposta entro 20s)"}), 504
    except Exception as exc:
        current_app.logger.error("ping_printer: errore rete verso %s: %s", url, str(exc))
        return jsonify({"error": f"Errore comunicazione con la stampante: {str(exc)}"}), 502

@settings_bp.route('/settings/business-info', methods=['GET'])
def business_info():
    """Pagina delle informazioni aziendali."""
    business_info = BusinessInfo.query.filter_by(is_deleted=False).first()
    user_id = session.get('user_id')
    current_user = db.session.get(User, user_id) if user_id else None
    return render_template('business_info.html', business_info=business_info, current_user=current_user)

@settings_bp.route('/settings/business_info', methods=['GET', 'POST'])
def set_business_info():
    business_info = BusinessInfo.query.filter_by(is_deleted=False).first()

    if request.method == 'POST':
        if not business_info:
            business_info = BusinessInfo()
            db.session.add(business_info)

        business_info.business_name = request.form.get('business_name')
        business_info.website = request.form.get('website')
        business_info.address = request.form.get('address')
        business_info.cap = request.form.get('cap')
        business_info.province = request.form.get('province')
        business_info.city = request.form.get('city')
        business_info.vat_code = request.form.get('vat_code')
        business_info.pec_code = request.form.get('pec_code')
        business_info.phone = request.form.get('phone')
        business_info.mobile = request.form.get('mobile')
        business_info.email = request.form.get('email')

        vat_percentage = request.form.get('vat_percentage')
        try:
            business_info.vat_percentage = float(vat_percentage)
        except (TypeError, ValueError):
            business_info.vat_percentage = 22.0

        business_info.rch_serial = request.form.get('rch_serial')

        # Orari e giorni di chiusura (se presenti nel form)
        open_time_str = request.form.get('opening_time', '08:00')
        business_info.opening_time = datetime.strptime(open_time_str, '%H:%M').time()

        close_time_str = request.form.get('closing_time', '20:00')
        business_info.closing_time = datetime.strptime(close_time_str, '%H:%M').time()

        active_open_str = request.form.get('active_opening_time', '08:00')
        business_info.active_opening_time = datetime.strptime(active_open_str, '%H:%M').time()

        active_close_str = request.form.get('active_closing_time', '20:00')
        business_info.active_closing_time = datetime.strptime(active_close_str, '%H:%M').time()

        closing_days = request.form.getlist('closing_days')
        business_info.closing_days_list = closing_days

        try:
            db.session.commit()
            flash("Informazioni aziendali aggiornate con successo!", "success")
        except Exception as e:
            db.session.rollback()
            app.logger.error("Errore durante l'aggiornamento delle info aziendali: %s", str(e))
            flash("Si è verificato un errore durante il salvataggio. Riprova.", "error")
            return redirect(url_for('settings.set_business_info'))

        # Dopo il salvataggio, ricarica la pagina con i dati aggiornati
        return redirect(url_for('settings.business_info'))

    # GET: mostra la pagina con i dati attuali
    return render_template('business_info.html', business_info=business_info)

@settings_bp.route('/settings/update-business-schedule', methods=['POST'])
def update_business_schedule():
    """
    Aggiorna gli orari giornalieri del negozio.
    """
    date = request.form.get('date')  # Esempio: "2025-01-26"
    opening_time = request.form.get('opening_time')  # Esempio: "08:00"
    closing_time = request.form.get('closing_time')  # Esempio: "20:00"

    if not date or not opening_time or not closing_time:
        flash("Tutti i campi sono obbligatori.", "error")
        return redirect(url_for('settings.business'))

    # Recupera il record BusinessInfo
    business_info = BusinessInfo.query.first()
    if not business_info:
        business_info = BusinessInfo(business_name="Negozio", daily_schedules={})

    # Aggiungi o aggiorna il JSON con i nuovi orari
    if not business_info.daily_schedules:
        business_info.daily_schedules = {}

    business_info.daily_schedules[date] = {
        "opening": opening_time,
        "closing": closing_time
    }

    db.session.add(business_info)
    db.session.commit()
    flash("Orari aggiornati con successo!", "success")
    return redirect(url_for('settings.business'))

# ===================== OPERATORS =====================
@settings_bp.route('/settings/operators', methods=['GET'])
def operators():
    """Pagina degli operatori."""
    user = session.get('user_id')
    current_user = db.session.get(User, user) if user else None
    operators = db.session.query(Operator).filter_by(is_deleted=False).all()
    appointments = db.session.query(Appointment).filter(Appointment.is_cancelled_by_client == False).all()
    appointments_by_operator = {}
    for op in operators:
        appointments_by_operator[op.id] = [appt for appt in appointments if appt.operator_id == op.id]
    return render_template(
        'operators.html',
        operators=operators,
        appointments_by_operator=appointments_by_operator,
        current_user=current_user
    )

@settings_bp.route('/operators/add', methods=['POST'])
def add_operator():
    """Aggiunge un nuovo operatore."""
    try:
        user_nome = format_name(request.form.get('user_nome'))
        user_cognome = format_name(request.form.get('user_cognome', ''))  # Campo cognome può essere vuoto
        user_tipo = request.form.get('user_tipo')
        user_cellulare = (request.form.get('user_cellulare') or '').strip()
        if not user_cellulare:
            user_cellulare = '0'

        # Verifica che i campi obbligatori siano stati compilati
        if not user_nome or not user_tipo:
            flash("I campi Nome e Tipo sono obbligatori.", "error")
            return redirect(url_for('settings.operators'))

        # Se il tipo è "macchinario", imposta il cognome come vuoto
        if user_tipo == 'macchinario':
            user_cognome = ''

        # Crea un nuovo operatore
        new_operator = Operator(
            user_nome=user_nome,
            user_cognome=user_cognome,  # Cognome vuoto per macchinario
            user_cellulare=user_cellulare,
            user_tipo=user_tipo
        )
        db.session.add(new_operator)
        db.session.commit()
    except Exception as e:
        app.logger.error("Errore durante l'aggiunta dell'operatore: %s", str(e))
        flash("Errore durante l'aggiunta dell'operatore. Riprova.", "error")
    
    return redirect(url_for('settings.operators'))

@settings_bp.route('/operators/<int:operator_id>/edit', methods=['GET', 'POST'])
def edit_operator(operator_id):
    """Modifica i dati di un operatore."""
    operator = db.session.get(Operator, operator_id)
    if not operator:
        abort(404)

    if request.method == 'POST':
        # Aggiorna i dati dell'operatore
        user_nome = format_name(request.form.get('user_nome'))
        user_cognome = format_name(request.form.get('user_cognome', ''))
        user_cellulare = (request.form.get('user_cellulare') or '').strip()
        user_tipo = request.form.get('user_tipo')

        # Applica le modifiche all'operatore
        operator.user_nome = user_nome
        operator.user_cognome = user_cognome
        operator.user_cellulare = user_cellulare
        operator.user_tipo = user_tipo

        try:
            db.session.commit()
            return redirect(url_for('settings.operators'))
        except Exception as e:
            app.logger.error("Errore durante l'aggiornamento dell'operatore %s: %s", operator_id, str(e))
            flash("Errore durante l'aggiornamento dell'operatore. Riprova.", "error")
            return redirect(url_for('settings.edit_operator', operator_id=operator.id))
    
    # Se la richiesta è GET, mostra il form di modifica
    return render_template('edit_operator.html', operator=operator)

@settings_bp.route('/operators/<int:operator_id>', methods=['PUT'])
def update_operator(operator_id):
    """Aggiorna i dettagli di un operatore."""
    data = request.json
    operator = db.session.get(Operator, operator_id)
    if not operator:
        return jsonify({'error': 'Operatore non trovato'}), 404

    # Aggiorna i campi base
    operator.user_nome = data.get('nome', operator.user_nome)
    operator.user_cognome = data.get('cognome', operator.user_cognome)
    operator.user_tipo = data.get('tipo', operator.user_tipo)
    operator.is_visible = data.get('is_visible', operator.is_visible)

    # Nuovo flag: memo turni via WhatsApp
    if 'notify_turni_via_whatsapp' in data:
        operator.notify_turni_via_whatsapp = bool(data['notify_turni_via_whatsapp'])

    db.session.commit()
    return jsonify({"message": "Operatore aggiornato con successo!"}), 200

@settings_bp.route('/settings/operators/<int:operator_id>/delete', methods=['POST'])
def delete_operator(operator_id):
    """Elimina un operatore (logicamente)."""
    try:
        operator = db.session.get(Operator, operator_id)
        if not operator:
            abort(404)
        # Imposta solo il flag is_deleted a True, senza modificare gli altri campi
        operator.is_deleted = True
        db.session.commit()
    except Exception as e:
        app.logger.error("Errore durante l'eliminazione dell'operatore %s: %s", operator_id, str(e))
        flash("Errore durante l'eliminazione dell'operatore. Riprova.", "error")
    
    return redirect(url_for('settings.operators'))

# ===================== SERVICES =====================
@settings_bp.route('/settings/services', methods=['GET'])
def services():
    services = (Service.query
        .filter(Service.is_deleted == False)
        .filter(~(
            or_(
                func.lower(func.trim(Service.servizio_nome)) == "dummy",
                func.lower(func.trim(Service.servizio_nome)) == "booking online"
            )
        ))
        .all())
    subcategories = Subcategory.query.filter_by(is_deleted=False).all()
    user_id = session.get('user_id')
    current_user = db.session.get(User, user_id) if user_id else None
    return render_template(
        'services.html',
        services=services,
        subcategories=subcategories,
        current_user=current_user
    )

@settings_bp.route('/api/subcategories/<string:category>', methods=['GET'])
def get_subcategories(category):
    """
    Restituisce le sottocategorie associate a una categoria specifica.
    """
    # Controlla se la categoria è valida
    valid_categories = ["Solarium", "Estetica"]
    if category not in valid_categories:
            return jsonify({"error": f"Categoria '{category}' non valida"}), 400

    # Recupera le sottocategorie per la categoria specificata
    subcategories = Subcategory.query.filter_by(categoria=category, is_deleted=False).all()

    # Restituisce un JSON con le sottocategorie
    return jsonify([{'id': sub.id, 'name': sub.nome} for sub in subcategories])

@settings_bp.route('/settings/services', methods=['POST'])
def add_service():
    """Aggiunge un nuovo servizio."""
    try:
        service_name = request.form.get('service_name')
        service_tag = request.form.get('service_tag')
        service_duration = request.form.get('service_duration')
        service_price = request.form.get('service_price')
        service_category = ServiceCategory(request.form.get('service_category'))
        service_subcategory = request.form.get('service_subcategory')

        # Recupera la sottocategoria per il controllo
        subcategory = db.session.get(Subcategory, service_subcategory)
        is_prodotti = subcategory and subcategory.nome.lower() == "prodotti"

        # Validazione: la durata è obbligatoria solo se NON è "prodotti"
        if not service_name or not service_price or not service_category:
            print(f"Validazione fallita: nome={service_name}, prezzo={service_price}, categoria={service_category}")
            return redirect(url_for('settings.services'))

        # Imposta durata e visibilità per prodotti
        is_visible_in_calendar = True

        if is_prodotti:
            service_duration = 0
            is_visible_in_calendar = False
        else:
            try:
                service_duration = int(service_duration)
            except (TypeError, ValueError):
                service_duration = 0
            if service_duration == 0:
                is_visible_in_calendar = False

        service_price = float(service_price)

        new_service = Service(
            servizio_nome=service_name,
            servizio_tag=service_tag,
            servizio_durata=service_duration,
            servizio_prezzo=service_price,
            servizio_categoria=ServiceCategory(service_category),
            servizio_sottocategoria_id=service_subcategory,
            is_visible_in_calendar=is_visible_in_calendar
        )

        db.session.add(new_service)
        db.session.commit()
    except Exception as e:
        app.logger.error("Errore durante l'aggiunta del servizio: %s", str(e))
        flash("Errore durante l'aggiunta del servizio. Riprova.", "error")
    
    return redirect(url_for('settings.services'))

@settings_bp.route('/settings/services/<int:service_id>/edit', methods=['GET', 'POST'], endpoint='edit_service')
def edit_service(service_id):
    """Modifica un servizio esistente."""
    service = db.session.get(Service, service_id)
    if not service:
        abort(404)

    if request.method == 'POST':
        try:
            service.servizio_nome = request.form.get('service_name')
            service.servizio_tag = request.form.get('service_tag')
            service.servizio_durata = int(request.form.get('service_duration'))
            service.servizio_prezzo = float(request.form.get('service_price'))
            service.servizio_categoria = ServiceCategory(request.form.get('service_category'))
            service.servizio_sottocategoria_id = request.form.get('service_subcategory')

            db.session.commit()
            flash("Servizio aggiornato con successo!", "success")
            return redirect(url_for('settings.services'))
        except Exception as e:
            app.logger.error("Errore durante l'aggiornamento del servizio %s: %s", service_id, str(e))
            flash("Errore durante l'aggiornamento del servizio. Riprova.", "error")

    subcategories = Subcategory.query.filter_by(is_deleted=False).all()
    return render_template('edit_service.html', service=service, subcategories=subcategories)

@settings_bp.route('/settings/services/<int:service_id>/delete', methods=['POST'], endpoint='delete_service')
def delete_service(service_id):
    """Elimina un servizio."""
    try:
        service = db.session.get(Service, service_id)
        if not service:
            abort(404)
        service.is_deleted = True  # Eliminazione logica
        db.session.commit()
        flash("Servizio eliminato con successo!", "success")
    except Exception as e:
        app.logger.error("Errore durante l'eliminazione del servizio %s: %s", service_id, str(e))
        flash("Errore durante l'eliminazione del servizio. Riprova.", "error")
    
    return redirect(url_for('settings.services'))

@settings_bp.route('/settings/services/<int:service_id>/description', methods=['POST'])
def service_description(service_id):
    """Salva la descrizione HTML del servizio (servizio_descrizione)."""
    service = db.session.get(Service, service_id)
    if not service:
        abort(404)

    # Consenti solo a admin/owner di salvare (controllo tramite sessione)
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Forbidden'}), 403
    
    current_user = db.session.get(User, user_id)
    if not current_user or current_user.ruolo.value == 'user':
        return jsonify({'error': 'Forbidden'}), 403

    data = request.get_json(silent=True) or {}
    descr = (data.get('descrizione') or '').strip()
    service.servizio_descrizione = descr if descr else None
    db.session.commit()
    return jsonify({'ok': True})
# ===================== CLIENTS =====================
@settings_bp.route('/settings/clients', methods=['GET'])
def clients():
    """Visualizza la pagina dei clienti senza caricare dati iniziali."""
    # Non carica clienti all'apertura per prestazioni
    return render_template('clients.html', clients=[])

@settings_bp.route('/settings/clients', methods=['POST'])
def add_client():
    from sqlalchemy.exc import IntegrityError

    try:
        # Supporta sia JSON (calendar) sia form (clients.html)
        data = request.get_json(silent=True) or {}
        form = request.form or {}

        # helper per leggere da JSON o form con fallback sicuro
        def get_value(json_key, form_key):
            if json_key in data and data.get(json_key) is not None:
                return str(data.get(json_key)).strip()
            return str(form.get(form_key) or "").strip()

        client_name = get_value('cliente_nome', 'client_name')
        client_surname = get_value('cliente_cognome', 'client_surname')
        client_phone = get_value('cliente_cellulare', 'client_phone')
        client_birthdate_raw = get_value('cliente_data_nascita', 'client_birthdate') or None
        client_email = get_value('cliente_email', 'client_email') or None
        client_gender = (data.get('cliente_sesso') if 'cliente_sesso' in data else form.get('client_gender') or form.get('cliente_sesso') or "").strip()

                # --- normalizzazione telefono per confronto di unicità ---
        def _normalize_phone(p):
            if not p:
                return ''
            s = re.sub(r'\D', '', str(p))
            if s.startswith('00'):
                s = s[2:]
            if s.startswith('39'):
                s = s[2:]
            if s.startswith('0'):
                s = s[1:]
            return s

        phone_norm = _normalize_phone(client_phone)

        # verifica duplicato: confronta rimuovendo spazi e +39 dalla colonna DB (allineato a search logic)
        if phone_norm:
            existing = Client.query.filter(
                func.replace(func.replace(Client.cliente_cellulare, ' ', ''), '+39', '') == phone_norm
            ).first()
            if existing:
               return jsonify("Attenzione! questo numero risulta assegnato ad un altro cliente"), 400

        # campi obbligatori
        if not client_name or not client_surname or not client_phone:
            return jsonify("Attenzione! I campi Nome, Cognome e Cellulare sono obbligatori."), 400

        # normalizza nome/cognome
        client_name = client_name.capitalize()
        client_surname = client_surname.capitalize()

        # Se il client_gender non è passato, prova Detector e fallback con eccezioni note
        if not client_gender:
            try:
                tokens = [t for t in (client_name or '').strip().split() if t]
                first = (tokens[0].lower() if tokens else '')
                first2 = (" ".join(tokens[:2]).lower() if len(tokens) >= 2 else '')
                male_exceptions = {'andrea', 'luca', 'gigi', 'luigi', 'pier maria', 'pier andrea', 'pier-maria', 'pier-andrea'}

                detector = Detector()
                guessed_gender = detector.get_gender(first or '')
                if guessed_gender in ['male', 'mostly_male']:
                    client_gender = 'M'
                elif guessed_gender in ['female', 'mostly_female']:
                    # Correggi i falsi positivi (es. Andrea in IT)
                    client_gender = 'M' if (first in male_exceptions or first2 in male_exceptions) else 'F'
                else:
                    # Fallback: eccezioni -> altrimenti ultima lettera
                    if first in male_exceptions or first2 in male_exceptions:
                        client_gender = 'M'
                    else:
                        ln = (client_name or '').lower()
                        if ln.endswith('o'):
                            client_gender = 'M'
                        elif ln.endswith('a'):
                            client_gender = 'F'
                        else:
                            client_gender = '-'
            except Exception:
                # Fallback robusto: eccezioni note prima, poi ultima lettera
                tokens = [t for t in (client_name or '').strip().split() if t]
                first = (tokens[0].lower() if tokens else '')
                first2 = (" ".join(tokens[:2]).lower() if len(tokens) >= 2 else '')
                male_exceptions = {'andrea', 'luca', 'gigi', 'luigi', 'pier maria', 'pier andrea', 'pier-maria', 'pier-andrea'}
                if first in male_exceptions or first2 in male_exceptions:
                    client_gender = 'M'
                else:
                    ln = (client_name or '').lower()
                    if ln.endswith('o'):
                        client_gender = 'M'
                    elif ln.endswith('a'):
                        client_gender = 'F'
                    else:
                        client_gender = '-'

        # parse data in modo sicuro (DATE)
        client_birthdate = None
        if client_birthdate_raw:
            try:
                client_birthdate = datetime.strptime(client_birthdate_raw, '%Y-%m-%d').date()
            except Exception:
                client_birthdate = None

        # crea cliente
        new_client = Client(
            cliente_nome=client_name,
            cliente_cognome=client_surname,
            cliente_cellulare=client_phone,
            cliente_email=client_email,
            cliente_data_nascita=client_birthdate,
            cliente_sesso=client_gender
        )
        db.session.add(new_client)
        try:
            db.session.commit()
        except IntegrityError as ie:
            db.session.rollback()
            app.logger.exception("IntegrityError add_client settings: %s", ie)
            return jsonify({"error": "Vincolo di integrità violato (es. duplicato)."}), 400
        except Exception as db_e:
            db.session.rollback()
            app.logger.exception("DB error add_client settings: %s", db_e)
            return jsonify({"error": "Errore interno del database."}), 500

        return jsonify({
            "message": "Cliente aggiunto con successo!",
            "client_id": new_client.id,
            "client_name": new_client.cliente_nome,
            "client_surname": new_client.cliente_cognome,
            "client_phone": new_client.cliente_cellulare
        }), 201

    except Exception as e:
        app.logger.exception("Unhandled exception in settings.add_client: %s", e)
        return jsonify({"error": "Errore interno durante l'aggiunta del cliente."}), 500
    
@settings_bp.route('/settings/clients/<int:client_id>/edit', methods=['GET', 'POST'])
def edit_client(client_id):
    client = db.session.get(Client, client_id)
    if not client:
        abort(404)

    if request.method == 'POST':
        try:
            client_name = request.form.get('client_name').strip()
            client_surname = request.form.get('client_surname').strip()
            client_phone = request.form.get('client_phone').strip()
            client_date_of_birth = request.form.get('client_date_of_birth')
            client_email = request.form.get('client_email').strip()

            if client_email and client_email != "None":
                email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                if not re.match(email_regex, client_email):
                    flash("Formato email non valido. Usa un formato valido o 'None'.", "error")
                    return redirect(url_for('settings.edit_client', client_id=client_id))

            client_name = client_name.capitalize() if client_name else ''
            client_surname = client_surname.capitalize() if client_surname else ''

            # Rileva il genere con gestione errori
            client_gender = client.cliente_sesso  # Inizializza con valore corrente
            if client_name:
                try:
                    detector = Detector()
                    guessed_gender = detector.get_gender(client_name.split()[0])
                    if guessed_gender in ['male', 'mostly_male']:
                        client_gender = 'M'
                    elif guessed_gender in ['female', 'mostly_female']:
                        client_gender = 'F'
                    else:
                        # Fallback basato sull'ultima lettera
                        if client_name.lower().endswith('o'):
                            client_gender = 'M'
                        elif client_name.lower().endswith('a'):
                            client_gender = 'F'
                except Exception as e:
                    app.logger.warning(f"Errore rilevamento genere per {client_name}: {str(e)}")
                    # Mantieni il valore corrente se fallisce

            # Converti data con validazione
            if client_date_of_birth:
                try:
                    client_date_of_birth = datetime.strptime(client_date_of_birth, '%Y-%m-%d').date()
                except ValueError:
                    app.logger.error(f"Data non valida: {client_date_of_birth}")
                    client_date_of_birth = None
            else:
                client_date_of_birth = None

            # Aggiorna cliente
            client.cliente_nome = client_name
            client.cliente_cognome = client_surname
            client.cliente_cellulare = client_phone
            client.cliente_email = client_email
            client.cliente_data_nascita = client_date_of_birth
            client.cliente_sesso = client_gender

            db.session.commit()
            return redirect(url_for('settings.clients'))

        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Errore modifica cliente {client_id}: {str(e)}")
            return jsonify({"error": f"Errore durante l'aggiornamento del cliente: {str(e)}"}), 500

    return render_template('edit_client.html', client=client)

@settings_bp.route('/delete_client/<int:client_id>', methods=['POST'])
def delete_client(client_id):
    client = db.session.get(Client, client_id)
    if client:
        client.is_deleted = True
        db.session.commit()
    # Assicurati di reindirizzare a una pagina che non reindirizza ulteriormente
    return redirect(url_for('settings.clients'))

@settings_bp.route('/api/client_history', methods=['GET'])
def client_history():
    query = request.args.get('q', '').strip()
    if not query or len(query) < 1:
        return jsonify({"error": "Query troppo corta"}), 400

    # Se la query è numerica, cerca per ID
    if query.isdigit():
        clients = Client.query.filter(
            Client.is_deleted == False,
            Client.id == int(query)
        ).all()
    else:
        clients = Client.query.filter(
            Client.is_deleted == False,
            or_(
                Client.cliente_nome.ilike(f"%{query}%"),
                Client.cliente_cognome.ilike(f"%{query}%")
            )
        ).all()

    result = []
    for client in clients:
        appointments = Appointment.query.filter_by(
            client_id=client.id,
            stato=AppointmentStatus.PAGATO
        ).filter(Appointment.is_cancelled_by_client == False).order_by(Appointment.start_time.desc()).all()

        for appt in appointments:
            service = db.session.get(Service, appt.service_id)
            costo = None
            operatore_nome = None

            receipts = db.session.query(Receipt).filter_by(cliente_id=client.id).order_by(Receipt.created_at.desc()).all()
            for receipt in receipts:
                if not receipt.voci:
                    continue
                for voce in receipt.voci:
                    if (voce.get('appointment_id') == appt.id) or \
                       (voce.get('service_id') == appt.service_id) or \
                       (voce.get('nome') == (service.servizio_nome if service else None)):
                        costo = voce.get('prezzo', None)
                        # Recupera l'operatore dal receipt
                        if receipt.operatore:
                            operatore_nome = (receipt.operatore.user_nome or "").strip()
                        else:
                            operatore_nome = None
                        break
                if costo is not None:
                    break

            result.append({
                "appointment_id": appt.id,
                "servizio": service.servizio_nome if service else None,
                "servizio_tag": service.servizio_tag if service else None,
                "ora_inizio": appt.start_time.strftime('%Y-%m-%d %H:%M'),
                "durata": appt.duration,
                "costo": costo,
                "operatore": operatore_nome,
                "stato": appt.stato.value if hasattr(appt.stato, 'value') else int(appt.stato),
                "cliente_nome": f"{client.cliente_nome} {client.cliente_cognome}".strip(),
                "cliente_cognome": client.cliente_cognome
            })

    return jsonify(result)

@settings_bp.route('/api/search-clients', methods=['GET'])
def search_clients_settings():
    q = request.args.get('q', '').strip().lower()
    if len(q) < 2:
        return jsonify([])

    parts = [p for p in q.split() if p]
    if len(parts) == 1:
        term = f"%{parts[0]}%"
        filters = or_(
            func.lower(Client.cliente_nome).like(term),
            func.lower(Client.cliente_cognome).like(term),
            Client.cliente_cellulare.like(term)
        )
    else:
        conditions = [
            or_(
                func.lower(Client.cliente_nome).like(f"%{part}%"),
                func.lower(Client.cliente_cognome).like(f"%{part}%")
            )
            for part in parts
        ]
        filters = and_(*conditions)

    # Query raw per debug (rimuovi dopo verifica)
    clients_raw = Client.query.filter(filters).filter_by(is_deleted=False).limit(50).all()
    current_app.logger.info(f"Clienti raw prima esclusione dummy: {len(clients_raw)} - Nomi: {[f'{c.cliente_nome} {c.cliente_cognome}' for c in clients_raw]}")

    # Esclusione semplificata
    clients = Client.query.filter(filters).filter_by(is_deleted=False).filter(
        ~(
            or_(
                and_(func.lower(Client.cliente_nome) == "dummy", func.lower(Client.cliente_cognome) == "dummy"),
                and_(func.lower(Client.cliente_nome) == "cliente", func.lower(Client.cliente_cognome) == "booking"),
                and_(func.lower(Client.cliente_nome) == "booking", func.lower(Client.cliente_cognome) == "online"),
                Client.cliente_nome == "dummy dummy",
                Client.cliente_nome == "booking online"
            )
        )
    ).limit(50).all()

    current_app.logger.info(f"Clienti dopo esclusione dummy: {len(clients)}")

    clients_data = []
    if clients:
        client_ids = [c.id for c in clients]

        num_passaggi_query = db.session.query(
            Appointment.client_id,
            func.count(func.distinct(func.date(Appointment.start_time))).label('num_passaggi')
        ).filter(
            Appointment.client_id.in_(client_ids),
            Appointment.stato == AppointmentStatus.PAGATO,
            Appointment.is_cancelled_by_client == False  # <-- AGGIUNGI QUESTO
        ).group_by(Appointment.client_id).all()
        num_passaggi_dict = {r.client_id: r.num_passaggi for r in num_passaggi_query}

        ultimo_passaggio_query = db.session.query(
            Appointment.client_id,
            func.max(Appointment.start_time).label('ultimo_passaggio')
        ).filter(
            Appointment.client_id.in_(client_ids),
            Appointment.stato == AppointmentStatus.PAGATO,
            Appointment.is_cancelled_by_client == False
        ).group_by(Appointment.client_id).all()
        ultimo_passaggio_dict = {r.client_id: r.ultimo_passaggio for r in ultimo_passaggio_query}

        for c in clients:
            clients_data.append({
                'id': c.id,
                'cliente_nome': getattr(c, 'cliente_nome', '') or '',
                'cliente_cognome': getattr(c, 'cliente_cognome', '') or '',
                'cliente_cellulare': getattr(c, 'cliente_cellulare', '') or '',
                'cliente_email': getattr(c, 'cliente_email', '') or '',
                'cliente_data_nascita': (c.cliente_data_nascita.strftime('%d/%m/%Y') if getattr(c, 'cliente_data_nascita', None) else '-'),
                'cliente_sesso': getattr(c, 'cliente_sesso', '') or '-',
                'created_at': (c.created_at.strftime('%d/%m/%Y') if getattr(c, 'created_at', None) else '-'),
                'num_passaggi': int(num_passaggi_dict.get(c.id, 0)),
                'ultimo_passaggio': (ultimo_passaggio_dict.get(c.id).strftime('%d/%m/%Y') if ultimo_passaggio_dict.get(c.id) else '-'),
                'note': getattr(c, 'note', '') or ''
            })

    current_app.logger.debug("search-clients -> returning %d items", len(clients_data))
    return jsonify(clients_data)

@settings_bp.route('/api/recent-clients', methods=['GET'])
def recent_clients():
    """Restituisce gli ultimi 10 clienti modificati (basato su created_at, o updated_at se presente)."""
    try:
        # Filtra clienti non eliminati, escludendo "booking online"
        query = Client.query.filter(
            Client.is_deleted == False,
            ~(
                (func.lower(func.trim(func.coalesce(Client.cliente_nome, ''))) == "booking") &
                (func.lower(func.trim(func.coalesce(Client.cliente_cognome, ''))) == "online")
            )
        )

        # Ordina per created_at discendente (assumendo che rappresenti l'ultima modifica; se hai updated_at, cambia qui)
        recent_clients = query.order_by(Client.created_at.desc()).limit(10).all()

        # Calcola num_passaggi e ultimo_passaggio per questi clienti
        if recent_clients:
            client_ids = [c.id for c in recent_clients]

            # Query aggregata per num_passaggi
            num_passaggi_query = db.session.query(
                Appointment.client_id,
                func.count(func.distinct(func.date(Appointment.start_time))).label('num_passaggi')
            ).filter(
                Appointment.client_id.in_(client_ids),
                Appointment.stato.in_([AppointmentStatus.PAGATO]),
                Appointment.is_cancelled_by_client == False  # <-- AGGIUNGI QUESTO
            ).group_by(Appointment.client_id).all()

            num_passaggi_dict = {row.client_id: row.num_passaggi for row in num_passaggi_query}

            # Query aggregata per ultimo_passaggio
            ultimo_passaggio_query = db.session.query(
                Appointment.client_id,
                func.max(Appointment.start_time).label('ultimo_passaggio')
            ).filter(
                Appointment.client_id.in_(client_ids),
                Appointment.stato.in_([AppointmentStatus.PAGATO]),
                Appointment.is_cancelled_by_client == False
            ).group_by(Appointment.client_id).all()

            ultimo_passaggio_dict = {row.client_id: row.ultimo_passaggio for row in ultimo_passaggio_query}

            # Assegna valori ai clienti
            for client in recent_clients:
                client.num_passaggi = num_passaggi_dict.get(client.id, 0)
                client.ultimo_passaggio = ultimo_passaggio_dict.get(client.id, None)

        clients_data = [
            {
                'id': client.id,
                'cliente_nome': client.cliente_nome,
                'cliente_cognome': client.cliente_cognome,
                'cliente_cellulare': client.cliente_cellulare,
                'cliente_email': client.cliente_email,
                'cliente_data_nascita': client.cliente_data_nascita.strftime('%d/%m/%Y') if client.cliente_data_nascita else '-',
                'cliente_sesso': client.cliente_sesso or '-',
                'created_at': client.created_at.strftime('%d/%m/%Y') if client.created_at else '-',
                'num_passaggi': client.num_passaggi,
                'ultimo_passaggio': client.ultimo_passaggio.strftime('%d/%m/%Y') if client.ultimo_passaggio else '-',
            }
            for client in recent_clients
        ]
        return jsonify(clients_data)
    except Exception as e:
        current_app.logger.error(f"Errore in recent_clients: {e}")
        return jsonify({'error': 'Errore interno del server'}), 500
# ===================== SUB-CATEGORIES =====================
@settings_bp.route('/settings/subcategories', methods=['POST'])
def subcategories():
    """Aggiunge una nuova sottocategoria."""
    try:
        nome = request.form.get('nome')  # Nome della sottocategoria
        categoria = request.form.get('categoria')  # Categoria (es. "Solarium" o "Estetica")

        # Controllo sui campi mancanti
        if not nome or not categoria:
            flash("Tutti i campi sono obbligatori.", "error")
            return redirect(url_for('settings.services'))

        # Crea una nuova sottocategoria
        new_subcategory = Subcategory(
            nome=nome,
            categoria=categoria,  # Deve corrispondere a "Solarium" o "Estetica"
            is_deleted=False
        )
        db.session.add(new_subcategory)
        db.session.commit()

    except Exception as e:
        app.logger.error("Errore durante l'aggiunta della sottocategoria: %s", str(e))
        flash("Errore durante l'aggiunta della sottocategoria.", "error")
    
    return redirect(url_for('settings.services'))
    
@settings_bp.route('/settings/subcategories/<int:subcategory_id>/delete', methods=['POST'])
def delete_subcategory(subcategory_id):
    """Elimina una sottocategoria."""
    try:
        subcategory = db.session.get(Subcategory, subcategory_id)
        if not subcategory:
            abort(404)
        subcategory.is_deleted = True  # Eliminazione logica
        db.session.commit()
    except Exception as e:
        app.logger.error("Errore durante l'eliminazione della sottocategoria %s: %s", subcategory_id, str(e))
        flash("Errore durante l'eliminazione della sottocategoria. Riprova.", "error")
    
    return redirect(url_for('settings.services'))

@settings_bp.route('/clients/<int:client_id>/update_note', methods=['POST'])
def update_client_note(client_id):
    data = request.get_json()
    note_text = data.get('note')
    if note_text is None:
        return jsonify({"error": "Parametro 'note' mancante"}), 400

    client = db.session.get(Client, client_id)
    if not client:
        abort(404)
    client.note = note_text
    db.session.commit()

    return jsonify({"message": "Nota cliente aggiornata", "client_id": client_id}), 200

@settings_bp.route('/clients/<int:client_id>/update_gender', methods=['POST'])
def update_client_gender(client_id):
    data = request.get_json()
    new_gender = data.get('gender')

    # Validazione del nuovo valore del sesso
    if new_gender not in ['M', 'F', '-']:
        return jsonify({"error": "Valore del sesso non valido"}), 400

    client = db.session.get(Client, client_id)
    if not client:
        abort(404)
    client.cliente_sesso = new_gender
    db.session.commit()

    return jsonify({"message": "Sesso aggiornato con successo", "client_id": client_id}), 200

#================= WHATSAPP ====================
def format_data_italiana(dt):
    mesi = [
        "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
        "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"
    ]
    giorno = dt.day
    mese_nome = mesi[dt.month - 1]
    anno = dt.year
    return f"{giorno} {mese_nome} {anno}"

@settings_bp.route('/api/services_by_ids', methods=['GET'])
def services_by_ids():
    """GET ?ids=1,2,3  -> ritorna { "services": { "1": {"id":1,"nome":"...", "tag":"..."} , ... } }"""
    ids_raw = (request.args.get('ids') or "").strip()
    if not ids_raw:
        return jsonify({"services": {}}), 200
    try:
        ids = [int(x) for x in ids_raw.split(',') if x.strip().isdigit()]
    except Exception:
        return jsonify({"services": {}}), 200

    services = {}
    try:
        if ids:
            apiv = Service.query.filter(Service.id.in_(ids)).all()
            for svc in apiv:
                services[str(svc.id)] = {
                    "id": svc.id,
                    "nome": (getattr(svc, 'servizio_nome', '') or '').strip(),
                    "tag": (getattr(svc, 'servizio_tag', '') or '').strip() if hasattr(svc, 'servizio_tag') else ""
                }
    except Exception as e:
        current_app.logger.exception("services_by_ids error: %s", e)
        return jsonify({"services": {}}), 200

    return jsonify({"services": services}), 200

@settings_bp.route('/settings/api/client_info/<int:client_id>', methods=['GET'])
def whatsapp_client_info(client_id):
    """
    Restituisce i dati cliente con nome/cognome NORMALIZZATI per WhatsApp.
    Non modifica template o frontend: la normalizzazione avviene lato backend.
    """
    c = db.session.get(Client, client_id)
    if not c or getattr(c, 'is_deleted', False):
        return jsonify({"error": "Cliente non trovato"}), 404

    # format_name è già definita nel file (gestisce apostrofi e title case)
    nome_norm = format_name(c.cliente_nome)
    cognome_norm = format_name(c.cliente_cognome)

        # PATCH: costruisci elenco servizi dai blocchi contigui passati (appointment_ids=1,2,3)
    servizi_text = ""
    appt_ids_raw = (request.args.get('appointment_ids') or "").strip()
    current_app.logger.info("appt_ids_raw: %s", appt_ids_raw)
    if appt_ids_raw:
        try:
            ids = [int(x) for x in appt_ids_raw.split(',') if str(x).strip().isdigit()]
            current_app.logger.info("parsed ids: %s", ids)
            if ids:
                appts = Appointment.query.filter(Appointment.id.in_(ids)).order_by(Appointment.start_time.asc()).all()
                current_app.logger.info("found appts: %s", len(appts))
                lines = []
                for appt in appts:
                    svc = db.session.get(Service, appt.service_id) if appt.service_id else None
                    label = ((svc.servizio_tag or "").strip() or (svc.servizio_nome or "").strip() or "Servizio") if svc else ""
                    current_app.logger.info("appt %s: service_id=%s, tag=%s, nome=%s, label=%s", appt.id, appt.service_id, svc.servizio_tag if svc else None, svc.servizio_nome if svc else None, label)
                    if label:
                        lines.append(f"- {label}")
                servizi_text = "\n".join(lines)
                current_app.logger.info("servizi_text: %s", servizi_text)
        except Exception as e:
            current_app.logger.error("Error building servizi_text: %s", e)
            servizi_text = ""

    return jsonify({
        "id": c.id,
        "cliente_nome": nome_norm,
        "cliente_cognome": cognome_norm,
        "display_name": f"{nome_norm} {cognome_norm}".strip(),
        "cliente_cellulare": c.cliente_cellulare or "",
        "cliente_email": c.cliente_email or "",
        "servizi": servizi_text 
    }), 200

@settings_bp.route('/api/settings/whatsapp', methods=['GET', 'POST'])
def api_whatsapp_setting():
    """GET: ritorna JSON con la preferenza whatsapp_modal_disable.
       POST: aggiorna la preferenza (JSON body: {"whatsapp_modal_disable": true|false})"""
    try:
        if request.method == 'GET':
            biz = BusinessInfo.query.first()
            disabled = bool(getattr(biz, 'whatsapp_modal_disable', False)) if biz else False
            return jsonify({'whatsapp_modal_disable': disabled})

        # POST -> aggiorna il flag
        data = request.get_json(silent=True) or request.form or {}
        val = data.get('whatsapp_modal_disable', None)

        # Normalizza il valore
        if isinstance(val, bool):
            disabled = val
        elif isinstance(val, str):
            disabled = val.lower() in ('1', 'true', 'on', 'yes')
        else:
            disabled = bool(val)

        biz = BusinessInfo.query.first()
        if not biz:
            biz = BusinessInfo()
            db.session.add(biz)

        biz.whatsapp_modal_disable = bool(disabled)
        db.session.commit()

        return jsonify({'whatsapp_modal_disable': bool(biz.whatsapp_modal_disable)}), 200

    except Exception as e:
        current_app.logger.exception("Errore lettura/aggiornamento impostazione whatsapp: %s", e)
        return jsonify({'whatsapp_modal_disable': False}), 500

@settings_bp.route('/whatsapp', methods=['GET', 'POST'])
def whatsapp():
    business_info = BusinessInfo.query.filter_by(is_deleted=False).first()
    saved = False
    saved_auto = False

    if request.method == 'POST':
        msg = request.form.get('whatsapp_message')
        msg_auto = request.form.get('whatsapp_message_auto')
        msg_morning = request.form.get('whatsapp_message_morning')
                # PATCH: Leggi i nuovi valori dal form
        reminder_enabled = 'whatsapp_morning_reminder_enabled' in request.form
        reminder_time_str = request.form.get('whatsapp_morning_reminder_time')

        if not business_info:
            business_info = BusinessInfo(
                business_name="Nome Azienda",
                opening_time=datetime.strptime("08:00", "%H:%M").time(),
                closing_time=datetime.strptime("20:00", "%H:%M").time(),
                active_opening_time=datetime.strptime("08:00", "%H:%M").time(),
                active_closing_time=datetime.strptime("20:00", "%H:%M").time(),
                whatsapp_message=msg,
                whatsapp_message_auto=msg_auto,
                whatsapp_message_morning=msg_morning
            )
            db.session.add(business_info)
            flash('Impostazioni iniziali salvate!', 'success')
        else:
            # PATCH: Usa flash() per ogni form invece delle variabili booleane
            if msg is not None:
                business_info.whatsapp_message = msg
                flash('Messaggio manuale salvato con successo!', 'success')
            
            if msg_auto is not None:
                business_info.whatsapp_message_auto = msg_auto
                flash('Messaggio automatico salvato con successo!', 'success')

            if msg_morning is not None:
                business_info.whatsapp_message_morning = msg_morning
                # PATCH: Salva le nuove impostazioni del reminder
                business_info.whatsapp_morning_reminder_enabled = reminder_enabled
                if reminder_time_str:
                    business_info.whatsapp_morning_reminder_time = datetime.strptime(reminder_time_str, '%H:%M').time()
                flash('Messaggio di reminder salvato con successo!', 'success')

        db.session.commit()
        return redirect(url_for('settings.whatsapp'))

    whatsapp_message = business_info.whatsapp_message if business_info and business_info.whatsapp_message else ""
    whatsapp_message_auto = business_info.whatsapp_message_auto if business_info and getattr(business_info, "whatsapp_message_auto", None) else ""
    whatsapp_message_morning = business_info.whatsapp_message_morning if business_info and getattr(business_info, "whatsapp_message_morning", None) else ""
    return render_template(
        'whatsapp.html',
        business_info=business_info,
        whatsapp_message=whatsapp_message,
        whatsapp_message_auto=whatsapp_message_auto,
        whatsapp_message_morning=whatsapp_message_morning,
        saved=saved,
        saved_auto=saved_auto
    )

#================= ACCOUNT ====================
@settings_bp.route('/landing', methods=['GET', 'POST'])
def settings_landing():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            return redirect(url_for('settings.manage_users'))
        else:
            flash('Credenziali errate', 'danger')
    return render_template('landing.html')

@settings_bp.route('/users', methods=['GET', 'POST'])
def manage_users():
    if 'user_id' not in session:
        return redirect(url_for('settings.settings_landing'))
    user_id = session.get('user_id')
    current_user = db.session.get(User, user_id) if user_id else None

    # Blocca l'accesso agli user normali
    if current_user.ruolo.value == 'user':
        return redirect(url_for('settings.settings_home'))

    if current_user.ruolo.value == 'owner':
        users = User.query.all()
    elif current_user.ruolo.value == 'admin':
        users = User.query.filter(User.ruolo != 'owner').all()

    # ORDINA GLI UTENTI: prima owner, poi admin, poi user
    ruolo_order = {'owner': 0, 'admin': 1, 'user': 2}
    users = sorted(users, key=lambda u: ruolo_order.get(u.ruolo.value, 99))

    return render_template(
        'users.html',
        users=users,
        current_user=current_user,
        ruolo=current_user.ruolo.value
    )

@settings_bp.route('/users/change_password/<int:user_id>', methods=['GET', 'POST'])
def change_password(user_id):
    if 'user_id' not in session:
        return redirect(url_for('settings.settings_landing'))
    current_user = db.session.get(User, user_id)
    user = db.session.get(User, user_id)

    # Permessi:
    # - owner può cambiare la sua password e quelle di admin/user (non altri owner)
    # - admin può cambiare la sua password e quella di ogni user (non owner, non altri admin)
    # - user non può cambiare alcuna password
    if current_user.ruolo.value == 'owner':
        if user.ruolo.value == 'owner' and current_user.id != user.id:
            flash('Non hai i permessi per modificare questa password.', 'danger')
            return redirect(url_for('settings.manage_users'))
    elif current_user.ruolo.value == 'admin':
        if user.ruolo.value not in ['user'] and current_user.id != user.id:
            flash('Non hai i permessi per modificare questa password.', 'danger')
            return redirect(url_for('settings.manage_users'))
    else:
        flash('Non hai i permessi per modificare questa password.', 'danger')
        return redirect(url_for('settings.manage_users'))

    if request.method == 'POST':
        old = request.form.get('old_password')
        new = request.form.get('new_password')
        # Se stai cambiando la tua password, verifica la vecchia
        if current_user.id == user.id:
            if not check_password_hash(user.password, old):
                flash('Vecchia password errata', 'danger')
                return redirect(url_for('settings.change_password', user_id=user.id))
        # Se cambi la password di un altro, non serve la vecchia
        user.password = generate_password_hash(new)
        db.session.commit()
        flash(f"Password aggiornata per {user.username}", "success")
        return redirect(url_for('settings.manage_users'))
    return render_template('change_password.html', current_user=current_user, user=user)

@settings_bp.route('/users/add', methods=['POST'])
def add_user():
    if 'user_id' not in session:
        return redirect(url_for('settings.settings_landing'))
    current_user = db.session.get(User, session['user_id'])
    username = request.form['username']
    password = request.form['password']
    ruolo = request.form['ruolo']

    # Controllo permessi
    if current_user.ruolo.value == 'owner':
        # Owner può creare qualsiasi ruolo
        pass
    elif current_user.ruolo.value == 'admin':
        # Admin NON può creare owner
        if ruolo == 'owner':
            flash('Non puoi creare un owner!', 'danger')
            return redirect(url_for('settings.manage_users'))
    else:
        # User non può creare nessuno
        flash('Permesso negato!', 'danger')
        return redirect(url_for('settings.manage_users'))

    hashed_password = generate_password_hash(password)
    user = User(username=username, password=hashed_password, ruolo=ruolo)
    db.session.add(user)
    db.session.commit()
    flash('Utente aggiunto!', 'success')
    return redirect(url_for('settings.manage_users'))

@settings_bp.route('/users/<int:user_id>/delete', methods=['POST'])
def delete_user(user_id):
    if 'user_id' not in session:
        return redirect(url_for('settings.settings_landing'))
    current_user = db.session.get(User, session['user_id'])
    user = db.session.get(User, user_id)
    if current_user.ruolo.value == 'owner':
        pass  # può eliminare chiunque tranne se stesso
    elif current_user.ruolo.value == 'admin':
        if user.ruolo == 'owner' or user.ruolo == 'admin':
            flash('Non puoi eliminare questo utente!', 'danger')
            return redirect(url_for('settings.manage_users'))
    else:
        flash('Permesso negato!', 'danger')
        return redirect(url_for('settings.manage_users'))
    db.session.delete(user)
    db.session.commit()
    flash('Utente eliminato!', 'success')
    return redirect(url_for('settings.manage_users'))

# ===================== ONLINE BOOKING SETTINGS =====================
@settings_bp.route('/settings/set_bookings', methods=['GET'])
def set_bookings():
    user_id = session.get('user_id')
    current_user = user = db.session.get(User, user_id) if user_id else None
    business_info = db.session.get(BusinessInfo, 1)
    # carica servizi con sottocategoria e operators in modo efficiente (evita N+1)
    servizi = (db.session.query(Service)
               .options(
                   joinedload(Service.servizio_sottocategoria).load_only(Subcategory.nome)
               )
               .filter(Service.is_deleted == False)
               .order_by(func.lower(Service.servizio_nome))
               .all())

    counts = dict(db.session.query(
        Service.id,
        func.count(Operator.id)
    ).outerjoin(Service.operators)
     .filter(Service.is_deleted == False)
     .filter(Operator.is_deleted == False, Operator.is_visible == True)
     .group_by(Service.id)
     .all())

    operatori = db.session.query(Operator).filter_by(is_deleted=False, is_visible=True).with_entities(
        Operator.id, Operator.user_nome, Operator.user_cognome
    ).all()

    servizi_tabella = []
    for s in servizi:
        servizi_tabella.append({
            "id": s.id,
            "nome": s.servizio_nome,
            "sottocategoria": s.servizio_sottocategoria.nome if s.servizio_sottocategoria else "",
            "is_visible_online": getattr(s, "is_visible_online", True),
            "operatori_count": int(counts.get(s.id, 0)),
        })
    # Serializza gli operatori in una lista di dizionari
    operatori_serializzati = [
        {"id": op.id, "nome": op.user_nome, "cognome": op.user_cognome, "full_name": f"{op.user_nome} {op.user_cognome}"}
        for op in operatori
    ]

    return render_template(
        'set_booking.html',
        current_user=current_user,
        servizi_tabella=servizi_tabella,
        operatori=operatori_serializzati,
        business_info=business_info
    )

@settings_bp.route('/update_service_operators', methods=['POST'])
def update_service_operators():
    data = request.get_json()
    service = db.session.get(Service, data['service_id'])
    if not service:
        return jsonify(success=False)
    ids = [int(x) for x in (data.get('operator_ids') or [])]
    new_ops = db.session.query(Operator).filter(
        Operator.id.in_(ids),
        Operator.is_visible == True,
        Operator.is_deleted == False
    ).all()
    service.operators = new_ops
    db.session.commit()
    return {'success': True}

@settings_bp.route('/update_service_visibility', methods=['POST'])
def update_service_visibility():
    data = request.get_json()
    service_id = data.get('service_id')
    value = data.get('value', False)
    service = db.session.get(Service, service_id)
    if not service:
        return {'success': False, 'error': 'Servizio non trovato'}, 404
    service.is_visible_online = value
    db.session.commit()
    return {'success': True}

@settings_bp.route('/get_service_operators/<int:service_id>')
def get_service_operators(service_id):
    service = db.session.get(Service, service_id)
    if not service:
        return jsonify(operator_ids=[])
    return jsonify(operator_ids=[op.id for op in service.operators if getattr(op, 'is_visible', False) and not getattr(op, 'is_deleted', False)])

@settings_bp.route('/update_booking_rules', methods=['POST'])
def update_booking_rules():
    data = request.get_json()
    business_info = BusinessInfo.query.first()
    if not business_info:
        return jsonify({"success": False, "error": "BusinessInfo non trovato"})

    # Prendi i dati dal payload strutturato come { durata: {...}, prezzo: {...} }
    durata = data.get('durata', {})
    prezzo = data.get('prezzo', {})

    # Durata
    business_info.booking_max_durata = int(durata.get('max', 0)) if durata.get('active') else 0
    # Prezzo
    business_info.booking_max_prezzo = float(prezzo.get('max', 0)) if prezzo.get('active') else 0

    # Tipo regola: block ha priorità su warning, altrimenti none
    if durata.get('block'):
        business_info.booking_rule_type = 'block'
        business_info.booking_rule_message = durata.get('block_msg', '')
    elif durata.get('warning'):
        business_info.booking_rule_type = 'warning'
        business_info.booking_rule_message = durata.get('warning_msg', '')
    elif prezzo.get('block'):
        business_info.booking_rule_type = 'block'
        business_info.booking_rule_message = prezzo.get('block_msg', '')
    elif prezzo.get('warning'):
        business_info.booking_rule_type = 'warning'
        business_info.booking_rule_message = prezzo.get('warning_msg', '')
    else:
        business_info.booking_rule_type = 'none'
        business_info.booking_rule_message = ''

    message_durata = (durata.get('warning_msg', '') or durata.get('block_msg', '')).strip()
    if not message_durata:
        message_durata = "none"
    business_info.booking_rule_message_durata = message_durata

    message_prezzo = (prezzo.get('warning_msg', '') or prezzo.get('block_msg', '')).strip()
    if not message_prezzo:
        message_prezzo = "none"
    business_info.booking_rule_message_prezzo = message_prezzo

    business_info.booking_rule_message_durata = message_durata
    business_info.booking_rule_message_prezzo = message_prezzo

    db.session.commit()
    return jsonify({"success": True})

@settings_bp.route('/api/export_clients', methods=['GET'])
def export_clients():
    try:
        # Ottieni business_name
        business_info = BusinessInfo.query.first()
        business_name = (business_info.business_name or "").strip() if business_info else ""
        # Sostituisci spazi e caratteri speciali per nome file sicuro
        safe_business_name = re.sub(r'[^\w\s-]', '', business_name).replace(' ', '_')

        # Query clienti: non eliminati, escludendo dummy/booking
        clients = Client.query.filter(
            Client.is_deleted == False,
            ~(
                or_(
                    and_(func.lower(Client.cliente_nome) == "dummy", func.lower(Client.cliente_cognome) == "dummy"),
                    and_(func.lower(Client.cliente_nome) == "cliente", func.lower(Client.cliente_cognome) == "booking"),
                    and_(func.lower(Client.cliente_nome) == "booking", func.lower(Client.cliente_cognome) == "online")
                )
            )
        ).order_by(Client.cliente_nome, Client.cliente_cognome).all()

        clients_data = [
            {
                "id": c.id,
                "nome": c.cliente_nome or "",
                "cognome": c.cliente_cognome or "",
                "cellulare": c.cliente_cellulare or ""
            }
            for c in clients
        ]

        return jsonify({
            "business_name": safe_business_name,
            "clients": clients_data
        }), 200

    except Exception as e:
        current_app.logger.error(f"Errore in export_clients: {e}")
        return jsonify({"error": "Errore interno del server"}), 500
    
@settings_bp.route('/settings/whatsapp_per_operatori', methods=['GET', 'POST'])
def whatsapp_per_operatori():
    # Funzione rimossa: endpoint lasciato solo per compatibilità del template
    return jsonify({"error": "Funzione promemoria operatori rimossa"}), 410

# ================= MARKETING ===================