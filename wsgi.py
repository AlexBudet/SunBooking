# wsgi.py - WSGI entry point per SunBooking con supporto multi-database
import os
import re
from urllib.parse import urlparse
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, redirect, url_for, request, session, send_from_directory
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from waitress import serve

# Thread di waitress: quante richieste l'applicazione puo' servire davvero in
# parallelo. Non e' un dettaglio del server ma IL numero da cui dipende la
# capienza: con 16 thread e una richiesta che dura in media D secondi, il tetto
# teorico e' 16/D richieste al secondo. Sta qui in cima, e non sepolto dentro
# la serve() in fondo al file, perche' il pannello consumi lo legge per
# calcolare quanti negozi si reggono.
THREAD_SERVER = 16
from appl import create_app, db
from appl.models import BusinessInfo
from appl.autologin import issue_token as autologin_issue
import time as time_mod
import json
import uuid
from collections import deque
from threading import Lock
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
base_static = os.path.join(base_dir, 'appl', 'static')
root_app = Flask('sunbooking_root',
                 template_folder=base_templates,
                 static_folder=base_static,
                 static_url_path='/static')
root_app.secret_key = secret
root_app.config['SESSION_COOKIE_HTTPONLY'] = True
root_app.config['SESSION_COOKIE_SECURE'] = use_https
root_app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# La root_app non ha Flask-WTF inizializzato: forniamo un csrf_token() no-op
# per i template che lo includono (landing_web.html, owner_login.html).
root_app.jinja_env.globals['csrf_token'] = lambda: ''

@root_app.before_request
def root_redirect_to_selected_db():
    path = request.path or '/'
    if path in ('/', '/landing-web', '/landing-logout') or path.startswith('/select-db/') or path.startswith('/s/') or path.startswith('/owner') or path.startswith('/static/') or path.startswith('/apple-touch-icon'):
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
                    try:
                        role_val = user.ruolo.value if hasattr(user.ruolo, 'value') else str(user.ruolo)
                    except Exception:
                        role_val = ''
                    matches.append({'idx': int(idx), 'user_id': int(user.id), 'label': label, 'role': role_val})
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
    # tenant_idx: da qui il child ricava nome del cookie, percorso e chiave di
    # firma tutti suoi. Senza, i negozi condividerebbero la sessione.
    child = create_app(uri, tenant_idx=idx)
    # NB: la chiave la imposta create_app derivandola per tenant. Riassegnare
    # qui "secret" a tutti rimetterebbe la chiave in comune e riaprirebbe il
    # buco: si tocca solo se manca SECRET_KEY nell'ambiente.
    if not os.getenv('SECRET_KEY'):
        child.secret_key = secret
    # Marchiamo i child come "cloud": serve al context processor per decidere
    # se nascondere la sezione Cassa quando l'owner del tenant non l'ha
    # esplicitamente abilitata da Tools/Info Azienda.
    child.config["IS_CLOUD"] = True

    @child.context_processor
    def inject_cloud_cassa_flags():
        """Per ogni request del child cloud, calcola hide_cassa leggendo il
        flag OWNER.cassa_enabled_on_web dal DB del tenant corrente.
        Logica:
          - IS_CLOUD False  -> hide_cassa = False (start.py: sempre visibile)
          - IS_CLOUD True   -> hide_cassa = NOT cassa_enabled_on_web
        Se la lettura DB fallisce (es. tabella non ancora migrata),
        fallback prudente: hide_cassa = True. La query e' leggera (singola
        riga, indice PK) ma viene fatta una volta per request; se diventa un
        collo di bottiglia si puo' cachare in flask.g.
        """
        hide = True
        cassa_enabled = False
        try:
            from appl.models import OWNER as _OWNER
            cfg = _OWNER.query.first()
            if cfg is not None:
                cassa_enabled = bool(getattr(cfg, 'cassa_enabled_on_web', False))
                hide = not cassa_enabled
        except Exception:
            # Tabella/colonna mancante o errore DB: tieni Cassa nascosta.
            hide = True
            cassa_enabled = False
        return {
            'hide_cassa': hide,
            'cassa_enabled_on_web': cassa_enabled,
            'is_cloud': True,
        }

    creds = unipile_creds_for(idx)

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
        is_owner = any((m.get('role') or '').lower() == 'owner' for m in allowed)
        return render_template('landing_web.html',
                               db_links=links,
                               root_user=root_user,
                               is_owner=is_owner)

    # Altrimenti: form di login
    return render_template('landing_web.html',
                           db_links=None,
                           root_user=None,
                           login_error=error)


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

# Rate limit per /owner-login (in-memory, sliding window per IP).
# Dopo MAX tentativi falliti nella finestra, l'IP è bloccato finché il più
# vecchio tentativo non esce dalla finestra.
_OWNER_LOGIN_MAX_ATTEMPTS = 5
_OWNER_LOGIN_WINDOW_SECONDS = 10 * 60
_OWNER_LOGIN_ATTEMPTS: dict[str, deque] = {}
_OWNER_LOGIN_LOCK = Lock()

def _owner_login_check_rate(ip: str):
    """Ritorna (allowed, retry_after_seconds)."""
    now = _time_mod_wsgi.time()
    cutoff = now - _OWNER_LOGIN_WINDOW_SECONDS
    with _OWNER_LOGIN_LOCK:
        dq = _OWNER_LOGIN_ATTEMPTS.get(ip)
        if not dq:
            return True, 0
        while dq and dq[0] < cutoff:
            dq.popleft()
        if not dq:
            _OWNER_LOGIN_ATTEMPTS.pop(ip, None)
            return True, 0
        if len(dq) >= _OWNER_LOGIN_MAX_ATTEMPTS:
            retry = int(dq[0] + _OWNER_LOGIN_WINDOW_SECONDS - now)
            return False, max(retry, 1)
        return True, 0

def _owner_login_record_failure(ip: str):
    now = _time_mod_wsgi.time()
    with _OWNER_LOGIN_LOCK:
        _OWNER_LOGIN_ATTEMPTS.setdefault(ip, deque()).append(now)

def _owner_login_clear(ip: str):
    with _OWNER_LOGIN_LOCK:
        _OWNER_LOGIN_ATTEMPTS.pop(ip, None)

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
    'einvoice_customer_id': None,  # id cliente presso il provider di fatturazione (OpenAPI)
    'payment_customer_ref': None,  # riferimento cliente presso il provider di pagamenti
    'invoices': [],
    'payments': [],
}

# ── Storage della fatturazione ────────────────────────────────────────────
# La forma dei dati resta quella del vecchio JSON: un dict con chiave str(idx)
# e dentro i campi di _BILLING_DEFAULTS piu' le liste invoices/payments. Cosi'
# _compliance_status(), owner_setup() e tutte le rotte /owner-setup/billing/*
# non cambiano di una riga: cambia solo DOVE i dati vengono letti e scritti.
#
# Se REGISTRY_DATABASE_URI non e' configurata si continua a usare il file, che
# resta anche come rete di sicurezza durante il passaggio.

# Alzato al primo fallimento di lettura del registro: serve solo a non
# ripetere lo stack trace completo a ogni richiesta.
_REGISTRY_READ_FAILED = False


def _registry_on():
    try:
        from appl.registry_models import registry_enabled
        return registry_enabled()
    except Exception:
        return False


def _iso(d):
    return d.isoformat() if d is not None else None


