"""Envelope AES-256-GCM v1; AAD vincula imagem à PTS, identificador e MIME."""
import base64
import binascii
import json
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

PREFIX = b"PTS-AESGCM-1\x00"


class EvidenceError(RuntimeError):
    pass


class EvidenceCipher:
    def __init__(self, encoded):
        try:
            key = base64.b64decode(encoded or "", validate=True)
        except (ValueError, binascii.Error, TypeError):
            raise EvidenceError("EVIDENCE_KEY deve ser uma chave de 32 bytes em base64.") from None
        if len(key) != 32:
            raise EvidenceError("Configure EVIDENCE_KEY com 32 bytes em base64; use manage.py crypto-key.")
        self.aes = AESGCM(key)

    @staticmethod
    def aad(ident, permit_id, mime):
        return json.dumps(["evidence-v1", ident, permit_id, mime], separators=(",", ":")).encode()

    def encrypt(self, raw, ident, permit_id, mime):
        nonce = os.urandom(12)
        return PREFIX + nonce + self.aes.encrypt(nonce, bytes(raw), self.aad(ident, permit_id, mime))

    def decrypt(self, blob, ident, permit_id, mime):
        blob = bytes(blob)
        if not blob.startswith(PREFIX):
            raise EvidenceError("Evidência antiga não criptografada; execute encrypt-evidence.")
        try:
            nonce = blob[len(PREFIX):len(PREFIX)+12]
            return self.aes.decrypt(nonce, blob[len(PREFIX)+12:], self.aad(ident, permit_id, mime))
        except (InvalidTag, ValueError):
            raise EvidenceError("Não foi possível autenticar a evidência. Confira a chave e a integridade do banco.") from None


def configured_cipher():
    return EvidenceCipher(os.environ.get("EVIDENCE_KEY"))
