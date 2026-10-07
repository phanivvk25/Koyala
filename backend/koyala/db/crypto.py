"""Envelope encryption for sensitive fields (TDD §9, Compliance §8.2).

Each user has a random 256-bit data key (DEK). Message content is encrypted
with AES-256-GCM under the user's DEK; the DEK is stored wrapped (encrypted)
by the master key. Ciphertexts are bound to their owner via associated data,
so a row copied to another user fails to decrypt.

The master key comes from KOYALA_MASTER_KEY (base64, 32 bytes) for now; in
production it should be held in a cloud KMS and only wrap/unwrap calls made.
"""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE_BYTES = 12
KEY_BYTES = 32
VERSION = b"\x01"


class Crypto:
    def __init__(self, master_key: bytes) -> None:
        if len(master_key) != KEY_BYTES:
            raise ValueError("master key must be 32 bytes")
        self._master = AESGCM(master_key)

    @classmethod
    def from_env(cls) -> Crypto:
        raw = os.environ.get("KOYALA_MASTER_KEY")
        if not raw:
            raise RuntimeError("KOYALA_MASTER_KEY is required when a database is configured")
        return cls(base64.b64decode(raw))

    @staticmethod
    def generate_key() -> str:
        """Return a new base64 master key (for setup scripts and tests)."""
        return base64.b64encode(AESGCM.generate_key(bit_length=256)).decode()

    def new_wrapped_dek(self, user_id: str) -> bytes:
        dek = AESGCM.generate_key(bit_length=256)
        return _seal(self._master, dek, _aad("dek", user_id))

    def encrypt(self, wrapped_dek: bytes, user_id: str, plaintext: str) -> bytes:
        dek = AESGCM(_open(self._master, wrapped_dek, _aad("dek", user_id)))
        return _seal(dek, plaintext.encode(), _aad("data", user_id))

    def decrypt(self, wrapped_dek: bytes, user_id: str, ciphertext: bytes) -> str:
        dek = AESGCM(_open(self._master, wrapped_dek, _aad("dek", user_id)))
        return _open(dek, ciphertext, _aad("data", user_id)).decode()


def _aad(purpose: str, user_id: str) -> bytes:
    return f"koyala:{purpose}:{user_id}".encode()


def _seal(key: AESGCM, plaintext: bytes, aad: bytes) -> bytes:
    nonce = os.urandom(NONCE_BYTES)
    return VERSION + nonce + key.encrypt(nonce, plaintext, aad)


def _open(key: AESGCM, blob: bytes, aad: bytes) -> bytes:
    if blob[:1] != VERSION:
        raise ValueError("unsupported ciphertext version")
    nonce, ct = blob[1 : 1 + NONCE_BYTES], blob[1 + NONCE_BYTES :]
    return key.decrypt(nonce, ct, aad)
