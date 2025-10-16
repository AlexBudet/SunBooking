import os
import re
from urllib.parse import urlparse
from dotenv import load_dotenv
from flask import Flask, render_template, redirect, url_for, request
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from waitress import serve
from appl import create_app

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
        if q:
            return redirect(f"/s/{dbidx}{path}?{q}", code=302)
        return redirect(f"/s/{dbidx}{path}", code=302)
    return None

@root_app.route('/')
def root():
    return redirect(url_for('landing_web'))

@root_app.route('/landing-web')
def landing_web():
    links = []
    for idx, uri in pool.items():
        links.append({
            "id": str(idx),
            "label": db_label(uri),
            "url": f"/select-db/{idx}"
        })
    return render_template('landing_web.html', db_links=links)

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

def with_db_cookie(app, idx, secure=False):
    def wrapper(environ, start_response):
        def sr(status, headers, exc_info=None):
            cookie = "dbidx=" + str(idx) + "; Path=/; SameSite=Lax"
            if secure:
                cookie += "; Secure"
            headers.append(('Set-Cookie', cookie))
            return start_response(status, headers, exc_info)
        return app(environ, sr)
    return wrapper

mounts = {}
for idx, uri in pool.items():
    child = create_app(uri)
    child.secret_key = secret
    mounts[f"/s/{idx}"] = with_db_cookie(child, idx, secure=use_https)

application = DispatcherMiddleware(root_app, mounts)
app = application

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5050"))
    print(f"Avvio server su http://127.0.0.1:{port}/landing-web")
    serve(application, host='127.0.0.1', port=port)