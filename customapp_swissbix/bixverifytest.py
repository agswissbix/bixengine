from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.views.decorators.csrf import csrf_exempt
from customapp_swissbix.services.qr_services import generate_qr_token, validate_qr_token

@csrf_exempt
@api_view(["POST"])
def issue_qr_token(request):
    """
    Body:
    {
      "companyId": 456,
      "employeeId": "E123",
      "ttl": 300   // opzionale
    }
    Ritorna: { "token": "..." }
    """
    try:
        company_id = request.data.get("companyId")
        employee_external_id = request.data.get("employeeId")
        ttl = int(request.data.get("ttl", 300))
        print("Issuing QR token for companyId:", company_id, "employee")
        token = generate_qr_token(company_id=company_id, employee_external_id=employee_external_id, ttl_seconds=ttl)
        return Response({"token": token}, status=status.HTTP_201_CREATED)
    except (ValueError, TypeError) as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

@csrf_exempt
@api_view(["POST"])
def verify_qr_token(request):
    """
    Body:
    { "token": "..." }

    Se valido: ritorna i dati base del dipendente/company,
    oppure qui potresti anche emettere un tuo JWT di sessione applicativa.
    """
    try:
        token = request.data.get("token")
        result, employee, company = validate_qr_token(token)
        # Esempio: includi permessi/ruoli da DB se servono
        return Response({"valid": True, "data": result}, status=status.HTTP_200_OK)
    except (ValueError, TypeError) as e:
        return Response({"valid": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
