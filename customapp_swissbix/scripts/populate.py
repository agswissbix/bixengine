from customapp_swissbix.models import Company, Employee
from django.db import transaction, IntegrityError

with transaction.atomic():
    company, created = Company.objects.get_or_create(
        id=4893,
        defaults={"name": "International School of Switzerland"}
    )
    if not created:
        company.name = "International School of Switzerland"
        company.save()

    employees_data = [
        ("20250001", "Rebecca Hauch"),
        ("20250003", "Peter Hauch"),
        ("20250005", "Maria Scotto"),
        ("20250006", "Rodrigo Telles"),
        ("20250012", "Paul Doggett"),
        ("20250007", "Debora Telles"),
        ("20250014", "Jannette Mclaughlin"),
        ("20250013", "Larry Mclaughlin"),
        ("20250015", "Mattia Monaco"),
        ("20250008", "Claudia Degli Alessandrini"),
        ("20250010", "Kerry Helmuth"),
        ("20250011", "Sara Pfaff"),
        ("20250009", "Linda Gualco-Vanetta"),
    ]

    for external_id, full_name in employees_data:
        first_name, last_name = (full_name.split(" ", 1) + [""])[:2]
        try:
            emp, created = Employee.objects.update_or_create(
                external_id=external_id,   # external_id è unique → lookup diretto
                defaults={
                    "company": company,
                    "first_name": first_name,
                    "last_name": last_name,
                    "is_active": True,
                },
            )
            if created:
                print(f"✅ Creato dipendente: {first_name} {last_name}")
            else:
                print(f"♻️ Aggiornato dipendente: {first_name} {last_name}")
        except IntegrityError as e:
            print(f"❌ Errore su {external_id} {full_name}: {e}")

print(f"Totale dipendenti in azienda '{company.name}' (ID={company.id}): {company.employees.count()}")
