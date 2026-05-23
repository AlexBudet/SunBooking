import os, sys, time, socket, subprocess, multiprocessing, shutil, requests, zipfile, tempfile
import logging
import threading
from logging.handlers import RotatingFileHandler
from waitress import serve
from dotenv import load_dotenv


# ============================================================================
#   SPLASH SCREEN (tkinter, eseguito nel MAIN THREAD)
# ============================================================================
# Per animare la Progressbar serve il mainloop tkinter attivo nel main thread.
# Questo significa che tutto il lavoro pesante (create_app, avvio Waitress,
# lancio browser) deve girare in un BACKGROUND thread. Quando il browser e'
# pronto, il bg thread chiama splash.close_threadsafe() che fa destroy() sul
# main thread via root.after(0, ...): la finestra si chiude pulita e mainloop
# ritorna.
class SplashWindow:
    """Splash 360x240 con logo Tosca + barra di progresso indeterminata."""

    def __init__(self):
        self._root = None
        self._photo = None         # ref al PhotoImage (no GC)
        self._progress = None
        self._closed = False
        try:
            self._build()
        except Exception as e:
            try:
                print(f"[splash] non disponibile: {e}", file=sys.stderr)
            except Exception:
                pass
            self._root = None

    def _logo_path(self):
        if getattr(sys, "frozen", False):
            base = sys._MEIPASS  # type: ignore[attr-defined]
        else:
            base = os.path.dirname(__file__)
        return os.path.join(base, "appl", "static", "img", "logo-192.png")

    def _build(self):
        import tkinter as tk
        from tkinter import ttk

        root = tk.Tk()
        root.overrideredirect(True)
        root.attributes('-topmost', True)
        root.configure(bg='white')

        w, h = 360, 240
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        root.geometry(f"{w}x{h}+{x}+{y}")

        # Logo: tk.PhotoImage legge PNG nativamente (stdlib).
        # subsample(2,2) riduce 192px -> 96px senza dipendenze esterne.
        logo_path = self._logo_path()
        if os.path.isfile(logo_path):
            try:
                img = tk.PhotoImage(file=logo_path)
                self._photo = img.subsample(2, 2)
                tk.Label(root, image=self._photo, bg='white', bd=0).pack(pady=(22, 6))
            except Exception:
                self._photo = None

        tk.Label(
            root, text='TOSCA',
            font=('Arial', 22, 'bold'),
            bg='white', fg='#d6336c',
        ).pack()

        tk.Label(
            root, text='Avvio in corso...',
            font=('Arial', 11),
            bg='white', fg='#666',
        ).pack(pady=(2, 12))

        # Barra indeterminata: start() registra un after-callback che la
        # anima 'da sola' purche' il mainloop sia attivo.
        self._progress = ttk.Progressbar(
            root, mode='indeterminate', length=240,
        )
        self._progress.pack()
        self._progress.start(12)  # ms per frame

        self._root = root

    def mainloop(self):
        """Blocca il MAIN thread finche' close_threadsafe() non chiude
        la finestra. Senza questo, la Progressbar NON si anima."""
        if self._root is None:
            return
        try:
            self._root.mainloop()
        except Exception:
            pass

    def close_threadsafe(self):
        """Sicuro da chiamare da QUALSIASI thread: schedula la chiusura
        della finestra sul thread del mainloop tramite root.after(0, ...)."""
        if self._closed:
            return
        self._closed = True
        if self._root is None:
            return
        try:
            self._root.after(0, self._do_close)
        except Exception:
            pass

    def _do_close(self):
        try:
            if self._progress is not None:
                self._progress.stop()
        except Exception:
            pass
        try:
            self._root.quit()       # interrompe mainloop
            self._root.destroy()    # rimuove la finestra
        except Exception:
            pass


# ============================================================================
#   SETUP CWD / ENV / LOGGING
# ============================================================================
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


# ============================================================================
#   APP FLASK (lazy: creata on demand per coprirne l'avvio con lo splash)
# ============================================================================
from appl import create_app, db

db_uri = os.getenv('SQLALCHEMY_DATABASE_URI')

_app = None
_app_lock = threading.Lock()


def get_app():
    """Crea l'app Flask alla prima chiamata. Thread-safe via lock. Su Windows
    multiprocessing ri-importa questo modulo nel child: il child chiama
    start_server() che a sua volta richiama get_app(), quindi anche li' l'app
    viene creata correttamente."""
    global _app
    with _app_lock:
        if _app is None:
            a = create_app(db_uri)
            a.secret_key = os.getenv('SECRET_KEY') or os.urandom(24)
            with a.app_context():
                db.create_all()
            _app = a
        return _app


PORT = 5050


def start_server():
    try:
        a = get_app()
        # Configura logging Flask dentro il processo server
        a.logger.handlers = []
        a.logger.addHandler(file_handler)
        a.logger.addHandler(console_handler)
        a.logger.setLevel(logging.WARNING)

        # Log Waitress
        waitress_logger = logging.getLogger('waitress')
        waitress_logger.addHandler(file_handler)
        waitress_logger.setLevel(logging.INFO)

        logger.info(f"Server Waitress in ascolto su 127.0.0.1:{PORT}")
        serve(a, host='127.0.0.1', port=PORT)
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


def _startup_background(splash):
    """Eseguito in un thread separato: fa TUTTO il lavoro pesante (init app,
    Waitress, lancio browser) mentre il main thread anima lo splash. Quando
    il browser e' aperto chiude lo splash e attende che l'utente chiuda
    Chrome per terminare il processo."""
    try:
        # 1. Init Flask app (il vero costo: ~1-3s)
        get_app()

        # 2. Avvia server in processo separato (killabile)
        server_proc = multiprocessing.Process(target=start_server, daemon=True)
        server_proc.start()

        logger.info(f"Avvio server su http://127.0.0.1:{PORT} ...")

        if not wait_for_server(PORT, 20):
            logger.error("Server non avviato (controlla .env/DB).")
            if server_proc.is_alive():
                server_proc.terminate()
            splash.close_threadsafe()
            os._exit(1)

        # 3. Lancia browser (o saltalo se siamo in post-update)
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

        # 4. Browser pronto: chiudi lo splash dal main thread.
        splash.close_threadsafe()

        # 5. Attendi che l'utente chiuda il browser, poi termina il server.
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
        logger.exception(f"Errore fatale in startup: {e}")
        try:
            splash.close_threadsafe()
        except Exception:
            pass
        os._exit(1)


if __name__ == "__main__":
    multiprocessing.freeze_support()

    # Worker multiprocessing? Non eseguire il main flow (start_server e'
    # gia' richiamato da freeze_support tramite spawn_main).
    if multiprocessing.current_process().name != 'MainProcess':
        sys.exit(0)

    # Crea splash nel MAIN thread.
    splash = SplashWindow()

    # Lancia il lavoro pesante in un thread separato.
    bg = threading.Thread(
        target=_startup_background,
        args=(splash,),
        daemon=True,
        name="startup",
    )
    bg.start()

    # Pompa il mainloop tkinter (anima la Progressbar). Esce quando bg thread
    # chiama splash.close_threadsafe() -> root.quit() -> root.destroy().
    splash.mainloop()

    # Tieni in vita il main thread finche' Chrome resta aperto. Il bg thread
    # chiama os._exit() quando proc.wait() ritorna, quindi questo join non
    # ritorna in pratica.
    bg.join()
