# app/routes/settings.py
import re
import sys
import tempfile
from sqlalchemy import and_
from sqlalchemy.orm import joinedload
from werkzeug.security import generate_password_hash, check_password_hash
from gender_guesser.detector import Detector
from flask import Blueprint, current_app, render_template, request, jsonify, flash, redirect, url_for, session, abort
from flask import current_app as app
from datetime import datetime, timedelta
import os, ipaddress, requests
from sqlalchemy.sql import func, or_
from .. import db
from ..models import Appointment, AppointmentStatus, Operator, OperatorShift, Pacchetto, Receipt, Service, Client, BusinessInfo, ServiceCategory, Subcategory, WeekDay, User, RuoloUtente, PromoPacchetto, MarketingTemplate

# Blueprint per le rotte delle impostazioni
settings_bp = Blueprint('settings', __name__, template_folder='../templates')

# ===================== AUTO-UPDATE CONFIG =====================
GITHUB_REPO = "AlexBudet/SunBooking"
APP_EXE_NAME = "Tosca.exe"
BACKUP_FOLDER = "ToscaBackups"

PORT = 5050

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

    # 2) Validazione IP: solo IPv4 privati (no loopback, no pubblici)
    try:
        ip_addr = ipaddress.ip_address(printer_ip)
    except ValueError:
        current_app.logger.warning("ping_printer: printer_ip non è un indirizzo IP valido: %s", printer_ip)
        return jsonify({"error": "IP stampante non valido"}), 400

    # Verifica che sia IPv4 privato
    if ip_addr.version != 4:
        current_app.logger.warning("ping_printer: IPv6 non supportato: %s", printer_ip)
        return jsonify({"error": "Solo indirizzi IPv4 sono supportati"}), 400
    
    if ip_addr.is_loopback:
        current_app.logger.warning("ping_printer: loopback non ammesso: %s", printer_ip)
        return jsonify({"error": "Indirizzo loopback non ammesso"}), 400
    
    if not ip_addr.is_private:
        current_app.logger.warning("ping_printer: IP pubblico non ammesso: %s", printer_ip)
        return jsonify({"error": "Solo indirizzi IP di rete locale sono ammessi (192.168.x.x, 10.x.x.x, 172.16-31.x.x)"}), 400

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


# ===================== LOGO NEGOZIO =====================
@settings_bp.route('/settings/upload-logo', methods=['POST'])
def upload_logo():
    """
    Upload e ottimizzazione logo negozio.
    Accetta: PNG, JPEG, WebP, GIF, SVG
    Salva: PNG (se trasparenza) o WebP (altrimenti), max 200px altezza
    """
    from PIL import Image
    import io
    
    # Limite upload: 5MB
    MAX_UPLOAD_SIZE = 5 * 1024 * 1024
    # Altezza massima output
    MAX_HEIGHT = 200
    # Larghezza massima output
    MAX_WIDTH = 400
    # Qualità compressione WebP/JPEG
    QUALITY = 85
    
    file = request.files.get('logo')
    if not file or file.filename == '':
        flash("Nessun file selezionato.", "error")
        return redirect(url_for('settings.business_info'))
    
    # Verifica dimensione
    file.seek(0, 2)  # Vai alla fine
    file_size = file.tell()
    file.seek(0)  # Torna all'inizio
    
    if file_size > MAX_UPLOAD_SIZE:
        flash(f"File troppo grande. Massimo consentito: 5MB.", "error")
        return redirect(url_for('settings.business_info'))
    
    # Estensioni ammesse
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'}
    filename = file.filename.lower()
    ext = filename.rsplit('.', 1)[-1] if '.' in filename else ''
    
    if ext not in allowed_extensions:
        flash(f"Formato non supportato. Formati ammessi: PNG, JPEG, WebP, GIF, SVG.", "error")
        return redirect(url_for('settings.business_info'))
    
    try:
        # Caso speciale: SVG (salvato as-is)
        if ext == 'svg':
            svg_data = file.read()
            # Verifica che sia effettivamente XML/SVG
            if b'<svg' not in svg_data.lower():
                flash("Il file SVG non sembra valido.", "error")
                return redirect(url_for('settings.business_info'))
            
            business_info = BusinessInfo.query.filter_by(is_deleted=False).first()
            if not business_info:
                business_info = BusinessInfo(business_name="Negozio")
                db.session.add(business_info)
            
            business_info.logo_image = svg_data
            business_info.logo_mime_type = 'image/svg+xml'
            business_info.logo_filename = file.filename
            db.session.commit()
            
            flash("Logo SVG caricato con successo!", "success")
            return redirect(url_for('settings.business_info'))
        
        # Immagini raster: elaborazione con Pillow
        img = Image.open(file)
        original_format = img.format
        
        # Verifica se ha trasparenza (alpha channel)
        has_alpha = img.mode in ('RGBA', 'LA', 'PA') or \
                    (img.mode == 'P' and 'transparency' in img.info)
        
        # Converti in RGBA se necessario per preservare trasparenza
        if has_alpha and img.mode != 'RGBA':
            img = img.convert('RGBA')
        elif not has_alpha and img.mode not in ('RGB',):
            img = img.convert('RGB')
        
        # Ridimensiona mantenendo le proporzioni
        width, height = img.size
        if height > MAX_HEIGHT or width > MAX_WIDTH:
            # Calcola ratio per entrambi i limiti
            ratio_h = MAX_HEIGHT / height
            ratio_w = MAX_WIDTH / width
            ratio = min(ratio_h, ratio_w)
            
            new_width = int(width * ratio)
            new_height = int(height * ratio)
            img = img.resize((new_width, new_height), Image.LANCZOS)
        
        # Salva in memoria
        output = io.BytesIO()
        
        if has_alpha:
            # Con trasparenza: salva come PNG
            img.save(output, format='PNG', optimize=True)
            mime_type = 'image/png'
        else:
            # Senza trasparenza: salva come WebP (più efficiente)
            img.save(output, format='WEBP', quality=QUALITY, method=6)
            mime_type = 'image/webp'
        
        output.seek(0)
        image_data = output.read()
        
        # Verifica peso finale (warning se > 100KB)
        if len(image_data) > 100 * 1024:
            current_app.logger.warning(
                "Logo salvato con peso > 100KB: %d bytes", len(image_data)
            )
        
        # Salva in database
        business_info = BusinessInfo.query.filter_by(is_deleted=False).first()
        if not business_info:
            business_info = BusinessInfo(business_name="Negozio")
            db.session.add(business_info)
        
        business_info.logo_image = image_data
        business_info.logo_mime_type = mime_type
        business_info.logo_filename = file.filename
        db.session.commit()
        
        flash("Logo caricato e ottimizzato con successo!", "success")
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error("Errore upload logo: %s", str(e))
        flash(f"Errore durante l'elaborazione del logo: {str(e)}", "error")
    
    return redirect(url_for('settings.business_info'))


@settings_bp.route('/settings/logo')
def get_logo():
    """Restituisce il logo salvato come immagine."""
    business_info = BusinessInfo.query.filter_by(is_deleted=False).first()
    
    if not business_info or not business_info.logo_image:
        # Restituisce un'immagine placeholder o 404
        abort(404)
    
    from flask import Response
    return Response(
        business_info.logo_image,
        mimetype=business_info.logo_mime_type or 'image/png',
        headers={
            'Cache-Control': 'public, max-age=86400',  # Cache 1 giorno
            'Content-Disposition': f'inline; filename="{business_info.logo_filename or "logo"}"'
        }
    )


@settings_bp.route('/settings/delete-logo', methods=['POST'])
def delete_logo():
    """Elimina il logo corrente."""
    business_info = BusinessInfo.query.filter_by(is_deleted=False).first()
    
    if business_info:
        business_info.logo_image = None
        business_info.logo_mime_type = None
        business_info.logo_filename = None
        db.session.commit()
        flash("Logo eliminato con successo.", "success")
    
    return redirect(url_for('settings.business_info'))


@settings_bp.route('/settings/set-logo-visibility', methods=['POST'])
def set_logo_visibility():
    """Imposta la visibilità del logo nella pagina booking."""
    try:
        data = request.get_json(silent=True) or {}
        visible = data.get('visible', True)
        
        business_info = BusinessInfo.query.filter_by(is_deleted=False).first()
        if not business_info:
            return jsonify({"ok": False, "error": "BusinessInfo non trovato"}), 404
        
        business_info.logo_visible_in_booking_page = bool(visible)
        db.session.commit()
        
        return jsonify({"ok": True})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error("Errore set_logo_visibility: %s", str(e))
        return jsonify({"ok": False, "error": str(e)}), 500


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

        business_info.operator_whatsapp_notification_enabled = 'operator_whatsapp_notification_enabled' in request.form
        operator_time_str = request.form.get('operator_whatsapp_notification_time', '20:00')
        business_info.operator_whatsapp_notification_time = datetime.strptime(operator_time_str, '%H:%M').time()
        business_info.operator_whatsapp_message_template = request.form.get('operator_whatsapp_message_template', '')

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
        return redirect(url_for('settings.business_info'))

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

# ===================== SHIFT PRESETS =====================
@settings_bp.route('/api/shift-presets', methods=['GET'])
def get_shift_presets():
    """Restituisce i preset turno salvati in business_info."""
    import json
    biz = BusinessInfo.query.first()
    if not biz or not biz.shift_presets:
        return jsonify([])
    try:
        return jsonify(json.loads(biz.shift_presets))
    except Exception:
        return jsonify([])

@settings_bp.route('/api/shift-presets', methods=['POST'])
def save_shift_presets():
    """Salva l'intero array di preset turno in business_info."""
    import json
    biz = BusinessInfo.query.first()
    if not biz:
        return jsonify({"error": "BusinessInfo non trovata"}), 404
    data = request.json  # array di preset
    if not isinstance(data, list):
        return jsonify({"error": "Formato non valido, atteso array"}), 400
    biz.shift_presets = json.dumps(data, ensure_ascii=False)
    db.session.commit()
    return jsonify({"message": "Preset salvati", "count": len(data)}), 200

@settings_bp.route('/api/shift-presets/<int:index>', methods=['DELETE'])
def delete_shift_preset(index):
    """Elimina un singolo preset per indice."""
    import json
    biz = BusinessInfo.query.first()
    if not biz:
        return jsonify({"error": "BusinessInfo non trovata"}), 404
    try:
        presets = json.loads(biz.shift_presets or '[]')
    except Exception:
        presets = []
    if index < 0 or index >= len(presets):
        return jsonify({"error": "Indice non valido"}), 404
    removed = presets.pop(index)
    biz.shift_presets = json.dumps(presets, ensure_ascii=False)
    db.session.commit()
    return jsonify({"message": "Preset eliminato", "removed": removed}), 200

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

