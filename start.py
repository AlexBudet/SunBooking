import os, sys, time, socket, subprocess, multiprocessing
from waitress import serve
from dotenv import load_dotenv

try:
    from .appl import create_app, db
except ImportError:
    from appl import create_app, db

# CWD accanto allo script/exe
if getattr(sys, "frozen", False):
    os.chdir(os.path.dirname(sys.executable))
else:
    os.chdir(os.path.dirname(__file__))

# Carica .env accanto allo script/exe
load_dotenv(dotenv_path=os.path.join(os.getcwd(), '.env'))

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