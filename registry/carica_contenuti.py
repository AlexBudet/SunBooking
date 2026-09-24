"""
Carica notizie e oroscopo della settimana in TUTTI i negozi, con un comando.

    py -3.13 registry/carica_contenuti.py notizie.json oroscopo.json
    py -3.13 registry/carica_contenuti.py notizie.json oroscopo.json --prova

Stesso batch, stesso contenuto, scritto:
  - nel registro centrale (contenuto_news, contenuto_oroscopo), da cui legge
    l'app con appl/contenuti_report.py nuovo; le tabelle si creano da sole
    se mancano (stesse istruzioni di registry/06_contenuti_report.sql);
  - nelle tabelle beauty_news e oroscopo_settimanale di ogni database del
    .env (SQLALCHEMY_DATABASE_URI* e DEMO_DATABASE_URI*), da cui leggono la
    versione precedente dell'app e gli exe dei saloni.
Cosi' qualunque versione sia online, tutti vedono gli stessi contenuti.

Prima di scrivere passa dalle stesse regole della pagina Contenuti Report
(appl/contenuti_report.py): notizie datate e fresche, oroscopo senza nomi di
negozi. Un solo errore di validazione e non si scrive niente da nessuna parte.
--prova: controlla e mostra cosa scriverebbe, senza scrivere.
"""

import os
import re
import sys
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from dotenv import dotenv_values                      # noqa: E402
from sqlalchemy import create_engine, text           # noqa: E402

from appl import contenuti_report as cr              # noqa: E402

ENV = dotenv_values(os.path.join(BASE, '.env'))


def database_dei_negozi():
    """(nome variabile, uri) di ogni database negozio e demo del .env."""
    chiavi = sorted(k for k in ENV
                    if re.fullmatch(r'(SQLALCHEMY|DEMO)_DATABASE_URI\d+', k) and ENV[k])
    return [(k, ENV[k]) for k in chiavi]


def nomi_negozi(reg):
    nomi = []
    with reg.connect() as c:
        nomi += [r[0] for r in c.execute(text("SELECT business_name FROM tenant")) if r[0]]
    for _, uri in database_dei_negozi():
        try:
            with create_engine(uri).connect() as c:
                n = c.execute(text("SELECT business_name FROM business_info LIMIT 1")).scalar()
                if n:
                    nomi.append(n)
        except Exception:
            pass
    return sorted(set(nomi))


def crea_tabelle_registro(reg):
    sql = open(os.path.join(BASE, 'registry', '06_contenuti_report.sql'), encoding='utf-8').read()
    sql = '\n'.join(riga for riga in sql.splitlines() if not riga.strip().startswith('--'))
    with reg.begin() as c:
        for istruzione in sql.split(';'):
            if istruzione.strip().upper().startswith('CREATE'):
                c.execute(text(istruzione))


def scrivi(conn, t_news, t_oroscopo, batch, notizie, oroscopo):
    for i, n in enumerate(notizie):
        conn.execute(text(
            f"INSERT INTO {t_news} (scan_batch, titolo, sintesi, categoria, fonte, url, "
            f"data_notizia, ordine) VALUES (:b, :titolo, :sintesi, :categoria, :fonte, "
            f":url, :data_notizia, :o)"), dict(n, b=batch, o=i))
    for i, (segno, testo) in enumerate(oroscopo):
        conn.execute(text(
            f"INSERT INTO {t_oroscopo} (scan_batch, segno, testo, ordine) "
            f"VALUES (:b, :segno, :testo, :o)"), dict(b=batch, segno=segno, testo=testo, o=i))


def main():
    argomenti = [a for a in sys.argv[1:] if not a.startswith('--')]
    prova = '--prova' in sys.argv
    if len(argomenti) != 2:
        sys.exit(__doc__)

    reg = create_engine(ENV['REGISTRY_DATABASE_URI'])
    notizie, avvisi_n = cr.valida_notizie(
        cr.carica_json(open(argomenti[0], encoding='utf-8').read()))
    nomi = nomi_negozi(reg)
    oroscopo, avvisi_o = cr.valida_oroscopo(
        cr.carica_json(open(argomenti[1], encoding='utf-8').read()), nomi)
    if avvisi_n or avvisi_o:
        sys.exit('Non scrivo niente, ci sono avvisi:\n  ' + '\n  '.join(avvisi_n + avvisi_o))

    batch = datetime.now().strftime('%Y%m%dT%H%M%S')
    print(f'Batch {batch}: {len(notizie)} notizie, {len(oroscopo)} segni. '
          f'Nomi controllati: {", ".join(nomi)}')
    if prova:
        print('--prova: niente scritto.')
        return

    crea_tabelle_registro(reg)
    with reg.begin() as c:
        scrivi(c, 'contenuto_news', 'contenuto_oroscopo', batch, notizie, oroscopo)
    print('  registro centrale: scritto')

    for chiave, uri in database_dei_negozi():
        eng = create_engine(uri)
        try:
            with eng.begin() as c:
                nome_db = c.execute(text('SELECT current_database()')).scalar()
                scrivi(c, 'beauty_news', 'oroscopo_settimanale', batch, notizie, oroscopo)
            print(f'  {nome_db} ({chiave}): scritto')
        except Exception as exc:
            print(f'  {chiave}: NON scritto ({str(exc).splitlines()[0]})')
        finally:
            eng.dispose()


if __name__ == '__main__':
    main()
