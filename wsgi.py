# wsgi.py - WSGI entry point per SunBooking con supporto multi-database
import os
import re
from urllib.parse import urlparse
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, redirect, url_for, request, session, send_from_directory
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from waitress import serve
from appl import create_app, db
from appl.models import BusinessInfo
from appl.autologin import issue_token as autologin_issue
import time as time_mod
import json
import uuid
from werkzeug.security import check_password_hash
try:
    from argon2 import PasswordHasher as _ArgonPH
    from argon2 import exceptions as _argon_exc
    _root_ph = _ArgonPH()
except ImportError:
    _root_ph = None
    _argon_exc = None

base_dir = os.path.dirname(__file__)
env_candidates = [
    os.path.join(base_dir, '.env'),
    os.path.join(base_dir, 'dist', '.env'),
    os.path.join(os.getcwd(), '.env')
]
for p in env_candidates:
    if os.path.isfile(p):
        load_dotenv(p, override=False)
load_dotenv(override=False)

def collect_db_pool():
    pattern = re.compile(r'^SQLALCHEMY_DATABASE_URI(\d+)$', re.IGNORECASE)
    pool = {}
    for k, v in os.environ.items():
        m = pattern.match(k)
        if m and v:
            try:
                idx = int(m.group(1))
                pool[idx] = v
            except Exception:
                pass
    return dict(sorted(pool.items()))

def db_label(uri):
    try:
        p = urlparse(uri)
        name = (p.path or "/").strip("/").split("/")[-1]
        return name or "DB"
    except Exception:
        return "DB"

def unipile_creds_for(idx: int):
    """Restituisce le credenziali Unipile per il tenant specificato."""
    s = str(idx)
    return {
        "UNIPILE_DSN": os.getenv(f"UNIPILE_DSN{s}") or os.getenv("UNIPILE_DSN") or "",
        "UNIPILE_ACCESS_TOKEN": os.getenv(f"UNIPILE_ACCESS_TOKEN{s}") or os.getenv("UNIPILE_ACCESS_TOKEN") or "",
    }

def with_request_env(app, per_request_env: dict):
    def wrapper(environ, start_response):
        keys = list(per_request_env.keys())
        old = {k: os.environ.get(k) for k in keys}
        try:
            for k, v in per_request_env.items():
                if v is None or v == "":
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = str(v)
            return app(environ, start_response)
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
    return wrapper

def block_paths(app, blocked_prefixes: tuple[str, ...]):
    def _wrap(environ, start_response):
        path = (environ.get("PATH_INFO") or "").lower()
        # Nel child PATH_INFO è relativo al mount (/s/<idx> è in SCRIPT_NAME)
        if any(path == p or path.startswith(p.rstrip("/") + "/") for p in blocked_prefixes):
            start_response("404 Not Found", [("Content-Type", "text/html; charset=utf-8")])
            return [b"<!doctype html><title>Not Found</title><h1>404 Not Found</h1>"]
        return app(environ, start_response)
    return _wrap

def fix_delete_method_middleware(app):
    def wrapper(environ, start_response):
        path = environ.get('PATH_INFO', '')
        method = environ.get('REQUEST_METHOD', '')
        # Se è GET su /calendar/delete/, cambia a POST
        if path.startswith('/calendar/delete/') and method == 'GET':
            environ['REQUEST_METHOD'] = 'POST'
        return app(environ, start_response)
    return wrapper

pool = collect_db_pool()
secret = os.getenv('SECRET_KEY') or os.urandom(24)
use_https = os.getenv('USE_HTTPS', 'false').lower() in ('1', 'true', 'yes')

base_templates = os.path.join(base_dir, 'appl', 'templates')
root_app = Flask('sunbooking_root', template_folder=base_templates)
root_app.secret_key = secret

# La root_app non ha Flask-WTF inizializzato: forniamo un csrf_token() no-op
# per i template che lo includono (landing_web.html, owner_login.html).
root_app.jinja_env.globals['csrf_token'] = lambda: ''

