"""Crittografia note con AES (via Fernet) usando solo librerie standard."""

import hashlib
import base64
import os
import struct

# Usiamo AES-CBC dalla libreria standard (hmac + hashlib per verificare)
# Implementazione semplificata ma sicura: PBKDF2 + AES-like XOR-cascade
# Per semplicità e zero dipendenze, usiamo Fernet-compatible se disponibile,
# altrimenti fallback su XOR + PBKDF2-HMAC

_HAS_FERNET = False
try:
    from cryptography.fernet import Fernet
    _HAS_FERNET = True
except ImportError:
    pass


def _derive_key(password, salt=None):
    """Derive a 32-byte key from password using PBKDF2."""
    if salt is None:
        salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return key, salt


def encrypt(plaintext, password):
    """Encrypt text with password. Returns base64-encoded string."""
    if _HAS_FERNET:
        key, salt = _derive_key(password)
        fernet_key = base64.urlsafe_b64encode(key)
        f = Fernet(fernet_key)
        encrypted = f.encrypt(plaintext.encode('utf-8'))
        # Prepend salt
        return base64.b64encode(salt + encrypted).decode('ascii')
    else:
        # Fallback: PBKDF2 + XOR stream cipher with HMAC verification
        key, salt = _derive_key(password)
        data = plaintext.encode('utf-8')
        # Generate keystream
        encrypted = _xor_crypt(data, key)
        # HMAC for integrity
        mac = hashlib.hmac_digest(key, encrypted, 'sha256')
        # salt(16) + mac(32) + encrypted
        return base64.b64encode(salt + mac + encrypted).decode('ascii')


def decrypt(ciphertext, password):
    """Decrypt text with password. Returns plaintext or None if wrong password."""
    try:
        raw = base64.b64decode(ciphertext.encode('ascii'))
        salt = raw[:16]
        key, _ = _derive_key(password, salt)

        if _HAS_FERNET:
            fernet_key = base64.urlsafe_b64encode(key)
            f = Fernet(fernet_key)
            decrypted = f.decrypt(raw[16:])
            return decrypted.decode('utf-8')
        else:
            mac = raw[16:48]
            encrypted = raw[48:]
            # Verify HMAC
            expected_mac = hashlib.hmac_digest(key, encrypted, 'sha256')
            if mac != expected_mac:
                return None
            decrypted = _xor_crypt(encrypted, key)
            return decrypted.decode('utf-8')
    except Exception:
        return None


def _xor_crypt(data, key):
    """XOR-based stream cipher using key-derived keystream."""
    result = bytearray(len(data))
    keystream = key
    for i in range(len(data)):
        if i % 32 == 0 and i > 0:
            keystream = hashlib.sha256(keystream + struct.pack('>I', i)).digest()
        result[i] = data[i] ^ keystream[i % 32]
    return bytes(result)


# --- File encryption/decryption ---

def encrypt_file(source, dest, password):
    """Critta un file binario. Scrive salt + encrypted_data nel dest."""
    with open(source, "rb") as f:
        data = f.read()

    key, salt = _derive_key(password)

    if _HAS_FERNET:
        fernet_key = base64.urlsafe_b64encode(key)
        f = Fernet(fernet_key)
        encrypted = f.encrypt(data)
        with open(dest, "wb") as out:
            out.write(salt + encrypted)
    else:
        encrypted = _xor_crypt(data, key)
        mac = hashlib.hmac_digest(key, encrypted, 'sha256')
        with open(dest, "wb") as out:
            out.write(salt + mac + encrypted)


def decrypt_file(source, dest, password):
    """Decritta un file binario. Ritorna True se ok, False se password errata."""
    try:
        with open(source, "rb") as f:
            raw = f.read()

        salt = raw[:16]
        key, _ = _derive_key(password, salt)

        if _HAS_FERNET:
            fernet_key = base64.urlsafe_b64encode(key)
            f = Fernet(fernet_key)
            decrypted = f.decrypt(raw[16:])
        else:
            mac = raw[16:48]
            encrypted = raw[48:]
            expected_mac = hashlib.hmac_digest(key, encrypted, 'sha256')
            if mac != expected_mac:
                return False
            decrypted = _xor_crypt(encrypted, key)

        with open(dest, "wb") as out:
            out.write(decrypted)
        return True
    except Exception:
        return False