@settings_bp.route('/download-listino', methods=['GET'])
def download_listino():
    """Genera e scarica il listino prezzi in formato TXT o PDF."""
    from flask import make_response
    import html
    
    format_type = request.args.get('format', 'txt').lower()
    include_description = request.args.get('include_description', 'false').lower() == 'true'
    
    # Recupera tutti i servizi non eliminati, ordinati per categoria e sottocategoria
    services = (Service.query
        .filter(Service.is_deleted == False)
        .filter(~(
            or_(
                func.lower(func.trim(Service.servizio_nome)) == "dummy",
                func.lower(func.trim(Service.servizio_nome)) == "booking online"
            )
        ))
        .options(joinedload(Service.servizio_sottocategoria))
        .order_by(Service.servizio_categoria, Service.servizio_sottocategoria_id, Service.servizio_nome)
        .all())
    
    # Organizza i servizi per categoria e sottocategoria
    organized_services = {}
    for service in services:
        cat_name = service.servizio_categoria.value
        subcat_name = service.servizio_sottocategoria.nome if service.servizio_sottocategoria else "Altro"
        
        if cat_name not in organized_services:
            organized_services[cat_name] = {}
        if subcat_name not in organized_services[cat_name]:
            organized_services[cat_name][subcat_name] = []
        
        organized_services[cat_name][subcat_name].append(service)
    
    if format_type == 'txt':
        # Recupera il nome del negozio
        business_info = BusinessInfo.query.filter_by(is_deleted=False).first()
        business_name = business_info.business_name if business_info and business_info.business_name else "LISTINO PREZZI"
        
        # Genera listino in formato TXT semplice
        output = []
        output.append(f"LISTINO PREZZI {business_name}")
        output.append("")
        
        for categoria in sorted(organized_services.keys()):
            output.append("")
            output.append(f"CATEGORIA: {categoria.upper()}")
            output.append("")
            
            for sottocategoria in sorted(organized_services[categoria].keys()):
                output.append(f"SOTTOCATEGORIA: {sottocategoria.upper()}")
                
                for service in organized_services[categoria][sottocategoria]:
                    prezzo_str = f"{int(service.servizio_prezzo)}€" if service.servizio_prezzo == int(service.servizio_prezzo) else f"{service.servizio_prezzo:.2f}€"
                    
                    line = f"{service.servizio_nome} {prezzo_str}"
                    
                    if include_description and service.servizio_descrizione:
                        # Rimuove i tag HTML dalla descrizione per il TXT
                        import re
                        desc_clean = re.sub(r'<[^>]+>', '', service.servizio_descrizione)
                        desc_clean = html.unescape(desc_clean).strip()
                        if desc_clean:
                            line += f" {desc_clean}"
                    
                    output.append(line)
                
                output.append("")
        
        content = "\n".join(output)
        response = make_response(content)
        response.headers['Content-Type'] = 'text/plain; charset=utf-8'
        response.headers['Content-Disposition'] = 'attachment; filename=listino_prezzi.txt'
        return response
    
    elif format_type == 'pdf':
        # Restituisce JSON per generazione PDF lato client (come report agenda)
        business_info = BusinessInfo.query.filter_by(is_deleted=False).first()
        business_name = business_info.business_name if business_info and business_info.business_name else "Centro"
        
        data = {
            'business_name': business_name,
            'categories': []
        }
        
        for categoria in sorted(organized_services.keys()):
            cat_data = {
                'name': categoria.upper(),
                'subcategories': []
            }
            
            for sottocategoria in sorted(organized_services[categoria].keys()):
                subcat_data = {
                    'name': sottocategoria.upper(),
                    'services': []
                }
                
                for service in organized_services[categoria][sottocategoria]:
                    prezzo = service.servizio_prezzo
                    prezzo_str = f"€ {int(prezzo)}" if prezzo == int(prezzo) else f"€ {prezzo:.2f}"
                    durata_str = f"({service.servizio_durata} min)" if service.servizio_durata > 0 else ""
                    
                    svc_data = {
                        'nome': service.servizio_nome,
                        'prezzo': prezzo_str,
                        'durata': durata_str
                    }
                    
                    if include_description and service.servizio_descrizione:
                        import re
                        desc_clean = re.sub(r'<[^>]+>', '', service.servizio_descrizione)
                        desc_clean = html.unescape(desc_clean).strip()
                        svc_data['descrizione'] = desc_clean
                    
                    subcat_data['services'].append(svc_data)
                
                cat_data['subcategories'].append(subcat_data)
            
            data['categories'].append(cat_data)
        
        return jsonify(data)
    
    else:
        return jsonify({"error": "Formato non valido. Usa 'txt' o 'pdf'."}), 400
    
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
                flash('Messaggio di reminder salvato con successo!', 'success')

            # Aggiorna enabled/time SOLO se reminder_time è stato inviato
            if reminder_time_str is not None and reminder_time_str != '':
                business_info.whatsapp_morning_reminder_enabled = reminder_enabled
                business_info.whatsapp_morning_reminder_time = datetime.strptime(reminder_time_str, '%H:%M').time()

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

@settings_bp.route('/api/whatsapp/status', methods=['GET'])
def api_whatsapp_status():
    """
    Controlla lo stato della connessione WhatsApp per il tenant corrente.
    Usa l'account_id salvato in DB, con fallback su .env per retrocompatibilità.
    """
    unipile_dsn = os.getenv("UNIPILE_DSN")
    unipile_token = os.getenv("UNIPILE_ACCESS_TOKEN")
    
    # Leggi account_id SOLO da DB (no fallback su .env per evitare conflitti multi-tenant)
    business_info = BusinessInfo.query.filter_by(is_deleted=False).first()
    unipile_account_id = None
    if business_info and business_info.unipile_account_id:
        unipile_account_id = business_info.unipile_account_id
    
    current_app.logger.info("[WHATSAPP-STATUS] DSN=%s, AccountID=%s (from DB: %s)", 
                            unipile_dsn, unipile_account_id, 
                            bool(business_info and business_info.unipile_account_id))
    
    if not unipile_dsn or not unipile_token:
        return jsonify({
            'status': 'not_configured', 
            'connected': False,
            'error': 'Configurazione Unipile mancante'
        }), 200

    unipile_base_url = f"https://{unipile_dsn}"
    headers = {
        "X-API-KEY": unipile_token,
        "accept": "application/json"
    }
    
    try:
        # Se abbiamo un account_id, proviamo con quello
        if unipile_account_id:
            status_url = f"{unipile_base_url}/api/v1/accounts/{unipile_account_id}"
            r = requests.get(status_url, headers=headers, timeout=15)
            current_app.logger.info("[WHATSAPP-STATUS] GET %s -> %s", status_url, r.status_code)
            
            if r.status_code == 200:
                data = r.json()
                result = _parse_account_status(data, unipile_account_id)
                # Ritorna SEMPRE il risultato se l'account esiste (connesso o meno)
                return jsonify(result)
                    
            elif r.status_code == 404:
                # Account non esiste più, rimuovilo dal DB
                if business_info and business_info.unipile_account_id:
                    current_app.logger.info("[WHATSAPP-STATUS] Account %s non esiste più, rimuovo da DB", unipile_account_id)
                    business_info.unipile_account_id = None
                    db.session.commit()
        
        
        # Se siamo in polling (durante scansione QR), cerca account creati di recente
        is_polling = request.args.get('polling', '').lower() == 'true'
        if is_polling:
            try:
                list_url = f"{unipile_base_url}/api/v1/accounts"
                list_resp = requests.get(list_url, headers=headers, timeout=15)
                current_app.logger.info("[WHATSAPP-STATUS] Polling: ricerca nuovi account, status=%s", list_resp.status_code)
                
                if list_resp.status_code == 200:
                    accounts_data = list_resp.json()
                    items = accounts_data.get('items', [])
                    
                    from datetime import timezone
                    now = datetime.now(timezone.utc)
                    
                    for acc in items:
                        acc_type = acc.get('type', '').upper()
                        if acc_type != 'WHATSAPP':
                            continue
                        
                        created_at_str = acc.get('created_at', '')
                        if created_at_str:
                            try:
                                created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                                age_seconds = (now - created_at).total_seconds()
                                
                                if age_seconds < 300:
                                    acc_id = acc.get('id')
                                    sources = acc.get('sources', [])
                                    status = sources[0].get('status', '').upper() if sources else ''
                                    
                                    current_app.logger.info("[WHATSAPP-STATUS] Trovato account recente %s, status=%s, age=%ds", acc_id, status, int(age_seconds))
                                    
                                    if status in ('OK', 'CONNECTED', 'ACTIVE', 'READY'):
                                        if business_info:
                                            business_info.unipile_account_id = acc_id
                                            db.session.commit()
                                            current_app.logger.info("[WHATSAPP-STATUS] Salvato nuovo account %s nel DB", acc_id)
                                        
                                        result = _parse_account_status(acc, acc_id)
                                        return jsonify(result)
                            except Exception as parse_err:
                                current_app.logger.warning("[WHATSAPP-STATUS] Errore parsing created_at: %s", parse_err)
            except Exception as list_err:
                current_app.logger.warning("[WHATSAPP-STATUS] Errore ricerca nuovo account: %s", list_err)
        
        return jsonify({
            'status': 'not_connected',
            'connected': False,
            'message': 'Nessun account WhatsApp configurato per questo tenant'
        }), 200
        
    except Exception as e:
        current_app.logger.exception("[WHATSAPP-STATUS] Exception")
        return jsonify({
            'status': 'error',
            'connected': False,
            'error': str(e)
        }), 200

@settings_bp.route('/api/whatsapp/db_status', methods=['GET'])
def api_whatsapp_db_status():
    """
    Ritorna lo stato dell'account_id salvato nel DB (senza chiamare Unipile).
    Usato per sincronizzazione tra istanze webapp/on-premise.
    """
    business_info = BusinessInfo.query.filter_by(is_deleted=False).first()
    account_id = business_info.unipile_account_id if business_info else None
    
    return jsonify({
        'has_account': bool(account_id),
        'account_id': account_id
    })