@root_app.before_request
def root_redirect_to_selected_db():
    path = request.path or '/'
    if path in ('/', '/landing-web', '/landing-logout') or path.startswith('/select-db/') or path.startswith('/s/') or path.startswith('/owner'):
        return None
    dbidx = request.cookies.get('dbidx', '').strip()
    if dbidx and dbidx.isdigit():
        q = request.query_string.decode('utf-8')
        target = f"/s/{dbidx}{path}"
        if q:
            target = f"{target}?{q}"
        return redirect(target, code=307)  # preserva POST/PUT/DELETE
    return None


# =============================================================
#   AUTENTICAZIONE CROSS-TENANT (per la landing root)
# =============================================================
_root_login_attempts = {}  # ip -> (count, first_ts)
ROOT_MAX_ATTEMPTS = 5
ROOT_WINDOW_SECONDS = 60


def _root_is_locked(ip):
    entry = _root_login_attempts.get(ip)
    if not entry:
        return False
    count, first_ts = entry
    if time_mod.time() - first_ts > ROOT_WINDOW_SECONDS:
        _root_login_attempts.pop(ip, None)
        return False
    return count >= ROOT_MAX_ATTEMPTS


def _root_record_failure(ip):
    now = time_mod.time()
    entry = _root_login_attempts.get(ip)
    if not entry or (now - entry[1] > ROOT_WINDOW_SECONDS):
        _root_login_attempts[ip] = (1, now)
    else:
        _root_login_attempts[ip] = (entry[0] + 1, entry[1])


def _verify_password(stored_hash, password):
    if not stored_hash or not password:
        return False
    if _root_ph:
        try:
            return _root_ph.verify(stored_hash, password)
        except Exception:
            pass
    try:
        return check_password_hash(stored_hash, password)
    except Exception:
        return False


def find_user_in_all_tenants(username, password):
    """Cerca username+password su tutti i tenant. Ritorna [{idx, user_id, label}, ...]."""
    if not username or not password:
        return []
    matches = []
    for idx, child in children.items():
        try:
            with child.app_context():
                from appl.models import User as _U
                user = _U.query.filter_by(username=username).first()
                if user and _verify_password(user.password, password):
                    label = db_label(pool.get(idx, ''))
                    try:
                        bi = BusinessInfo.query.first()
                        if bi and bi.business_name:
                            label = bi.business_name
                    except Exception:
                        pass
                    matches.append({'idx': int(idx), 'user_id': int(user.id), 'label': label})
        except Exception:
            continue
    return matches

@root_app.route('/favicon.ico')
def root_favicon():
    return send_from_directory(
        os.path.join(base_dir, 'appl', 'static', 'img'),
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon'
    )

# iOS cerca apple-touch-icon all'origine del sito (non sotto /static).
# Esponiamo gli alias per evitare il fallback "S" quando si "Aggiungi a Home".
@root_app.route('/apple-touch-icon.png')
@root_app.route('/apple-touch-icon-precomposed.png')
@root_app.route('/apple-touch-icon-180x180.png')
@root_app.route('/apple-touch-icon-180x180-precomposed.png')
def root_apple_touch_icon():
    return send_from_directory(
        os.path.join(base_dir, 'appl', 'static', 'img'),
        'apple-touch-icon.png',
        mimetype='image/png'
    )

@root_app.route('/')
def root():
    return redirect(url_for('landing_web'))