def _tenant_da_cancellare():
    """Negozi cessati per cui e' scaduto il periodo di conservazione.

    L'art. 20.1.c del contratto concede 30 giorni dalla cessazione perche' il
    Cliente esporti i suoi dati; scaduti quelli, i dati vanno cancellati.
    La cancellazione e' MANUALE: qui si produce solo il promemoria, perche'
    una cancellazione automatica di un intero database e' esattamente il tipo
    di automatismo che non si vuole.
    """
    from datetime import datetime, timedelta, timezone
    if not _registry_on():
        return []
    try:
        from appl.registry_models import registry_session, Tenant
        limite = datetime.now(timezone.utc) - timedelta(days=GIORNI_CONSERVAZIONE)
        out = []
        with registry_session() as s:
            righe = (s.query(Tenant)
                      .filter(Tenant.terminated_at.isnot(None),
                              Tenant.purged_at.is_(None),
                              Tenant.terminated_at <= limite)
                      .order_by(Tenant.terminated_at)
                      .all())
            for t in righe:
                giorni = (datetime.now(timezone.utc) - t.terminated_at).days
                out.append({
                    'id': t.id,
                    'idx': t.idx,
                    'business_name': t.business_name,
                    'cessato_il': t.terminated_at.date().isoformat(),
                    'giorni': giorni,
                })
        return out
    except Exception:
        root_app.logger.warning("[registry] elenco cancellazioni non leggibile")
        return []


@root_app.route('/owner-setup/purged/<int:tenant_id>', methods=['POST'])
def owner_setup_purged(tenant_id):
    """Segna che la cancellazione dei dati e' stata eseguita.

    Non cancella niente: registra soltanto la data. Serve a far sparire
    l'avviso e, soprattutto, a poter dimostrare QUANDO si e' adempiuto.
    """
    if not _require_owner_auth():
        return jsonify({'error': 'Non autorizzato'}), 401
    if not _registry_on():
        return jsonify({'error': 'Registro non disponibile'}), 503
    from datetime import datetime, timezone
    try:
        from appl.registry_models import registry_session, Tenant
        with registry_session() as s:
            t = s.query(Tenant).filter_by(id=tenant_id).one_or_none()
            if t is None:
                return jsonify({'error': 'Negozio non trovato'}), 404
            t.purged_at = datetime.now(timezone.utc)
            nome = t.business_name
        root_app.logger.info("[gdpr] dati di '%s' segnati come cancellati", nome)
        return jsonify({'ok': True})
    except Exception as e:
        root_app.logger.exception("[gdpr] impossibile segnare la cancellazione")
        return jsonify({'error': str(e)}), 500


# I tre moduli che il PREMIUM porta con se'. Il BASE non e' in lista: quello
# c'e' sempre e non dipende dal piano sottoscritto.
MODULI_EXTRA = ('web', 'pacchetti', 'solarium')


def _contratto_tenant(idx):
    """Piano e stato del contratto di un negozio, IN QUESTO MOMENTO.

    Torna sempre un dizionario, mai None: il pannello deve poter scrivere
    "nessun contratto" senza confonderlo con "registro irraggiungibile".

        piano               'standard' | 'premium' | 'custom' | None
        status              lo stato del contratto, com'e' nel registro
        extra_ammessi       se i tre moduli aggiuntivi sono consentiti
        extra_da_accendere  se vanno accesi da soli alla prima occasione
        etichetta           cosa scrivere nella colonna STATO del pannello

    Lo status prima veniva ignorato, e conta: `contract.status` ammette
    'draft', 'ready', 'signed', 'void'. Un premium ancora da firmare non e'
    un premium, e accendere i moduli su una bozza vuol dire regalarli.

    L'asimmetria fra i due casi e' voluta:
      - lo STANDARD blocca i moduli QUALUNQUE sia lo status: non si concede
        mai piu' di quello che c'e' scritto nel contratto;
      - il PREMIUM li accende SOLO se firmato: non si concede prima del tempo.

    Registro spento o irraggiungibile: nessun vincolo e nessuna forzatura. E'
    il caso dei tre database dell'owner, che un contratto non ce l'hanno, ed
    e' anche la scelta prudente quando il registro non risponde - meglio
    lasciare il pannello com'e' che spegnere i moduli di un negozio per un
    problema di connessione.
    """
    vuoto = {'piano': None, 'status': None, 'extra_ammessi': True,
             'extra_da_accendere': False, 'etichetta': None}
    if not _registry_on():
        return vuoto
    try:
        from appl.registry_models import registry_session, Tenant, Contract, Billing
        with registry_session() as s:
            # I DATABASE NOSTRI (suncity, sunexp3, sunbookingdb) non sono
            # clienti: li usiamo in negozio con TUTTI i moduli accesi. Non
            # devono poter essere spenti da questa logica nemmeno per sbaglio -
            # per esempio se un contratto finisse agganciato a uno di loro.
            # `extra_da_accendere` a True e' la rete di sicurezza: se un giorno
            # si ritrovassero tutti e tre spenti, tornano su da soli.
            owner_db = (s.query(Billing.is_owner_db)
                         .join(Tenant, Tenant.id == Billing.tenant_id)
                         .filter(Tenant.idx == idx)
                         .first())
            if owner_db and owner_db[0]:
                nostro = dict(vuoto)
                nostro['extra_da_accendere'] = True
                nostro['etichetta'] = 'database nostro'
                return nostro

            row = (s.query(Contract.price_plan, Contract.status)
                    .join(Tenant, Tenant.id == Contract.tenant_id)
                    .filter(Tenant.idx == idx)
                    .order_by(Contract.id.desc())
                    .first())
    except Exception:
        root_app.logger.warning("[registry] contratto del tenant %s non leggibile", idx)
        return vuoto
    if not row:
        return vuoto

    piano = (row[0] or '').strip().lower() or None
    status = (row[1] or '').strip().lower() or None
    firmato = (status == 'signed')
    coda = '' if firmato else ' - da firmare'

    if piano == 'standard':
        return {'piano': 'standard', 'status': status, 'extra_ammessi': False,
                'extra_da_accendere': False, 'etichetta': 'BASE' + coda}
    if piano in ('premium', 'custom'):
        nome = 'PREMIUM' if piano == 'premium' else 'PREMIUM - prezzo concordato'
        return {'piano': piano, 'status': status, 'extra_ammessi': True,
                'extra_da_accendere': firmato, 'etichetta': nome + coda}

    fuori = dict(vuoto)
    fuori['status'] = status
    fuori['etichetta'] = 'contratto senza piano'
    return fuori


def _spegni_invii_automatici():
    """Senza il modulo WEB non partono ne' il memo mattutino ne' le notifiche
    dei turni. Lasciarli accesi vorrebbe dire continuare a mandare WhatsApp
    per conto di un negozio che quel modulo non ce l'ha. Da chiamare DENTRO
    l'app context del tenant."""
    from appl.models import BusinessInfo as _BI, Operator as _Op
    from appl import db as child_db
    bi = _BI.query.first()
    if bi:
        bi.whatsapp_morning_reminder_enabled = False
    child_db.session.query(_Op).filter_by(is_deleted=False).update(
        {'notify_turni_via_whatsapp': False}
    )