def _parse_account_status(data, account_id):
    """Helper per parsare lo stato di un account Unipile."""
    sources = data.get('sources', [])
    connection_status = 'unknown'
    if sources and len(sources) > 0:
        connection_status = sources[0].get('status', 'unknown')
    
    phone = data.get('name') or data.get('identifier') or ''
    
    if phone and phone.isdigit() and len(phone) > 10:
        phone_display = f"+{phone[:2]} {phone[2:5]} {phone[5:8]} {phone[8:]}"
    else:
        phone_display = phone
    
    is_connected = connection_status.upper() in ('OK', 'CONNECTED', 'ACTIVE', 'READY')
    
    return {
        'status': connection_status,
        'connected': is_connected,
        'phone': phone_display,
        'phone_raw': phone,
        'account_id': account_id,
        'provider': data.get('type', 'WHATSAPP'),
        'created_at': data.get('created_at')
    }


@settings_bp.route('/api/whatsapp/connect', methods=['POST'])
def api_whatsapp_connect():
    """
    Genera il link hosted Unipile per connettere/riconnettere WhatsApp.
    """
    unipile_dsn = os.getenv("UNIPILE_DSN")
    unipile_token = os.getenv("UNIPILE_ACCESS_TOKEN")
    
    # Leggi account_id da DB
    business_info = BusinessInfo.query.filter_by(is_deleted=False).first()
    unipile_account_id = None
    if business_info and business_info.unipile_account_id:
        unipile_account_id = business_info.unipile_account_id
    
    current_app.logger.info("[WHATSAPP-CONNECT] DSN=%s, AccountID=%s", unipile_dsn, unipile_account_id)
    
    if not unipile_dsn or not unipile_token:
        return jsonify({'error': 'Configurazione Unipile mancante'}), 500

    unipile_base_url = f"https://{unipile_dsn}"
    headers = {
        "X-API-KEY": unipile_token,
        "accept": "application/json",
        "content-type": "application/json"
    }

    try:
        account_exists = False
        account_connected = False
        
        # Se abbiamo un account_id, verifica se esiste ancora
        if unipile_account_id:
            status_url = f"{unipile_base_url}/api/v1/accounts/{unipile_account_id}"
            status_resp = requests.get(status_url, headers=headers, timeout=15)
            current_app.logger.info("[WHATSAPP-CONNECT] Check account %s: status=%s", unipile_account_id, status_resp.status_code)
            
            if status_resp.status_code == 200:
                account_exists = True
                data = status_resp.json()
                sources = data.get('sources', [])
                if sources and sources[0].get('status', '').upper() == 'OK':
                    account_connected = True
                    phone = data.get('name', '')
                    if phone and phone.isdigit() and len(phone) > 10:
                        phone = f"+{phone[:2]} {phone[2:5]} {phone[5:8]} {phone[8:]}"
                    return jsonify({
                        'already_connected': True,
                        'status': 'OK',
                        'phone': phone,
                        'account_id': unipile_account_id
                    })
            elif status_resp.status_code == 404:
                account_exists = False
                # Rimuovi ID non valido dal DB
                if business_info:
                    business_info.unipile_account_id = None
                    db.session.commit()
                current_app.logger.info("[WHATSAPP-CONNECT] Account %s non esiste più, rimosso da DB", unipile_account_id)
        
        # Genera hosted link
        connect_url = f"{unipile_base_url}/api/v1/hosted/accounts/link"
        
        from datetime import timezone
        expires_dt = datetime.now(timezone.utc) + timedelta(hours=1)
        expires_on = expires_dt.strftime('%Y-%m-%dT%H:%M:%S.000Z')
        
        if account_exists and not account_connected:
            payload = {
                "type": "reconnect",
                "reconnect_account": unipile_account_id,
                "api_url": unipile_base_url,
                "expiresOn": expires_on
            }
            current_app.logger.info("[WHATSAPP-CONNECT] Usando RECONNECT")
        else:
            payload = {
                "type": "create",
                "providers": ["WHATSAPP"],
                "api_url": unipile_base_url,
                "expiresOn": expires_on
            }
            current_app.logger.info("[WHATSAPP-CONNECT] Usando CREATE")
        
        current_app.logger.info("[WHATSAPP-CONNECT] POST %s payload=%s", connect_url, payload)
        resp = requests.post(connect_url, headers=headers, json=payload, timeout=30)
        current_app.logger.info("[WHATSAPP-CONNECT] Response: %s %s", resp.status_code, resp.text[:500] if resp.text else "")
        
        if resp.status_code in (200, 201):
            data = resp.json()
            current_app.logger.info("[WHATSAPP-CONNECT] Response keys: %s", list(data.keys()))
            
            # Cerca l'URL in vari campi possibili
            hosted_url = None
            for key in ['url', 'hosted_link_url', 'link', 'hosted_auth_link_url']:
                if data.get(key):
                    hosted_url = data[key]
                    break
            
            if not hosted_url and isinstance(data.get('object'), dict):
                hosted_url = data['object'].get('url')
            
            # Cerca qualsiasi campo che contenga un URL Unipile
            if not hosted_url:
                for key, value in data.items():
                    if isinstance(value, str) and 'unipile.com' in value:
                        hosted_url = value
                        break
            
            if hosted_url:
                return jsonify({
                    'hosted_url': hosted_url,
                    'expires': data.get('expiresOn'),
                    'is_new_account': not account_exists
                })
            else:
                return jsonify({
                    'error': 'URL non trovato nella risposta',
                    'raw': data
                }), 500
        else:
            return jsonify({
                'error': f'Errore Unipile: {resp.status_code}', 
                'detail': resp.text
            }), 500
            
    except Exception as e:
        current_app.logger.exception("[WHATSAPP-CONNECT] Exception")
        return jsonify({'error': 'Eccezione interna', 'detail': str(e)}), 500


@settings_bp.route('/api/whatsapp/disconnect', methods=['POST'])
def api_whatsapp_disconnect():
    """
    Disconnette l'account WhatsApp corrente da Unipile.
    """
    unipile_dsn = os.getenv("UNIPILE_DSN")
    unipile_token = os.getenv("UNIPILE_ACCESS_TOKEN")
    
    business_info = BusinessInfo.query.filter_by(is_deleted=False).first()
    unipile_account_id = business_info.unipile_account_id if business_info else None
    
    current_app.logger.info("[WHATSAPP-DISCONNECT] DSN=%s, AccountID=%s", unipile_dsn, unipile_account_id)
    
    if not unipile_dsn or not unipile_token:
        return jsonify({"error": "Configurazione Unipile mancante"}), 400

    if not unipile_account_id:
        return jsonify({"error": "Nessun account WhatsApp configurato"}), 400

    unipile_base_url = f"https://{unipile_dsn}"
    headers = {
        "X-API-KEY": unipile_token,
        "accept": "application/json"
    }

    try:
        url = f"{unipile_base_url}/api/v1/accounts/{unipile_account_id}"
        current_app.logger.info("[WHATSAPP-DISCONNECT] DELETE %s", url)
        
        resp = requests.delete(url, headers=headers, timeout=30)
        current_app.logger.info("[WHATSAPP-DISCONNECT] Response: %s - %s", resp.status_code, resp.text[:500] if resp.text else "")
        
        if resp.status_code in (200, 204, 404):
            # Rimuovi account_id dal DB
            if business_info:
                business_info.unipile_account_id = None
                db.session.commit()
                current_app.logger.info("[WHATSAPP-DISCONNECT] Rimosso account_id dal DB")
            
            return jsonify({"success": True, "message": "Account WhatsApp disconnesso"})
        else:
            return jsonify({
                "error": "Errore durante la disconnessione",
                "status_code": resp.status_code,
                "detail": resp.text[:200] if resp.text else None
            }), resp.status_code
            
    except Exception as e:
        current_app.logger.exception("[WHATSAPP-DISCONNECT] Errore: %s", e)
        return jsonify({"error": str(e)}), 500
    
@settings_bp.route('/api/whatsapp/save_account', methods=['POST'])
def api_whatsapp_save_account():
    """
    Salva l'account_id Unipile nel database dopo una connessione riuscita.
    Chiamato dal frontend dopo che il polling rileva status=OK.
    """
    data = request.get_json(silent=True) or {}
    account_id = data.get('account_id')
    
    if not account_id:
        return jsonify({"error": "account_id mancante"}), 400
    
    try:
        business_info = BusinessInfo.query.filter_by(is_deleted=False).first()
        if not business_info:
            business_info = BusinessInfo(
                business_name="",
                opening_time=datetime.strptime("08:00", "%H:%M").time(),
                closing_time=datetime.strptime("20:00", "%H:%M").time()
            )
            db.session.add(business_info)
        
        business_info.unipile_account_id = account_id
        db.session.commit()
        
        current_app.logger.info("[WHATSAPP-SAVE] Salvato account_id=%s nel DB", account_id)
        return jsonify({"success": True, "account_id": account_id})
        
    except Exception as e:
        current_app.logger.exception("[WHATSAPP-SAVE] Errore: %s", e)
        return jsonify({"error": str(e)}), 500

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
    
@settings_bp.route('/whatsapp_per_operatori', methods=['GET', 'POST'])
def whatsapp_per_operatori():
    business_info = BusinessInfo.query.filter_by(is_deleted=False).first()
    if request.method == 'POST':
        op_enabled = 'operator_whatsapp_notification_enabled' in request.form
        op_time_str = request.form.get('operator_whatsapp_notification_time')
        op_tpl = request.form.get('operator_whatsapp_message_template')

        if not business_info:
            business_info = BusinessInfo(
                business_name="Nome Azienda",
                opening_time=datetime.strptime("08:00", "%H:%M").time(),
                closing_time=datetime.strptime("20:00", "%H:%M").time(),
            )
            db.session.add(business_info)

        # Distingui submit form (solo template) da submit JS (enabled/time)
        if 'operator_whatsapp_message_template' in request.form:
            # Submit del form: aggiorna solo il template
            if op_tpl is not None:
                business_info.operator_whatsapp_message_template = op_tpl
        else:
            # Submit JS: aggiorna enabled e time
            business_info.operator_whatsapp_notification_enabled = bool(op_enabled)
            if op_time_str:
                try:
                    business_info.operator_whatsapp_notification_time = datetime.strptime(op_time_str, '%H:%M').time()
                except Exception:
                    pass
            # Template lasciato invariato

        db.session.commit()
        return redirect(url_for('settings.whatsapp'))

    # GET render invariato
    whatsapp_message = business_info.whatsapp_message if business_info and business_info.whatsapp_message else ""
    whatsapp_message_auto = business_info.whatsapp_message_auto if business_info and getattr(business_info, "whatsapp_message_auto", None) else ""
    whatsapp_message_morning = business_info.whatsapp_message_morning if business_info and getattr(business_info, "whatsapp_message_morning", None) else ""
    return render_template('whatsapp.html',
        business_info=business_info,
        whatsapp_message=whatsapp_message,
        whatsapp_message_auto=whatsapp_message_auto,
        whatsapp_message_morning=whatsapp_message_morning
    )

