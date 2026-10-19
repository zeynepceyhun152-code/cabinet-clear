"""
crypto_store.py - encrypts saved history before it goes into the database.

  * AES-256-GCM: the text is scrambled AND protected against tampering.
  * The key comes from the environment variable DATA_KEY (a Render setting), never from the database. So
    someone who only gets the database, such as a leak or the database company, sees unreadable text.
  * Each value is locked to its owner and field. A record copied into another person's row will not open.
  * Key rotation: DATA_KEY may hold several keys separated by commas. The FIRST one encrypts new data,
    every one of them can open old data. To change keys: put the new key first, keep the old one after it.
  * If DATA_KEY is not set, text is stored as before (readable) and /health says "encrypted": false.

Limit, stated plainly: the server needs the key to show history back to its owner, so whoever runs the server
could also read it. This protects the stored data, not against the person who holds the key.
"""
import base64
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

PREFIX = "enc1:"


class DecryptError(Exception):
    pass


def generate_key():
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


def _keys():
    keys = []
    for part in os.environ.get("DATA_KEY", "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            raw = base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))
            if len(raw) == 32:
                keys.append(raw)
                continue
        except Exception:
            pass
        print("WARNING: a DATA_KEY entry is not a valid 32-byte key and was ignored.")
    return keys


def enabled():
    return bool(_keys())


def encrypt(text, context):
    """Encrypted text (starting with enc1:), or the text unchanged when no key is set."""
    if text is None:
        text = ""
    keys = _keys()
    if not keys:
        return text
    nonce = os.urandom(12)
    ct = AESGCM(keys[0]).encrypt(nonce, text.encode("utf-8"), context.encode("utf-8"))
    return PREFIX + base64.urlsafe_b64encode(nonce + ct).decode()


def is_encrypted(value):
    return isinstance(value, str) and value.startswith(PREFIX)


def decrypt(value, context):
    """Plain text. Old unencrypted values are returned as they are. Raises DecryptError if it cannot be opened."""
    if not is_encrypted(value):
        return value
    try:
        raw = base64.urlsafe_b64decode(value[len(PREFIX):] + "=" * (-len(value[len(PREFIX):]) % 4))
        nonce, ct = raw[:12], raw[12:]
    except Exception:
        raise DecryptError("damaged value")
    for key in _keys():
        try:
            return AESGCM(key).decrypt(nonce, ct, context.encode("utf-8")).decode("utf-8")
        except InvalidTag:
            continue
    raise DecryptError("no key opens this value")
