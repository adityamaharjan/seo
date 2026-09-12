"""Symmetric encryption for secrets we must store and later read back.

Distinct from :mod:`app.core.security`, which hashes credentials we never need
to recover. A user's provider API key has to be sent to Google verbatim, so it
is encrypted rather than hashed.
"""
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class EncryptionUnavailableError(RuntimeError):
    """Raised when key storage is attempted with no encryption key configured.

    Storing secrets in plaintext is never an acceptable fallback, so callers
    surface this to the user as "ask the operator to configure the server".
    """


def is_available() -> bool:
    return bool(settings.API_KEY_ENCRYPTION_KEY)


def _cipher() -> Fernet:
    if not is_available():
        raise EncryptionUnavailableError(
            "API_KEY_ENCRYPTION_KEY is not configured on this server."
        )
    return Fernet(settings.API_KEY_ENCRYPTION_KEY.encode())


def encrypt(plaintext: str) -> str:
    return _cipher().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str | None:
    """Decrypt a stored secret, or None if it cannot be read.

    Returns None rather than raising when the ciphertext does not match the
    current key, which is what a rotated ``API_KEY_ENCRYPTION_KEY`` looks like.
    Callers treat that the same as "no key stored" and prompt for re-entry.
    """
    try:
        return _cipher().decrypt(token.encode()).decode()
    except InvalidToken:
        return None