def _normalize_for_wbiz(numero: str):
    raw = (str(numero or '')).strip().replace(' ', '')
    if not raw:
        return None, None  # numero, country
    if raw.startswith('+'):
        numero_norm = raw
    elif raw and raw[0].isdigit():
        if raw.startswith('3'):
            numero_norm = ('+' + raw) if len(raw) > 10 else ('+39' + raw)
        else:
            numero_norm = '+' + raw
    else:
        numero_norm = raw

    numero_pulito = re.sub(r'\D', '', numero_norm or '')
    if numero_pulito.startswith('00'):
        numero_pulito = numero_pulito.lstrip('0')
    if not numero_pulito:
        return None, None
    country_code = '39' if numero_pulito.startswith('39') else numero_pulito[:2]
    return numero_pulito, country_code

def _fmt_data_italiana(dt):
    giorni = ["Lunedì","Martedì","Mercoledì","Giovedì","Venerdì","Sabato","Domenica"]
    mesi = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
    return f"{giorni[dt.weekday()]} {dt.day} {mesi[dt.month - 1]}"

def _build_operator_targets_for_tomorrow(require_phone: bool = True):
    tomorrow = datetime.now().date() + timedelta(days=1)
    
    # Query operators who are active, visible, not machines, and opted for WhatsApp notifications
    operators = db.session.query(Operator).filter(
        Operator.is_deleted == False,
        Operator.is_visible == True,
        Operator.user_tipo != 'macchinario',
        Operator.notify_turni_via_whatsapp == True
    ).all()
    
    targets = []
    for op in operators:
        phone, country = _normalize_for_wbiz(op.user_cellulare)
        if require_phone and (not phone or len(phone) < 4):
            continue
        
        # Fetch the shift for tomorrow
        shift = db.session.query(OperatorShift).filter(
            OperatorShift.operator_id == op.id,
            OperatorShift.shift_date == tomorrow
        ).first()
        
        if not shift:
            continue  # Skip operators with no shift for tomorrow

        if shift.shift_start_time == shift.shift_end_time:
            continue  # Skip day off
        
        # Fetch appointments for tomorrow, excluding cancelled ones
        appointments = db.session.query(Appointment).filter(
            Appointment.operator_id == op.id,
            Appointment.is_cancelled_by_client == False,
            func.date(Appointment.start_time) == tomorrow
        ).order_by(Appointment.start_time.asc()).all()
        
        schedule_items = []
        first_app_label = None
        first_app_time = None
        pausa_label = None
        pausa_time = None
        
        for appt in appointments:
            # Filter out appointments outside the shift time
            if shift:
                shift_start = shift.shift_start_time
                shift_end = shift.shift_end_time
                appt_time = appt.start_time.time()
                if appt_time < shift_start or appt_time >= shift_end:
                    continue
            
            # Determine if it's an OFF slot
            client = appt.client
            service = db.session.get(Service, appt.service_id) if appt.service_id else None
            
            client_is_dummy = (
                client is None or
                (client.cliente_nome or '').strip().lower() == 'dummy' and
                (client.cliente_cognome or '').strip().lower() == 'dummy'
            )
            
            service_is_dummy = (
                service is None or
                (getattr(service, 'servizio_nome', '') or '').strip().lower() == 'dummy' or
                (getattr(service, 'servizio_tag', '') or '').strip().lower() == 'dummy'
            )
            
            is_off = client_is_dummy or service_is_dummy
            
            if is_off:
                titolo = (appt.note or '').strip()
                label = titolo if titolo else 'OFF'
                duration = appt.duration if isinstance(appt.duration, int) else None
                if label.upper() == 'PAUSA':
                    pausa_label = label
                    pausa_time = appt.start_time.strftime('%H:%M')
            else:
                # Prefer name over tag for service label
                if service:
                    label = (getattr(service, 'servizio_nome', '') or '').strip() or (getattr(service, 'servizio_tag', '') or '').strip()
                else:
                    label = ''
                duration = None
            
            # Set first appointment if not set and not off
            if first_app_label is None and not is_off:
                first_app_label = label or ''
                first_app_time = appt.start_time.strftime('%H:%M')
            
            schedule_items.append({
                "ora": appt.start_time.strftime('%H:%M'),
                "label": label,
                "is_off": is_off,
                "durata": duration
            })
        
        targets.append({
            "operator_id": op.id,
            "operatore_nome": (op.user_nome or "").strip(),  # First name only
            "phone": phone,
            "country_code": country,
            "date": str(tomorrow),
            "shift_start": shift.shift_start_time.strftime('%H:%M') if shift else None,
            "shift_end": shift.shift_end_time.strftime('%H:%M') if shift else None,
            "schedule": schedule_items,
            "primo_app_label": first_app_label,
            "primo_app_time": first_app_time,
            "pausa_label": pausa_label,
            "pausa_time": pausa_time,
        })
    
    return targets

def _render_operator_msg(tpl: str, target: dict):
    tpl = (tpl or "")
    
    lines = []
    for x in target.get('schedule', []):
        if not x:
            continue
        if x.get('is_off'):
            dur = x.get('durata')
            dur_txt = f" ({dur} minuti)" if (isinstance(dur, int) and dur > 0) else ""
            lines.append(f"- {x.get('ora')} {x.get('label')}{dur_txt}")
        else:
            lines.append(f"- {x.get('ora')} {x.get('label')}")
    
    data_it = _fmt_data_italiana(datetime.strptime(target["date"], "%Y-%m-%d"))

    pausa_section = ""
    if target.get("pausa_time"):
        pausa_section = f"Pausa alle {target.get('pausa_time')}"

    # Sezione primo appuntamento condizionale
    primo_app_section = ""
    if target.get("primo_app_time") and target.get("primo_app_label"):
        primo_app_section = f"Il primo impegno della giornata sarà alle {target.get('primo_app_time')} e sarà {target.get('primo_app_label')}"
    else:
        primo_app_section = "Per il momento domani non avrai appuntamenti"
    
    return (tpl
        .replace("{{operatore}}", target.get("operatore_nome", ""))
        .replace("{{data}}", data_it)
        .replace("{{ora_inizio}}", target.get("shift_start") or "OFF")
        .replace("{{ora_fine}}", target.get("shift_end") or "OFF")
        .replace("{{sezione_primo_app}}", primo_app_section)
        .replace("{{ora_primo_app}}", target.get("primo_app_time") or "N/D")
        .replace("{{primo_app}}", target.get("primo_app_label") or "N/D")
        .replace("{{ora_pausa}}", target.get("pausa_time") or "")
        .replace("{{pausa}}", target.get("pausa_label") or "")
        .replace("{{sezione_pausa}}", pausa_section)
    )

@settings_bp.route('/api/operator_notifications/preview', methods=['GET'], endpoint='preview_operator_notifications')
def preview_operator_notifications():
    bi = BusinessInfo.query.first()
    tpl_default = (
    "Ciao {{operatore}},\n\n"
    "Domani {{data}} il tuo turno sarà: {{ora_inizio}}-{{ora_fine}}\n\n"
    "{{sezione_pausa}}"
    "{{sezione_primo_app}}\n\n"
    "Buon lavoro!"
    )
    tpl = (getattr(bi, 'operator_whatsapp_message_template', '') or tpl_default)

    targets = _build_operator_targets_for_tomorrow(require_phone=False)

    full = str(request.args.get('full', '') or '').lower() in ('1', 'true', 'yes', 'on')
    preview = []
    for t in targets:
        msg = _render_operator_msg(tpl, t)
        item = {
            "operator_id": t["operator_id"],
            "operatore": t["operatore_nome"],
            "phone": t.get("phone") or "(nessun numero)",
            "date": t["date"],
            "msg_preview": msg[:240] + ("..." if len(msg) > 240 else "")
        }
        if full:
            item["msg_full"] = msg
        preview.append(item)

    return jsonify({
        "enabled": bool(getattr(bi, 'operator_whatsapp_notification_enabled', False)),
        "count": len(preview),
        "items": preview
    })

# ================= PACCHETTI ====================
@settings_bp.route('/pacchetti_settings', methods=['GET'])
def pacchetti_settings():
    """Pagina impostazioni pacchetti - promo e template WhatsApp."""
    business_info = BusinessInfo.query.first()
    template = getattr(business_info, 'whatsapp_template_pacchetti', None) if business_info else None
    template_prepagate = getattr(business_info, 'whatsapp_template_prepagate', None) if business_info else None
    disclaimer = getattr(business_info, 'whatsapp_template_pacchetti_disclaimer', None) if business_info else None
    giorni = getattr(business_info, 'pacchetti_giorni_abbandono', 90) if business_info else 90
    
    # Carica solo servizi attivi, visibili online e non dummy
    servizi = Service.query.filter(
        Service.is_deleted == False,
        Service.is_visible_online == True,
        Service.servizio_nome != 'dummy'
    ).order_by(Service.servizio_nome).all()
    
    return render_template('pacchetti_settings.html', 
                           whatsapp_template=template,
                           whatsapp_template_prepagate=template_prepagate,
                           disclaimer_template=disclaimer,
                           giorni_abbandono=giorni,
                           servizi=servizi)

@settings_bp.route('/api/pacchetti/whatsapp_template', methods=['GET'])
def api_get_whatsapp_template_pacchetti():
    """Restituisce il template WhatsApp per pacchetti."""
    business_info = BusinessInfo.query.first()
    template = getattr(business_info, 'whatsapp_template_pacchetti', None) if business_info else None
    return jsonify({'template': template or ''})

