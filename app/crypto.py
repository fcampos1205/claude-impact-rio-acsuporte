"""Fernet encryption wrapper — LGPD compliance for message content.

All chat message content MUST be encrypted before persisting to database.
See ADR 003 and docs/architecture/decisoes_design.md G16.
"""

import base64
import hashlib
import os

from cryptography.fernet import Fernet


def _load_key() -> bytes:
    """Load and validate Fernet key from environment.

    Fernet requires a URL-safe base64-encoded 32-byte key.
    If ENCRYPTION_KEY is a valid Fernet key, use it directly.
    Otherwise, derive a 32-byte key via SHA-256 (for dev compatibility).
    """
    raw = os.environ.get("ENCRYPTION_KEY", "")
    if not raw:
        # Dev fallback: generate ephemeral key (NOT suitable for production)
        return Fernet.generate_key()

    key_bytes = raw.encode() if isinstance(raw, str) else raw

    # Try to use as a valid Fernet key directly
    try:
        Fernet(key_bytes)
        return key_bytes
    except Exception:
        # Derive a valid 32-byte key from the string via SHA-256
        derived = base64.urlsafe_b64encode(
            hashlib.sha256(raw.encode()).digest()
        )
        return derived


def _make_fernet() -> Fernet:
    return Fernet(_load_key())


# Module-level Fernet instance — re-created on module reload (test_decrypt_falha_com_chave_errada)
_fernet = _make_fernet()


def encrypt(text: str) -> bytes:
    """Encrypt a plaintext string. Returns Fernet token bytes.

    Fernet includes timestamp + random IV — same input produces different output each call.
    """
    return _fernet.encrypt(text.encode())


def decrypt(data: bytes) -> str:
    """Decrypt a Fernet token. Raises InvalidToken if key or data is wrong."""
    return _fernet.decrypt(data).decode()