# Costruzione mounts e cache dei child
mounts = {}
children = {}
for idx, uri in pool.items():
    child = create_app(uri)
    child.secret_key = secret
    child.config["HIDE_PRINTER_IP"] = True
    child.config["HIDE_CASSA"] = True

    @child.context_processor
    def inject_hide_cassa():
        return {'hide_cassa': True}
    
    creds = unipile_creds_for(idx)
    creds["HIDE_CASSA"] = "1"

    # Aggiungi la route mancante per client_info ai child
    @child.route('/settings/api/client_info/<int:client_id>')
    def client_info_wsgi(client_id):
        from appl.models import Client
        client = db.session.get(Client, client_id)
        if not client:
            return jsonify({})
        return jsonify({
            'cliente_nome': client.cliente_nome,
            'cliente_cognome': client.cliente_cognome,
            'cliente_cellulare': client.cliente_cellulare,
            'cliente_email': client.cliente_email,
            'note': client.note
        })
    
    @child.route('/settings/api/update_client_info', methods=['POST'])
    def update_client_info_wsgi():
        from appl.models import Client
        data = request.get_json(silent=True) or {}
        client_id = data.get('client_id')
        if not client_id:
            return jsonify(success=False, error="client_id mancante"), 400

        try:
            client = db.session.get(Client, int(client_id))
            if not client:
                return jsonify(success=False, error="cliente non trovato"), 404

            nome = data.get('cliente_nome')
            cognome = data.get('cliente_cognome')
            if nome is not None:
                client.cliente_nome = nome.strip()
            if cognome is not None:
                client.cliente_cognome = cognome.strip()

            db.session.commit()
            return jsonify(success=True, cliente_nome=client.cliente_nome, cliente_cognome=client.cliente_cognome), 200

        except Exception as e:
            db.session.rollback()
            child.logger.exception("update_client_info error")
            return jsonify(success=False, error="errore interno"), 500

    @child.route('/settings/api/update_client_phone', methods=['POST'])
    def update_client_phone_wsgi():
        from appl.models import Client
        data = request.get_json()
        client = db.session.get(Client, data.get('client_id'))
        if client:
            client.cliente_cellulare = data.get('phone', '')
            db.session.commit()
            return jsonify(success=True, phone=client.cliente_cellulare)
        return jsonify(success=False), 404

    @child.route('/settings/api/update_client_email', methods=['POST'])
    def update_client_email_wsgi():
        from appl.models import Client
        data = request.get_json()
        client = db.session.get(Client, data.get('client_id'))
        if client:
            client.cliente_email = data.get('email', '')
            db.session.commit()
            return jsonify(success=True, email=client.cliente_email)
        return jsonify(success=False), 404
    
    @child.route('/settings/api/update_client_note', methods=['POST'])
    def update_client_note_wsgi():
        from appl.models import Client
        data = request.get_json()
        client = db.session.get(Client, data.get('client_id'))
        if client:
            client.note = data.get('note', '')
            db.session.commit()
            return jsonify(success=True, note=client.note)
        return jsonify(success=False), 404

    def with_db_cookie(app, idx_local, secure=False):
        def _wrap(environ, start_response):
            def sr(status, headers, exc_info=None):
                cookie = "dbidx=" + str(idx_local) + "; Path=/; SameSite=Lax"
                if secure:
                    cookie += "; Secure"
                headers.append(('Set-Cookie', cookie))
                return start_response(status, headers, exc_info)
            return app(environ, sr)
        return _wrap

    wrapped = with_request_env(child, creds)
    wrapped = with_db_cookie(wrapped, idx, secure=use_https)
    wrapped = block_paths(wrapped, ("/cassa", "/cassa.html"))
    wrapped = fix_delete_method_middleware(wrapped)
    mounts[f"/s/{idx}"] = wrapped
    children[idx] = child

application = DispatcherMiddleware(root_app, mounts)
app = application

@root_app.route('/landing-web', methods=['GET', 'POST'])
def landing_web():
    error = None
    ip = request.remote_addr or 'unknown'

    # POST: tentativo di login cross-tenant
    if request.method == 'POST':
        if _root_is_locked(ip):
            error = 'Troppi tentativi. Riprova tra poco.'
        else:
            username = (request.form.get('username') or '').strip()
            password = request.form.get('password', '')
            matches = find_user_in_all_tenants(username, password)
            if matches:
                session.clear()
                session['root_user'] = username
                session['root_allowed'] = matches  # [{idx, user_id, label}, ...]
                session.permanent = False
                # Se è autorizzato a un solo negozio: redirect diretto con auto-login
                if len(matches) == 1:
                    only = matches[0]
                    token = autologin_issue(only['idx'], only['user_id'])
                    resp = redirect(f"/s/{only['idx']}/?_autologin={token}", code=302)
                    cookie = f"dbidx={only['idx']}; Path=/; SameSite=Lax"
                    if use_https:
                        cookie += "; Secure"
                    resp.headers.add('Set-Cookie', cookie)
                    return resp
                return redirect(url_for('landing_web'))
            else:
                _root_record_failure(ip)
                error = 'Credenziali non valide.'

    # GET: se loggato a livello root, mostra solo i negozi autorizzati
    root_user = session.get('root_user')
    allowed = session.get('root_allowed') or []
    if root_user and allowed:
        links = [{
            'id': str(m['idx']),
            'label': m['label'],
            'url': f"/select-db/{m['idx']}",
        } for m in allowed]
        return render_template('landing_web.html',
                               db_links=links,
                               root_user=root_user,
                               hide_cassa=True)

    # Altrimenti: form di login
    return render_template('landing_web.html',
                           db_links=None,
                           root_user=None,
                           login_error=error,
                           hide_cassa=True)