@settings_bp.route('/api/pacchetti/whatsapp_template', methods=['POST'])
def api_save_whatsapp_template_pacchetti():
    """Salva il template WhatsApp per pacchetti."""
    data = request.get_json(silent=True) or {}
    template = data.get('template', '').strip()
    
    business_info = BusinessInfo.query.first()
    if not business_info:
        business_info = BusinessInfo(
            business_name="Centro",
            opening_time=datetime.strptime("08:00", "%H:%M").time(),
            closing_time=datetime.strptime("20:00", "%H:%M").time(),
            active_opening_time=datetime.strptime("08:00", "%H:%M").time(),
            active_closing_time=datetime.strptime("20:00", "%H:%M").time()
        )
        db.session.add(business_info)
    
    business_info.whatsapp_template_pacchetti = template if template else None
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Template salvato con successo'})

@settings_bp.route('/api/pacchetti/whatsapp_template_prepagate', methods=['GET'])
def api_get_whatsapp_template_prepagate():
    """Restituisce il template WhatsApp per carte prepagate."""
    business_info = BusinessInfo.query.first()
    template = getattr(business_info, 'whatsapp_template_prepagate', None) if business_info else None
    return jsonify({'template': template or ''})

@settings_bp.route('/api/pacchetti/whatsapp_template_prepagate', methods=['POST'])
def api_save_whatsapp_template_prepagate():
    """Salva il template WhatsApp per carte prepagate."""
    data = request.get_json(silent=True) or {}
    template = data.get('template', '').strip()
    
    business_info = BusinessInfo.query.first()
    if not business_info:
        business_info = BusinessInfo(
            business_name="Centro",
            opening_time=datetime.strptime("08:00", "%H:%M").time(),
            closing_time=datetime.strptime("20:00", "%H:%M").time(),
            active_opening_time=datetime.strptime("08:00", "%H:%M").time(),
            active_closing_time=datetime.strptime("20:00", "%H:%M").time()
        )
        db.session.add(business_info)
    
    business_info.whatsapp_template_prepagate = template if template else None
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Template prepagate salvato con successo'})

@settings_bp.route('/api/pacchetti/giorni_abbandono', methods=['POST'])
def api_save_giorni_abbandono():
    """Salva il numero di giorni per considerare un pacchetto abbandonato."""
    data = request.get_json(silent=True) or {}
    giorni = data.get('giorni', 90)
    
    try:
        giorni = int(giorni)
        if giorni < 1 or giorni > 365:
            return jsonify({'success': False, 'error': 'Valore deve essere tra 1 e 365'}), 400
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Valore non valido'}), 400
    
    business_info = BusinessInfo.query.first()
    if not business_info:
        business_info = BusinessInfo(
            business_name="Centro",
            opening_time=datetime.strptime("08:00", "%H:%M").time(),
            closing_time=datetime.strptime("20:00", "%H:%M").time(),
            active_opening_time=datetime.strptime("08:00", "%H:%M").time(),
            active_closing_time=datetime.strptime("20:00", "%H:%M").time()
        )
        db.session.add(business_info)
    
    business_info.pacchetti_giorni_abbandono = giorni
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Giorni abbandono salvati'})

@settings_bp.route('/api/pacchetti/disclaimer_template', methods=['GET'])
def api_get_disclaimer_template():
    """Restituisce il template disclaimer per pacchetti."""
    business_info = BusinessInfo.query.first()
    template = getattr(business_info, 'whatsapp_template_pacchetti_disclaimer', None) if business_info else None
    return jsonify({'template': template or ''})

@settings_bp.route('/api/pacchetti/disclaimer_template', methods=['POST'])
def api_save_disclaimer_template():
    """Salva il template disclaimer per pacchetti."""
    data = request.get_json(silent=True) or {}
    template = data.get('template', '').strip()
    
    business_info = BusinessInfo.query.first()
    if not business_info:
        business_info = BusinessInfo(
            business_name="Centro",
            opening_time=datetime.strptime("08:00", "%H:%M").time(),
            closing_time=datetime.strptime("20:00", "%H:%M").time(),
            active_opening_time=datetime.strptime("08:00", "%H:%M").time(),
            active_closing_time=datetime.strptime("20:00", "%H:%M").time()
        )
        db.session.add(business_info)
    
    business_info.whatsapp_template_pacchetti_disclaimer = template if template else None
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Template disclaimer salvato con successo'})

# API per salvare disclaimer servizio
@settings_bp.route('/api/servizi/<int:servizio_id>/disclaimer', methods=['POST'])
def api_save_servizio_disclaimer(servizio_id):
    """Salva il disclaimer per un servizio specifico."""
    servizio = Service.query.get(servizio_id)
    if not servizio:
        return jsonify({'success': False, 'error': 'Servizio non trovato'}), 404
    
    data = request.get_json(silent=True) or {}
    disclaimer = data.get('disclaimer', '').strip()
    
    servizio.servizio_disclaimer = disclaimer if disclaimer else None
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Disclaimer salvato'})

@settings_bp.route('/api/pacchetti/<int:pacchetto_id>/disclaimer_data', methods=['GET'])
def api_get_disclaimer_data(pacchetto_id):
    """Restituisce i dati per generare il PDF disclaimer del pacchetto."""
    pacchetto = Pacchetto.query.get_or_404(pacchetto_id)
    business_info = BusinessInfo.query.first()
    
    # Raggruppa servizi per nome e conta quantità
    servizi_count = {}
    servizi_disclaimers = {}
    
    for seduta in pacchetto.sedute:
        service = seduta.service
        if service:
            nome = service.servizio_nome
            if nome not in servizi_count:
                servizi_count[nome] = 0
                # Salva il disclaimer se presente
                if service.servizio_disclaimer:
                    servizi_disclaimers[nome] = service.servizio_disclaimer
            servizi_count[nome] += 1
    
    # Prepara lista servizi
    servizi = [{'nome': nome, 'quantita': qty} for nome, qty in servizi_count.items()]
    
    # Prepara lista disclaimers (solo servizi che ce l'hanno)
    disclaimers = [{'servizio': nome, 'testo': testo} for nome, testo in servizi_disclaimers.items()]
    
    # Prepara elenco servizi formattato
    servizi_text = '\n'.join([f"• {s['quantita']} {s['nome']}" for s in servizi])
    
    # Prepara disclaimers formattati
    disclaimers_text = '\n\n'.join([f"{d['servizio']}:\n{d['testo']}" for d in disclaimers]) if disclaimers else ''
    
    # Recupera il template disclaimer (o usa default)
    template = getattr(business_info, 'whatsapp_template_pacchetti_disclaimer', None) if business_info else None
    
    return jsonify({
        'success': True,
        'template': template,
        'servizi': servizi,
        'servizi_text': servizi_text,
        'disclaimers': disclaimers,
        'disclaimers_text': disclaimers_text,
        'centro_nome': business_info.business_name if business_info else 'Centro Estetico',
        'centro_indirizzo': f"{business_info.address or ''}, {business_info.city or ''}".strip(', ') if business_info else ''
    })
# ================= PROMO PACCHETTI ====================
@settings_bp.route('/api/pacchetti/promo', methods=['GET'])
def api_get_promo_list():
    """Restituisce tutte le promo salvate."""
    promo_list = PromoPacchetto.query.order_by(PromoPacchetto.nome).all()
    return jsonify([p.to_dict() for p in promo_list])

@settings_bp.route('/api/pacchetti/promo', methods=['POST'])
def api_create_promo():
    """Crea una nuova promo."""
    data = request.get_json(silent=True) or {}
    
    nome = (data.get('nome') or '').strip()
    if not nome:
        return jsonify({'error': 'Nome promo obbligatorio'}), 400
    
    tipo = data.get('tipo', 'percentuale')
    
    promo = PromoPacchetto(
        nome=nome,
        tipo=tipo,
        soglia=data.get('soglia'),
        percentuale=data.get('percentuale') if tipo == 'percentuale' else None,
        sedute_omaggio=data.get('sedute_omaggio') if tipo == 'sedute_omaggio' else None,
        attiva=data.get('attiva', True)
    )
    db.session.add(promo)
    db.session.commit()
    
    return jsonify({'success': True, 'promo': promo.to_dict()})

@settings_bp.route('/api/pacchetti/promo/<int:promo_id>', methods=['PUT'])
def api_update_promo(promo_id):
    """Aggiorna una promo esistente."""
    promo = PromoPacchetto.query.get_or_404(promo_id)
    data = request.get_json(silent=True) or {}
    
    if 'nome' in data:
        promo.nome = (data['nome'] or '').strip()
    if 'tipo' in data:
        promo.tipo = data['tipo']
    if 'soglia' in data:
        promo.soglia = data['soglia']
    if 'percentuale' in data:
        promo.percentuale = data['percentuale']
    if 'sedute_omaggio' in data:
        promo.sedute_omaggio = data['sedute_omaggio']
    if 'attiva' in data:
        promo.attiva = data['attiva']
    
    db.session.commit()
    return jsonify({'success': True, 'promo': promo.to_dict()})

@settings_bp.route('/api/pacchetti/promo/<int:promo_id>', methods=['DELETE'])
def api_delete_promo(promo_id):
    """Elimina una promo."""
    promo = PromoPacchetto.query.get_or_404(promo_id)
    db.session.delete(promo)
    db.session.commit()
    return jsonify({'success': True})

# ================= MARKETING ====================
# Messaggio di benvenuto predefinito
DEFAULT_WELCOME_MESSAGE = """Ciao {{nome}}! 👋

Grazie per aver scelto {{centro}} per il tuo primo trattamento!

Speriamo che la tua esperienza sia stata fantastica ✨

Se ti sei trovato/a bene, ti saremmo grati se lasciassi una recensione su Google:
{{link_recensione}}

Le tue 5 stelle ⭐⭐⭐⭐⭐ ci aiutano a crescere!

A presto! 💆‍♀️"""

@settings_bp.route('/marketing', methods=['GET'])
def marketing():
    """Pagina principale Marketing"""
    business_info = BusinessInfo.query.filter_by(is_deleted=False).first()
    services = Service.query.filter_by(is_deleted=False).order_by(Service.servizio_nome).all()
    saved_templates = MarketingTemplate.query.order_by(MarketingTemplate.nome).all()
    
    # Recupera template marketing salvato
    marketing_message = getattr(business_info, 'marketing_message_template', '') if business_info else ''
    
    # Recupera template nuovo cliente
    new_client_message = getattr(business_info, 'new_client_welcome_message', '') if business_info else ''
    
    user_id = session.get('user_id')
    current_user = db.session.get(User, user_id) if user_id else None
    
    return render_template(
        'marketing.html',
        business_info=business_info,
        services=services,
        saved_templates=saved_templates,
        marketing_message=marketing_message,
        new_client_message=new_client_message,
        default_welcome_message=DEFAULT_WELCOME_MESSAGE,
        current_user=current_user
    )

