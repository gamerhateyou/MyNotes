"""Crittografia note e backup con AES-128-CBC (Fernet) + PBKDF2."""

import hashlib
import base64
import os
import logging

log = logging.getLogger("crypto")

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:
    raise ImportError(
        "Libreria 'cryptography' richiesta per la crittografia.\n"
        "Installa con: pip install cryptography"
    )

_ITERATIONS = 600_000
_LEGACY_ITERATIONS = 100_000


def _derive_key(password, salt=None, iterations=_ITERATIONS):
    """Derive a 32-byte key from password using PBKDF2."""
    if salt is None:
        salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
    return key, salt


def encrypt(plaintext, password):
    """Encrypt text with password. Returns base64-encoded string."""
    key, salt = _derive_key(password)
    fernet_key = base64.urlsafe_b64encode(key)
    f = Fernet(fernet_key)
    encrypted = f.encrypt(plaintext.encode('utf-8'))
    return base64.b64encode(salt + encrypted).decode('ascii')


def _try_decrypt(ciphertext_raw, password, iterations):
    """Try decryption with specific iteration count. Returns plaintext or None."""
    salt = ciphertext_raw[:16]
    key, _ = _derive_key(password, salt, iterations)
    fernet_key = base64.urlsafe_b64encode(key)
    f = Fernet(fernet_key)
    decrypted = f.decrypt(ciphertext_raw[16:])
    return decrypted.decode('utf-8')


def decrypt(ciphertext, password):
    """Decrypt text with password. Returns plaintext or None if wrong password."""
    try:
        raw = base64.b64decode(ciphertext.encode('ascii'))
        # Try modern iterations first
        try:
            return _try_decrypt(raw, password, _ITERATIONS)
        except InvalidToken:
            pass
        # Fallback to legacy iterations
        return _try_decrypt(raw, password, _LEGACY_ITERATIONS)
    except Exception:
        return None


# --- File encryption/decryption ---

def encrypt_file(source, dest, password):
    """Critta un file binario. Scrive salt + encrypted_data nel dest."""
    with open(source, "rb") as f:
        data = f.read()

    key, salt = _derive_key(password)
    fernet_key = base64.urlsafe_b64encode(key)
    f = Fernet(fernet_key)
    encrypted = f.encrypt(data)
    with open(dest, "wb") as out:
        out.write(salt + encrypted)


def decrypt_file(source, dest, password):
    """Decritta un file binario. Ritorna (True, None) se ok, (False, errore) se fallisce."""
    try:
        with open(source, "rb") as f:
            raw = f.read()

        salt = raw[:16]

        # Try modern iterations first
        decrypted = None
        try:
            key, _ = _derive_key(password, salt, _ITERATIONS)
            fernet_key = base64.urlsafe_b64encode(key)
            f = Fernet(fernet_key)
            decrypted = f.decrypt(raw[16:])
        except InvalidToken:
            # Fallback to legacy iterations
            key, _ = _derive_key(password, salt, _LEGACY_ITERATIONS)
            fernet_key = base64.urlsafe_b64encode(key)
            f = Fernet(fernet_key)
            decrypted = f.decrypt(raw[16:])

        with open(dest, "wb") as out:
            out.write(decrypted)
        return True, None
    except Exception as e:
        log.warning("decrypt_file fallito: %s: %s", type(e).__name__, e)
        return False, str(e)
