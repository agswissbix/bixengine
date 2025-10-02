import json
from typing import Dict, Any
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

fernet = Fernet(settings.HASHEDID_FERNET_KEY.encode() if isinstance(settings.HASHEDID_FERNET_KEY, str) else settings.HASHEDID_FERNET_KEY)

def get_hashedid_from_recordid(recordid: int) -> str:
    recordid_bytes = str(recordid).encode()
    hashed_id_bytes = fernet.encrypt(recordid_bytes)
    
    hashed_id_string = hashed_id_bytes.decode()
    return hashed_id_string

def get_recordid_from_hashedid(hashed_id_string):
    try:
        hashed_id_bytes = hashed_id_string.encode()
        decrypted_bytes = fernet.decrypt(hashed_id_bytes)
        original_record_id = int(decrypted_bytes.decode())
        return original_record_id
    except Exception as e:
        return None
