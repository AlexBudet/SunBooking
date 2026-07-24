"""
Immagini dei macchinari solarium (lampade) mostrate sui tasti della barra
"Monitor Lampade" del Calendario.

Le immagini vivono sul database, nelle colonne solarium_devices.immagine
(BYTEA) e solarium_devices.immagine_mime (VARCHAR) create dalla migrazione
manuale migrations/manual_solarium_device_images.sql.

L'accesso e' in SQL diretto (niente colonne aggiunte a models.py): se la
migrazione non e' ancora stata lanciata su un database, ogni funzione degrada
in modo silenzioso (nessuna immagine) e il resto del programma continua a
funzionare esattamente come prima.
"""
import logging

from sqlalchemy import text

from .. import db

logger = logging.getLogger('SunBooking')

# Le immagini sono mostrate a max 60x60 px: si salvano a 120x120 (2x, per
# schermi retina) cosi' restano pochi KB l'una.
MAX_IMAGE_SIZE_PX = 120
# Limite di upload accettato prima dell'elaborazione
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'}


# Diventa False al primo errore SQL (colonne non ancora create dalla migrazione):
# evita di ripetere la query fallita a ogni polling del Monitor Lampade e di
# riempire il log. Torna a essere ritentata al riavvio dell'applicazione.
_columns_available = True


def _fail_soft(exc, what):
    """Colonne non ancora create (o altro errore SQL): rollback e via, senza
    rompere la pagina che ci sta chiamando."""
    global _columns_available
    try:
        db.session.rollback()
    except Exception:
        pass
    if _columns_available:
        logger.warning(
            "Immagini macchinari solarium non disponibili (%s): %s — lanciare "
            "migrations/manual_solarium_device_images.sql sul database.", what, exc)
    _columns_available = False


def device_ids_with_image():
    """Set degli id dei macchinari che hanno un'immagine salvata."""
    if not _columns_available:
        return set()
    try:
        rows = db.session.execute(text(
            "SELECT id FROM solarium_devices "
            "WHERE immagine IS NOT NULL AND is_deleted = false"
        )).fetchall()
        return {r[0] for r in rows}
    except Exception as e:
        _fail_soft(e, "lettura elenco")
        return set()


def get_device_image(device_id):
    """Restituisce (bytes, mime) dell'immagine del macchinario, o (None, None)."""
    try:
        row = db.session.execute(text(
            "SELECT immagine, immagine_mime FROM solarium_devices WHERE id = :id"
        ), {'id': device_id}).first()
    except Exception as e:
        _fail_soft(e, "lettura immagine")
        return None, None
    if not row or row[0] is None:
        return None, None
    return bytes(row[0]), row[1] or 'image/png'


def set_device_image(device_id, data, mime):
    """Salva l'immagine (bytes gia' ridimensionati) sul macchinario."""
    global _columns_available
    try:
        db.session.execute(text(
            "UPDATE solarium_devices "
            "SET immagine = :img, immagine_mime = :mime, updated_at = NOW() "
            "WHERE id = :id"
        ), {'img': data, 'mime': mime, 'id': device_id})
        db.session.commit()
        # La migrazione c'e': riabilita le letture eventualmente disattivate
        _columns_available = True
        return True
    except Exception as e:
        _fail_soft(e, "salvataggio immagine")
        return False


def clear_device_image(device_id):
    """Rimuove l'immagine dal macchinario."""
    try:
        db.session.execute(text(
            "UPDATE solarium_devices "
            "SET immagine = NULL, immagine_mime = NULL, updated_at = NOW() "
            "WHERE id = :id"
        ), {'id': device_id})
        db.session.commit()
        return True
    except Exception as e:
        _fail_soft(e, "rimozione immagine")
        return False


def process_upload(file_storage):
    """Valida e ridimensiona l'immagine caricata (max 120x120, proporzioni
    mantenute). Restituisce (bytes, mime) oppure solleva ValueError con un
    messaggio gia' pronto per la flash."""
    from PIL import Image
    import io

    if not file_storage or not file_storage.filename:
        raise ValueError("Nessun file selezionato.")

    filename = file_storage.filename.lower()
    ext = filename.rsplit('.', 1)[-1] if '.' in filename else ''
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Formato non supportato. Ammessi: PNG, JPEG, WebP, GIF, BMP.")

    file_storage.seek(0, 2)
    size = file_storage.tell()
    file_storage.seek(0)
    if size > MAX_UPLOAD_BYTES:
        raise ValueError("File troppo grande. Massimo consentito: 5MB.")

    try:
        img = Image.open(file_storage)
        has_alpha = (img.mode in ('RGBA', 'LA', 'PA')
                     or (img.mode == 'P' and 'transparency' in img.info))
        if has_alpha and img.mode != 'RGBA':
            img = img.convert('RGBA')
        elif not has_alpha and img.mode != 'RGB':
            img = img.convert('RGB')

        width, height = img.size
        if width > MAX_IMAGE_SIZE_PX or height > MAX_IMAGE_SIZE_PX:
            ratio = min(MAX_IMAGE_SIZE_PX / width, MAX_IMAGE_SIZE_PX / height)
            img = img.resize((max(1, int(width * ratio)), max(1, int(height * ratio))),
                             Image.LANCZOS)

        output = io.BytesIO()
        if has_alpha:
            img.save(output, format='PNG', optimize=True)
            mime = 'image/png'
        else:
            img.save(output, format='WEBP', quality=85, method=6)
            mime = 'image/webp'
        output.seek(0)
        return output.read(), mime
    except ValueError:
        raise
    except Exception as e:
        logger.error("Errore elaborazione immagine macchinario solarium: %s", e)
        raise ValueError("Immagine non valida o non elaborabile.")
