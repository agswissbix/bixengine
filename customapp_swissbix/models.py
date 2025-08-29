import uuid
from django.db import models
from django.utils import timezone

class Company(models.Model):
    name = models.CharField(max_length=200, unique=True)

    def __str__(self):
        return f"{self.id} - {self.name}"

class Employee(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="employees")
    external_id = models.CharField(max_length=100, unique=True)  # tuo ID dipendente
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.external_id} ({self.company_id})"

class QRToken(models.Model):
    """
    Per prevenire replay:
    - jti unico
    """
    jti = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="qr_tokens")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="qr_tokens")

    class Meta:
        indexes = [
            models.Index(fields=["employee", "company"]),
        ]

    @property
    def is_used(self) -> bool:
        return self.used_at is not None