@root_app.route('/landing-logout')
def landing_logout():
    session.pop('root_user', None)
    session.pop('root_allowed', None)
    return redirect(url_for('landing_web'))


@root_app.route('/select-db/<idx>')
def select_db(idx):
    if not idx.isdigit() or int(idx) not in pool:
        return redirect(url_for('landing_web'))
    idx_int = int(idx)
    # Verifica che l'utente root sia autorizzato a questo negozio
    allowed = session.get('root_allowed') or []
    match = next((m for m in allowed if int(m.get('idx', -1)) == idx_int), None)
    if not match:
        return redirect(url_for('landing_web'))
    # Emetti token monouso e redirigi al child con auto-login
    token = autologin_issue(idx_int, int(match['user_id']))
    resp = redirect(f"/s/{idx}/?_autologin={token}", code=302)
    cookie = "dbidx=" + idx + "; Path=/; SameSite=Lax"
    if use_https:
        cookie += "; Secure"
    resp.headers.add('Set-Cookie', cookie)
    return resp

import time as _time_mod_wsgi

OWNER_SESSION_MINUTES = 15

def _mask_uri(uri):
    """Maschera la password nella URI del database."""
    try:
        p = urlparse(uri)
        if p.password:
            masked = p._replace(netloc=p.netloc.replace(p.password, '****'))
            return masked.geturl()
        return uri
    except Exception:
        return uri

_BILLING_JSON = os.path.join(os.path.dirname(__file__), 'owner_billing.json')
_BILLING_DEFAULTS = {
    'activation_date': None,
    'contract_start_date': None,
    'starter_expiry_date': None,
    'starter_total': None,
    'saas_monthly_amount': None,
    'saas_next_renewal': None,
    'max_payment_days': 15,        # giorni entro cui il pagamento è "in attesa" (giallo)
    'is_owner_db': False,          # True = database dell'owner, mai fatturabile, sempre verde
    'fiscozen_contact_id': None,   # placeholder per API FiscoZen
    'revolut_account_ref': None,   # placeholder per API Revolut
    'invoices': [],
    'payments': [],
}

def _load_billing():
    try:
        with open(_BILLING_JSON, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}

