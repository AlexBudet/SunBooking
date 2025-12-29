import os
import re
from urllib.parse import urlparse
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, redirect, url_for, request
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from waitress import serve
from appl import create_app, db
from appl.models import BusinessInfo
import threading
import time as time_mod

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

def wbiztool_creds_for(idx: int):
    s = str(idx)
    return {
        "WBIZTOOL_API_KEY": os.getenv(f"WBIZTOOL_API_KEY{s}") or os.getenv("WBIZTOOL_API_KEY") or "",
        "WBIZTOOL_CLIENT_ID": os.getenv(f"WBIZTOOL_CLIENT_ID{s}") or os.getenv("WBIZTOOL_CLIENT_ID") or "",
        "WBIZTOOL_WHATSAPP_CLIENT_ID": os.getenv(f"WBIZTOOL_WHATSAPP_CLIENT_ID{s}") or os.getenv("WBIZTOOL_WHATSAPP_CLIENT_ID") or "",
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

@root_app.before_request
def root_redirect_to_selected_db():
    path = request.path or '/'
    if path in ('/', '/landing-web') or path.startswith('/select-db/') or path.startswith('/s/'):
        return None
    dbidx = request.cookies.get('dbidx', '').strip()
    if dbidx and dbidx.isdigit():
        q = request.query_string.decode('utf-8')
        target = f"/s/{dbidx}{path}"
        if q:
            target = f"{target}?{q}"
        return redirect(target, code=307)  # preserva POST/PUT/DELETE
    return None

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

    creds = wbiztool_creds_for(idx)
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

def _start_operator_scheduler_once():
    # Evita multi-avvio in ambienti con più worker (solo su Web App)
    if os.getenv('WEBSITE_SITE_NAME'):  # Solo su Azure Web App
        if hasattr(_start_operator_scheduler_once, '_started'):
            return
        _start_operator_scheduler_once._started = True

        def worker():
            import importlib
            # importa il modulo una volta e leggi attributi
            settings_mod = importlib.import_module('appl.routes.settings')
            process_operator_tick = getattr(settings_mod, 'process_operator_tick')

            while True:
                try:
                    for idx, child in children.items():
                        creds = wbiztool_creds_for(idx)
                        keys = list(creds.keys())
                        old = {k: os.environ.get(k) for k in keys}
                        try:
                            for k, v in creds.items():
                                if v:
                                    os.environ[k] = str(v)
                                else:
                                    os.environ.pop(k, None)
                            with child.app_context():
                                process_operator_tick()
                        except Exception as e:
                            print(f"[WA-OPERATOR][{idx}] tick error: {repr(e)}")
                        finally:
                            for k, v in old.items():
                                if v is None:
                                    os.environ.pop(k, None)
                                else:
                                    os.environ[k] = v
                except Exception as e:
                    print(f"[WA-OPERATOR] loop error: {repr(e)}")
                time_mod.sleep(60)

        t = threading.Thread(target=worker, name="wa_operator_scheduler", daemon=True)
        t.start()

# Chiama la funzione dopo aver creato i children
_start_operator_scheduler_once()

@root_app.route('/landing-web')
def landing_web():
    links = []
    for idx, uri in pool.items():
        label = db_label(uri)
        child = children.get(idx)
        if child:
            try:
                with child.app_context():
                    info = BusinessInfo.query.first()
                    if info and getattr(info, 'business_name', None):
                        label = info.business_name
            except Exception:
                pass
        links.append({
            "id": str(idx),
            "label": label,
            "url": f"/select-db/{idx}"
        })
    return render_template('landing_web.html', db_links=links, hide_cassa=True)

@root_app.route('/select-db/<idx>')
def select_db(idx):
    if not idx.isdigit() or int(idx) not in pool:
        return redirect(url_for('landing_web'))
    resp = redirect(f"/s/{idx}/", code=302)
    cookie = "dbidx=" + idx + "; Path=/; SameSite=Lax"
    if use_https:
        cookie += "; Secure"
    resp.headers.add('Set-Cookie', cookie)
    return resp

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5050"))
    print(f"Avvio server su http://127.0.0.1:{port}/landing-web")
    serve(application, host='127.0.0.1', port=port)