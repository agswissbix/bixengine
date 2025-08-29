import json
from typing import Dict, Any
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

fernet = Fernet(settings.QR_FERNET_KEY.encode() if isinstance(settings.QR_FERNET_KEY, str) else settings.QR_FERNET_KEY)

def encrypt_payload(payload: Dict[str, Any]) -> str:
    """
    payload -> str token opaco, URL-safe.
    """
    data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    token = fernet.encrypt(data).decode("utf-8")
    return token

def decrypt_token(token: str) -> Dict[str, Any]:
    """
    token opaco -> payload dict
    Lancia ValueError se non valido/alterato/scaduto (a livello Fernet TTL opzionale lo gestiamo noi).
    """
    try:
        raw = fernet.decrypt(token.encode("utf-8"))
    except InvalidToken:
        raise ValueError("Token non valido o alterato")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        raise ValueError("Payload non decodificabile")
    return payload
