from datetime import timedelta
from typing import Tuple, Dict, Any
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from customapp_swissbix.models import Company, Employee, QRToken  # Decommentato: usa i modelli reali
from customapp_swissbix.utils.crypto import encrypt_payload, decrypt_token

DEFAULT_TTL_SECONDS = 300  # 5 minuti

# Commenta/rimuovi le classi di esempio
# class ExampleCompany: ...
# class ExampleEmployee: ...
# class ExampleQRToken: ...

def _employee_in_company(company_id: int | str, employee_external_id: str) -> Employee:
    try:
        emp = Employee.objects.select_related("company").get(
            company_id=company_id,
            external_id=employee_external_id,
            is_active=True
        )
    except ObjectDoesNotExist:
        raise ValueError("Dipendente non trovato o non attivo per l'azienda")
    return emp

@transaction.atomic
def generate_qr_token(*, company_id: int | str, employee_external_id: str, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> str:
    """
    - Verifica employee ∈ company
    - Crea record QRToken (jti, exp)
    - Costruisce payload e lo cifra (token opaco da mettere nel QR)
    """
    emp = _employee_in_company(company_id, employee_external_id)
    qrt = QRToken.objects.create(
        employee=emp,
        company=emp.company,
    )
    payload = {
        "jti": str(qrt.jti),
        "companyId": emp.company_id,
        "employeeId": emp.external_id,
        "v": 1
    }
    token = encrypt_payload(payload)
    return token

@transaction.atomic
def validate_qr_token(token: str) -> Tuple[Dict[str, Any], Employee, Company]:
    """
    - Decifra token
    - Verifica esistenza QRToken/jti
    - Controlla exp/used e coerenza employee/company
    - Marca come usato (one-shot) e ritorna dati per il client
    """
    payload = decrypt_token(token)

    required = {"jti", "companyId", "employeeId"}
    if not required.issubset(payload.keys()):
        raise ValueError("Payload incompleto")

    jti = payload["jti"]
    company_id = payload["companyId"]
    employee_external_id = payload["employeeId"]

    emp = _employee_in_company(company_id, employee_external_id)
    try:
        qrt = QRToken.objects.select_for_update().get(pk=jti)
    except QRToken.DoesNotExist:
        raise ValueError("Token non registrato")

    if qrt.company_id != emp.company_id or qrt.employee_id != emp.id:
        raise ValueError("Token non coerente con i dati del dipendente/azienda")

    result = {
        "companyId": emp.company_id,
        "employeeId": emp.external_id,
        "employeeName": f"{emp.first_name} {emp.last_name}",
        "companyName": emp.company.name,
        "jti": jti,
    }
    return result, emp, emp.company
