"""Token monouso per auto-login child dopo selezione negozio dalla landing root."""
import secrets
import threading
import time

_TOKEN_TTL_SECONDS = 30
_lock = threading.Lock()
_tokens = {}  # token_str -> (idx, user_id, expiry_ts)


def issue_token(idx, user_id):
    token = secrets.token_urlsafe(24)
    expiry = time.time() + _TOKEN_TTL_SECONDS
    with _lock:
        _purge_expired_locked()
        _tokens[token] = (int(idx), int(user_id), expiry)
    return token


def consume_token(token):
    """Restituisce (idx, user_id) se il token è valido, altrimenti None. Monouso."""
    if not token:
        return None
    with _lock:
        entry = _tokens.pop(token, None)
        _purge_expired_locked()
    if not entry:
        return None
    idx, user_id, expiry = entry
    if time.time() > expiry:
        return None
    return (idx, user_id)


def _purge_expired_locked():
    now = time.time()
    expired = [t for t, (_, _, exp) in _tokens.items() if exp < now]
    for t in expired:
        _tokens.pop(t, None)
