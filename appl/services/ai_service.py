"""
Info Service Layer (ex AI Booking Assistant).

L'assistente AI conversazionale (Groq/LLM) è stato RIMOSSO: in un gestionale di
estetica si è rivelato poco preciso e controproducente. I due badge deterministici
del calendario — "INFO" e "CERCA UN BUCO" — fanno tutto il lavoro necessario.

Questo modulo conserva SOLO gli helper deterministici (niente AI/LLM) usati dal
badge INFO via gli endpoint /api/info/* in appl/routes/calendar.py:
- find_client_by_text  → ricerca cliente (match esatto + fuzzy)
- build_client_info    → anagrafica + ultimo/prossimo appuntamento
"""

import logging
import unicodedata
from datetime import datetime, date

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Helper: normalizzazione date dal DB
# ──────────────────────────────────────────────

def _fmt_date(val) -> str:
    """
    Converte qualsiasi valore data in stringa 'YYYY-MM-DD'.
    Gestisce: date, datetime, str già formattata, None.
    """
    if val is None:
        return ""
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")
    if isinstance(val, date):
        return val.strftime("%Y-%m-%d")
    s = str(val)
    # Se è già YYYY-MM-DD prende solo i primi 10 char
    return s[:10] if len(s) >= 10 else s


def build_client_info(client_id: int) -> dict:
    """
    Restituisce i dati anagrafici del cliente (non lo storico appuntamenti).
    Usato dal badge INFO (endpoint /api/info/client/<id>).
    Distingue:
    - ultimo_appuntamento: ultimo appuntamento PRIMA di now (passato)
    - prossimo_appuntamento: primo appuntamento DA now in avanti (futuro)
    """
    from appl.models import Client, Appointment
    from datetime import datetime as dt_class

    client = Client.query.get(client_id)
    if not client:
        return {}

    now = dt_class.now()

    # Ultimo appuntamento PASSATO (start_time < now)
    last_appt = Appointment.query.filter(
        Appointment.client_id == client_id,
        Appointment.is_cancelled_by_client == False,
        Appointment.start_time < now,
    ).order_by(Appointment.start_time.desc()).first()

    last_appt_date = ""
    if last_appt and last_appt.start_time:
        last_appt_date = _fmt_date(last_appt.start_time)

    # Prossimo appuntamento FUTURO (start_time >= now)
    next_appt = Appointment.query.filter(
        Appointment.client_id == client_id,
        Appointment.is_cancelled_by_client == False,
        Appointment.start_time >= now,
    ).order_by(Appointment.start_time.asc()).first()

    next_appt_date = ""
    if next_appt and next_appt.start_time:
        next_appt_date = _fmt_date(next_appt.start_time)

    # Conta totale appuntamenti
    total_appts = Appointment.query.filter(
        Appointment.client_id == client_id,
        Appointment.is_cancelled_by_client == False,
    ).count()

    return {
        "id": client.id,
        "nome": client.cliente_nome or "",
        "cognome": client.cliente_cognome or "",
        "cellulare": client.cliente_cellulare or "",
        "email": getattr(client, 'cliente_email', "") or "",
        "sesso": getattr(client, 'cliente_sesso', "") or "",
        "data_nascita": _fmt_date(getattr(client, 'cliente_data_nascita', None)) or "",
        "data_registrazione": _fmt_date(getattr(client, 'created_at', None)) or "",
        "ultimo_appuntamento": last_appt_date,
        "prossimo_appuntamento": next_appt_date,
        "totale_appuntamenti": total_appts,
        "note": getattr(client, 'note', "") or "",
    }


