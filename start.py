import os, sys, time, socket, subprocess, multiprocessing, shutil, requests, zipfile, tempfile
from waitress import serve
from dotenv import load_dotenv

# CWD accanto allo script/exe
if getattr(sys, "frozen", False):
    os.chdir(os.path.dirname(sys.executable))
else:
    os.chdir(os.path.dirname(__file__))

# Carica .env accanto allo script/exe
load_dotenv(dotenv_path=os.path.join(os.getcwd(), '.env'))

# ============ AUTO-UPDATE DA GITHUB ============
GITHUB_REPO = "AlexBudet/SunBooking"  # <-- MODIFICA CON IL TUO REPO
GITHUB_BRANCH = "main"
VERSION_FILE = os.path.join(os.getcwd(), ".version")
UPDATE_ENABLED = os.getenv("AUTO_UPDATE", "1") == "1"

def get_local_version():
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, "r") as f:
            return f.read().strip()
    return None

def get_remote_version():
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/commits/{GITHUB_BRANCH}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("sha", "")[:12]
    except Exception as e:
        print(f"[AutoUpdate] Errore controllo versione: {e}")
    return None

def download_and_apply_update():
    try:
        print("[AutoUpdate] Scarico aggiornamento...")
        zip_url = f"https://github.com/{GITHUB_REPO}/archive/refs/heads/{GITHUB_BRANCH}.zip"
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = os.path.join(tmpdir, "update.zip")
            resp = requests.get(zip_url, timeout=60, stream=True)
            with open(zip_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(tmpdir)
            
            # Trova la cartella estratta (es. repo-main/)
            extracted = [d for d in os.listdir(tmpdir) if os.path.isdir(os.path.join(tmpdir, d))]
            if not extracted:
                print("[AutoUpdate] Nessuna cartella trovata nello zip")
                return False
            
            src_dir = os.path.join(tmpdir, extracted[0])
            dest_dir = os.getcwd()
            
            # Copia i file (escludi .env, .version, eventuali file locali)
            exclude = {".env", ".version", "browser-profile", "__pycache__", ".git"}
            for item in os.listdir(src_dir):
                if item in exclude:
                    continue
                s = os.path.join(src_dir, item)
                d = os.path.join(dest_dir, item)
                if os.path.isdir(s):
                    if os.path.exists(d):
                        shutil.rmtree(d)
                    shutil.copytree(s, d)
                else:
                    shutil.copy2(s, d)
            
            print("[AutoUpdate] Aggiornamento applicato!")
            return True
    except Exception as e:
        print(f"[AutoUpdate] Errore durante aggiornamento: {e}")
        return False

def save_version(version):
    with open(VERSION_FILE, "w") as f:
        f.write(version)

def check_and_update():
    if not UPDATE_ENABLED:
        return
    
    local_ver = get_local_version()
    remote_ver = get_remote_version()
    
    if not remote_ver:
        print("[AutoUpdate] Impossibile verificare aggiornamenti")
        return
    
    if local_ver == remote_ver:
        print(f"[AutoUpdate] Versione attuale: {local_ver}")
        return
    
    print(f"[AutoUpdate] Nuova versione disponibile: {remote_ver} (locale: {local_ver})")
    if download_and_apply_update():
        save_version(remote_ver)
        print("[AutoUpdate] Riavvio necessario per completare l'aggiornamento...")
        # Riavvia lo script
        os.execv(sys.executable, [sys.executable] + sys.argv)

# Esegui controllo aggiornamenti all'avvio
check_and_update()
# ============ FINE AUTO-UPDATE ============

from appl import create_app, db

# Crea app
db_uri = os.getenv('SQLALCHEMY_DATABASE_URI')
try:
    app = create_app(db_uri)
except Exception as e:
    print(f"Errore create_app: {e}")
    input("Premi Invio per chiudere...")
    sys.exit(1)

# SECRET_KEY
app.secret_key = os.getenv('SECRET_KEY') or os.urandom(24)

# CREA TABELLE SE NON ESISTONO
with app.app_context():
    db.create_all()

PORT = 5050

def start_server():
    try:
        serve(app, host='127.0.0.1', port=PORT)
    except Exception as e:
        print(f"Errore serve(): {e}")
        raise

def wait_for_server(port, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False

def launch_app_window(url: str):
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
    ]
    browser = next((p for p in candidates if os.path.exists(p)), None)
    if browser:
        profile_dir = os.path.join(os.getenv('LOCALAPPDATA', os.getcwd()), 'SunBooking', 'browser-profile')
        os.makedirs(profile_dir, exist_ok=True)
        args = [
            browser, f"--app=http://127.0.0.1:{PORT}",
            "--disable-extensions", "--no-first-run",
            "--disable-features=TranslateUI",
            f"--user-data-dir={profile_dir}",
            "--start-maximized",
        ]
        if os.getenv("KIOSK", "0") == "1":
            args.append("--kiosk")
            args.append("--edge-kiosk-type=fullscreen")
        return subprocess.Popen(args)
    else:
        import webbrowser
        webbrowser.open(f"http://127.0.0.1:{PORT}")
        return None

if __name__ == "__main__":
    multiprocessing.freeze_support()

    # Avvia server in PROCESSO separato (killabile)
    server_proc = multiprocessing.Process(target=start_server, daemon=True)
    server_proc.start()

    print(f"Avvio server su http://127.0.0.1:{PORT} ...")
    if not wait_for_server(PORT, 20):
        print("Server non avviato (controlla .env/DB).")
        if server_proc.is_alive():
            server_proc.terminate()
        sys.exit(1)

    print("Apro finestra app…")
    proc = launch_app_window(f"http://127.0.0.1:{PORT}")
    try:
        if proc:
            proc.wait()  # Quando chiudi la finestra, esce qui
        else:
            # Fallback: nessun handle al browser → tieni vivo finché non viene chiuso esternamente
            while True:
                time.sleep(3600)
    finally:
        # Chiudi server e termina il processo principale
        try:
            if server_proc.is_alive():
                server_proc.terminate()
                server_proc.join(timeout=5)
        finally:
            os._exit(0)