def _applica_regole_moduli(owner_cfg, contratto, richiesti=None):
    """Porta i flag `module_*` di OWNER a quello che il contratto consente.

    `richiesti`: i quattro booleani arrivati dal pannello quando si preme
    Salva, oppure None per dire "tieni quelli che ci sono" - cioe' la semplice
    apertura della pagina.

    Ritorna la lista dei moduli cambiati, vuota quando non c'era niente da
    fare: serve al chiamante per decidere se committare e cosa scrivere nel
    log. NON committa: il commit e' di chi ha aperto l'app context.

    Questa funzione e' l'unico posto in cui si decide se un modulo e' acceso.
    Il pannello mostra il risultato, non lo calcola: un controllo che vive
    solo nel browser lo aggira chiunque sappia aprire la console.
    """
    from datetime import date as _date

    attuali = {m: bool(getattr(owner_cfg, 'module_%s_enabled' % m))
               for m in ('base',) + MODULI_EXTRA}
    voluti = dict(attuali)
    if richiesti is not None:
        voluti.update({m: bool(v) for m, v in richiesti.items() if m in voluti})

    if not contratto.get('extra_ammessi', True):
        # Contratto BASE: i moduli aggiuntivi non esistono. Non "disabilitati
        # nel pannello" - spenti nel database del negozio, che e' l'unico
        # posto che la sua applicazione legge davvero.
        for m in MODULI_EXTRA:
            voluti[m] = False
    elif (contratto.get('extra_da_accendere') and richiesti is None
            and not any(attuali[m] for m in MODULI_EXTRA)):
        # PREMIUM firmato e tutti e tre i moduli spenti: e' un cliente che
        # paga il canone alto per non avere niente in piu' di un BASE. E' lo
        # stato in cui si trova un negozio appena passato al premium, e si
        # sistema da solo alla prima apertura del pannello.
        #
        # La condizione richiede che siano spenti TUTTI E TRE apposta: da qui
        # in avanti spegnerne uno (il solarium a chi non ha lampade) resta una
        # scelta dell'owner e non viene piu' toccata.
        for m in MODULI_EXTRA:
            voluti[m] = True

    cambiati = []
    oggi = _date.today()
    for m in ('base',) + MODULI_EXTRA:
        if voluti[m] == attuali[m]:
            continue
        setattr(owner_cfg, 'module_%s_enabled' % m, voluti[m])
        # La data di attivazione non si scrive piu' a mano nel pannello: la
        # tiene il programma. Serve alla fatturazione - da quando quel negozio
        # paga quel modulo - non all'occhio dell'owner, che dal pannello vuole
        # sapere un'altra cosa: se il contratto ADESSO e' base o premium.
        setattr(owner_cfg, 'module_%s_activated_on' % m, oggi if voluti[m] else None)
        cambiati.append(m)

    if not voluti['web'] and ('web' in cambiati or richiesti is not None):
        _spegni_invii_automatici()

    return cambiati


def _load_billing_json():
    try:
        with open(_BILLING_JSON, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}


def _load_billing():
    if not _registry_on():
        return _load_billing_json()
    try:
        from appl.registry_models import (registry_session, Tenant, Billing,
                                          Invoice, Payment)
        out = {}
        with registry_session() as s:
            rows = (s.query(Billing, Tenant)
                     .join(Tenant, Tenant.id == Billing.tenant_id)
                     .filter(Tenant.idx.isnot(None))
                     .all())
            for b, t in rows:
                entry = dict(_BILLING_DEFAULTS)
                entry.update({
                    'activation_date':     _iso(b.activation_date),
                    'contract_start_date': _iso(b.contract_start_date),
                    'starter_expiry_date': _iso(b.starter_expiry_date),
                    'starter_total':       float(b.starter_total) if b.starter_total is not None else None,
                    'saas_monthly_amount': float(b.saas_monthly_amount) if b.saas_monthly_amount is not None else None,
                    'saas_next_renewal':   _iso(b.saas_next_renewal),
                    'max_payment_days':    b.max_payment_days,
                    'is_owner_db':         bool(b.is_owner_db),
                    'einvoice_customer_id': b.einvoice_customer_id,
                    'payment_customer_ref': b.payment_customer_ref,
                    'invoices': [], 'payments': [],
                })
                for i in s.query(Invoice).filter_by(tenant_id=t.id).order_by(Invoice.date).all():
                    entry['invoices'].append({
                        'id': i.id, 'date': _iso(i.date) or '', 'number': i.number or '',
                        'description': i.description or '',
                        'amount': float(i.amount or 0), 'paid': bool(i.paid),
                        'einvoice_id': i.einvoice_id, 'einvoice_url': i.einvoice_url,
                    })
                for p in s.query(Payment).filter_by(tenant_id=t.id).order_by(Payment.date).all():
                    entry['payments'].append({
                        'id': p.id, 'date': _iso(p.date) or '',
                        'amount': float(p.amount or 0), 'method': p.method or '',
                        'reference': p.reference or '', 'provider_payment_id': p.provider_payment_id,
                    })
                out[str(t.idx)] = entry
        return out
    except Exception as e:
        # Un registro irraggiungibile non deve rendere inutilizzabile
        # owner-setup: si ripiega sul file e si annota l'errore.
        # Lo stack trace completo UNA VOLTA SOLA: e' quasi sempre un problema
        # di configurazione (password, host, firewall) e ripeterlo a ogni
        # richiesta rende i log illeggibili proprio quando servono.
        global _REGISTRY_READ_FAILED
        if not _REGISTRY_READ_FAILED:
            _REGISTRY_READ_FAILED = True
            root_app.logger.exception(
                "[registry] lettura fatturazione fallita, uso il JSON. "
                "Questo messaggio non verra' ripetuto per intero.")
        else:
            root_app.logger.warning("[registry] non raggiungibile, uso il JSON (%s)",
                                    type(e).__name__)
        return _load_billing_json()