def find_client_by_text(search: str) -> list:
    """
    Cerca cliente per nome, cognome o cellulare (OR). Usato dal badge INFO
    (endpoint /api/info/client/search).

    Strategia di ricerca (in ordine di priorità):
    1. Match esatto su inizio campo o inizio parola (LIKE pattern)
       - Evita match parziali errati: "Ciara" NON matcha "Sciara"
       - Supporta ricerca combinata nome+cognome su colonne separate
         es: "Cristina Gallo" → nome LIKE 'cristina%' AND cognome LIKE 'gallo%'
    2. Fuzzy matching (soglia 0.70) se nessun match esatto trovato
       - Tollerante a errori di battitura
         es: "Rachele Dell'Angelo" trova "Rachele Dall'Angelo"
         es: "Cone" trova "Coone" (1 char diff su 5 = 80% similarità)
    """
    from appl.models import Client
    from sqlalchemy import or_, func, and_

    # ── Normalizzazione input ────────────────────────────────────
    q = search.strip()
    if not q:
        return []

    q_lower = q.lower()
    parts   = q_lower.split()

    # ── Pattern LIKE per match su inizio campo / inizio parola ──
    # "q%"   → matcha dall'inizio del campo (es: "ciara%" matcha "Ciara" ma NON "Sciara")
    # "% q%" → matcha dall'inizio di qualsiasi parola interna (dopo uno spazio)
    starts_pattern = f"{q_lower}%"
    word_pattern   = f"% {q_lower}%"

    conditions = [
        func.lower(Client.cliente_nome).like(starts_pattern),
        func.lower(Client.cliente_nome).like(word_pattern),
        func.lower(Client.cliente_cognome).like(starts_pattern),
        func.lower(Client.cliente_cognome).like(word_pattern),
        Client.cliente_cellulare.contains(q),
    ]

    # ── Ricerca combinata nome+cognome (query con 2+ parole) ────
    # Per ogni permutazione parte[i] → nome, parte[j] → cognome
    # es: "Cristina Gallo" → (nome LIKE 'cristina%' AND cognome LIKE 'gallo%')
    if len(parts) >= 2:
        for i, nome_part in enumerate(parts):
            other_parts = [p for j, p in enumerate(parts) if j != i]
            for cognome_part in other_parts:
                conditions.append(
                    and_(
                        func.lower(Client.cliente_nome).like(f"{nome_part}%"),
                        func.lower(Client.cliente_cognome).like(f"{cognome_part}%"),
                    )
                )

    # ── Query DB (match esatto) ──────────────────────────────────
    results = Client.query.filter(
        Client.is_deleted == False,
        or_(*conditions)
    ).limit(20).all()

    exact_matches = [
        {
            "id":        c.id,
            "nome":      c.cliente_nome or "",
            "cognome":   c.cliente_cognome or "",
            "cellulare": c.cliente_cellulare or "",
            "ref":       f"C{c.id % 9999:04d}",
        }
        for c in results
    ]

    # ── Ritorna subito se trovati match esatti ───────────────────
    if exact_matches:
        return exact_matches

    # ── Fuzzy matching (fallback) ────────────────────────────────
    # Attivato solo se nessun match esatto trovato.
    # Soglia 0.70: sufficiente per tollerare varianti ortografiche comuni.
    logger.info(
        "find_client_by_text: nessun match esatto per '%s', provo fuzzy matching", q
    )

    fuzzy_results = _fuzzy_match_clients(q, threshold=0.70)

    if fuzzy_results:
        for fr in fuzzy_results:
            logger.info(
                "find_client_by_text: FUZZY MATCH '%s %s' (score=%.2f%%) per query '%s'",
                fr["client"].get("nome"),
                fr["client"].get("cognome"),
                fr["score"] * 100,
                q,
            )
        # Restituisce solo il dict cliente (senza score) per compatibilità col formato esistente
        return [fr["client"] for fr in fuzzy_results]

    # ── Nessun risultato ─────────────────────────────────────────
    logger.warning(
        "find_client_by_text: nessun cliente trovato per '%s' (né esatto né fuzzy)", q
    )
    return []


# ──────────────────────────────────────────────
# Fuzzy matching deterministico (no AI)
# ──────────────────────────────────────────────

def _normalize(text: str) -> str:
    """
    Normalizza per confronto fuzzy:
    - Rimuove accenti (é→e, è→e, à→a)
    - Normalizza apostrofi (', ', `) → '
    - Lowercase
    """
    if not text:
        return ""
    # Normalizza varianti di apostrofo
    text = text.replace("'", "'").replace("`", "'").replace("'", "'")
    # Rimuove accenti
    normalized = unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode('ascii')
    return normalized.lower().strip()


