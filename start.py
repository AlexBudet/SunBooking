import os, sys, time, socket, subprocess, multiprocessing, shutil, requests, zipfile, tempfile
import logging
from logging.handlers import RotatingFileHandler
from waitress import serve
from dotenv import load_dotenv

# CWD accanto allo script/exe
if getattr(sys, "frozen", False):
    os.chdir(os.path.dirname(sys.executable))
else:
    os.chdir(os.path.dirname(__file__))

# Carica .env accanto allo script/exe
load_dotenv(dotenv_path=os.path.join(os.getcwd(), '.env'))

# Setup logging su file
LOG_DIR = os.path.join(os.getenv('LOCALAPPDATA', os.getcwd()), 'SunBooking', 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, 'sunbooking.log')

# Formatter comune
log_formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Handler con rotazione (5MB max, 3 backup)
file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.DEBUG)

# Console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.INFO)

# Root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

# Logger per l'app
logger = logging.getLogger('SunBooking')
logger.info(f"=== SunBooking avviato === Log: {LOG_FILE}")

# Silenzia warning inutili di Waitress queue
logging.getLogger('waitress.queue').setLevel(logging.ERROR)

from appl import create_app, db

# Crea app
db_uri = os.getenv('SQLALCHEMY_DATABASE_URI')
try:
    app = create_app(db_uri)
except Exception as e:
    logger.error(f"Errore create_app: {e}")
    try:
        input("Premi Invio per chiudere...")
    except (RuntimeError, EOFError, OSError):
        time.sleep(5)
    sys.exit(1)

# SECRET_KEY
app.secret_key = os.getenv('SECRET_KEY') or os.urandom(24)

# CREA TABELLE SE NON ESISTONO
with app.app_context():
    db.create_all()

PORT = 5050

def start_server():
    try:
        # Configura logging Flask dentro il processo server
        app.logger.handlers = []
        app.logger.addHandler(file_handler)
        app.logger.addHandler(console_handler)
        app.logger.setLevel(logging.WARNING)
        
        # Log Waitress
        waitress_logger = logging.getLogger('waitress')
        waitress_logger.addHandler(file_handler)
        waitress_logger.setLevel(logging.INFO)
        
        logger.info(f"Server Waitress in ascolto su 127.0.0.1:{PORT}")
        serve(app, host='127.0.0.1', port=PORT)
    except Exception as e:
        logger.exception(f"Errore serve(): {e}")
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

    try:
        # Avvia server in PROCESSO separato (killabile)
        server_proc = multiprocessing.Process(target=start_server, daemon=True)
        server_proc.start()

        logger.info(f"Avvio server su http://127.0.0.1:{PORT} ...")
        if not wait_for_server(PORT, 20):
            logger.error("Server non avviato (controlla .env/DB).")
            if server_proc.is_alive():
                server_proc.terminate()
            sys.exit(1)

        # Se siamo in post-update, il browser è già aperto: non aprirne un altro
        post_update_flag = os.path.join(os.getenv('LOCALAPPDATA', os.getcwd()), 'SunBooking', '_post_update')
        is_post_update = os.path.exists(post_update_flag)
        if is_post_update:
            logger.info("Post-update rilevato: il browser è già aperto, non ne apro un altro")
            try:
                os.remove(post_update_flag)
            except Exception:
                pass
            proc = None
        else:
            logger.info("Apro finestra app...")
            proc = launch_app_window(f"http://127.0.0.1:{PORT}")
        try:
            if proc:
                proc.wait()
            else:
                while True:
                    time.sleep(3600)
        finally:
            logger.info("Chiusura applicazione...")
            try:
                if server_proc.is_alive():
                    server_proc.terminate()
                    server_proc.join(timeout=5)
            finally:
                os._exit(0)
    except Exception as e:
        logger.exception(f"Errore fatale: {e}")
        sys.exit(1)