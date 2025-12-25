# appl/__init__.py
from flask_wtf.csrf import CSRFProtect, generate_csrf
from flask import Flask, current_app, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash
from argon2 import PasswordHasher, exceptions as argon2_exceptions
from sqlalchemy import text
import time
import json, os

# Istanza globale di SQLAlchemy
db = SQLAlchemy()
csrf = CSRFProtect()
app = None  # riferimento globale all’app
ph = PasswordHasher()

def create_app(db_uri: str | None = None):
    """
    Restituisce una nuova istanza Flask.
    - Usa SOLO PostgreSQL (es. Azure). Se la variabile non è impostata o non è PostgreSQL, solleva errore.
    """

    global app
    app = Flask(__name__)
    app.secret_key = os.getenv('SECRET_KEY') or os.urandom(24)

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

    # Inizializza estensione CSRF
    csrf.init_app(app)

    # Espone il token ai template Jinja come csrf_token()
    app.jinja_env.globals["csrf_token"] = generate_csrf

    # Solo PostgreSQL: niente fallback su SQLite/Dropbox
    if not db_uri or not db_uri.startswith("postgresql"):
        raise RuntimeError("Devi impostare la variabile d'ambiente SQLALCHEMY_DATABASE_URI con la stringa di connessione PostgreSQL!")
    app.config["SQLALCHEMY_DATABASE_URI"] = db_uri

    # Opzioni di pool per Azure (opzionali)
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        "pool_size": 15,                # Numero di connessioni persistenti
        "max_overflow": 10,             # Connessioni extra temporanee
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

    # Inizializza Flask-Migrate
    from flask_migrate import Migrate
    migrate = Migrate(app, db)

    # Importa e registra i blueprint
    from .routes.calendar import calendar_bp
    from .routes.settings import settings_bp
    from .routes.clients import clients_bp
    from .routes.services import services_bp
    from .routes.operators import operators_bp
    from appl.routes.cassa import cassa_bp
    from appl.routes.report import report_bp

    app.register_blueprint(calendar_bp,  url_prefix="/calendar")
    app.register_blueprint(settings_bp,  url_prefix="/settings")
    app.register_blueprint(clients_bp,   url_prefix="/clients")
    app.register_blueprint(services_bp,  url_prefix="/services")
    app.register_blueprint(operators_bp, url_prefix="/operators")
    app.register_blueprint(cassa_bp)
    app.register_blueprint(report_bp)

    # ---- CONTEXT PROCESSOR: current_user disponibile in tutti i template ----
    @app.context_processor
    def inject_current_user():
        user_id = session.get('user_id')
        from appl.models import User
        current_user = db.session.get(User, user_id) if user_id else None
        return dict(current_user=current_user)

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
                print(f"DEBUG: Tentativo login - Username: {username}, Password length: {len(password)}")
                current_app.logger.info(f"Tentativo login - Username: {username}")

                # controllo blocco account (minimo)
                if username and is_account_locked(username):
                    print(f"DEBUG: Account bloccato per {username}")
                    current_app.logger.warning("Account bloccato temporaneamente per username=%s", username)
                    flash('Troppi tentativi. Riprova più tardi.', 'danger')
                    return render_template('landing.html', login_attempts=None, reset_email=reset_email)

                user = None
                valid = False
                try:
                    user = User.query.filter_by(username=username).first() if username else None
                    print(f"DEBUG: User trovato: {user is not None}")
                except Exception:
                    # DB read error: rollback e fallimento silenzioso
                    try:
                        db.session.rollback()
                    except Exception:
                        pass
                    user = None

                if user:
                    print(f"DEBUG: User ID: {user.id}, Password hash presente: {user.password is not None}")
                    try:
                        valid = False
                        try:
                            valid = ph.verify(user.password, password)
                            if ph.check_needs_rehash(user.password):
                                user.password = ph.hash(password)
                                db.session.commit()
                            print(f"DEBUG: Password valida Argon2id: {valid}")
                        except (argon2_exceptions.VerifyMismatchError, argon2_exceptions.InvalidHash):
                            # Non è Argon2id, prova hash legacy
                            valid = check_password_hash(user.password, password)
                            print(f"DEBUG: Password valida legacy: {valid}")
                            if valid:
                                user.password = ph.hash(password)
                                db.session.commit()
                    except Exception as e:
                        print(f"DEBUG: Errore verifica password: {e}")
                        try:
                            db.session.rollback()
                        except Exception:
                            pass
                        valid = False

                if valid:
                    print(f"DEBUG: Login OK per {username}")
                    # login OK
                    reset_login_attempts(username)
                    session.clear()
                    session['user_id'] = user.id
                    # rigenera CSRF token se possibile
                    try:
                        from flask_wtf.csrf import generate_csrf
                        generate_csrf()
                    except Exception:
                        pass
                    try:
                        redirect_url = url_for('calendar.calendar_home')
                        print(f"DEBUG: Redirect URL: {redirect_url}")
                        return redirect(redirect_url)
                    except Exception as e:
                        print(f"DEBUG: Errore url_for: {e}")
                        return f"Errore redirect: {e}", 500
                else:
                    print(f"DEBUG: Login fallito per {username}")
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
        session.pop('user_id', None)
        return redirect(url_for('landing'))

    # ---- LOGIN REQUIRED su tutte le route (eccetto whitelist) ----
    @app.before_request
    def require_login():
        allowed_endpoints = {'landing', 'healthz', 'static', 'ping'}
        ep = request.endpoint or ''
        print(f"DEBUG: require_login - Endpoint: {ep}, user_id in session: {'user_id' in session}")
        if (ep not in allowed_endpoints) and ('user_id' not in session):
            print(f"DEBUG: Redirect to landing")
            return redirect(url_for('landing'))
        else:
            print(f"DEBUG: Accesso permesso a {ep}")

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

    return app