def _save_billing(data):
    if not _registry_on():
        with open(_BILLING_JSON, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return
    from datetime import date as _date
    from appl.registry_models import (registry_session, Tenant, Billing,
                                      Invoice, Payment)

    def _d(v):
        try:
            return _date.fromisoformat(v) if v else None
        except (ValueError, TypeError):
            return None

    with registry_session() as s:
        for key, entry in data.items():
            try:
                idx = int(key)
            except (TypeError, ValueError):
                continue

            t = s.query(Tenant).filter_by(idx=idx).one_or_none()
            if t is None:
                # Un idx che non e' ancora nel registro: lo si crea con il nome
                # del database, lo stesso ripiego di db_label() in owner_setup.
                t = Tenant(idx=idx, business_name=db_label(pool.get(idx, '')) or f'tenant{idx}',
                           status='active')
                s.add(t)
                s.flush()

            b = s.query(Billing).filter_by(tenant_id=t.id).one_or_none()
            if b is None:
                b = Billing(tenant_id=t.id)
                s.add(b)

            b.activation_date     = _d(entry.get('activation_date'))
            b.contract_start_date = _d(entry.get('contract_start_date'))
            b.starter_expiry_date = _d(entry.get('starter_expiry_date'))
            b.starter_total       = entry.get('starter_total')
            b.saas_monthly_amount = entry.get('saas_monthly_amount')
            b.saas_next_renewal   = _d(entry.get('saas_next_renewal'))
            b.max_payment_days    = int(entry.get('max_payment_days') or 15)
            b.is_owner_db         = bool(entry.get('is_owner_db'))
            b.einvoice_customer_id = entry.get('einvoice_customer_id')
            b.payment_customer_ref = entry.get('payment_customer_ref')

            # Righe figlie riscritte per intero: e' la stessa semantica del
            # vecchio JSON (si salvava tutto il dizionario) e a questi volumi
            # costa meno di un diff riga per riga.
            s.query(Invoice).filter_by(tenant_id=t.id).delete(synchronize_session=False)
            for inv in entry.get('invoices', []):
                s.add(Invoice(
                    id=inv['id'], tenant_id=t.id, date=_d(inv.get('date')),
                    number=inv.get('number') or None,
                    description=inv.get('description') or None,
                    amount=round(float(inv.get('amount') or 0), 2),
                    paid=bool(inv.get('paid')),
                    einvoice_id=inv.get('einvoice_id'),
                    einvoice_url=inv.get('einvoice_url'),
                ))

            s.query(Payment).filter_by(tenant_id=t.id).delete(synchronize_session=False)
            for pay in entry.get('payments', []):
                s.add(Payment(
                    id=pay['id'], tenant_id=t.id, date=_d(pay.get('date')),
                    amount=round(float(pay.get('amount') or 0), 2),
                    method=pay.get('method') or None,
                    reference=pay.get('reference') or None,
                    provider_payment_id=pay.get('provider_payment_id'),
                ))

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
        ip = request.remote_addr or 'unknown'
        allowed, retry = _owner_login_check_rate(ip)
        if not allowed:
            minutes = max(retry // 60, 1)
            error = f'Troppi tentativi falliti. Riprova tra {minutes} min.'
            return render_template('owner_login.html', error=error), 429

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
            _owner_login_clear(ip)
            session['owner_auth'] = True
            session['owner_expiry'] = _time_mod_wsgi.time() + OWNER_SESSION_MINUTES * 60
            return redirect(url_for('owner_setup'))
        else:
            _owner_login_record_failure(ip)
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

        # Il piano si legge PRIMA di aprire il negozio: e' quello che decide
        # cosa mostrare, non il contrario.
        contratto = _contratto_tenant(idx)

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
            'module_solarium_enabled': False,
            'contratto': contratto,
        }
        if child:
            try:
                with child.app_context():
                    from appl.models import BusinessInfo, OWNER
                    from appl import db as child_db
                    bi = BusinessInfo.query.first()
                    if bi:
                        if bi.business_name:
                            info['business_name'] = bi.business_name
                        info['localita'] = bi.city or ''
                    owner_cfg = OWNER.query.first()
                    if owner_cfg:
                        # Il pannello non si limita a MOSTRARE i moduli: prima
                        # di disegnarli li rimette in riga con il contratto.
                        # Senza questo passaggio un negozio passato allo
                        # standard restava con i moduli accesi nel proprio
                        # database - il pannello li faceva vedere spenti e
                        # l'applicazione del cliente continuava a usarli.
                        try:
                            cambiati = _applica_regole_moduli(owner_cfg, contratto)
                            if cambiati:
                                child_db.session.commit()
                                root_app.logger.info(
                                    "[moduli] tenant %s allineato al contratto %s: %s",
                                    idx, contratto.get('piano') or 'assente',
                                    ', '.join(cambiati))
                        except Exception:
                            child_db.session.rollback()
                            root_app.logger.warning(
                                "[moduli] tenant %s: allineamento al contratto non "
                                "riuscito, mostro i valori come stanno", idx,
                                exc_info=True)
                        info['module_base_enabled'] = owner_cfg.module_base_enabled
                        info['module_web_enabled'] = owner_cfg.module_web_enabled
                        info['module_pacchetti_enabled'] = owner_cfg.module_pacchetti_enabled
                        info['module_solarium_enabled'] = owner_cfg.module_solarium_enabled
            except Exception:
                # Un negozio irraggiungibile non deve far sparire la pagina, ma
                # nemmeno passare inosservato: la riga resta con i valori di
                # comodo e il motivo finisce nel log.
                root_app.logger.warning(
                    "[owner-setup] tenant %s non leggibile", idx, exc_info=True)
        tenants.append(info)

    billing_all = _load_billing()
    for info in tenants:
        entry = billing_all.get(str(info['idx']), {})
        info['compliance'] = _compliance_status(entry)
        info['is_owner_db'] = bool(entry.get('is_owner_db', False))

    return render_template('owner_setup.html', tenants=tenants,
                           da_cancellare=_tenant_da_cancellare(),
                           giorni_conservazione=GIORNI_CONSERVAZIONE)

@root_app.route('/owner-setup/monitor')
def owner_monitor():
    """Pannello consumi: una pagina, i dati arrivano dopo via JSON.

    Separare pagina e dati non e' un vezzo: la raccolta interroga ogni tenant e
    puo' arrivare a qualche secondo, mentre Azure Monitor - quando la cache e'
    fredda - fa quattro chiamate HTTP. Servire l'HTML subito e riempirlo dopo
    evita che il pannello sembri bloccato.
    """
    if not _require_owner_auth():
        return redirect(url_for('landing_web'))
    return render_template('owner_monitor.html')


@root_app.route('/owner-setup/monitor/dati')
def owner_monitor_dati():
    """Raccolta vera. Un tenant alla volta, ognuno nel proprio app context.

    Un tenant che non risponde NON fa cadere il pannello: finisce nella lista
    con la propria chiave 'errore' e gli altri si vedono lo stesso. E' il caso
    di un database spento o di un negozio in migrazione, che non deve rendere
    cieco il monitoraggio di tutti gli altri.
    """
    if not _require_owner_auth():
        return jsonify({'errore': 'non autorizzato'}), 403

    try:
        giorni = max(1, min(365, int(request.args.get('giorni', 30))))
    except (TypeError, ValueError):
        giorni = 30

    # A quanti negozi proiettare. Fisso a 100 rispondeva sempre alla domanda
    # piu' lontana; quella che si fa davvero adesso e' "e con dieci?".
    try:
        obiettivo = int(request.args.get('negozi', 10))
    except (TypeError, ValueError):
        obiettivo = 10
    obiettivo = max(10, min(100, round(obiettivo / 10.0) * 10))

    from appl.services import (usage_monitor, usage_projection, azure_monitor,
                               unipile_monitor)

    per_tenant = []
    for idx, uri in pool.items():
        child = children.get(idx)
        voce = {'idx': idx, 'nome': db_label(uri)}
        if not child:
            voce['errore'] = 'tenant non montato'
            per_tenant.append(voce)
            continue
        try:
            with child.app_context():
                from appl.models import BusinessInfo
                try:
                    bi = BusinessInfo.query.first()
                    if bi and bi.business_name:
                        voce['nome'] = bi.business_name
                except Exception:
                    pass
                voce.update(usage_monitor.raccogli(giorni=giorni))
        except Exception as e:
            voce['errore'] = str(e)[:200]
        per_tenant.append(voce)

    # ---- Proiezioni -------------------------------------------------------
    # Tutti gli ingredienti sono MISURATI, non stimati: e' il punto della
    # pagina. L'unica cosa che resta un'ipotesi e' il prezzo, che infatti sta
    # in una variabile d'ambiente e viene dichiarato accanto al risultato.
    validi = [t for t in per_tenant if 'errore' not in t]
    n_tenant = len(validi)

    tetto_pool = 3
    max_conn = 35
    riservate = 0
    conn_server = conn_tenant = 0
    for t in validi:
        p = t.get('pool') or {}
        if p.get('tetto'):
            tetto_pool = p['tetto']
        d = t.get('database') or {}
        if d.get('max_connections'):
            max_conn = d['max_connections']
            riservate = d.get('connessioni_riservate', 0)
        c = d.get('connessioni') or {}
        conn_server = max(conn_server, c.get('del_server') or 0)
        conn_tenant += c.get('del_db') or 0

    # Quanto del server NON e' nostro: l'app di prenotazione ha i propri engine
    # e i propri pool sullo stesso PostgreSQL. Si misura per differenza invece
    # di indovinarlo, perche' indovinarlo e' esattamente il modo in cui si
    # sbaglia una previsione di capienza.
    altre_app = max(0, conn_server - conn_tenant)

    prj_conn = usage_projection.proiezione_connessioni(
        n_tenant, tetto_pool, max_conn,
        connessioni_riservate=riservate, connessioni_altre_app=altre_app)
    prj_conn['connessioni_altre_app_misurate'] = altre_app

    byte_tenant = [t['database']['dimensione_byte'] for t in validi
                   if (t.get('database') or {}).get('dimensione_byte')]

    # Il denominatore dello spazio: prima quello dichiarato a mano, poi quello
    # che Azure sa da se'. Da dentro PostgreSQL non si vede quanto disco c'e'
    # sotto, e senza un tetto "66 MB" non dice niente a nessuno.
    quota = None
    fonte_quota = None
    try:
        quota = int(os.environ.get('AZURE_QUOTA_STORAGE_BYTE', '0')) or None
        if quota:
            fonte_quota = 'AZURE_QUOTA_STORAGE_BYTE'
    except (TypeError, ValueError):
        quota = None
    if not quota:
        try:
            quota = azure_monitor.quota_storage_postgres()
            if quota:
                fonte_quota = 'metrica Azure storage_limit'
        except Exception:
            quota = None
    prj_storage = usage_projection.proiezione_storage(byte_tenant, n_tenant, quota_byte=quota)
    prj_storage['fonte_quota'] = fonte_quota

    # Un tenant che non si riesce a leggere NON entra nella media come se
    # avesse mandato zero messaggi: viene messo da parte e dichiarato. Prima
    # una tabella usage_events mancante diventava uno "0 msg" indistinguibile
    # da un negozio che davvero non manda niente.
    invii_tenant = []
    invii_non_misurati = []
    # I limiti di Azure Communication Services sono "per Subscription": tutti i
    # negozi pescano dallo STESSO tetto. Quindi per ora si SOMMA quello che e'
    # partito nella stessa ora da tutti, e poi si prende l'ora peggiore. Il
    # massimo fra i negozi - che sembra la cosa naturale - sottostimerebbe
    # proprio il caso che fa scattare il 429: tre negozi che mandano insieme.
    #
    # Il picco al MINUTO resta invece il massimo di un singolo negozio: per
    # sommarlo servirebbe la serie al minuto di ogni negozio (43.200 righe per
    # 30 giorni ciascuno), che costa piu' di quanto valga. E' dichiarato come
    # tale nel pannello, non spacciato per il totale.
    # Di ogni picco si porta dietro QUANDO e, dove ha senso, DI CHI.
    # Un "8 su 6" da solo non si puo' nemmeno andare a guardare: non si sa in
    # che negozio e' successo ne' a che ora, e finche' resta nella finestra dei
    # 30 giorni sembra una cosa che sta succedendo adesso.
    # Il "chi" c'e' solo per i picchi al MINUTO, che sono il massimo di un
    # singolo negozio. I picchi ORARI sono la SOMMA di tutti i negozi (i limiti
    # ACS valgono per sottoscrizione): li' un nome sarebbe falso, e resta l'ora.
    picchi_msg = {'whatsapp_ora': 0, 'whatsapp_minuto': 0,
                  'email_ora': 0, 'email_minuto': 0,
                  'whatsapp_minuto_quando': None, 'email_minuto_quando': None,
                  'whatsapp_minuto_chi': None, 'email_minuto_chi': None,
                  'whatsapp_ora_quando': None, 'email_ora_quando': None}

    def _ora_italiana(iso):
        """serie_oraria arriva in UTC senza fuso (AT TIME ZONE 'UTC' nella
        query). L'owner legge l'ora del negozio, non quella di Greenwich."""
        try:
            from zoneinfo import ZoneInfo
            momento = datetime.fromisoformat(iso)
            if momento.tzinfo is None:
                momento = momento.replace(tzinfo=timezone.utc)
            return momento.astimezone(ZoneInfo('Europe/Rome')).strftime('%d/%m alle %H:%M')
        except Exception:
            return None
    per_ora = {}          # (ora, canale) -> totale su tutti i negozi
    for t in validi:
        inv = t.get('invii') or {}
        if inv.get('errore') or 'per_canale' not in inv:
            invii_non_misurati.append(t.get('nome') or t.get('idx'))
            continue
        canali = inv.get('per_canale') or {}
        invii_tenant.append({c: v.get('stima_mensile', 0) for c, v in canali.items()})
        for canale, chiave in (('email', 'email_minuto'), ('whatsapp', 'whatsapp_minuto')):
            dati_canale = canali.get(canale) or {}
            valore = dati_canale.get('picco_al_minuto') or 0
            if valore > picchi_msg[chiave]:
                picchi_msg[chiave] = valore
                picchi_msg[chiave + '_quando'] = dati_canale.get('picco_al_minuto_quando')
                picchi_msg[chiave + '_chi'] = t.get('nome') or ('negozio %s' % t.get('idx'))

        for punto in (inv.get('serie_oraria') or []):
            chiave = (punto.get('ora'), punto.get('canale'))
            per_ora[chiave] = per_ora.get(chiave, 0) + (punto.get('n') or 0)

    for (_ora, canale), totale in per_ora.items():
        if canale == 'email' and totale > picchi_msg['email_ora']:
            picchi_msg['email_ora'] = totale
            picchi_msg['email_ora_quando'] = _ora_italiana(_ora)
        elif canale == 'whatsapp' and totale > picchi_msg['whatsapp_ora']:
            picchi_msg['whatsapp_ora'] = totale
            picchi_msg['whatsapp_ora_quando'] = _ora_italiana(_ora)

    # Da quanti giorni si misura davvero. I totali "al mese" sono estrapolati:
    # se il contatore e' acceso da tre ore, quel numero e' un moltiplicatore
    # applicato al rumore e va detto, non mostrato come una misura.
    osservati = [(t.get('invii') or {}).get('giorni_osservati')
                 for t in validi if (t.get('invii') or {}).get('giorni_osservati')]
    prj_msg = usage_projection.proiezione_messaggi(
        invii_tenant, n_tenant, tenant_obiettivo=obiettivo,
        tenant_non_misurati=len(invii_non_misurati),
        picchi_orari=picchi_msg)
    if osservati:
        # Il MINIMO, non il massimo. I totali sono una SOMMA fra negozi: se uno
        # misura da 30 giorni e un altro da tre ore, il totale vale quanto il
        # piu' debole dei due, perche' il secondo ci mette dentro una
        # estrapolazione x240. Dichiarare i 30 giorni del migliore nasconderebbe
        # esattamente il difetto che il campo esiste per rendere visibile.
        prj_msg['giorni_osservati'] = round(min(osservati), 2)
        prj_msg['giorni_osservati_max'] = round(max(osservati), 2)
        prj_msg['estrapolazione_fragile'] = min(osservati) < 3
    if invii_non_misurati:
        prj_msg['negozi_non_misurati'] = invii_non_misurati

    # Il canone WhatsApp si paga per ACCOUNT COLLEGATO. Quanti ce ne siano lo
    # sa solo Unipile: dedurlo dal numero di negozi e' comodo e sbagliato (il
    # 28/08/2026: 3 negozi, 2 account). Una chiamata sola, con cache di 5 minuti.
    stato_unipile = unipile_monitor.stato_account()
    prj_msg['unipile'] = stato_unipile
    # Il canone si paga sugli account collegati: se Unipile risponde, il costo
    # di oggi si ricalcola sul numero vero invece che sul numero di negozi.
    if stato_unipile.get('stato') == 'ok':
        prj_msg = usage_projection.proiezione_messaggi(
            invii_tenant, n_tenant, tenant_obiettivo=obiettivo,
            tenant_non_misurati=len(invii_non_misurati),
            picchi_orari=picchi_msg,
            account_whatsapp=stato_unipile.get('account_whatsapp'))
        prj_msg['unipile'] = stato_unipile
        if invii_non_misurati:
            prj_msg['negozi_non_misurati'] = invii_non_misurati
        if osservati:
            prj_msg['giorni_osservati'] = round(min(osservati), 2)
            prj_msg['giorni_osservati_max'] = round(max(osservati), 2)
            prj_msg['estrapolazione_fragile'] = min(osservati) < 3

    # Picco SIMULTANEO: si sommano le ore uguali fra i negozi e si prende la
    # peggiore. Sommare invece i picchi di ciascun negozio - che capitano in ore
    # diverse - descriverebbe un'ora mai esistita. Le chiavi sono ISO in UTC
    # proprio perche' devono combaciare fra database diversi.
    ore_http = {}
    for t in validi:
        for punto in ((t.get('traffico') or {}).get('serie') or []):
            ora = punto.get('ora')
            if ora:
                ore_http[ora] = ore_http.get(ora, 0) + (punto.get('richieste') or 0)
    picco_simultaneo = max(ore_http.values()) if ore_http else 0
    richieste_totali = sum(ore_http.values())
    ore_osservate = len(ore_http)
    tenant_con_traffico = sum(1 for t in validi
                              if ((t.get('traffico') or {}).get('serie') or []))

    # Il tetto di richieste al secondo NON e' un numero che Azure pubblica: i
    # piani App Service non dichiarano req/s. Lo si ricava dai due numeri che
    # misuriamo: quante richieste si servono in parallelo (i thread) e quanto
    # dura in media una richiesta. 16 thread e 80 ms l'una fanno 200 req/s.
    # E' un tetto di CONCORRENZA: la CPU puo' saturare prima, e quando le
    # metriche Azure sono configurate il riquadro App Service lo dice.
    ms_totali = sum(((t.get('traffico') or {}).get('ms_medi') or 0) *
                    ((t.get('traffico') or {}).get('richieste_misurate') or 0)
                    for t in validi)
    richieste_misurate = sum((t.get('traffico') or {}).get('richieste_misurate') or 0
                             for t in validi)
    ms_medi = (ms_totali / richieste_misurate) if richieste_misurate else None
    tetto_req_sec = (THREAD_SERVER / (ms_medi / 1000.0)) if ms_medi else None

    prj_traffico = usage_projection.proiezione_traffico(
        picco_simultaneo, richieste_totali, ore_osservate, n_tenant,
        tenant_obiettivo=obiettivo,
        tetto_richieste_secondo=tetto_req_sec,
        tenant_misurati=tenant_con_traffico)
    if ms_medi:
        prj_traffico['ms_medi_misurati'] = round(ms_medi)
        prj_traffico['thread_server'] = THREAD_SERVER
        prj_traffico['richieste_misurate'] = richieste_misurate

    proiezioni = [prj_conn, prj_storage, prj_msg, prj_traffico]

    # ---- Un elenco solo: quanto si sta usando di ogni tetto ---------------
    # L'owner non deve girare quattro schede e mettere insieme i numeri da se'.
    # Ogni riga e' "usato su massimo", con la stessa forma per tutti i limiti,
    # a prescindere dall'unita' di misura.
    def _limite(nome, dettaglio, usato, limite, formato='numero', rischio=''):
        if not limite:
            return None
        pct = 100.0 * usato / limite
        return {
            'nome': nome, 'dettaglio': dettaglio,
            'usato': usato, 'limite': limite, 'formato': formato,
            'percentuale': round(pct, 1),
            'livello': ('superata' if pct >= 100
                        else 'attenzione' if pct >= usage_projection.ATTENZIONE_PCT
                        else 'ok'),
            'rischio': rischio,
        }

    limiti = [
        _limite('Connessioni al database', 'nel momento peggiore',
                prj_conn.get('valore_attuale') or 0,
                prj_conn.get('disponibili_per_app') or 0,
                rischio=('le richieste in attesa falliscono e i negozi vedono '
                         'errori o lentezza')),
        _limite('Spazio database', 'sul disco del server',
                prj_storage.get('totale_byte') or 0, prj_storage.get('quota_byte'),
                formato='byte',
                rischio='il database smette di accettare scritture'),
        _limite('Traffico HTTP', "nell'ora di punta",
                prj_traffico.get('req_sec_picco') or 0,
                prj_traffico.get('tetto_richieste_secondo'),
                formato='reqsec',
                rischio='le richieste si accodano e le pagine rallentano'),
    ]
    # Le soglie dei messaggi hanno gia' questa forma, si convertono e basta.
    for s in (prj_msg.get('soglie') or []):
        limiti.append({
            'nome': s['canale'], 'dettaglio': s['periodo'],
            'usato': s['inviati'], 'limite': s['soglia'], 'formato': 'numero',
            'percentuale': s['percentuale'], 'livello': s['livello'],
            'rischio': s.get('rischio', ''),
        })
    limiti = [x for x in limiti if x]

    return jsonify({
        'tenant': per_tenant,
        'proiezioni': proiezioni,
        'limiti': limiti,
        'riepilogo': usage_projection.riepilogo(proiezioni),
        'azure': {
            'configurazione': azure_monitor.stato_configurazione(),
            'app_service': azure_monitor.metriche_app_service(),
            'postgres': azure_monitor.metriche_postgres(),
            'email': azure_monitor.metriche_email(),
        },
        'giorni': giorni,
        'negozi_obiettivo': obiettivo,
    })


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

    # Chi ha sottoscritto lo STANDARD non puo' vedersi attivare i moduli
    # aggiuntivi: quelli appartengono al PREMIUM. Il Premium invece puo'
    # spegnerne uno o due quando vuole — il canone non cambia.
    # Il controllo sta qui e non solo nel pannello: il pannello e' una comodita',
    # questa e' la regola. Le date di attivazione arrivate dal pannello vengono
    # ignorate apposta: da adesso le tiene il programma.
    contratto = _contratto_tenant(db_idx)

    try:
        with child.app_context():
            from appl.models import OWNER
            from appl import db as child_db
            owner_cfg = OWNER.query.first()
            if not owner_cfg:
                owner_cfg = OWNER()
                child_db.session.add(owner_cfg)
            _applica_regole_moduli(owner_cfg, contratto, richiesti={
                'base': data.get('module_base_enabled', True),
                'web': data.get('module_web_enabled', True),
                'pacchetti': data.get('module_pacchetti_enabled', True),
                'solarium': data.get('module_solarium_enabled', False),
            })
            child_db.session.commit()
        return jsonify({'ok': True})
    except Exception as e:
        root_app.logger.warning("[moduli] salvataggio del tenant %s non riuscito: %s",
                                db_idx, e)
        return jsonify({'error': str(e)}), 500

@root_app.route('/owner-setup/reveal-password/<int:db_idx>', methods=['POST'])
def owner_setup_reveal_password(db_idx):
    if not _require_owner_auth():
        return jsonify({'error': 'Non autorizzato'}), 401
    if db_idx not in pool:
        return jsonify({'error': 'DB non trovato'}), 404
    return jsonify({'uri': pool.get(db_idx, '')})

def ensure_database_exists(uri):
    """Crea il database indicato nella URI se non c'e' gia'.

    Ci si connette al database di servizio "postgres" sullo STESSO server e con
    le STESSE credenziali della URI: sono quelle dell'amministratore, le stesse
    che aprono gli altri negozi. Cosi' l'aggiunta di un cliente non richiede
    piu' un passaggio manuale nel portale Azure.

    CREATE DATABASE non puo' stare dentro una transazione: serve autocommit.

    Ritorna (creato, messaggio). Non solleva: se il ruolo non ha il permesso
    CREATEDB si torna indietro con un messaggio leggibile e il database si crea
    a mano dal portale.
    """
    import psycopg2
    from psycopg2 import sql as _sql

    p = urlparse(uri)
    db_name = (p.path or '/').strip('/').split('/')[-1]
    if not db_name:
        return False, "URI senza nome del database."

    admin_dsn = {
        'host': p.hostname,
        'port': p.port or 5432,
        'user': p.username,
        'password': p.password,
        'dbname': 'postgres',
        'sslmode': 'require',
        'connect_timeout': 15,
    }

    conn = None
    try:
        conn = psycopg2.connect(**admin_dsn)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
            if cur.fetchone():
                return False, f"Il database '{db_name}' esiste gia'."
            cur.execute(_sql.SQL("CREATE DATABASE {}").format(_sql.Identifier(db_name)))
        return True, f"Database '{db_name}' creato."
    except Exception as e:
        return False, (
            f"Non sono riuscito a creare il database '{db_name}': {e}. "
            "Crealo dal portale Azure (Impostazioni -> Database) e riprova."
        )
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def provision_tenant(uri, business_name, city='', modules=None,
                     opening_time=None, closing_time=None, create_db=True):
    """Crea un negozio completo e lo rende raggiungibile su /s/<idx>.

    Un solo punto di verita' per la creazione di un tenant, chiamato da due
    parti: la rotta del pannello owner (come oggi) e, in futuro, il form di
    attivazione dopo la firma del contratto.

    Passi: crea il database se manca, costruisce la child app, inizializza lo
    schema, semina BusinessInfo/OWNER/utente owner, scrive nel .env, monta il
    child senza riavvio e registra il negozio nel registro centrale.

    Solleva RuntimeError con un messaggio gia' leggibile dall'utente.
    """
    from datetime import date as _date, time as _time

    uri = (uri or '').strip()
    business_name = (business_name or '').strip()
    if not business_name:
        raise RuntimeError("Nome negozio obbligatorio")
    if not uri or not uri.startswith('postgresql'):
        raise RuntimeError("URI PostgreSQL non valida (deve iniziare con postgresql://)")
    if uri in pool.values():
        raise RuntimeError("Questa URI e' gia' configurata")

    # `pool` contiene SOLO le SQLALCHEMY_DATABASE_URI<N>, cioe' i negozi.
    # Il registro centrale (tosca_registry) NON e' li' dentro: ha la sua
    # REGISTRY_DATABASE_URI apposta, per non essere montato come tenant.
    # Quindi con i tre database dell'owner (1 suncity, 2 sunexp3,
    # 3 sunbookingdb) il PRIMO CLIENTE A PAGAMENTO prende idx 4 e vive su
    # /s/4 — non /s/5, anche se sul server tosca_registry e' il quarto
    # database in ordine di creazione.
    next_idx = max(pool.keys(), default=0) + 1

    # ── 0. Il database esiste? Altrimenti si crea ─────────────────────────
    db_created = False
    if create_db:
        db_created, msg = ensure_database_exists(uri)
        root_app.logger.info("[provision] %s", msg)

    # ── 1. Child app ──────────────────────────────────────────────────────
    try:
        new_child = create_app(uri, tenant_idx=next_idx)
        if not os.getenv('SECRET_KEY'):
            new_child.secret_key = secret
        new_child.config['IS_CLOUD'] = True

        @new_child.context_processor
        def _inject_cloud_cassa_flags():
            hide = True
            cassa_enabled = False
            try:
                from appl.models import OWNER as _OWNER
                cfg = _OWNER.query.first()
                if cfg is not None:
                    cassa_enabled = bool(getattr(cfg, 'cassa_enabled_on_web', False))
                    hide = not cassa_enabled
            except Exception:
                hide = True
                cassa_enabled = False
            return {
                'hide_cassa': hide,
                'cassa_enabled_on_web': cassa_enabled,
                'is_cloud': True,
            }
    except Exception as e:
        raise RuntimeError(f"Errore creazione app: {e}")

    # ── 2. Schema e dati iniziali ─────────────────────────────────────────
    mods = modules or {}
    try:
        with new_child.app_context():
            db.create_all()
            from appl.models import BusinessInfo, OWNER

            if not BusinessInfo.query.first():
                # opening_time e closing_time sono NOT NULL senza default:
                # il form li chiede, il pannello owner no e resta il 9-19.
                db.session.add(BusinessInfo(
                    business_name=business_name,
                    city=city or None,
                    opening_time=opening_time or _time(9, 0),
                    closing_time=closing_time or _time(19, 0),
                ))

            if not OWNER.query.first():
                today = _date.today()
                db.session.add(OWNER(
                    module_base_enabled=bool(mods.get('base', True)),
                    module_web_enabled=bool(mods.get('web', True)),
                    module_pacchetti_enabled=bool(mods.get('pacchetti', True)),
                    module_solarium_enabled=bool(mods.get('solarium', False)),
                    module_base_activated_on=today if mods.get('base', True) else None,
                    module_web_activated_on=today if mods.get('web', True) else None,
                    module_pacchetti_activated_on=today if mods.get('pacchetti', True) else None,
                    module_solarium_activated_on=today if mods.get('solarium', False) else None,
                ))

            # Copia l'utente owner da un database esistente
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
        raise RuntimeError(f"Errore inizializzazione DB: {e}")

    # ── 3. .env ───────────────────────────────────────────────────────────
    try:
        _write_env_var(f'SQLALCHEMY_DATABASE_URI{next_idx}', uri)
    except Exception as e:
        raise RuntimeError(f"Errore scrittura .env: {e}")

    # ── 4. Montaggio nel dispatcher, senza riavvio ────────────────────────
    creds = unipile_creds_for(next_idx)
    wrapped = with_request_env(new_child, creds)
    wrapped = with_db_cookie(wrapped, next_idx, secure=use_https)
    wrapped = fix_delete_method_middleware(wrapped)

    pool[next_idx] = uri
    children[next_idx] = new_child
    mounts[f'/s/{next_idx}'] = wrapped

    # ── 5. Registro centrale ──────────────────────────────────────────────
    # Il negozio entra nel registro con is_owner_db = false: e' un cliente
    # pagante. I tre database dell'owner (idx 1-3) restano gli unici esenti.
    # Un fallimento qui non annulla il tenant, che a questo punto e' gia' vivo
    # e funzionante: si logga e si va avanti.
    try:
        if _registry_on():
            from appl.registry_models import registry_session, Tenant, Billing
            from datetime import datetime as _dt
            with registry_session() as s:
                t = s.query(Tenant).filter_by(idx=next_idx).one_or_none()
                if t is None:
                    t = Tenant(idx=next_idx, business_name=business_name)
                    s.add(t)
                t.business_name = business_name
                t.status = 'active'
                t.provisioned_at = _dt.now()
                s.flush()
                if s.query(Billing).filter_by(tenant_id=t.id).one_or_none() is None:
                    s.add(Billing(tenant_id=t.id, is_owner_db=False))
    except Exception:
        root_app.logger.exception(
            "[provision] tenant %s creato ma non registrato nel registro", next_idx)

    try:
        _p = urlparse(uri)
        db_name = (_p.path or '/').strip('/').split('/')[-1] or '—'
        db_user = _p.username or '—'
    except Exception:
        db_name = db_user = '—'

    today_str = _date.today().isoformat()
    return {
        'ok': True,
        'idx': next_idx,
        'business_name': business_name,
        'localita': city,
        'db_name': db_name,
        'db_user': db_user,
        'db_created': db_created,
        'uri_masked': _mask_uri(uri),
        'module_base_activated_on': today_str,
        'module_web_activated_on': today_str,
        'module_pacchetti_activated_on': today_str,
    }


@root_app.route('/owner-setup/add-tenant', methods=['POST'])
def owner_setup_add_tenant():
    if not _require_owner_auth():
        return jsonify({'error': 'Non autorizzato'}), 401

    data = request.get_json(silent=True) or {}
    try:
        result = provision_tenant(
            uri=data.get('uri') or '',
            business_name=data.get('business_name') or '',
            city=(data.get('city') or '').strip(),
        )
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        root_app.logger.exception("[provision] errore imprevisto")
        return jsonify({'error': f'Errore imprevisto: {e}'}), 500

    return jsonify(result)


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
                  'max_payment_days', 'is_owner_db', 'einvoice_customer_id', 'payment_customer_ref'):
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
        'einvoice_id': None,
        'einvoice_url': None,
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
        'provider_payment_id': None,
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