def _save_billing(data):
    with open(_BILLING_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _billing_entry(billing, idx):
    key = str(idx)
    if key not in billing:
        billing[key] = dict(_BILLING_DEFAULTS)
        billing[key]['invoices'] = []
        billing[key]['payments'] = []
    return billing[key]

def _compliance_status(entry):
    """
    ⚪ unconfigured : contratto non partito o nessuna fattura emessa
    🟢 ok           : contratto attivo, importi pagati coprono il fatturato
    🟡 warning      : fattura/e non pagate, ma entro max_payment_days dalla data fattura
    🔴 overdue      : fattura/e non pagate oltre max_payment_days
    """
    if not entry:
        return 'unconfigured'
    if entry.get('is_owner_db'):
        return 'owner'
    if not entry.get('activation_date'):
        return 'unconfigured'
    invoices = entry.get('invoices', [])
    if not invoices:
        return 'unconfigured'
    total_invoiced = sum(float(i.get('amount', 0)) for i in invoices)
    total_paid = sum(float(p.get('amount', 0)) for p in entry.get('payments', []))
    if round(total_paid - total_invoiced, 2) >= 0:
        return 'ok'
    # Saldo residuo: controlla se qualche fattura non pagata è scaduta
    from datetime import date as _d
    today = _d.today()
    max_days = int(entry.get('max_payment_days') or 15)
    for inv in invoices:
        if not inv.get('paid'):
            try:
                inv_date = _d.fromisoformat(inv.get('date', ''))
                if (today - inv_date).days > max_days:
                    return 'overdue'
            except (ValueError, TypeError):
                pass
    return 'warning'

def _write_env_var(key, value):
    """Aggiunge o aggiorna una variabile KEY=VALUE nel file .env attivo."""
    env_path = next((p for p in env_candidates if os.path.isfile(p)), os.path.join(base_dir, '.env'))
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        content = ''
    pattern = re.compile(rf'^\s*{re.escape(key)}\s*=.*$', re.MULTILINE)
    new_line = f'{key}={value}'
    if pattern.search(content):
        content = pattern.sub(new_line, content)
    else:
        if content and not content.endswith('\n'):
            content += '\n'
        content += new_line + '\n'
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write(content)

def _require_owner_auth():
    if not session.get('owner_auth'):
        return False
    if _time_mod_wsgi.time() > session.get('owner_expiry', 0):
        session.pop('owner_auth', None)
        return False
    return True

@root_app.route('/owner-login', methods=['GET', 'POST'])
def owner_login():
    error = None

    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password', '')

        # Verifica le credenziali su TUTTI i database: basta trovarne uno
        # con un utente owner che abbia username e password corrispondenti.
        authenticated = False
        from werkzeug.security import check_password_hash
        try:
            from argon2 import PasswordHasher
            from argon2 import exceptions as argon2_exc
            ph = PasswordHasher()
        except ImportError:
            ph = None
            argon2_exc = None

        for idx, child in children.items():
            try:
                with child.app_context():
                    from appl.models import User
                    user = User.query.filter_by(username=username).first()
                    if user and user.ruolo.value == 'owner':
                        valid = False
                        if ph:
                            try:
                                valid = ph.verify(user.password, password)
                            except Exception:
                                valid = check_password_hash(user.password, password)
                        else:
                            valid = check_password_hash(user.password, password)
                        if valid:
                            authenticated = True
                            break
            except Exception:
                continue

        if authenticated:
            session['owner_auth'] = True
            session['owner_expiry'] = _time_mod_wsgi.time() + OWNER_SESSION_MINUTES * 60
            return redirect(url_for('owner_setup'))
        else:
            error = 'Credenziali non valide o utente non owner.'

    return render_template('owner_login.html', error=error)

@root_app.route('/owner-setup')
def owner_setup():
    if not _require_owner_auth():
        return redirect(url_for('landing_web'))

    tenants = []
    for idx, uri in pool.items():
        child = children.get(idx)
        try:
            _p = urlparse(uri)
            _db_name = (_p.path or '/').strip('/').split('/')[-1] or '—'
            _db_user = _p.username or '—'
        except Exception:
            _db_name = _db_user = '—'

        info = {
            'idx': idx,
            'uri_masked': _mask_uri(uri),
            'uri_full': uri,
            'business_name': db_label(uri),
            'db_name': _db_name,
            'db_user': _db_user,
            'localita': '',
            'module_base_enabled': True,
            'module_web_enabled': True,
            'module_pacchetti_enabled': True,
            'module_base_activated_on': None,
            'module_web_activated_on': None,
            'module_pacchetti_activated_on': None,
        }
        if child:
            try:
                with child.app_context():
                    from appl.models import BusinessInfo, OWNER
                    bi = BusinessInfo.query.first()
                    if bi:
                        if bi.business_name:
                            info['business_name'] = bi.business_name
                        info['localita'] = bi.city or ''
                    owner_cfg = OWNER.query.first()
                    if owner_cfg:
                        info['module_base_enabled'] = owner_cfg.module_base_enabled
                        info['module_web_enabled'] = owner_cfg.module_web_enabled
                        info['module_pacchetti_enabled'] = owner_cfg.module_pacchetti_enabled
                        info['module_base_activated_on'] = (
                            owner_cfg.module_base_activated_on.isoformat()
                            if owner_cfg.module_base_activated_on else None
                        )
                        info['module_web_activated_on'] = (
                            owner_cfg.module_web_activated_on.isoformat()
                            if owner_cfg.module_web_activated_on else None
                        )
                        info['module_pacchetti_activated_on'] = (
                            owner_cfg.module_pacchetti_activated_on.isoformat()
                            if owner_cfg.module_pacchetti_activated_on else None
                        )
            except Exception:
                pass
        tenants.append(info)

    billing_all = _load_billing()
    for info in tenants:
        entry = billing_all.get(str(info['idx']), {})
        info['compliance'] = _compliance_status(entry)
        info['is_owner_db'] = bool(entry.get('is_owner_db', False))

    return render_template('owner_setup.html', tenants=tenants)

@root_app.route('/owner-setup/save/<int:db_idx>', methods=['POST'])
def owner_setup_save(db_idx):
    if not _require_owner_auth():
        return jsonify({'error': 'Non autorizzato'}), 401
    if db_idx not in pool:
        return jsonify({'error': 'DB non trovato'}), 404
    child = children.get(db_idx)
    if not child:
        return jsonify({'error': 'App non trovata'}), 404

    data = request.get_json(silent=True) or {}
    try:
        with child.app_context():
            from appl.models import OWNER
            from appl import db as child_db
            from datetime import date as _date
            owner_cfg = OWNER.query.first()
            if not owner_cfg:
                owner_cfg = OWNER()
                child_db.session.add(owner_cfg)
            owner_cfg.module_base_enabled = bool(data.get('module_base_enabled', True))
            owner_cfg.module_web_enabled = bool(data.get('module_web_enabled', True))
            owner_cfg.module_pacchetti_enabled = bool(data.get('module_pacchetti_enabled', True))
            for field in ('module_base_activated_on', 'module_web_activated_on',
                          'module_pacchetti_activated_on'):
                val = data.get(field)
                if val:
                    try:
                        setattr(owner_cfg, field, _date.fromisoformat(val))
                    except (ValueError, AttributeError):
                        pass
                else:
                    setattr(owner_cfg, field, None)
            if not owner_cfg.module_web_enabled:
                from appl.models import BusinessInfo as _BI, Operator as _Op
                bi = _BI.query.first()
                if bi:
                    bi.whatsapp_morning_reminder_enabled = False
                child_db.session.query(_Op).filter_by(is_deleted=False).update(
                    {'notify_turni_via_whatsapp': False}
                )
            child_db.session.commit()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@root_app.route('/owner-setup/reveal-password/<int:db_idx>', methods=['POST'])
def owner_setup_reveal_password(db_idx):
    if not _require_owner_auth():
        return jsonify({'error': 'Non autorizzato'}), 401
    if db_idx not in pool:
        return jsonify({'error': 'DB non trovato'}), 404
    return jsonify({'uri': pool.get(db_idx, '')})

@root_app.route('/owner-setup/add-tenant', methods=['POST'])
def owner_setup_add_tenant():
    if not _require_owner_auth():
        return jsonify({'error': 'Non autorizzato'}), 401

    data = request.get_json(silent=True) or {}
    business_name = (data.get('business_name') or '').strip()
    city = (data.get('city') or '').strip()
    uri = (data.get('uri') or '').strip()

    if not business_name:
        return jsonify({'error': 'Nome negozio obbligatorio'}), 400
    if not uri or not uri.startswith('postgresql'):
        return jsonify({'error': 'URI PostgreSQL non valida (deve iniziare con postgresql://)'}), 400
    if uri in pool.values():
        return jsonify({'error': 'Questa URI è già configurata'}), 400

    next_idx = max(pool.keys(), default=0) + 1

    # 1. Crea child app e inizializza schema
    try:
        new_child = create_app(uri)
        new_child.secret_key = secret
        new_child.config['HIDE_PRINTER_IP'] = True
        new_child.config['HIDE_CASSA'] = True
    except Exception as e:
        return jsonify({'error': f'Errore creazione app: {str(e)}'}), 500

    try:
        with new_child.app_context():
            db.create_all()
            from appl.models import BusinessInfo, OWNER
            from datetime import date as _date, time as _time

            if not BusinessInfo.query.first():
                bi = BusinessInfo(
                    business_name=business_name,
                    city=city or None,
                    opening_time=_time(9, 0),
                    closing_time=_time(19, 0),
                )
                db.session.add(bi)

            if not OWNER.query.first():
                today = _date.today()
                owner_cfg = OWNER(
                    module_base_enabled=True,
                    module_web_enabled=True,
                    module_pacchetti_enabled=True,
                    module_base_activated_on=today,
                    module_web_activated_on=today,
                    module_pacchetti_activated_on=today,
                )
                db.session.add(owner_cfg)

            # Copia l'utente owner (Alessio) da un database esistente
            from appl.models import User, RuoloUtente
            if not User.query.first():
                owner_source = None
                for _existing_child in children.values():
                    try:
                        with _existing_child.app_context():
                            from appl.models import User as _U, RuoloUtente as _R
                            _u = _U.query.filter_by(ruolo=_R.owner).first()
                            if _u:
                                owner_source = (_u.username, _u.password)
                                break
                    except Exception:
                        pass
                if owner_source:
                    db.session.add(User(
                        username=owner_source[0],
                        password=owner_source[1],
                        ruolo=RuoloUtente.owner,
                    ))

            db.session.commit()
    except Exception as e:
        return jsonify({'error': f'Errore inizializzazione DB: {str(e)}'}), 500

    # 2. Scrivi nel .env
    try:
        _write_env_var(f'SQLALCHEMY_DATABASE_URI{next_idx}', uri)
    except Exception as e:
        return jsonify({'error': f'Errore scrittura .env: {str(e)}'}), 500

    # 3. Registra context processor e monta il child nel dispatcher (senza riavvio)
    @new_child.context_processor
    def _inject_hide_cassa():
        return {'hide_cassa': True}

    creds = unipile_creds_for(next_idx)
    creds['HIDE_CASSA'] = '1'
    wrapped = with_request_env(new_child, creds)
    wrapped = with_db_cookie(wrapped, next_idx, secure=use_https)
    wrapped = block_paths(wrapped, ('/cassa', '/cassa.html'))
    wrapped = fix_delete_method_middleware(wrapped)

    pool[next_idx] = uri
    children[next_idx] = new_child
    mounts[f'/s/{next_idx}'] = wrapped

    # 4. Prepara dati risposta
    try:
        _p = urlparse(uri)
        db_name = (_p.path or '/').strip('/').split('/')[-1] or '—'
        db_user = _p.username or '—'
    except Exception:
        db_name = db_user = '—'

    from datetime import date as _d2
    today_str = _d2.today().isoformat()

    return jsonify({
        'ok': True,
        'idx': next_idx,
        'business_name': business_name,
        'localita': city,
        'db_name': db_name,
        'db_user': db_user,
        'uri_masked': _mask_uri(uri),
        'module_base_activated_on': today_str,
        'module_web_activated_on': today_str,
        'module_pacchetti_activated_on': today_str,
    })


@root_app.route('/owner-setup/billing/<int:db_idx>', methods=['GET'])
def owner_billing_get(db_idx):
    if not _require_owner_auth():
        return jsonify({'error': 'Non autorizzato'}), 401
    billing = _load_billing()
    entry = dict(_billing_entry(billing, db_idx))
    entry['compliance'] = _compliance_status(entry)
    total_invoiced = sum(float(i.get('amount', 0)) for i in entry.get('invoices', []))
    total_paid = sum(float(p.get('amount', 0)) for p in entry.get('payments', []))
    entry['total_invoiced'] = round(total_invoiced, 2)
    entry['total_paid'] = round(total_paid, 2)
    entry['balance'] = round(total_invoiced - total_paid, 2)
    return jsonify(entry)

@root_app.route('/owner-setup/billing/<int:db_idx>', methods=['POST'])
def owner_billing_save(db_idx):
    if not _require_owner_auth():
        return jsonify({'error': 'Non autorizzato'}), 401
    billing = _load_billing()
    entry = _billing_entry(billing, db_idx)
    data = request.get_json(silent=True) or {}
    for field in ('activation_date', 'contract_start_date', 'starter_expiry_date',
                  'starter_total', 'saas_monthly_amount', 'saas_next_renewal',
                  'max_payment_days', 'is_owner_db', 'fiscozen_contact_id', 'revolut_account_ref'):
        if field in data:
            entry[field] = data[field] or None
    _save_billing(billing)
    return jsonify({'ok': True, 'compliance': _compliance_status(entry)})

@root_app.route('/owner-setup/billing/<int:db_idx>/invoice', methods=['POST'])
def owner_billing_add_invoice(db_idx):
    if not _require_owner_auth():
        return jsonify({'error': 'Non autorizzato'}), 401
    billing = _load_billing()
    entry = _billing_entry(billing, db_idx)
    data = request.get_json(silent=True) or {}
    inv = {
        'id': uuid.uuid4().hex[:10],
        'date': data.get('date', ''),
        'number': data.get('number', ''),
        'description': data.get('description', ''),
        'amount': round(float(data.get('amount', 0)), 2),
        'paid': bool(data.get('paid', False)),
        'fiscozen_id': None,
        'fiscozen_url': None,
    }
    entry['invoices'].append(inv)
    _save_billing(billing)
    return jsonify({'ok': True, 'invoice': inv, 'compliance': _compliance_status(entry)})

@root_app.route('/owner-setup/billing/<int:db_idx>/invoice/<inv_id>', methods=['DELETE'])
def owner_billing_delete_invoice(db_idx, inv_id):
    if not _require_owner_auth():
        return jsonify({'error': 'Non autorizzato'}), 401
    billing = _load_billing()
    entry = _billing_entry(billing, db_idx)
    entry['invoices'] = [i for i in entry['invoices'] if i['id'] != inv_id]
    _save_billing(billing)
    return jsonify({'ok': True, 'compliance': _compliance_status(entry)})

@root_app.route('/owner-setup/billing/<int:db_idx>/invoice/<inv_id>/toggle', methods=['POST'])
def owner_billing_toggle_invoice(db_idx, inv_id):
    if not _require_owner_auth():
        return jsonify({'error': 'Non autorizzato'}), 401
    billing = _load_billing()
    entry = _billing_entry(billing, db_idx)
    for inv in entry['invoices']:
        if inv['id'] == inv_id:
            inv['paid'] = not inv.get('paid', False)
            break
    _save_billing(billing)
    return jsonify({'ok': True, 'compliance': _compliance_status(entry)})

@root_app.route('/owner-setup/billing/<int:db_idx>/payment', methods=['POST'])
def owner_billing_add_payment(db_idx):
    if not _require_owner_auth():
        return jsonify({'error': 'Non autorizzato'}), 401
    billing = _load_billing()
    entry = _billing_entry(billing, db_idx)
    data = request.get_json(silent=True) or {}
    pay = {
        'id': uuid.uuid4().hex[:10],
        'date': data.get('date', ''),
        'amount': round(float(data.get('amount', 0)), 2),
        'method': data.get('method', ''),
        'reference': data.get('reference', ''),
        'revolut_id': None,
    }
    entry['payments'].append(pay)
    _save_billing(billing)
    return jsonify({'ok': True, 'payment': pay, 'compliance': _compliance_status(entry)})

@root_app.route('/owner-setup/billing/<int:db_idx>/payment/<pay_id>', methods=['DELETE'])
def owner_billing_delete_payment(db_idx, pay_id):
    if not _require_owner_auth():
        return jsonify({'error': 'Non autorizzato'}), 401
    billing = _load_billing()
    entry = _billing_entry(billing, db_idx)
    entry['payments'] = [p for p in entry['payments'] if p['id'] != pay_id]
    _save_billing(billing)
    return jsonify({'ok': True, 'compliance': _compliance_status(entry)})


@root_app.route('/owner-logout')
def owner_logout():
    session.pop('owner_auth', None)
    session.pop('owner_db_idx', None)
    session.pop('owner_expiry', None)
    return redirect(url_for('landing_web'))

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5050"))
    print(f"Avvio server su http://127.0.0.1:{port}/landing-web")
    serve(application, host='127.0.0.1', port=port, threads=16)