"""Crittografia note e backup con AES-128-CBC (Fernet) + PBKDF2."""

from __future__ import annotations

import base64
import hashlib
import logging
import os

log: logging.Logger = logging.getLogger("crypto")

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:
    raise ImportError(
        "Libreria 'cryptography' richiesta per la crittografia.\nInstalla con: pip install cryptography"
    ) from None

_ITERATIONS: int = 600_000
_LEGACY_ITERATIONS: int = 100_000


def _derive_key(password: str, salt: bytes | None = None, iterations: int = _ITERATIONS) -> tuple[bytes, bytes]:
    """Derive a 32-byte key from password using PBKDF2."""
    if salt is None:
        salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return key, salt


def encrypt(plaintext: str, password: str) -> str:
    """Encrypt text with password. Returns base64-encoded string."""
    key, salt = _derive_key(password)
    fernet_key = base64.urlsafe_b64encode(key)
    f = Fernet(fernet_key)
    encrypted = f.encrypt(plaintext.encode("utf-8"))
    return base64.b64encode(salt + encrypted).decode("ascii")


def _try_decrypt(ciphertext_raw: bytes, password: str, iterations: int) -> str:
    """Try decryption with specific iteration count. Returns plaintext or None."""
    salt = ciphertext_raw[:16]
    key, _ = _derive_key(password, salt, iterations)
    fernet_key = base64.urlsafe_b64encode(key)
    f = Fernet(fernet_key)
    decrypted = f.decrypt(ciphertext_raw[16:])
    return decrypted.decode("utf-8")


def decrypt(ciphertext: str, password: str) -> str | None:
    """Decrypt text with password. Returns plaintext or None if wrong password."""
    try:
        raw = base64.b64decode(ciphertext.encode("ascii"))
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


def encrypt_file(source: str, dest: str, password: str) -> None:
    """Critta un file binario. Scrive salt + encrypted_data nel dest."""
    with open(source, "rb") as src_f:
        data = src_f.read()

    key, salt = _derive_key(password)
    fernet_key = base64.urlsafe_b64encode(key)
    fern: Fernet = Fernet(fernet_key)
    encrypted = fern.encrypt(data)
    with open(dest, "wb") as out:
        out.write(salt + encrypted)


def decrypt_file(source: str, dest: str, password: str) -> tuple[bool, str | None]:
    """Decritta un file binario. Ritorna (True, None) se ok, (False, errore) se fallisce."""
    try:
        with open(source, "rb") as src_f:
            raw = src_f.read()

        salt = raw[:16]

        # Try modern iterations first
        decrypted = None
        try:
            key, _ = _derive_key(password, salt, _ITERATIONS)
            fernet_key = base64.urlsafe_b64encode(key)
            fern: Fernet = Fernet(fernet_key)
            decrypted = fern.decrypt(raw[16:])
        except InvalidToken:
            # Fallback to legacy iterations
            key, _ = _derive_key(password, salt, _LEGACY_ITERATIONS)
            fernet_key = base64.urlsafe_b64encode(key)
            fern2: Fernet = Fernet(fernet_key)
            decrypted = fern2.decrypt(raw[16:])

        with open(dest, "wb") as out:
            out.write(decrypted)
        return True, None
    except Exception as e:
        log.warning("decrypt_file fallito: %s: %s", type(e).__name__, e)
        return False, str(e)
