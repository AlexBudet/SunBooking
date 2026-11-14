# appl/services/whatsapp_errori.py
"""Gli errori di Unipile scritti in modo che l'operatrice li capisca.

Unipile risponde con un JSON tecnico (es. HTTP 422 `errors/invalid_recipient`,
"Recipient cannot be reached"). Mostrato com'e' all'operatrice non dice niente;
il caso piu' frequente e' un cellulare che non ha WhatsApp.

Si riconosce il tipo cercandolo nel TESTO e non con json.loads: il marketing
salva la risposta gia' tagliata a 180 caratteri, e un JSON tagliato non si
legge piu'.

In `usage_events` e `marketing_invii` resta salvata la risposta originale, che
serve per la diagnosi: questa frase e' solo quella che si mostra.
"""


def numero_leggibile(numero):
    """39335123456 -> '+39 335 123456'. Altri prefissi: '+' e le cifre."""
    cifre = ''.join(ch for ch in str(numero or '') if ch.isdigit())
    if cifre.startswith('00'):
        cifre = cifre[2:]
    if cifre.startswith('39') and len(cifre) in (11, 12):
        return '+39 %s %s' % (cifre[2:5], cifre[5:])
    return ('+' + cifre) if cifre else ''


def non_su_whatsapp(testo_errore):
    """True se Unipile ha risposto che il destinatario non e' raggiungibile."""
    return 'errors/invalid_recipient' in str(testo_errore or '')


def spiega_errore(testo_errore, numero=None, breve=False):
    """La frase da mostrare all'operatrice, o None se l'errore non e' fra quelli
    riconosciuti (in quel caso chi chiama mostra il suo messaggio di sempre).

    breve=True per gli elenchi del marketing, dove davanti c'e' gia' il nome
    del cliente.
    """
    if not non_su_whatsapp(testo_errore):
        return None
    n = numero_leggibile(numero)
    frase = ('il numero %s non è su WhatsApp' % n) if n else 'il numero non è su WhatsApp'
    if breve:
        return frase
    return (frase[0].upper() + frase[1:] + '. Controlla che sia scritto giusto: '
            'se lo è, il cliente non usa WhatsApp e va contattato in un altro modo.')
