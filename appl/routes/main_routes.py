import os
import time
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from werkzeug.security import check_password_hash
from appl.models import BusinessInfo, User

# Crea un nuovo Blueprint
main_bp = Blueprint('main', __name__)

# --- Logica per il blocco tentativi di login ---
_login_attempts = {}
MAX_LOGIN_ATTEMPTS = int(os.getenv('MAX_LOGIN_ATTEMPTS', '10'))
LOGIN_WINDOW_SECONDS = int(os.getenv('LOGIN_WINDOW_SECONDS', '300'))

def record_login_failure(username):
    now = time.time()
    entry = _login_attempts.get(username)
    if not entry or (now - entry['first'] > LOGIN_WINDOW_SECONDS):
        entry = {'count': 1, 'first': now}
    else:
        entry['count'] += 1
    _login_attempts[username] = entry
    return entry

def reset_login_attempts(username):
    _login_attempts.pop(username, None)

def is_account_locked(username):
    entry = _login_attempts.get(username)
    if not entry:
        return False
    if time.time() - entry['first'] > LOGIN_WINDOW_SECONDS:
        _login_attempts.pop(username, None)
        return False
    return entry.get('count', 0) >= MAX_LOGIN_ATTEMPTS

@main_bp.route('/', methods=['GET', 'POST'])
def landing():
    # Se l'utente è già loggato, reindirizzalo al calendario
    if 'user_id' in session:
        return redirect(url_for('calendar.calendar_home'))

    attempts_count = 0
    reset_email = ''
    try:
        # Usa la sessione del DB per la query
        biz = BusinessInfo.query.first()
        if biz:
            reset_email = biz.email
    except Exception as e:
        current_app.logger.error(f"Errore nel recuperare BusinessInfo: {e}")
        reset_email = ''

    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()

        if username and is_account_locked(username):
            current_app.logger.warning("Account bloccato per troppi tentativi: %s", username)
            attempts_count = _login_attempts.get(username, {}).get('count', 0)
            return render_template('landing.html', login_attempts=attempts_count, reset_email=reset_email)

        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).one_or_none()
        
        if user and check_password_hash(user.password, password):
            reset_login_attempts(username)
            session.clear()
            session.permanent = True
            session['user_id'] = user.id
            try:
                from flask_wtf.csrf import generate_csrf
                generate_csrf()
            except Exception:
                pass
            return redirect(url_for('calendar.calendar_home'))
        else:
            entry = record_login_failure(username)
            attempts_count = entry.get('count', 0)
            current_app.logger.warning("Login fallito per username=%s (tentativi: %s)", username, attempts_count)
            flash('Credenziali non valide', 'danger')

    return render_template('landing.html', login_attempts=attempts_count, reset_email=reset_email)

@main_bp.route('/logout')
def logout():
    session.clear()
    flash('Sei stato disconnesso.', 'info')
    return redirect(url_for('main.landing'))