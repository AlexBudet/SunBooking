# appl/__init__.py
from flask_wtf.csrf import CSRFProtect, generate_csrf
from flask import Flask, current_app, g, jsonify, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash
from argon2 import PasswordHasher, exceptions as argon2_exceptions
from sqlalchemy import text
import time
import os
import sys
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_compress import Compress

migrate = Migrate()

# Istanza globale di SQLAlchemy
db = SQLAlchemy()
csrf = CSRFProtect()
app = None  # riferimento globale all'app
ph = PasswordHasher()

def chiave_per_tenant(master, idx):
    """Chiave di firma dei cookie DIVERSA per ogni negozio, derivata da quella
    madre. E' deterministica - sopravvive ai riavvii, quindi non butta fuori
    nessuno - ma non e' riutilizzabile fra tenant: un cookie di sessione
    firmato per /s/1 non supera la verifica di firma su /s/2."""
    import hmac, hashlib
    if isinstance(master, str):
        master = master.encode('utf-8')
    return hmac.new(master, b'tosca-tenant-' + str(idx).encode('ascii'),
                    hashlib.sha256).digest()


def marca_sessione_tenant():
    """Da chiamare SUBITO dopo aver messo user_id in sessione: registra su
    quale negozio quella sessione e' stata aperta. require_login lo confronta
    a ogni richiesta. Terzo livello di difesa dopo cookie separato e chiave
    separata: da solo non basterebbe, ma se gli altri due venissero
    disattivati per errore questo continua a reggere."""
    from flask import current_app, session
    session['tenant_idx'] = current_app.config.get('TENANT_IDX')


def get_base_path():
    """Restituisce il path base corretto sia per exe che per script."""
    if getattr(sys, 'frozen', False):
        # Eseguito come exe PyInstaller
        return sys._MEIPASS
    else:
        # Eseguito come script Python
        return os.path.dirname(os.path.abspath(__file__))

