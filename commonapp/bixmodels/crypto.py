# Criptazione deterministica e reversibile.
#
#   - Deterministico: lo STESSO plaintext produce sempre lo STESSO ciphertext,
#     quindi le colonne cifrate restano interrogabili / dedup-abili.
#   - Reversibile: i valori si decifrano con la chiave.
#   - Cross-language: il lato PHP implementa lo stesso identico spec.
#
# SPEC:
#   master  = base64_decode(masterKeyB64)               # 32 byte grezzi
#   encKey  = HMAC_SHA256(key=master, msg="enc")        # 32 byte  (chiave AES-256)
#   ivKey   = HMAC_SHA256(key=master, msg="iv")         # 32 byte
#   iv      = HMAC_SHA256(key=ivKey, msg=plaintext)[0:12]   # IV sintetico 12 byte
#   ct, tag = AES_256_GCM(encKey, iv, plaintext)        # tag = 16 byte
#   blob    = base64( iv(12) || ct || tag(16) )         # cosa viene salvato

import base64
import hashlib
import hmac

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class Crypto:
    """
    Cifratura deterministica e reversibile dei campi
    La chiave master viene PASSATA al costruttore (base64 di 32 byte)
    """

    def __init__(self, master_key_b64: str):
        master = base64.b64decode(master_key_b64)
        if len(master) != 32:
            raise ValueError("master key non valida: attesi 32 byte in base64.")

        # Sotto-chiavi derivate una sola volta (come cryptoKeys() nel PHP).
        # ATTENZIONE all'ordine args: hmac.new(key, msg) <-> hash_hmac(algo, msg, key).
        self._enc_key = hmac.new(master, b"enc", hashlib.sha256).digest()  # chiave AES-256
        self._iv_key = hmac.new(master, b"iv", hashlib.sha256).digest()    # chiave per l'IV

    def encrypt(self, plaintext) -> str | None:
        """Cifra un valore. None passa come None (colonna NULL nel DB)."""
        if plaintext is None:
            return None

        data = str(plaintext).encode("utf-8")
        # IV sintetico: HMAC(ivKey, plaintext)[0:12] -> deterministico.
        iv = hmac.new(self._iv_key, data, hashlib.sha256).digest()[:12]
        # AESGCM.encrypt restituisce ct || tag(16) concatenati -> blob = iv || ct || tag.
        ct_and_tag = AESGCM(self._enc_key).encrypt(iv, data, None)
        return base64.b64encode(iv + ct_and_tag).decode("ascii")

    def decrypt(self, blob) -> str | None:
        """Operazione inversa di encrypt(). None passa come None.
        Solleva se i dati sono manomessi o la chiave e' sbagliata (auth GCM)."""
        if blob is None:
            return None

        raw = base64.b64decode(blob)
        if len(raw) < 12 + 16:
            raise ValueError("ciphertext non valido.")

        iv = raw[:12]
        ct_and_tag = raw[12:]   # ct || tag: AESGCM.decrypt si aspetta proprio questo
        return AESGCM(self._enc_key).decrypt(iv, ct_and_tag, None).decode("utf-8")