# ═══════════════════════════════════════════════════════════════════════════
#  ATTIVAZIONE CLIENTE — invito dal pannello owner e form pubblico
#
#  Il link consegnato al cliente e' l'UNICA cosa che viaggia: il contratto non
#  esce mai come file. Dentro il link c'e' un token monouso di cui in database
#  resta solo lo SHA-256, cosi' chi legge il registro non puo' usarlo.
#
#  La rotta pubblica non apre nessuna sessione applicativa e non tocca i
#  database dei negozi: parla solo con il registro.
# ═══════════════════════════════════════════════════════════════════════════
INVITE_TTL_DAYS = int(os.getenv('INVITE_TTL_DAYS', '14'))

# Giorni di conservazione dei dati dopo la cessazione, art. 20.1.c del
# contratto. Se cambia il contratto, cambia qui.
GIORNI_CONSERVAZIONE = int(os.getenv('GIORNI_CONSERVAZIONE', '30'))


def _token_hash(token):
    import hashlib
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def _invite_or_404(token):
    """Ritorna (invite, contract, tenant) oppure None.

    Un token inesistente, scaduto o gia' usato riceve lo stesso trattamento:
    non si deve poter capire quale dei tre casi sia.
    """
    from datetime import datetime, timezone
    from appl.registry_models import registry_session, OnboardingInvite, Contract, Tenant
    with registry_session() as s:
        inv = s.query(OnboardingInvite).filter_by(token_hash=_token_hash(token)).one_or_none()
        if inv is None or inv.used_at is not None:
            return None
        if inv.expires_at and inv.expires_at < datetime.now(timezone.utc):
            return None
        tenant = s.query(Tenant).filter_by(id=inv.tenant_id).one_or_none()
        contract = s.query(Contract).filter_by(tenant_id=inv.tenant_id).one_or_none()
        if tenant is None or contract is None:
            return None
        if inv.opened_at is None:
            inv.opened_at = datetime.now(timezone.utc)
        return {
            'invite_id': inv.id,
            'tenant_id': tenant.id,
            'contract_id': contract.id,
            'business_name': tenant.business_name,
            'starter_total': float(contract.starter_total) if contract.starter_total is not None else None,
            'saas_monthly_amount': float(contract.saas_monthly_amount) if contract.saas_monthly_amount is not None else None,
            'modules': {
                'base': bool(contract.module_base),
                'web': bool(contract.module_web),
                'pacchetti': bool(contract.module_pacchetti),
                'solarium': bool(contract.module_solarium),
            },
        }