def create_app(db_uri: str | None = None, tenant_idx=None):
    """
    Restituisce una nuova istanza Flask.
    - Usa SOLO PostgreSQL (es. Azure). Se la variabile non è impostata o non è PostgreSQL, solleva errore.
    """

    global app
    
    base_path = get_base_path()
    
    # Quando frozen, i templates sono in _MEIPASS/appl/templates
    # Quando non frozen, sono relativi a questo file (appl/__init__.py)
    if getattr(sys, 'frozen', False):
        template_folder = os.path.join(base_path, 'appl', 'templates')
        static_folder = os.path.join(base_path, 'appl', 'static')
    else:
        template_folder = os.path.join(os.path.dirname(__file__), 'templates')
        static_folder = os.path.join(os.path.dirname(__file__), 'static')
    
    app = Flask(__name__, 
                template_folder=template_folder,
                static_folder=static_folder)
    
    app.secret_key = os.getenv('SECRET_KEY') or os.urandom(24)

    # === ISOLAMENTO FRA NEGOZI =========================================
    # Con piu' tenant montati sullo stesso processo (wsgi.py: /s/1, /s/2, ...)
    # tutti i child condividevano nome del cookie, percorso e chiave di firma,
    # e la sessione conteneva solo user_id. Risultato: un cookie ottenuto su
    # /s/1 veniva accettato da /s/2, che risolveva quell'user_id sul PROPRIO
    # database - entrando come un utente di un'altra azienda.
    #
    # Tre barriere indipendenti, in ordine di quando intervengono:
    #   1. nome del cookie diverso -> l'app 2 non legge nemmeno il cookie dell'app 1
    #   2. percorso del cookie /s/<idx> -> il browser non lo manda proprio agli altri
    #   3. chiave di firma diversa -> un cookie copiato a mano non supera la verifica
    # Piu' il marchio in sessione (marca_sessione_tenant) controllato da
    # require_login. Ne basterebbe una: ci sono tutte perche' e' un confine
    # fra aziende diverse.
    #
    # tenant_idx None = installazione a negozio singolo (start.py, main.py):
    # li' non c'e' niente da isolare e tutto resta com'era.
    app.config['TENANT_IDX'] = tenant_idx
    if tenant_idx is not None:
        app.config['SESSION_COOKIE_NAME'] = 'sess_s%s' % tenant_idx
        app.config['SESSION_COOKIE_PATH'] = '/s/%s' % tenant_idx
        _master = os.getenv('SECRET_KEY')
        if _master:
            app.secret_key = chiave_per_tenant(_master, tenant_idx)

    import json
    def escapejs_filter(value):
        """Escape a Python value for safe use inside JS string literals
        when the template already wraps the expression in quotes.
        Returns the JSON-escaped string content without surrounding quotes."""
        if value is None:
            return ''
        return json.dumps(str(value))[1:-1]

    app.jinja_env.filters['escapejs'] = escapejs_filter

    use_https = os.getenv('USE_HTTPS', 'false').lower() in ('1', 'true', 'yes')
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SECURE'] = use_https   # prima era True fisso
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['REMEMBER_COOKIE_SECURE'] = use_https
    app.config['WTF_CSRF_SSL_STRICT'] = use_https
    app.config['PREFERRED_URL_SCHEME'] = 'https' if use_https else 'http'

    # Compressione delle risposte (gzip/brotli, scelta in base a quello che
    # il browser dichiara di accettare). Riguarda solo il trasporto: il
    # browser decomprime da solo e a schermo non cambia nulla.
    # Misurato il 22/08/2026 sui file veri: calendar.js 821K -> 188K,
    # calendar.html 323K -> 82K, cassa.js 251K -> 66K, styles.css 165K -> 39K.
    # In tutto il primo caricamento dell'Agenda passa da ~1,25 MB a ~300 KB,
    # che su una linea lenta e in traffico in uscita da Azure si sente.
    # Va inizializzata PER OGNI app creata da questa factory, non una volta
    # sola a livello di modulo: i tenant sono app distinte.
    #
    # La riga qui sotto NON e' facoltativa. I file statici (calendar.js,
    # styles.css) vengono serviti in streaming, e per lo streaming
    # Flask-Compress usa una lista di algoritmi separata da cui gzip e'
    # ESCLUSO di default: un client che dichiara solo "gzip" si ritroverebbe
    # calendar.js non compresso, cioe' proprio il file che pesa di piu'.
    # Verificato in prova isolata il 22/08/2026: senza questa riga, con
    # Accept-Encoding: gzip il file esce a 840 KB; con la riga, 192 KB.
    app.config['COMPRESS_ALGORITHM_STREAMING'] = ['zstd', 'br', 'gzip', 'deflate']
    Compress(app)

    # Inizializza estensione CSRF
    csrf.init_app(app)

    # ---- RATE LIMITER ----
    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=["200 per minute"],  # limite globale
        storage_uri="memory://",
    )

    # Limite più stretto sul login
    @limiter.limit("5 per minute")
    @app.before_request
    def rate_limit_login():
        if request.endpoint == 'landing' and request.method == 'POST':
            pass  # il decoratore applica il limite

    # Limite endpoint AI: largo (ogni query dura 1-3 sec comunque)
    @limiter.limit("100 per minute")
    @app.before_request
    def rate_limit_ai():
        if request.endpoint in ('calendar.ai_query',) and request.method == 'POST':
            pass  # il decoratore applica il limite

    # Espone il token ai template Jinja come csrf_token()
    app.jinja_env.globals["csrf_token"] = generate_csrf

    # Solo PostgreSQL: niente fallback su SQLite/Dropbox
    if not db_uri or not db_uri.startswith("postgresql"):
        raise RuntimeError("Devi impostare la variabile d'ambiente SQLALCHEMY_DATABASE_URI con la stringa di connessione PostgreSQL!")
    app.config["SQLALCHEMY_DATABASE_URI"] = db_uri

    # Opzioni di pool per Azure (opzionali)
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        # ATTENZIONE: questo pool e' PER TENANT. wsgi.py crea una child app (e
        # quindi un engine dedicato) per ogni database configurato, percio' il
        # totale di connessioni aperte e' pool_size x numero di tenant.
        # Con 15+10 per tenant si superavano i ~50 slot di Azure e il server
        # rispondeva "remaining connection slots are reserved...", facendo
        # fallire richieste a caso (compresa la stampa in cassa).
        #
        # 2+1 = 3 connessioni per negozio. Su un B1ms (~35 slot) significa una
        # decina di negozi per server, contro i 6 che si avevano con 3+2.
        #
        # Perche' 3 bastano anche con piu' persone collegate: una connessione
        # NON e' un utente. Viene presa in prestito per la durata della singola
        # query (10-50 ms) e subito restituita. Chi tiene l'Agenda aperta senza
        # cliccare non ne occupa nessuna. Tre connessioni reggono ~60 query al
        # secondo per negozio; un salone con tre postazioni ne genera una o due.
        # E a pool pieno la richiesta non fallisce: aspetta in coda fino a
        # pool_timeout.
        #
        # Dove si sente davvero: le query LENTE (un report da 3 secondi tiene
        # una connessione per 3 secondi). Se capitera' di vedere attese sui
        # report, la risposta NON e' rialzare questo numero — sono i 35 slot
        # del B1ms il vincolo — ma passare a B2s o al pooler PgBouncer.
        "pool_size": 2,                 # Numero di connessioni persistenti
        "max_overflow": 1,              # Connessioni extra temporanee
        "pool_timeout": 10,             # Timeout breve per ottenere una connessione (secondi)
        "pool_recycle": 360,           # Ricicla connessioni ogni 30 minuti (evita idle drop Azure)
        "pool_pre_ping": True,          # Testa la connessione prima di usarla
        "pool_use_lifo": True,          # LIFO per ridurre la latenza
        "connect_args": {
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5
        }
    }

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Inizializza SQLAlchemy
    db.init_app(app)
    migrate.init_app(app, db)

    # Importa e registra i blueprint
    from .routes.calendar import calendar_bp
    from .routes.settings import settings_bp
    from .routes.clients import clients_bp
    from .routes.services import services_bp
    from .routes.operators import operators_bp
    from appl.routes.cassa import cassa_bp
    from appl.routes.report import report_bp
    from .routes.pacchetti import pacchetti_bp

    app.register_blueprint(calendar_bp,  url_prefix="/calendar")
    app.register_blueprint(settings_bp,  url_prefix="/settings")
    app.register_blueprint(clients_bp,   url_prefix="/clients")
    app.register_blueprint(services_bp,  url_prefix="/services")
    app.register_blueprint(operators_bp, url_prefix="/operators")
    app.register_blueprint(cassa_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(pacchetti_bp, url_prefix="/pacchetti")

    # ---- CARTE PREPAGATE: STATO ALLINEATO AL CREDITO ----
    # Una carta con credito non puo' restare "Completato" (= esaurita): sarebbe
    # grigia in elenco, senza badge in Agenda e fuori dai filtri, pur avendo
    # soldi sopra. Le carte ricaricate prima che questo controllo esistesse
    # sono rimaste indietro: si sistemano qui, con un solo UPDATE all'avvio.
    # Durante l'uso ci pensano le pagine che le leggono (elenchi, Agenda, Cassa).
    with app.app_context():
        try:
            from appl.routes.pacchetti import allinea_status_prepagate_con_credito
            corrette = allinea_status_prepagate_con_credito()
            if corrette:
                app.logger.info(
                    "[prepagate] %s carte con credito riportate ad Attivo all'avvio", corrette)
        except Exception:
            db.session.rollback()
            app.logger.exception("[prepagate] allineamento stato/credito all'avvio fallito")

    # ---- SCAN NOTIZIE BEAUTY (thread interno, due volte a settimana) ----
    # Il modulo si auto-disattiva se manca ANTHROPIC_API_KEY: in quel caso non
    # parte nessun thread e non viene fatta nessuna chiamata. Il thread viene
    # avviato una sola volta dal primo tenant registrato; gli altri si limitano
    # a registrarsi per ricevere le stesse notizie nel proprio database.
    try:
        from appl.news_beauty import register_app as _register_news
        _register_news(app)
    except Exception:
        app.logger.exception("[news_beauty] registrazione fallita")

    # ---- SECURITY HEADERS ----
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        # Cache control per pagine dinamiche
        if 'text/html' in response.content_type:
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return response

    # ---- CONTEXT PROCESSOR: current_user disponibile in tutti i template ----
    @app.context_processor
    def inject_current_user():
        user_id = session.get('user_id')
        from appl.models import User
        current_user = db.session.get(User, user_id) if user_id else None
        return dict(current_user=current_user)

    # ---- CONTEXT PROCESSOR: flag moduli owner (letti da tabella OWNER) ----
    @app.context_processor
    def inject_module_flags():
        try:
            from appl.models import OWNER
            owner_cfg = OWNER.query.first()
            if owner_cfg:
                return {
                    'module_web_enabled': owner_cfg.module_web_enabled,
                    'module_pacchetti_enabled': owner_cfg.module_pacchetti_enabled,
                    'module_solarium_enabled': owner_cfg.module_solarium_enabled,
                }
        except Exception:
            pass
        return {
            'module_web_enabled': True,
            'module_pacchetti_enabled': True,
            'module_solarium_enabled': False,
        }

    # ---- CONTEXT PROCESSOR: default Cassa visibile (start.py / non-cloud) ----
    # Questo viene SOVRASCRITTO da wsgi.py che registra un context processor
    # successivo che legge OWNER.cassa_enabled_on_web (in Flask vince l'ultimo
    # context processor registrato per la stessa chiave). Quindi:
    #   - start.py (.exe locale): hide_cassa = False sempre (Cassa visibile)
    #   - wsgi.py (cloud):        hide_cassa calcolato dal DB del tenant
    @app.context_processor
    def inject_cassa_defaults():
        try:
            from appl.models import OWNER
            owner_cfg = OWNER.query.first()
            cassa_enabled = bool(getattr(owner_cfg, 'cassa_enabled_on_web', False)) if owner_cfg else False
        except Exception:
            cassa_enabled = False
        return {
            'hide_cassa': False,
            'cassa_enabled_on_web': cassa_enabled,
            'is_cloud': False,
        }

    # ---- BEFORE REQUEST: blocco route se modulo disabilitato ----
    @app.before_request
    def enforce_module_access():
        try:
            from appl.models import OWNER
            owner_cfg = OWNER.query.first()
            if not owner_cfg:
                return
            path = request.path or ''
            # Pacchetti disabilitati: blocca /pacchetti/*
            if not owner_cfg.module_pacchetti_enabled:
                if path.startswith('/pacchetti'):
                    return redirect(url_for('calendar.calendar_home'))
            # Modulo WEB disabilitato: blocca pagine WhatsApp, Marketing, Booking Web
            if not owner_cfg.module_web_enabled:
                blocked = ('/settings/marketing',
                           '/settings/set_bookings', '/whatsapp_per_operatori')
                if any(path.startswith(p) for p in blocked):
                    return redirect(url_for('calendar.calendar_home'))
            # Modulo SOLARIUM disabilitato: blocca impostazioni e API monitor lampade
            if not owner_cfg.module_solarium_enabled:
                blocked_solarium = ('/settings/solarium', '/calendar/api/solarium')
                if any(path.startswith(p) for p in blocked_solarium):
                    return redirect(url_for('calendar.calendar_home'))
        except Exception:
            pass

# ---- ROUTE LANDING registrata nella app factory (minima, per WSGI) ----
    _login_attempts = {}  # username -> {'count': int, 'first': timestamp}
    MAX_LOGIN_ATTEMPTS = int(os.getenv('MAX_LOGIN_ATTEMPTS', '10'))
    LOGIN_WINDOW_SECONDS = int(os.getenv('LOGIN_WINDOW_SECONDS', '300'))

    def record_login_failure(username):
        now = time.time()
        entry = _login_attempts.get(username)
        if not entry or (now - entry['first'] > LOGIN_WINDOW_SECONDS):
            entry = {'count': 1, 'first': now}
        else:
            entry['count'] = entry.get('count', 0) + 1
        _login_attempts[username] = entry
        return entry

    def reset_login_attempts(username):
        _login_attempts.pop(username, None)

    def is_account_locked(username):
        entry = _login_attempts.get(username)
        if not entry:
            return False
        if time.time() - entry['first'] > LOGIN_WINDOW_SECONDS:
            # finestra scaduta -> resetta
            _login_attempts.pop(username, None)
            return False
        return entry.get('count', 0) >= MAX_LOGIN_ATTEMPTS

    @csrf.exempt
    @app.route('/', methods=['GET', 'POST'])
    def landing():
        # Se l'utente è già loggato (es. auto-login da landing root), vai diretto al calendario
        if request.method == 'GET' and session.get('user_id'):
            try:
                return redirect(url_for('calendar.calendar_home'))
            except Exception:
                pass
        attempts_count = 0
        reset_email = ''
        try:
            from .models import BusinessInfo, User
            biz = BusinessInfo.query.first()
            reset_email = getattr(biz, 'email', '') or getattr(biz, 'business_email', '') or ''
        except Exception:
            reset_email = ''

        try:
            if request.method == 'POST':
                username = (request.form.get('username') or '').strip()
                password = request.form.get('password', '')

                        # Log temporaneo per debug
                current_app.logger.info(f"Tentativo login - Username: {username}")

                # controllo blocco account (minimo)
                if username and is_account_locked(username):
                    current_app.logger.warning("Account bloccato temporaneamente per username=%s", username)
                    flash('Troppi tentativi. Riprova più tardi.', 'danger')
                    return render_template('landing.html', login_attempts=None, reset_email=reset_email)

                user = None
                valid = False
                try:
                    user = User.query.filter_by(username=username).first() if username else None
                except Exception:
                    # DB read error: rollback e fallimento silenzioso
                    try:
                        db.session.rollback()
                    except Exception:
                        pass
                    user = None

                if user:
                    try:
                        valid = False
                        try:
                            valid = ph.verify(user.password, password)
                            if ph.check_needs_rehash(user.password):
                                user.password = ph.hash(password)
                                db.session.commit()
                        except (argon2_exceptions.VerifyMismatchError, argon2_exceptions.InvalidHash):
                            # Non è Argon2id, prova hash legacy
                            valid = check_password_hash(user.password, password)
                            if valid:
                                user.password = ph.hash(password)
                                db.session.commit()
                    except Exception as e:
                        try:
                            db.session.rollback()
                        except Exception:
                            pass
                        valid = False

                if valid:
                    # login OK
                    reset_login_attempts(username)
                    session.clear()
                    session['user_id'] = user.id
                    marca_sessione_tenant()
                    # rigenera CSRF token se possibile
                    try:
                        from flask_wtf.csrf import generate_csrf
                        generate_csrf()
                    except Exception:
                        pass
                    try:
                        redirect_url = url_for('calendar.calendar_home')
                        return redirect(redirect_url)
                    except Exception as e:
                        return f"Errore redirect: {e}", 500
                else:
                    # login fallito: registra tentativo senza esporre contatore
                    record_login_failure(username)
                    current_app.logger.warning("Login fallito per username=%s", username)
                    flash('Credenziali non valide', 'danger')

            # GET o dopo POST mostriamo la landing senza esporre contatori
            return render_template('landing.html', login_attempts=None, reset_email=reset_email)

        except Exception as e:
            try:
                db.session.rollback()
            except Exception:
                pass
            current_app.logger.exception("Errore nella route landing: %s", e)
            return ("Errore interno. Controlla i log dell'app per dettagli."), 500
        
    # ---- ROUTE LOGOUT registrata nella app factory (minima, per WSGI) ----
    @app.route('/logout')
    def logout():
        session.clear()
        # Su un'installazione multi-negozio si torna SEMPRE alla landing
        # iniziale, mai a quella del singolo negozio.
        #
        # Prima si guardava il flag from_root_landing, che pero' viene messo
        # solo da chi entra con l'auto-login dalla landing root. Chi si era
        # autenticato direttamente sul form del negozio - per esempio dopo
        # essere stato espulso per aver cambiato l'indirizzo a mano - usciva e
        # si ritrovava sul form di QUEL negozio, restando agganciato li'.
        #
        # current_app e non app: dentro le funzioni annidate "app" e' la
        # variabile globale del modulo, cioe' l'ultimo tenant creato.
        if current_app.config.get('TENANT_IDX') is not None:
            return redirect('/landing-logout')

        # Installazione a negozio singolo (start.py, main.py): la landing root
        # non esiste, quindi si torna a quella locale come sempre.
        return redirect(url_for('landing'))

    # ---- AUTO-LOGIN: consume token monouso emesso dalla landing root ----
    @app.before_request
    def consume_autologin_token():
        token = request.args.get('_autologin')
        if not token:
            return None
        try:
            from appl.autologin import consume_token
            result = consume_token(token)
        except Exception:
            result = None
        if not result:
            return None
        idx_token, user_id_token = result
        # Il token vale SOLO sul negozio per cui e' stato emesso. Senza questo
        # controllo un token per /s/1 poteva essere speso su /s/2 e, se li'
        # esisteva un utente con lo stesso id, apriva la sessione di un'altra
        # azienda. Il controllo sull'esistenza dell'utente non basta: gli id
        # partono da 1 su ogni database, quindi si sovrappongono quasi sempre.
        # current_app, NON app: create_app dichiara "global app", quindi qui
        # dentro il nome "app" e' la variabile globale del modulo, che dopo il
        # ciclo di wsgi.py punta all'ULTIMA app creata - non a quella che sta
        # servendo la richiesta. Con tre negozi montati, leggere app.config
        # significava leggere sempre la configurazione del terzo.
        if str(idx_token) != str(current_app.config.get('TENANT_IDX')):
            current_app.logger.warning('[AUTOLOGIN] token per tenant %r speso su tenant %r: rifiutato',
                                       idx_token, current_app.config.get('TENANT_IDX'))
            return None
        # Verifica che l'utente esista in questo DB (sicurezza extra)
        try:
            from appl.models import User as _U
            user = db.session.get(_U, user_id_token)
        except Exception:
            user = None
        if not user:
            current_app.logger.warning('[AUTOLOGIN] utente id=%r inesistente nel DB del tenant %s',
                                       user_id_token, current_app.config.get('TENANT_IDX'))
            return None
        # Preserva la sessione root (selezione negozi) attraverso il clear,
        # così dopo il logout dal child l'utente torna alla scelta negozi senza re-login.
        preserved_root_user = session.get('root_user')
        preserved_root_allowed = session.get('root_allowed')
        session.clear()
        if preserved_root_user is not None:
            session['root_user'] = preserved_root_user
        if preserved_root_allowed is not None:
            session['root_allowed'] = preserved_root_allowed
        session['user_id'] = user_id_token
        marca_sessione_tenant()
        session['from_root_landing'] = True
        # Redirect alla stessa URL ripulita dal parametro.
        # IMPORTANTE: includere request.script_root (SCRIPT_NAME del mount, es. "/s/1")
        # altrimenti il redirect andrebbe alla root sbagliata e ripartirebbe il loop di login.
        from urllib.parse import urlencode
        args = request.args.to_dict(flat=True)
        args.pop('_autologin', None)
        clean_qs = urlencode(args)
        clean_url = (request.script_root or '') + request.path + (('?' + clean_qs) if clean_qs else '')
        return redirect(clean_url)

    # ---- LOGIN REQUIRED su tutte le route (eccetto whitelist) ----
    @app.before_request
    def require_login():
        allowed_endpoints = {'landing', 'healthz', 'static', 'ping'}
        ep = request.endpoint or ''

        # Una sessione aperta su un altro negozio non vale qui. Non dovrebbe
        # nemmeno arrivarci (cookie con nome e percorso diversi), ma se ci
        # arriva la si butta via invece di fidarsi dell'user_id che contiene.
        #
        # E si chiude TUTTO, non meta'. Ripulire il solo cookie del negozio
        # lasciava viva la sessione della landing root (cookie 'session',
        # percorso '/', con dentro root_user e l'elenco dei negozi
        # autorizzati): l'utente restava agganciato alla scelta precedente e
        # per entrare altrove doveva accorgersi da solo del link "Esci".
        # Svuotare la cache del browser non serviva: i cookie non sono cache.
        # /landing-logout sta sulla root app, azzera quella scelta e riporta al
        # form di accesso pulito.
        # current_app e non app: vedi la nota in consume_autologin_token.
        idx_app = current_app.config.get('TENANT_IDX')
        if idx_app is not None and 'user_id' in session:
            if str(session.get('tenant_idx')) != str(idx_app):
                current_app.logger.warning('[SESSIONE] marchio %r su tenant %r: espulsione',
                                           session.get('tenant_idx'), idx_app)
                session.clear()
                return redirect('/landing-logout')

        if (ep not in allowed_endpoints) and ('user_id' not in session):
            # Se è una richiesta AJAX/fetch, restituisci 401 JSON
            is_ajax = (
                request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
                request.accept_mimetypes.best == 'application/json' or
                request.content_type == 'application/json' or
                '/api/' in request.path
            )
            if is_ajax:
                return jsonify({'error': 'session_expired', 'message': 'Sessione scaduta'}), 401
            return redirect(url_for('landing'))

    # ---- PING: verifica raggiungibilità dell'app (non tocca il DB) ----
    @app.get("/ping")
    def ping():
        resp = app.response_class(
            response=json.dumps({"ok": True}),
            status=200,
            mimetype="application/json"
        )
        return resp

        # ---- HEALTH CHECK: verifica raggiungibilità DB (usato dal client per capire se è "online") ----
    @app.get("/healthz")
    def healthz():
        try:
            db.session.execute(text("SELECT 1"))
            return {"ok": True, "db": "up"}, 200
        except Exception as e:
            # Non trapelo stacktrace lato client, basta l'esito
            return {"ok": False, "db": "down"}, 503

    # ── Conteggio del traffico (pannello owner) ───────────────────────────
    # Due hook leggerissimi: uno segna l'inizio, l'altro somma in memoria. Il
    # database lo si tocca una volta all'ora, quando cambia l'ora e c'e' un
    # blocco da scaricare - non a ogni richiesta, altrimenti si consumerebbe
    # piu' database per misurare il traffico che per servirlo.
    #
    # Volutamente fuori da qualunque try di comodo: se il conteggio fallisce
    # non deve rompere la risposta, ma nemmeno restare invisibile.
    @app.before_request
    def _traffico_inizio():
        g._t_inizio = time.monotonic()

    @app.after_request
    def _traffico_fine(response):
        inizio = getattr(g, '_t_inizio', None)
        if inizio is None:
            return response
        try:
            from appl.services.usage_monitor import registra_richiesta, scarica_traffico
            da_scaricare = registra_richiesta((time.monotonic() - inizio) * 1000.0,
                                              response.status_code)
            # Lo scarico avviene fuori dal lock e una sola volta all'ora: e' la
            # prima richiesta dell'ora nuova a pagare la INSERT dell'ora vecchia.
            if da_scaricare:
                scarica_traffico(da_scaricare)
        except Exception:
            app.logger.debug("[traffico] conteggio non riuscito", exc_info=True)
        return response

    # ── Esaurimento connessioni al database ───────────────────────────────
    # Registrato qui, una volta per app, invece che nelle singole rotte:
    # il problema puo' presentarsi ovunque e non deve dipendere da chi si e'
    # ricordato di intercettarlo.
    #
    # Due errori distinti, stesso sintomo per il negozio:
    #   TimeoutError     -> il pool dell'app e' pieno (attesa oltre pool_timeout)
    #   OperationalError -> gli slot del SERVER sono finiti ("remaining
    #                       connection slots are reserved...")
    # Il secondo arriva anche per altre cause (server irraggiungibile), quindi
    # si distingue leggendo il testo.
    from sqlalchemy.exc import TimeoutError as _SATimeout, OperationalError as _SAOperational

    def _avvisa_connessioni(origine, err):
        try:
            from appl.services.error_log import log_connessioni_esaurite
            db.session.rollback()      # la sessione e' sporca: senza, l'insert fallirebbe
            log_connessioni_esaurite(origine, str(err)[:300])
        except Exception:
            app.logger.exception("[connessioni] impossibile registrare l'avviso")

    @app.errorhandler(_SATimeout)
    def _pool_pieno(err):
        _avvisa_connessioni('pool applicativo pieno', err)
        return {"ok": False, "errore": "Servizio momentaneamente occupato, riprova."}, 503

    @app.errorhandler(_SAOperational)
    def _db_non_disponibile(err):
        testo = str(err).lower()
        if 'remaining connection slots' in testo or 'too many clients' in testo:
            _avvisa_connessioni('slot del server esauriti', err)
        else:
            app.logger.exception("[db] errore operativo")
        return {"ok": False, "errore": "Database momentaneamente non raggiungibile."}, 503

    return app
