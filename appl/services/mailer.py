"""Invio e-mail tramite Azure Communication Services.

Perche' ACS e non un SMTP qualunque: e' il canale che l'app di prenotazione usa
gia' da mesi (`routes/booking.py` nel repo booking), con lo stesso dominio
mittente verificato e la stessa risorsa Azure. Riusare quello vuol dire zero
configurazione nuova, zero domini da far accettare ai filtri antispam e un solo
posto in cui guardare quando una mail non arriva.

Le variabili sono le STESSE del repo booking, di proposito:

    AZURE_EMAIL_CONNECTION_STRING   la risorsa ACS
    AZURE_EMAIL_SENDER              il mittente verificato

Se mancano, `attivo()` risponde False e `invia()` non solleva: la pagina che
consegna le credenziali continua a funzionare mostrandole a schermo. Una mail
che non parte non deve mai impedire a un potenziale cliente di entrare.

CAPIENZA (misurata il 03/09/2026): il picco reale e' 16 e-mail in un'ora sul
tenant piu' attivo, contro un tetto ACS di 100 all'ora condiviso da tutta la
sottoscrizione. Una prova gratuita ne aggiunge UNA per attivazione. Non e' il
canale da cui arriveranno i guai.
"""

from __future__ import annotations

import html as _html
import os
import re


def attivo() -> bool:
    """Vero se l'invio e' configurato. Da chiamare prima di promettere una mail."""
    return bool(os.environ.get('AZURE_EMAIL_CONNECTION_STRING')
                and os.environ.get('AZURE_EMAIL_SENDER'))


def _testo_da_html(contenuto: str) -> str:
    """Versione testuale: alcuni client la preferiscono, i filtri antispam la
    pretendono.

    ⚠️ Gli indirizzi dei collegamenti vanno TENUTI. Una conversione che toglie
    i tag e basta trasforma "<a href='...'>Entra nella prova</a>" nella frase
    "Entra nella prova" e basta: chi legge la versione testuale si ritrova un
    invito a cliccare senza niente da cliccare.
    """
    testo = contenuto or ''
    # Prima i collegamenti, finche' l'indirizzo c'e' ancora.
    def _link(m):
        indirizzo = m.group(1)
        etichetta = re.sub(r'<[^>]+>', '', m.group(2)).strip()
        # Quando l'etichetta e' gia' l'indirizzo, ripeterlo darebbe
        # "https://...: https://...".
        return indirizzo if etichetta in ('', indirizzo) else '%s: %s' % (etichetta, indirizzo)

    testo = re.sub(r'<a\s[^>]*href="([^"]+)"[^>]*>(.*?)</a>', _link,
                   testo, flags=re.S | re.I)
    testo = re.sub(r'<br\s*/?>', '\n', testo)
    testo = re.sub(r'</(p|div|h1|h2|h3|li|tr)>', '\n', testo)
    testo = re.sub(r'<[^>]+>', '', testo)
    testo = _html.unescape(testo)
    # Rientri dell'HTML: nel testo semplice diventano spazi a caso a inizio riga.
    testo = '\n'.join(riga.strip() for riga in testo.splitlines())
    return re.sub(r'\n{3,}', '\n\n', testo).strip()


def invia(destinatario: str, oggetto: str, contenuto_html: str,
          logger=None) -> bool:
    """Manda una e-mail. Ritorna True solo se ACS conferma l'invio.

    Non solleva mai: chi chiama decide cosa dire all'utente in base all'esito,
    e nel dubbio non promette nulla.
    """
    if not destinatario or not attivo():
        if logger:
            logger.info("[mail] invio saltato: configurazione ACS assente")
        return False
    try:
        from azure.communication.email import EmailClient
    except ImportError:
        if logger:
            logger.warning("[mail] azure-communication-email non installato")
        return False

    mittente = os.environ['AZURE_EMAIL_SENDER'].strip()
    try:
        client = EmailClient.from_connection_string(
            os.environ['AZURE_EMAIL_CONNECTION_STRING'])
        messaggio = {
            'senderAddress': mittente,
            'recipients': {'to': [{'address': destinatario}]},
            'content': {
                'subject': oggetto,
                'html': contenuto_html,
                'plainText': _testo_da_html(contenuto_html),
            },
        }
        risultato = client.begin_send(messaggio).result()
        ok = getattr(risultato, 'status', 'Succeeded') == 'Succeeded'
        if logger:
            logger.info("[mail] %s -> %s (%s)", oggetto, destinatario,
                        'inviata' if ok else 'rifiutata')
        return ok
    except Exception:
        if logger:
            logger.exception("[mail] invio fallito verso %s", destinatario)
        return False


# ═══════════════════════════════════════════════════════════════════════
#  TESTI DELLA PROVA GRATUITA
#
#  HTML volutamente scarno: niente immagini, niente fogli di stile esterni,
#  niente tabelle di impaginazione. Una mail di servizio deve arrivare e
#  leggersi, anche su un telefono con le immagini bloccate.
# ═══════════════════════════════════════════════════════════════════════

