"""
Foto allegate ai messaggi WhatsApp di marketing.

Chi carica la foto e' l'operatore, spesso dal telefono: file da 3-8 MB,
girati secondo l'EXIF. Qui si accettano PNG e JPG fino a MAX_UPLOAD_BYTES e se
ne ricava SEMPRE un JPEG col lato lungo al massimo MAX_LATO_PX: e' la misura a
cui WhatsApp comprime comunque le foto, quindi oltre non si vede niente di piu'
e si pagherebbero solo byte sul database e sulla chiamata a Unipile.

Sempre JPEG anche partendo da un PNG: la trasparenza su WhatsApp diventa uno
sfondo nero, quindi la si appoggia qui su bianco, dove si vede com'e'.
"""
import io
import logging

logger = logging.getLogger('SunBooking')

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_LATO_PX = 1600
QUALITA_JPEG = 82
ESTENSIONI_AMMESSE = {'png', 'jpg', 'jpeg'}
MIME = 'image/jpeg'


def elabora(file_storage):
    """Valida e ridimensiona la foto caricata. Restituisce i byte JPEG oppure
    solleva ValueError con un messaggio gia' pronto per l'operatore."""
    from PIL import Image, ImageOps

    if not file_storage or not file_storage.filename:
        raise ValueError("Nessuna foto selezionata.")

    nome = file_storage.filename.lower()
    ext = nome.rsplit('.', 1)[-1] if '.' in nome else ''
    if ext not in ESTENSIONI_AMMESSE:
        raise ValueError("Formato non supportato: la foto deve essere JPG o PNG.")

    file_storage.seek(0, 2)
    peso = file_storage.tell()
    file_storage.seek(0)
    if peso > MAX_UPLOAD_BYTES:
        raise ValueError("Foto troppo pesante: massimo 10 MB.")

    try:
        img = Image.open(file_storage)
        if img.format not in ('PNG', 'JPEG', 'MPO'):
            raise ValueError("Formato non supportato: la foto deve essere JPG o PNG.")
        # Le foto del telefono sono salvate "di lato" con l'orientamento
        # nell'EXIF: senza questo arriverebbero ruotate.
        img = ImageOps.exif_transpose(img)

        if img.mode in ('RGBA', 'LA', 'PA') or (img.mode == 'P' and 'transparency' in img.info):
            img = img.convert('RGBA')
            sfondo = Image.new('RGB', img.size, (255, 255, 255))
            sfondo.paste(img, mask=img.split()[-1])
            img = sfondo
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        img.thumbnail((MAX_LATO_PX, MAX_LATO_PX), Image.LANCZOS)

        out = io.BytesIO()
        img.save(out, format='JPEG', quality=QUALITA_JPEG, optimize=True, progressive=True)
        return out.getvalue()
    except ValueError:
        raise
    except Exception as e:
        logger.error("Errore elaborazione foto marketing: %s", e)
        raise ValueError("Foto non valida o non leggibile.")