@settings_bp.route('/api/marketing/search-clients', methods=['POST'])
def marketing_search_clients():
    """Ricerca clienti con filtri avanzati per campagne marketing"""
    data = request.get_json(silent=True) or {}
    
    try:
        # Query base: clienti attivi con cellulare
        query = Client.query.filter(
            Client.is_deleted == False,
            Client.cliente_cellulare != None,
            Client.cliente_cellulare != '',
            Client.cliente_cellulare != '0',
            Client.cliente_nome != 'dummy',
            Client.cliente_nome != 'cliente'
        )
        
        today = datetime.now().date()
        now = datetime.now()
        
        # Verifica se almeno un filtro è attivo
        any_filter_active = any([
            data.get('filter_inactivity'),
            data.get('filter_top_spender'),
            data.get('filter_service') and data.get('service_id'),
            data.get('filter_frequency'),
            data.get('filter_category') and data.get('category_id'),
            data.get('filter_new_clients'),
            data.get('filter_gender') and data.get('gender')
        ])
        
        if not any_filter_active:
            return jsonify({
                'success': True, 
                'clients': [],
                'message': 'Seleziona almeno un filtro per cercare clienti'
            })
        
        # FILTRO: Inattività (solo mesi/anni, minimo 1 mese)
        if data.get('filter_inactivity'):
            inactivity_value = max(1, int(data.get('inactivity_value', 3)))
            inactivity_unit = data.get('inactivity_unit', 'months')
            
            if inactivity_unit == 'years':
                cutoff_date = today - timedelta(days=inactivity_value * 365)
            else:  # months (default)
                cutoff_date = today - timedelta(days=inactivity_value * 30)
            
            cutoff_datetime = datetime.combine(cutoff_date, datetime.min.time())
            
            last_appt_subq = db.session.query(
                Appointment.client_id,
                func.max(Appointment.start_time).label('last_appt')
            ).filter(
                Appointment.is_cancelled_by_client == False,
                Appointment.stato != AppointmentStatus.NON_ARRIVATO
            ).group_by(Appointment.client_id).subquery()
            
            query = query.outerjoin(
                last_appt_subq, 
                Client.id == last_appt_subq.c.client_id
            ).filter(
                or_(
                    last_appt_subq.c.last_appt == None,
                    last_appt_subq.c.last_appt < cutoff_datetime
                )
            )
        
        # FILTRO: Top Spender
        if data.get('filter_top_spender'):
            spender_from = data.get('spender_from')
            spender_to = data.get('spender_to')
            spender_min = float(data.get('spender_min', 100))
            
            receipt_query = db.session.query(
                Receipt.cliente_id,
                func.sum(Receipt.total_amount).label('total_spent')
            ).filter(Receipt.cliente_id != None)
            
            if spender_from:
                try:
                    receipt_query = receipt_query.filter(Receipt.created_at >= datetime.strptime(spender_from, '%Y-%m-%d'))
                except:
                    pass
            if spender_to:
                try:
                    receipt_query = receipt_query.filter(Receipt.created_at <= datetime.strptime(spender_to, '%Y-%m-%d'))
                except:
                    pass
            
            receipt_subq = receipt_query.group_by(Receipt.cliente_id).having(
                func.sum(Receipt.total_amount) >= spender_min
            ).subquery()
            
            query = query.join(receipt_subq, Client.id == receipt_subq.c.cliente_id)
        
        # FILTRO: Per servizio
        if data.get('filter_service') and data.get('service_id'):
            try:
                service_id = int(data.get('service_id'))
                min_usage = int(data.get('service_min_usage', 1))
                
                service_subq = db.session.query(
                    Appointment.client_id
                ).filter(
                    Appointment.service_id == service_id,
                    Appointment.is_cancelled_by_client == False,
                    Appointment.stato != AppointmentStatus.NON_ARRIVATO
                ).group_by(Appointment.client_id).having(
                    func.count(Appointment.id) >= min_usage
                ).subquery()
                
                query = query.filter(Client.id.in_(db.session.query(service_subq.c.client_id)))
            except (ValueError, TypeError):
                pass
        
        # FILTRO: Frequenza visite
        if data.get('filter_frequency'):
            frequency_type = data.get('frequency_type', 'medium')
            frequency_months = int(data.get('frequency_months', 6))
            start_date = datetime.combine(today - timedelta(days=frequency_months * 30), datetime.min.time())
            
            freq_subq = db.session.query(
                Appointment.client_id,
                func.count(Appointment.id).label('visit_count')
            ).filter(
                Appointment.start_time >= start_date,
                Appointment.is_cancelled_by_client == False,
                Appointment.stato != AppointmentStatus.NON_ARRIVATO
            ).group_by(Appointment.client_id).subquery()
            
            thresholds = {'high': 4, 'medium': 2, 'low': 1, 'rare': 0}
            min_visits = thresholds.get(frequency_type, 1) * frequency_months
            
            if frequency_type == 'rare':
                query = query.outerjoin(freq_subq, Client.id == freq_subq.c.client_id).filter(
                    or_(freq_subq.c.visit_count == None, freq_subq.c.visit_count < frequency_months)
                )
            elif frequency_type == 'high':
                query = query.join(freq_subq, Client.id == freq_subq.c.client_id).filter(
                    freq_subq.c.visit_count >= min_visits
                )
            else:
                max_visits = (thresholds.get(frequency_type, 1) + 1) * frequency_months
                query = query.join(freq_subq, Client.id == freq_subq.c.client_id).filter(
                    freq_subq.c.visit_count >= min_visits, freq_subq.c.visit_count < max_visits
                )
        
        # FILTRO: Per categoria
        if data.get('filter_category') and data.get('category_id'):
            try:
                category = data.get('category_id')
                cat_subq = db.session.query(Appointment.client_id).join(Service).filter(
                    Service.servizio_categoria == ServiceCategory[category],
                    Appointment.is_cancelled_by_client == False
                ).distinct().subquery()
                query = query.filter(Client.id.in_(db.session.query(cat_subq.c.client_id)))
            except KeyError:
                pass
        
        # FILTRO: Nuovi clienti
        if data.get('filter_new_clients'):
            new_clients_days = int(data.get('new_clients_days', 30))
            cutoff = datetime.combine(today - timedelta(days=new_clients_days), datetime.min.time())
            query = query.filter(Client.created_at >= cutoff)
        
        # FILTRO: Per genere
        if data.get('filter_gender') and data.get('gender'):
            query = query.filter(Client.cliente_sesso == data.get('gender'))
        
        # LIMITE 50 risultati per velocità
        clients = query.distinct().limit(30).all()
        
        if not clients:
            return jsonify({'success': True, 'clients': [], 'message': 'Nessun cliente trovato con questi filtri'})
        
        # Ottimizzazione: query batch per tutti i clienti
        client_ids = [c.id for c in clients]
        
        # Batch: ultimo appuntamento per cliente
        last_appts = db.session.query(
            Appointment.client_id,
            func.max(Appointment.start_time).label('last_time')
        ).filter(
            Appointment.client_id.in_(client_ids),
            Appointment.is_cancelled_by_client == False,
            Appointment.stato != AppointmentStatus.NON_ARRIVATO
        ).group_by(Appointment.client_id).all()
        last_appt_dict = {r.client_id: r.last_time for r in last_appts}
        
        # Batch: totale visite per cliente
        visit_counts = db.session.query(
            Appointment.client_id,
            func.count(Appointment.id).label('cnt')
        ).filter(
            Appointment.client_id.in_(client_ids),
            Appointment.is_cancelled_by_client == False,
            Appointment.stato != AppointmentStatus.NON_ARRIVATO
        ).group_by(Appointment.client_id).all()
        visits_dict = {r.client_id: r.cnt for r in visit_counts}
        
        # Batch: totale speso per cliente
        spent_totals = db.session.query(
            Receipt.cliente_id,
            func.sum(Receipt.total_amount).label('total')
        ).filter(Receipt.cliente_id.in_(client_ids)).group_by(Receipt.cliente_id).all()
        spent_dict = {r.cliente_id: float(r.total or 0) for r in spent_totals}
        
        # Costruisci risposta
        clients_data = []
        for client in clients:
            last_time = last_appt_dict.get(client.id)
            giorni_assenza = None
            if last_time:
                if last_time.tzinfo is not None:
                    last_time = last_time.replace(tzinfo=None)
                giorni_assenza = (now - last_time).days
            
            clients_data.append({
                'id': client.id,
                'nome': client.cliente_nome,
                'cognome': client.cliente_cognome,
                'cellulare': client.cliente_cellulare,
                'email': client.cliente_email,
                'giorni_assenza': giorni_assenza,
                'totale_visite': visits_dict.get(client.id, 0),
                'totale_speso': round(spent_dict.get(client.id, 0), 2)
            })
        
        return jsonify({'success': True, 'clients': clients_data, 'limited': len(clients) == 30})
        
    except Exception as e:
        current_app.logger.exception("Errore ricerca clienti marketing: %s", e)
        return jsonify({'success': False, 'error': str(e), 'clients': []})
    
@settings_bp.route('/api/marketing/save-template', methods=['POST'])
def marketing_save_template():
    """Salva il template del messaggio marketing"""
    data = request.get_json(silent=True) or {}
    template = data.get('template', '')
    
    try:
        business_info = BusinessInfo.query.filter_by(is_deleted=False).first()
        if not business_info:
            return jsonify({'success': False, 'error': 'BusinessInfo non trovato'})
        
        business_info.marketing_message_template = template
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        current_app.logger.exception("Errore salvataggio template marketing: %s", e)
        return jsonify({'success': False, 'error': str(e)})


@settings_bp.route('/api/marketing/new-client-settings', methods=['POST'])
def marketing_new_client_settings():
    """Salva le impostazioni per il messaggio nuovo cliente"""
    data = request.get_json(silent=True) or {}
    
    try:
        business_info = BusinessInfo.query.filter_by(is_deleted=False).first()
        if not business_info:
            return jsonify({'success': False, 'error': 'BusinessInfo non trovato'})
        
        business_info.new_client_welcome_enabled = data.get('enabled', False)
        business_info.google_review_link = data.get('google_review_link', '')
        business_info.new_client_delay_send = data.get('delay_send', False)
        business_info.new_client_delay_hours = int(data.get('delay_hours', 2))
        
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        current_app.logger.exception("Errore salvataggio impostazioni nuovo cliente: %s", e)
        return jsonify({'success': False, 'error': str(e)})