@root_app.route('/owner-setup/invite', methods=['POST'])
def owner_setup_invite():
    """Crea un invito e restituisce il link da consegnare al cliente.

    Non crea nessun database: il negozio nasce solo dopo firma e incasso.
    """
    if not _require_owner_auth():
        return jsonify({'error': 'Non autorizzato'}), 401
    if not _registry_on():
        return jsonify({'error': 'Registro centrale non configurato '
                                 '(manca REGISTRY_DATABASE_URI).'}), 503

    import secrets as _secrets
    from datetime import datetime, timedelta, timezone
    from appl.registry_models import registry_session, Tenant, Contract, OnboardingInvite

    data = request.get_json(silent=True) or {}
    business_name = (data.get('business_name') or '').strip()
    if not business_name:
        return jsonify({'error': 'Nome negozio obbligatorio'}), 400

    def _num(v):
        try:
            return round(float(v), 2)
        except (TypeError, ValueError):
            return None

    # ── Listino ───────────────────────────────────────────────────────────
    # Due soli canoni a listino. Qualunque altra cifra e' un accordo fuori
    # listino e DEVE avere una motivazione scritta: il controllo sta qui e non
    # solo nel form, perche' un controllo che vive nel browser non e' un
    # controllo.
    LISTINO = {'standard': 39.00, 'premium': 59.00}

    price_plan = (data.get('price_plan') or 'standard').strip().lower()
    price_note = (data.get('price_note') or '').strip()

    # Lo STANDARD comprende il solo Tosca Base: i moduli aggiuntivi
    # appartengono al PREMIUM e al prezzo concordato.
    solo_base = (price_plan == 'standard')

    if price_plan in LISTINO:
        canone = LISTINO[price_plan]
        price_note = None
    elif price_plan == 'custom':
        canone = _num(data.get('saas_monthly_amount'))
        if canone is None or canone < 0:
            return jsonify({'error': 'Indica il canone mensile concordato.'}), 400
        if not price_note:
            return jsonify({'error': 'Un canone fuori listino richiede una motivazione.'}), 400
        # Se la cifra concordata coincide con il listino, si normalizza: non ha
        # senso avere una riga "custom" a 39 con una motivazione inventata.
        for nome, importo in LISTINO.items():
            if abs(canone - importo) < 0.005:
                price_plan, price_note = nome, None
                break
    else:
        return jsonify({'error': 'Piano non valido.'}), 400

    token = _secrets.token_urlsafe(32)
    try:
        with registry_session() as s:
            tenant = Tenant(business_name=business_name, status='invited')
            s.add(tenant)
            s.flush()

            contract = Contract(
                tenant_id=tenant.id,
                status='draft',
                contract_version=os.getenv('CONTRACT_VERSION', '1.0'),
                legal_business_name=business_name,
                email=(data.get('email') or '').strip() or None,
                # Importi e moduli li decide l'owner adesso: al cliente
                # arrivano in sola lettura, non e' lui a scegliersi il prezzo.
                starter_total=_num(data.get('starter_total')),
                saas_monthly_amount=canone,
                price_plan=price_plan,
                price_note=price_note,
                module_base=True,
                # I moduli appartengono al PREMIUM (e al prezzo concordato):
                # con lo STANDARD si spengono qui, non solo nel browser.
                module_web=(not solo_base) and bool(data.get('module_web')),
                module_pacchetti=(not solo_base) and bool(data.get('module_pacchetti')),
                module_solarium=(not solo_base) and bool(data.get('module_solarium')),
            )
            s.add(contract)

            s.add(OnboardingInvite(
                tenant_id=tenant.id,
                token_hash=_token_hash(token),
                email=(data.get('email') or '').strip() or None,
                expires_at=datetime.now(timezone.utc) + timedelta(days=INVITE_TTL_DAYS),
            ))
            tenant_id = tenant.id
    except Exception as e:
        root_app.logger.exception("[invito] creazione fallita")
        return jsonify({'error': f'Errore creazione invito: {e}'}), 500

    link = request.url_root.rstrip('/') + url_for('attiva', token=token)
    root_app.logger.info("[invito] creato per '%s' (tenant %s)", business_name, tenant_id)
    return jsonify({
        'ok': True,
        'tenant_id': tenant_id,
        'link': link,
        'scade_il': (datetime.now(timezone.utc) + timedelta(days=INVITE_TTL_DAYS)).date().isoformat(),
    })