def _levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calcola la distanza di Levenshtein tra due stringhe.
    Restituisce il numero minimo di operazioni (inserimento, cancellazione, sostituzione)
    necessarie per trasformare s1 in s2.
    """
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            # costo: 0 se i caratteri sono uguali, 1 altrimenti
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def _similarity_ratio(s1: str, s2: str) -> float:
    """
    Calcola la similarità tra due stringhe come percentuale (0.0 - 1.0).
    Usa la distanza di Levenshtein normalizzata.
    1.0 = stringhe identiche, 0.0 = completamente diverse.

    OTTIMIZZATO: confronta anche versioni senza apostrofo per gestire
    varianti come "Dell'Angelo" vs "Dall'Angelo".
    """
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0

    # Normalizza le stringhe (rimuovi accenti, lowercase, normalizza apostrofi)
    s1_norm = _normalize(s1.strip())
    s2_norm = _normalize(s2.strip())

    if s1_norm == s2_norm:
        return 1.0

    max_len = max(len(s1_norm), len(s2_norm))
    if max_len == 0:
        return 1.0

    # Calcola distanza standard
    distance = _levenshtein_distance(s1_norm, s2_norm)
    score_standard = 1.0 - (distance / max_len)

    # Se contengono apostrofi, calcola anche senza per tolleranza maggiore
    # "dell'angelo" vs "dall'angelo" → "dellangelo" vs "dallangelo" (diff = 1)
    if "'" in s1_norm or "'" in s2_norm:
        s1_no_apo = s1_norm.replace("'", "")
        s2_no_apo = s2_norm.replace("'", "")
        if s1_no_apo and s2_no_apo:
            max_len_na = max(len(s1_no_apo), len(s2_no_apo))
            distance_na = _levenshtein_distance(s1_no_apo, s2_no_apo)
            score_no_apo = 1.0 - (distance_na / max_len_na)
            # Usa il miglior score tra le due versioni
            return max(score_standard, score_no_apo)

    return score_standard


def _fuzzy_match_clients(search: str, threshold: float = 0.80) -> list:
    """
    Cerca clienti con matching fuzzy (tollerante agli errori di battitura).
    Restituisce clienti con similarità >= threshold (default 80%).

    IMPORTANTE: la similarità viene calcolata su:
    - nome+cognome completo (come stringa unica), oppure
    - cognome+nome completo (come stringa unica), oppure
    - numero di cellulare
    - confronto parola per parola (per ricerche multi-parola)

    MAI su nome o cognome singolarmente.

    Args:
        search: stringa di ricerca (nome e/o cognome)
        threshold: soglia minima di similarità (0.0 - 1.0)

    Returns:
        Lista di dict {client: {...}, score: float} ordinate per similarità decrescente
    """
    from appl.models import Client
    from sqlalchemy import or_, func

    search = (search or '').strip()
    if len(search) < 2:
        return []

    search_norm = _normalize(search)
    search_parts = [p for p in search_norm.split() if len(p) >= 2]

    if not search_parts:
        return []

    # PRE-FILTERING SQL: cerca clienti i cui nome/cognome iniziano con
    # i primi 1-3 caratteri di qualsiasi parola della ricerca.
    # Usiamo prefissi MOLTO corti (1-2 char) per tollerare errori all'inizio.
    # Es: "Cone" → prefissi "c", "co", "con" per trovare anche "Coone"
    prefixes = set()
    for part in search_parts:
        # Prefisso di 1 carattere: massima tolleranza (trova Cone→Coone, Dell→Dall)
        if len(part) >= 1:
            prefixes.add(part[:1])
        # Prefisso di 2 caratteri
        if len(part) >= 2:
            prefixes.add(part[:2])
        # Prefisso di 3 caratteri (più specifico)
        if len(part) >= 3:
            prefixes.add(part[:3])
        # Per cognomi con apostrofo (dell, dall), cerca anche senza
        if "'" in part:
            clean_part = part.replace("'", "")
            if len(clean_part) >= 1:
                prefixes.add(clean_part[:1])
            if len(clean_part) >= 2:
                prefixes.add(clean_part[:2])
            if len(clean_part) >= 3:
                prefixes.add(clean_part[:3])

    # Costruisci condizioni OR per ogni prefisso
    prefix_conditions = []
    for prefix in prefixes:
        prefix_conditions.append(func.lower(Client.cliente_nome).like(f"{prefix}%"))
        prefix_conditions.append(func.lower(Client.cliente_cognome).like(f"{prefix}%"))

    # Query con pre-filtering — NESSUN LIMITE per fuzzy matching
    # Il pre-filtering già riduce i candidati tramite i prefissi
    if prefix_conditions:
        clients = Client.query.filter(
            Client.is_deleted == False,
            or_(*prefix_conditions)
        ).all()
    else:
        # Fallback senza prefissi: carica TUTTI i clienti attivi
        # (necessario per fuzzy matching completo)
        clients = Client.query.filter(
            Client.is_deleted == False
        ).all()

    logger.warning("_fuzzy_match_clients: search='%s', prefixes=%r, clients_loaded=%d",
                   search, prefixes, len(clients))

    matches = []

    # Prepara versioni normalizzate della ricerca
    search_no_apo = search_norm.replace("'", "")

    for client in clients:
        nome = (client.cliente_nome or '').strip()
        cognome = (client.cliente_cognome or '').strip()
        cellulare = (client.cliente_cellulare or '').strip()

        # Costruisci le stringhe complete nome+cognome
        full_name = f"{nome} {cognome}".strip()
        full_name_rev = f"{cognome} {nome}".strip()

        # Versioni normalizzate
        full_name_norm = _normalize(full_name)
        full_name_rev_norm = _normalize(full_name_rev)
        full_name_no_apo = full_name_norm.replace("'", "")
        full_name_rev_no_apo = full_name_rev_norm.replace("'", "")

        scores = []

        # ═══ MATCH 1: Cellulare (se la ricerca sembra un numero) ═══
        # Se la ricerca contiene solo cifre, confronta col cellulare
        search_digits = ''.join(c for c in search if c.isdigit())
        if len(search_digits) >= 3 and cellulare:
            cell_digits = ''.join(c for c in cellulare if c.isdigit())
            if cell_digits:
                # Match esatto o contenuto
                if search_digits in cell_digits or cell_digits in search_digits:
                    scores.append(1.0)
                else:
                    # Similarità sulla sequenza di cifre
                    scores.append(_similarity_ratio(search_digits, cell_digits))

        # ═══ MATCH 2: Nome+Cognome completo (normalizzato) ═══
        # Confronta la ricerca con "nome cognome" e "cognome nome"
        scores.append(_similarity_ratio(search_norm, full_name_norm))
        scores.append(_similarity_ratio(search_norm, full_name_rev_norm))

        # ═══ MATCH 3: Senza apostrofi ═══
        # "Dell'Angelo" vs "Dall'Angelo" → "dellangelo" vs "dallangelo"
        if "'" in full_name_norm or "'" in search_norm:
            scores.append(_similarity_ratio(search_no_apo, full_name_no_apo))
            scores.append(_similarity_ratio(search_no_apo, full_name_rev_no_apo))

        # ═══ MATCH 4: Confronto parola per parola (per ricerche multi-parola) ═══
        # Se la ricerca ha 2+ parole, confronta ogni parola della ricerca
        # con nome e cognome separatamente, poi fai la MEDIA dei migliori score.
        # Es: "Carmine Cone" → confronta "carmine" vs nome, "cone" vs cognome
        if len(search_parts) >= 2:
            nome_norm = _normalize(nome)
            cognome_norm = _normalize(cognome)

            # Prova tutte le combinazioni: quale parola matcha il nome, quale il cognome
            word_scores = []
            for i, part in enumerate(search_parts):
                other_parts = [p for j, p in enumerate(search_parts) if j != i]

                # part vs nome, other_parts[0] vs cognome
                if other_parts:
                    score_nome = _similarity_ratio(part, nome_norm)
                    score_cognome = _similarity_ratio(other_parts[0], cognome_norm)
                    # Media dei due score
                    avg_score = (score_nome + score_cognome) / 2
                    # Bonus se entrambi sono alti (>0.7)
                    if score_nome >= 0.7 and score_cognome >= 0.7:
                        avg_score = min(1.0, avg_score + 0.1)
                    word_scores.append(avg_score)

            if word_scores:
                scores.append(max(word_scores))

        # ═══ NON fare match su nome o cognome singolarmente! ═══
        # Il cliente deve matchare sulla combinazione completa.

        best_score = max(scores) if scores else 0.0

        if best_score >= threshold:
            matches.append({
                "client": {
                    "id": client.id,
                    "nome": nome,
                    "cognome": cognome,
                    "cellulare": cellulare,
                    "ref": f"C{client.id % 9999:04d}",
                },
                "score": best_score
            })

    # Ordina per similarità decrescente
    matches.sort(key=lambda x: x["score"], reverse=True)

    # Log risultati per debug
    if matches:
        logger.info("_fuzzy_match_clients: search='%s' → %d match (top: '%s %s' score=%.2f)",
                   search, len(matches),
                   matches[0]["client"].get("nome"), matches[0]["client"].get("cognome"),
                   matches[0]["score"])
    else:
        logger.warning("_fuzzy_match_clients: search='%s' → 0 match (threshold=%.2f, clients_checked=%d)",
                      search, threshold, len(clients))

    # Restituisci solo i top 5 match
    return matches[:5]