@settings_bp.route('/api/marketing/save-new-client-template', methods=['POST'])
def marketing_save_new_client_template():
    """Salva il template del messaggio di benvenuto nuovo cliente"""
    data = request.get_json(silent=True) or {}
    template = data.get('template', '')
    
    try:
        business_info = BusinessInfo.query.filter_by(is_deleted=False).first()
        if not business_info:
            return jsonify({'success': False, 'error': 'BusinessInfo non trovato'})
        
        business_info.new_client_welcome_message = template
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        current_app.logger.exception("Errore salvataggio template nuovo cliente: %s", e)
        return jsonify({'success': False, 'error': str(e)})


@settings_bp.route('/api/marketing/check-new-client', methods=['GET'])
def marketing_check_new_client():
    """API per verificare se mostrare il prompt di benvenuto in cassa"""
    client_id = request.args.get('client_id')
    
    if not client_id:
        return jsonify({'show_prompt': False})
    
    try:
        business_info = BusinessInfo.query.filter_by(is_deleted=False).first()
        if not business_info or not getattr(business_info, 'new_client_welcome_enabled', False):
            return jsonify({'show_prompt': False})
        
        # Verifica se è un nuovo cliente (primo pagamento)
        receipt_count = Receipt.query.filter(Receipt.cliente_id == int(client_id)).count()
        
        if receipt_count == 0:  # Primo pagamento = nuovo cliente
            client = Client.query.get(int(client_id))
            if client:
                template = getattr(business_info, 'new_client_welcome_message', '') or DEFAULT_WELCOME_MESSAGE
                google_link = getattr(business_info, 'google_review_link', '') or ''
                
                message = template.replace('{{nome}}', client.cliente_nome or '')
                message = message.replace('{{centro}}', business_info.business_name or 'Centro')
                message = message.replace('{{link_recensione}}', google_link)
                
                return jsonify({
                    'show_prompt': True,
                    'client_name': f"{client.cliente_nome} {client.cliente_cognome}",
                    'client_phone': client.cliente_cellulare,
                    'message': message,
                    'delay_send': getattr(business_info, 'new_client_delay_send', False),
                    'delay_hours': getattr(business_info, 'new_client_delay_hours', 2)
                })
        
        return jsonify({'show_prompt': False})
        
    except Exception as e:
        current_app.logger.exception("Errore check nuovo cliente: %s", e)
        return jsonify({'show_prompt': False})
    
@settings_bp.route('/api/marketing/max-daily-sends', methods=['POST'])
def marketing_set_max_daily_sends():
    """Imposta il limite massimo di invii giornalieri (solo owner)"""
    user_id = session.get('user_id')
    current_user = db.session.get(User, user_id) if user_id else None
    
    if not current_user or current_user.ruolo.value != 'owner':
        return jsonify({'success': False, 'error': 'Solo il proprietario può modificare questo valore'}), 403
    
    data = request.get_json(silent=True) or {}
    max_sends = data.get('max_sends', 30)
    
    try:
        max_sends = int(max_sends)
        if max_sends < 1 or max_sends > 100:
            return jsonify({'success': False, 'error': 'Valore deve essere tra 1 e 100'}), 400
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Valore non valido'}), 400
    
    business_info = BusinessInfo.query.filter_by(is_deleted=False).first()
    if not business_info:
        return jsonify({'success': False, 'error': 'BusinessInfo non trovato'}), 404
    
    business_info.marketing_max_daily_sends = max_sends
    db.session.commit()
    
    return jsonify({'success': True, 'max_sends': max_sends})
    
# ================= MARKETING TEMPLATES ====================
@settings_bp.route('/api/marketing/templates', methods=['GET'])
def marketing_get_templates():
    """Restituisce tutti i template salvati"""
    templates = MarketingTemplate.query.order_by(MarketingTemplate.nome).all()
    return jsonify([t.to_dict() for t in templates])

@settings_bp.route('/api/marketing/templates', methods=['POST'])
def marketing_create_template():
    """Crea un nuovo template"""
    data = request.get_json(silent=True) or {}
    nome = (data.get('nome') or '').strip()
    testo = (data.get('testo') or '').strip()
    
    if not nome:
        return jsonify({'success': False, 'error': 'Nome obbligatorio'}), 400
    if not testo:
        return jsonify({'success': False, 'error': 'Testo obbligatorio'}), 400
    
    template = MarketingTemplate(nome=nome, testo=testo)
    db.session.add(template)
    db.session.commit()
    
    return jsonify({'success': True, 'template': template.to_dict()})

@settings_bp.route('/api/marketing/templates/<int:template_id>', methods=['PUT'])
def marketing_update_template(template_id):
    """Aggiorna un template esistente"""
    template = MarketingTemplate.query.get_or_404(template_id)
    data = request.get_json(silent=True) or {}
    
    if 'nome' in data:
        template.nome = (data['nome'] or '').strip()
    if 'testo' in data:
        template.testo = (data['testo'] or '').strip()
    
    db.session.commit()
    return jsonify({'success': True, 'template': template.to_dict()})

@settings_bp.route('/api/marketing/templates/<int:template_id>', methods=['DELETE'])
def marketing_delete_template(template_id):
    """Elimina un template"""
    template = MarketingTemplate.query.get_or_404(template_id)
    db.session.delete(template)
    db.session.commit()
    return jsonify({'success': True})

# ===================== AUTO-UPDATE ROUTES =====================

@settings_bp.route('/api/check-update', methods=['GET'])
def check_update():
    """Controlla se c'è una nuova versione disponibile su GitHub Releases."""
    try:
        # Versione locale (dal file .version in AppData)
        appdata_dir = os.path.join(os.getenv('LOCALAPPDATA', os.getcwd()), 'SunBooking')
        os.makedirs(appdata_dir, exist_ok=True)
        version_file = os.path.join(appdata_dir, '.version')
        
        # Se non esiste in AppData, prova nella cartella exe (prima installazione)
        if not os.path.exists(version_file):
            fallback_version = os.path.join(os.getcwd(), '.version')
            if os.path.exists(fallback_version):
                with open(fallback_version, 'r') as f:
                    local_version = f.read().strip()
                # Copia in AppData per le prossime volte
                with open(version_file, 'w') as f:
                    f.write(local_version)
            else:
                local_version = None
        else:
            with open(version_file, 'r') as f:
                local_version = f.read().strip()
        
        # Ultima release da GitHub
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        resp = requests.get(url, timeout=10)
        
        if resp.status_code != 200:
            return jsonify({"error": "Impossibile contattare GitHub", "status_code": resp.status_code}), 500
        
        release_data = resp.json()
        remote_version = release_data.get("tag_name", "")
        release_name = release_data.get("name", remote_version)
        release_notes = release_data.get("body", "")
        published_at = release_data.get("published_at", "")
        
        # Cerca l'asset Tosca.exe
        download_url = None
        for asset in release_data.get("assets", []):
            if asset.get("name") == APP_EXE_NAME:
                download_url = asset.get("browser_download_url")
                break
        
        has_update = local_version != remote_version if local_version else True
        
        return jsonify({
            "has_update": has_update,
            "local_version": local_version,
            "remote_version": remote_version,
            "release_name": release_name,
            "release_notes": release_notes,
            "published_at": published_at,
            "download_url": download_url
        })
    except Exception as e:
        current_app.logger.error(f"check_update error: {e}")
        return jsonify({"error": str(e)}), 500