_CORNICE = """\
<div style="font-family:Arial,Helvetica,sans-serif;font-size:15px;color:#333;
            line-height:1.6;max-width:520px;">
  %s
  <p style="margin-top:26px;padding-top:14px;border-top:1px solid #e2e2e2;
            font-size:12px;color:#999;">
    Tosca — il gestionale per centri estetici e solarium.<br>
    Hai ricevuto questo messaggio perche' hai chiesto la prova gratuita su
    tosca-crm.it. Se non sei stato tu, ignora pure: senza il link qui sopra
    non si entra da nessuna parte.
  </p>
</div>"""


def testo_credenziali(referente: str, url: str, utente: str, password: str,
                      link: str) -> tuple[str, str]:
    corpo = """
  <p>Ciao %s,</p>
  <p>la tua prova di Tosca &egrave; pronta. Hai <b>sette giorni</b> per girarci
     dentro con l'agenda di un centro di esempio, gi&agrave; piena di
     appuntamenti e di incassi.</p>
  <p style="margin:22px 0;">
    <a href="%s" style="background:#4a7c59;color:#fff;text-decoration:none;
       padding:12px 22px;border-radius:6px;display:inline-block;">Entra nella prova</a>
  </p>
  <p>Se il pulsante non funziona, entra da qui:</p>
  <p style="background:#f4f4f4;padding:12px;border-radius:6px;">
    Indirizzo: <a href="%s">%s</a><br>
    Utente: <b>%s</b><br>
    Password: <b>%s</b>
  </p>
  <p>Durante la prova sono attive <b>Agenda</b> e <b>Report</b>. Cassa,
     prenotazioni online, pacchetti e messaggi automatici fanno parte della
     versione completa: dentro il programma trovi un riquadro che ti racconta
     cosa fanno.</p>
  <p><b>I dati che vedi sono inventati</b>: non inserire nomi o numeri di
     persone vere. Al settimo giorno la prova si chiude da sola e il contenuto
     viene cancellato.</p>
  <p>Se qualcosa non ti torna, rispondi a questa mail.</p>
""" % (_html.escape(referente or 'ciao'), _html.escape(link),
       _html.escape(url), _html.escape(url), _html.escape(utente),
       _html.escape(password))
    return "La tua prova di Tosca e' pronta", _CORNICE % corpo


def testo_codice(referente: str, codice: str, minuti: int) -> tuple[str, str]:
    """Il codice sta anche nell'oggetto: cosi' si legge dall'anteprima del
    telefono senza nemmeno aprire il messaggio."""
    corpo = """
  <p>Ciao %s,</p>
  <p>ecco il codice per aprire la tua prova di Tosca:</p>
  <p style="font-size:32px;letter-spacing:6px;font-weight:bold;color:#4a3543;
            background:#f4f4f4;padding:16px;border-radius:8px;text-align:center;
            margin:22px 0;">%s</p>
  <p>Scrivilo nella pagina da cui l'hai chiesto. Vale <b>%d minuti</b>.</p>
  <p>Se non hai chiesto tu nulla, butta pure questo messaggio: senza il codice
     non succede niente.</p>
""" % (_html.escape(referente or 'ciao'), _html.escape(codice), minuti)
    return "%s e' il tuo codice per la prova di Tosca" % codice, _CORNICE % corpo


def testo_in_coda(referente: str, posizione: int, data: str) -> tuple[str, str]:
    quando = (" La tua dovrebbe partire intorno al <b>%s</b>." % _html.escape(data)) if data else ""
    corpo = """
  <p>Ciao %s,</p>
  <p>in questo momento le tre prove disponibili sono tutte in corso: sei il
     <b>%d&ordm;</b> in lista.%s</p>
  <p>Ti scriviamo noi appena si libera un posto, non devi ricontrollare niente.
     Da quel momento avrai <b>tre giorni</b> per attivarla, poi il posto passa
     a chi viene dopo.</p>
  <p>Se hai fretta facciamo prima cos&igrave;: mezz'ora insieme, ti mostriamo
     Tosca dal vivo e rispondiamo alle tue domande. Rispondi a questa mail e
     ci mettiamo d'accordo.</p>
""" % (_html.escape(referente or 'ciao'), posizione, quando)
    return "Sei in lista per la prova di Tosca", _CORNICE % corpo


def testo_tocca_a_te(referente: str, url: str, utente: str, password: str,
                     link: str) -> tuple[str, str]:
    corpo = """
  <p>Ciao %s,</p>
  <p>si &egrave; liberato un posto: la tua prova di Tosca &egrave; pronta.</p>
  <p style="margin:22px 0;">
    <a href="%s" style="background:#4a7c59;color:#fff;text-decoration:none;
       padding:12px 22px;border-radius:6px;display:inline-block;">Entra nella prova</a>
  </p>
  <p style="background:#f4f4f4;padding:12px;border-radius:6px;">
    Indirizzo: <a href="%s">%s</a><br>
    Utente: <b>%s</b><br>
    Password: <b>%s</b>
  </p>
  <p><b>Entra entro tre giorni</b>: dopo, il posto passa al prossimo in lista.
     I sette giorni di prova partono dal tuo primo accesso, non da oggi.</p>
""" % (_html.escape(referente or 'ciao'), _html.escape(link),
       _html.escape(url), _html.escape(url), _html.escape(utente),
       _html.escape(password))
    return "Tocca a te: la prova di Tosca e' pronta", _CORNICE % corpo
