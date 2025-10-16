# main.py
import os
import time
from flask import render_template, request, redirect, url_for, session, flash
from appl import create_app, db 
from appl.models import BusinessInfo, User, Subcategory, ServiceCategory
from dotenv import load_dotenv
from werkzeug.security import check_password_hash

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

load_dotenv()

def before_send(event, hint):
    # Rimuovi header, cookie e user
    if "request" in event:
        event["request"].pop("headers", None)
        event["request"].pop("cookies", None)
    event.pop("user", None)
    return event

def setup_database(app, _):
    """Crea le tabelle se non esistono e garantisce la presenza delle sottocategorie 'Prodotti'."""
    with app.app_context():
        db.create_all()  # Crea le tabelle se non esistono

        # Crea sottocategorie "Prodotti" se non esistono
        for categoria in ServiceCategory:
            if not Subcategory.query.filter_by(nome="Prodotti", categoria=categoria).first():
                db.session.add(Subcategory(nome="Prodotti", categoria=categoria))
        db.session.commit()

if __name__ == '__main__':
    db_uri = os.getenv('SQLALCHEMY_DATABASE_URI')
    app = create_app(db_uri)
    secret = os.getenv('SECRET_KEY')
    if not secret:
        raise RuntimeError("SECRET_KEY non impostata! Impostala come variabile d'ambiente.")
    app.secret_key = secret

    # Configurazione database
    setup_database(app, None)

        # Gestione sicura della sessione DB: rollback all'inizio di ogni request
    @app.before_request
    def ensure_clean_session():
        """
        Pulisce eventuali transazioni abortite residue all'inizio della request.
        Chiamare db.session.rollback() qui è sicuro e impedisce che una transazione
        abortata blocchi tutte le query successive nella stessa request.
        """
        try:
            db.session.rollback()
        except Exception:
            # In casi estremi rimuoviamo la sessione
            try:
                db.session.remove()
            except Exception:
                pass

    @app.teardown_request
    def shutdown_session(exception=None):
        """
        Alla fine della request, se c'è stata un'eccezione facciamo rollback,
        quindi rimuoviamo la sessione per evitare leak.
        """
        if exception is not None:
            try:
                db.session.rollback()
            except Exception:
                pass
        try:
            db.session.remove()
        except Exception:
            pass

    # Route principale per la landing page di login
    @app.route('/', methods=['GET', 'POST'])
    def landing():
        # valore di default per template
        attempts_count = 0
        reset_email = ''
        # tenta leggere l'email di reset dalla tabella BusinessInfo (se presente)
        try:
            biz = BusinessInfo.query.first()
            reset_email = getattr(biz, 'email', '') or getattr(biz, 'business_email', '') or ''
        except Exception:
            reset_email = ''

        if request.method == 'POST':
            username = (request.form.get('username') or '').strip()

            # controllo minimo: blocco per username se supera soglia
            if username and is_account_locked(username):
                app.logger.warning("Account bloccato temporaneamente per username=%s", username)
                # passa informazioni al template
                attempts_count = _login_attempts.get(username, {}).get('count', 0)
                return render_template('landing.html', login_attempts=attempts_count, reset_email=reset_email)

            password = request.form['password']
            user = User.query.filter_by(username=username).first()
            valid = False
            if user:
                try:
                    valid = check_password_hash(user.password, password)
                except Exception:
                    db.session.rollback()  # Ripristina la sessione in caso di errore
                    valid = False

            if valid:
                # Mitigazione session fixation: svuota la sessione precedente
                reset_login_attempts(username)
                session.clear()
                # Imposta il nuovo identificatore utente nella sessione rigenerata
                session['user_id'] = user.id
                # Rigenera token CSRF (se disponibile)
                try:
                    from flask_wtf.csrf import generate_csrf
                    generate_csrf()
                except Exception:
                    pass
                return redirect(url_for('calendar.calendar_home'))
            else:
                # fallimento: aumenta contatore (minimo impatto)
                entry = record_login_failure(username)
                attempts_count = entry.get('count', 0)
                app.logger.warning("Login fallito per username=%s (attempts=%s)", username, attempts_count)
                flash('Credenziali non valide', 'danger')

        # per GET o dopo POST mostriamo sempre i valori al template
        return render_template('landing.html', login_attempts=attempts_count, reset_email=reset_email)
    
    @app.route('/logout')
    def logout():
        session.pop('user_id', None)
        return redirect(url_for('landing'))

    # Avvia il server Flask
    app.run(
        host='127.0.0.1',
        port=5050,
        debug=False
    )