@settings_bp.route('/api/download-update', methods=['POST'])
def download_update():
    """Scarica la nuova versione e prepara l'aggiornamento."""
    try:
        data = request.get_json() or {}
        download_url = data.get("download_url")
        remote_version = data.get("remote_version")

        if not download_url:
            return jsonify({"error": "URL download mancante"}), 400

        if not getattr(sys, 'frozen', False):
            return jsonify({"error": "Aggiornamento disponibile solo per versione .exe"}), 400

        current_exe = sys.executable
        exe_dir = os.path.dirname(current_exe)
        appdata_dir = os.path.join(os.getenv('LOCALAPPDATA', exe_dir), 'SunBooking')
        backup_dir = os.path.join(appdata_dir, BACKUP_FOLDER)
        os.makedirs(backup_dir, exist_ok=True)

        existing_backups = [f for f in os.listdir(backup_dir) if f.startswith("ToscaBKP")]
        next_num = len(existing_backups) + 1
        backup_name = f"ToscaBKP{next_num}.exe"
        backup_path = os.path.join(backup_dir, backup_name)

        temp_dir = tempfile.mkdtemp()
        new_exe_temp = os.path.join(temp_dir, APP_EXE_NAME)

        current_app.logger.info(f"Downloading update from {download_url}")
        resp = requests.get(download_url, timeout=300, stream=True)

        if resp.status_code != 200:
            return jsonify({"error": f"Download fallito: {resp.status_code}"}), 500

        with open(new_exe_temp, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        # Salva info per il completamento
        update_info = {
            "current_exe": current_exe,
            "backup_path": backup_path,
            "new_exe_temp": new_exe_temp,
            "remote_version": remote_version
        }

        update_info_path = os.path.join(appdata_dir, ".pending_update")
        import json
        with open(update_info_path, 'w') as f:
            json.dump(update_info, f)

        return jsonify({
            "success": True,
            "message": "Download completato.",
            "backup_name": backup_name
        })

    except Exception as e:
        current_app.logger.error(f"download_update error: {e}")
        return jsonify({"error": str(e)}), 500


@settings_bp.route('/api/apply-update', methods=['POST'])
def apply_update():
    """Applica l'aggiornamento e riavvia."""
    try:
        if not getattr(sys, 'frozen', False):
            return jsonify({"error": "Disponibile solo per versione .exe"}), 400
        
        current_exe = sys.executable
        exe_dir = os.path.dirname(current_exe)
        appdata_dir = os.path.join(os.getenv('LOCALAPPDATA', exe_dir), 'SunBooking')
        update_info_path = os.path.join(appdata_dir, ".pending_update")
        
        if not os.path.exists(update_info_path):
            return jsonify({"error": "Nessun aggiornamento in sospeso"}), 400
        
        import json
        with open(update_info_path, 'r') as f:
            update_info = json.load(f)
        
        backup_path = update_info["backup_path"]
        new_exe_temp = update_info["new_exe_temp"]
        remote_version = update_info["remote_version"]
        
        current_app.logger.info(f"[UPDATER] sys.executable = {current_exe}")
        current_app.logger.info(f"[UPDATER] exe_dir = {exe_dir}")
        current_app.logger.info(f"[UPDATER] new_exe_temp = {new_exe_temp}")
        current_app.logger.info(f"[UPDATER] target copy = {current_exe}")
        
        if not os.path.exists(new_exe_temp):
            return jsonify({"error": f"File aggiornamento non trovato: {new_exe_temp}"}), 400
        
        batch_path = os.path.join(appdata_dir, "_update.bat")
        version_file = os.path.join(appdata_dir, ".version")
        
        needs_elevation = 'program files' in exe_dir.lower() or 'programmi' in exe_dir.lower()
        
        exe_name = os.path.basename(current_exe)
        
        log_file = os.path.join(appdata_dir, "_update.log")
        
        # Trova il browser-profile usato per chiudere anche le finestre del browser
        browser_profile = os.path.join(os.getenv('LOCALAPPDATA', ''), 'SunBooking', 'browser-profile')
        
        # Nome temporaneo per rinominare il vecchio exe prima di copiare
        old_exe_renamed = os.path.join(exe_dir, f"{exe_name}.old")
        
        # Script PowerShell per la finestra di progresso
        ps_progress_path = os.path.join(appdata_dir, "_update_progress.ps1")
        ps_progress_content = r'''
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$form = New-Object System.Windows.Forms.Form
$form.Text = "SunBooking - Aggiornamento"
$form.Size = New-Object System.Drawing.Size(420, 160)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false
$form.MinimizeBox = $false
$form.TopMost = $true
$form.BackColor = [System.Drawing.Color]::FromArgb(245, 240, 248)

$label = New-Object System.Windows.Forms.Label
$label.Text = "Aggiornamento in corso..."
$label.Font = New-Object System.Drawing.Font("Segoe UI", 11, [System.Drawing.FontStyle]::Bold)
$label.ForeColor = [System.Drawing.Color]::FromArgb(100, 30, 120)
$label.AutoSize = $true
$label.Location = New-Object System.Drawing.Point(20, 20)
$form.Controls.Add($label)

$progress = New-Object System.Windows.Forms.ProgressBar
$progress.Style = "Marquee"
$progress.MarqueeAnimationSpeed = 30
$progress.Size = New-Object System.Drawing.Size(370, 28)
$progress.Location = New-Object System.Drawing.Point(20, 55)
$form.Controls.Add($progress)

$sublabel = New-Object System.Windows.Forms.Label
$sublabel.Text = "Non chiudere questa finestra"
$sublabel.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$sublabel.ForeColor = [System.Drawing.Color]::FromArgb(120, 120, 120)
$sublabel.AutoSize = $true
$sublabel.Location = New-Object System.Drawing.Point(20, 95)
$form.Controls.Add($sublabel)

# Timer per auto-chiusura: controlla se il file segnale esiste
$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 500
$timer.Add_Tick({
    if (Test-Path "$env:LOCALAPPDATA\SunBooking\_update_done.flag") {
        Remove-Item "$env:LOCALAPPDATA\SunBooking\_update_done.flag" -Force -ErrorAction SilentlyContinue
        $label.Text = "Aggiornamento completato!"
        $sublabel.Text = "Riavvio in corso..."
        $progress.Style = "Continuous"
        $progress.Value = 100
        $form.Refresh()
        Start-Sleep -Milliseconds 800
        $form.Close()
    }
})
$timer.Start()

# Chiudi comunque dopo 120 secondi
$timeoutTimer = New-Object System.Windows.Forms.Timer
$timeoutTimer.Interval = 120000
$timeoutTimer.Add_Tick({ $form.Close() })
$timeoutTimer.Start()

$form.ShowDialog() | Out-Null
'''
        with open(ps_progress_path, 'w', encoding='utf-8') as f:
            f.write(ps_progress_content)
        
        done_flag = os.path.join(appdata_dir, "_update_done.flag")
        
        batch_content = f'''@echo off
chcp 65001 >nul

echo [%date% %time%] UPDATER START > "{log_file}"
echo [%date% %time%] current_exe = {current_exe} >> "{log_file}"
echo [%date% %time%] new_exe_temp = {new_exe_temp} >> "{log_file}"
echo [%date% %time%] backup_path = {backup_path} >> "{log_file}"

rem === FASE 0: Mostra finestra di progresso ===
start "" powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{ps_progress_path}"

rem === FASE 1: Chiudi SOLO il processo exe (il browser resta aperto) ===
echo [%date% %time%] Forzo chiusura processo {exe_name} e figli >> "{log_file}"
taskkill /F /T /IM "{exe_name}" >nul 2>&1

rem Breve attesa per rilascio file
timeout /t 1 /nobreak >nul

rem === FASE 2: Attendi che il file exe sia sbloccato ===
set RETRIES=0
:WAIT_UNLOCK
set /A RETRIES+=1
echo [%date% %time%] Tentativo sblocco %RETRIES% >> "{log_file}"

del "{old_exe_renamed}" >nul 2>&1
move /Y "{current_exe}" "{old_exe_renamed}" >nul 2>&1
if not errorlevel 1 (
    echo [%date% %time%] Vecchio exe rinominato in .old >> "{log_file}"
    goto DO_COPY
)

if %RETRIES% GEQ 20 (
    echo [%date% %time%] ERRORE: impossibile sbloccare dopo 20 tentativi >> "{log_file}"
    echo done> "{done_flag}"
    pause
    exit /b 1
)

timeout /t 1 /nobreak >nul
goto WAIT_UNLOCK

:DO_COPY
echo [%date% %time%] File sbloccato, procedo >> "{log_file}"

rem === FASE 3: Backup ===
copy /Y "{old_exe_renamed}" "{backup_path}" >nul 2>&1
if errorlevel 1 (
    echo [%date% %time%] WARN: backup fallito >> "{log_file}"
) else (
    echo [%date% %time%] Backup creato: {backup_path} >> "{log_file}"
)

rem === FASE 4: Copia il nuovo exe ===
copy /Y "{new_exe_temp}" "{current_exe}" >nul 2>&1
if errorlevel 1 (
    echo [%date% %time%] Primo tentativo copia FALLITO, riprovo... >> "{log_file}"
    timeout /t 2 /nobreak >nul
    copy /Y "{new_exe_temp}" "{current_exe}" >nul 2>&1
    if errorlevel 1 (
        echo [%date% %time%] ERRORE CRITICO: ripristino vecchio exe >> "{log_file}"
        move /Y "{old_exe_renamed}" "{current_exe}" >nul 2>&1
        echo done> "{done_flag}"
        pause
        exit /b 1
    )
)

echo [%date% %time%] Copia completata con successo >> "{log_file}"

if not exist "{current_exe}" (
    echo [%date% %time%] ERRORE: file target non esiste dopo copia! >> "{log_file}"
    move /Y "{old_exe_renamed}" "{current_exe}" >nul 2>&1
    echo done> "{done_flag}"
    pause
    exit /b 1
)

del "{old_exe_renamed}" >nul 2>&1

rem === FASE 5: Aggiorna versione ===
echo {remote_version}> "{version_file}"
echo [%date% %time%] Versione aggiornata a {remote_version} >> "{log_file}"

rem === FASE 6: Pulizia ===
del "{update_info_path}" >nul 2>&1
rmdir /s /q "{os.path.dirname(new_exe_temp)}" >nul 2>&1

rem === FASE 6b: Segnala post-update per non aprire un secondo browser ===
echo 1> "{os.path.join(appdata_dir, '_post_update')}"

rem === FASE 7: Riavvia app ===
echo [%date% %time%] Riavvio applicazione: {current_exe} >> "{log_file}"
start "" /D "{exe_dir}" "{current_exe}"

rem === FASE 8: Attendi che il server sia pronto, poi segnala la chiusura della finestra progresso ===
echo [%date% %time%] Attendo server pronto su porta {PORT}... >> "{log_file}"
set WAIT_SERVER=0
:WAIT_SERVER_LOOP
set /A WAIT_SERVER+=1
powershell -NoProfile -Command "try {{ $c = New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1', {PORT}); $c.Close(); exit 0 }} catch {{ exit 1 }}" >nul 2>&1
if not errorlevel 1 (
    echo [%date% %time%] Server pronto >> "{log_file}"
    goto SERVER_READY
)
if %WAIT_SERVER% GEQ 30 (
    echo [%date% %time%] Timeout attesa server >> "{log_file}"
    goto SERVER_READY
)
timeout /t 1 /nobreak >nul
goto WAIT_SERVER_LOOP

:SERVER_READY
rem Segnala alla finestra progresso di chiudersi
echo done> "{done_flag}"

echo [%date% %time%] UPDATER COMPLETATO >> "{log_file}"

rem Auto-elimina questo script
(goto) 2>nul & del "%~f0"
'''
        
        with open(batch_path, 'w', encoding='utf-8') as f:
            f.write(batch_content)
        
        import subprocess
        
        if needs_elevation:
            # Crea script VBS per elevazione UAC con quoting corretto
            vbs_path = os.path.join(appdata_dir, "_update_elevated.vbs")
            # Escape delle virgolette per VBS: raddoppia le virgolette nel path
            batch_path_escaped = batch_path.replace('"', '""')
            vbs_content = f'''Set UAC = CreateObject("Shell.Application")
UAC.ShellExecute "cmd.exe", "/c """"{batch_path_escaped}""""", "", "runas", 0
'''
            with open(vbs_path, 'w', encoding='utf-8') as f:
                f.write(vbs_content)
            
            subprocess.Popen(
                ['wscript', vbs_path],
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
                close_fds=True
            )
        else:
            subprocess.Popen(
                ['cmd', '/c', batch_path],
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
                close_fds=True
            )
        
        # Il batch farà taskkill, non serve os._exit() qui
        return jsonify({
            "success": True,
            "message": "Aggiornamento in corso...",
            "shutdown": True
        })
        
    except Exception as e:
        current_app.logger.error(f"apply_update error: {e}")
        return jsonify({"error": str(e)}), 500
    
@settings_bp.route('/api/shutdown', methods=['POST'])
def shutdown_app():
    """Chiude l'applicazione Flask per permettere l'aggiornamento."""
    import threading
    def _shutdown():
        import time
        time.sleep(1)
        os._exit(0)
    threading.Thread(target=_shutdown, daemon=True).start()
    return jsonify({"success": True, "message": "Chiusura in corso..."})