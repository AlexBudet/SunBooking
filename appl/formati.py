# appl/formati.py
"""Come si scrivono a video nomi di persona e date: una regola sola per tutta l'app.

Registrati in __init__.py anche come filtri Jinja (`nome_proprio`, `data_it`),
cosi' i template non devono rifarseli. La controparte JavaScript e'
window.capitalizeName (base.html, calendar.js, cassa.js): stessa regola.
"""
import html
from datetime import date, datetime

MESI_BREVI = ('GEN', 'FEB', 'MAR', 'APR', 'MAG', 'GIU',
              'LUG', 'AGO', 'SET', 'OTT', 'NOV', 'DIC')


def nome_proprio(testo):
    """Nome o cognome con la maiuscola all'inizio di ogni parola.

    "maria grazia" -> "Maria Grazia", "D'ANGELO" -> "D'Angelo",
    "anna-maria" -> "Anna-Maria", "ÉLISE" -> "Élise".

    str.title() e non capitalize(): capitalize() guarda solo la prima lettera
    della stringa e lasciava "Maria grazia" e "D'angelo". title() riparte dopo
    spazio, apostrofo (anche quello tipografico) e trattino, e conosce le
    lettere accentate. Le entita' HTML (&#39;) arrivano a volte dalla
    prenotazione online e vanno decodificate prima, se no "&#39;" resta a video.
    None e stringa vuota diventano '': dentro un f-string None scriverebbe "None".
    """
    if not testo:
        return ''
    return ' '.join(parola.title() for parola in html.unescape(str(testo)).split())


def data_it(valore):
    """Data a video nel formato dell'app: "06 NOV 2025".

    Accetta date, datetime o stringa che inizi con YYYY-MM-DD. Una stringa in
    un altro formato torna indietro com'e'; None e vuoto diventano ''.
    """
    if not valore:
        return ''
    if isinstance(valore, str):
        try:
            valore = date.fromisoformat(valore.strip()[:10])
        except ValueError:
            return valore
    if not isinstance(valore, (date, datetime)):
        return str(valore)
    return f"{valore.day:02d} {MESI_BREVI[valore.month - 1]} {valore.year}"