@root_app.route('/attiva/<token>', methods=['GET'])
def attiva(token):
    """Pagina pubblica di attivazione. Nessuna autenticazione: vale il token."""
    if not _registry_on():
        return render_template('attiva.html', errore='Servizio non disponibile.'), 503
    ctx = _invite_or_404(token)
    if ctx is None:
        # Stesso messaggio per token inesistente, scaduto o gia' usato.
        return render_template('attiva.html', errore=
            'Questo link non e\' piu\' valido. Contatta il tuo referente Tosca '
            'per riceverne uno nuovo.'), 404
    return render_template('attiva.html', token=token, ctx=ctx)


@root_app.route('/attiva/<token>/step', methods=['POST'])
def attiva_step(token):
    """Salvataggio progressivo del wizard.

    Accetta solo i campi previsti: un client che ne inviasse altri (importi,
    moduli, stato) non puo' toccarli.
    """
    if not _registry_on():
        return jsonify({'error': 'Servizio non disponibile'}), 503
    ctx = _invite_or_404(token)
    if ctx is None:
        return jsonify({'error': 'Link non piu\' valido'}), 404

    CAMPI = {
        'legal_business_name', 'trade_name', 'legal_form', 'vat_number',
        'fiscal_code', 'rea_number', 'rea_province', 'pec', 'sdi_code',
        'legal_address', 'legal_cap', 'legal_city', 'legal_province',
        'op_same_as_legal', 'op_address', 'op_cap', 'op_city', 'op_province',
        'email', 'phone', 'mobile', 'website',
        'signer_first_name', 'signer_last_name', 'signer_fiscal_code',
        'signer_role', 'signer_mobile', 'signer_email',
        'closing_days', 'operators_count', 'printer_model',
        'current_software', 'has_data_to_migrate', 'vat_percentage',
    }
    ORARI = {'opening_time', 'closing_time'}

    data = request.get_json(silent=True) or {}
    from datetime import datetime as _dt
    from appl.registry_models import registry_session, Contract

    try:
        with registry_session() as s:
            c = s.query(Contract).filter_by(id=ctx['contract_id']).one()
            for k, v in data.items():
                if k in CAMPI:
                    if isinstance(v, str):
                        v = v.strip() or None
                    setattr(c, k, v)
                elif k in ORARI and v:
                    try:
                        setattr(c, k, _dt.strptime(str(v), '%H:%M').time())
                    except ValueError:
                        pass
    except Exception as e:
        root_app.logger.exception("[attiva] salvataggio step fallito")
        return jsonify({'error': f'Errore salvataggio: {e}'}), 500

    return jsonify({'ok': True})


@root_app.route('/owner-logout')
def owner_logout():
    session.pop('owner_auth', None)
    session.pop('owner_db_idx', None)
    session.pop('owner_expiry', None)
    return redirect(url_for('landing_web'))

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5050"))
    print(f"Avvio server su http://127.0.0.1:{port}/landing-web")
    serve(application, host='127.0.0.1', port=port, threads=THREAD_SERVER)