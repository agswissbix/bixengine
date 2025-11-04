from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.utils import timezone


DISABLE_SCRIPT = False

FIELD_TYPE_MAPPING = {
    "chart": {
        "id": "Seriale",
        "name": "Parola",
        "title": "Parola",
        "description": "Memo",
        "type": "lookup",
        "fields": "multiselect",
        "dynamic_field_1": "lookup",
        "dynamic_field_1_label": "Parola",
        "operation": "lookup",
        "grouping": "lookup",
        "grouping_type": "lookup",
        "pivot_total_field": "lookup",
        "fields_2": "lookup",
        "dynamic_field_2": "lookup",
        "dynamic_field_2_label": "Parola",
        "operation2": "lookup",
        "operation2_total": "lookup",
        "icon": "Attachment",
        "status": "lookup",
        "report_id": "Parola",
        "table_name": "lookup",
        "dashboards": "multiselect",
        "views": "multiselect",
        "date_granularity": "lookup",
        "function_button": "lookup",
    },
    "email": {
        "id": "Seriale",
        "subject": "Parola",
        "recipients": "Parola",
        "mail_body": "Memo",
        "note": "Memo",
        "sent_date": "Data",
        "sent_timestamp": "Parola",
        "cc": "Parola",
        "bcc": "Parola",
        "status": "lookup",
    },
}

LOOKUP_ITEMS_MAP = {
    "type_chart": [
        "button", "value", "table", "stackedchart", "scatterchart", "radarchart", "polarchart",
        "piechart", "orizbarchart", "multibarlinechart", "multibarchart", "linechart",
        "heatchart", "donutchart", "barchart"
    ],
    "grouping_type_chart": ["Pivot", "Aggregazione"],
    "operation_chart": ["Somma", "Media", "Conteggio"],
    "operation2_chart": ["Somma", "Media", "Conteggio"],
    "operation2_total_chart": ["Si", "No"],
    "date_granularity_chart": ["year", "month", "day"],
}

INDIFFERENT_FIELDS = {  }
INCLUDE_FIELDS = {"commonapp.UserChart","commonapp.UserEmail", "commonapp.UserSchedulerLog", "commonapp.UserSystemLog","commonapp.UserEvents", "commonapp.UserUserLog"}

EXCLUDED_FIELDS = {
    "record_id",
    "creator_id",
    "created_at",
    "last_updater_id",
    "last_update",
    "total_pages",
    "first_page_filename",
    "record_status",
    "deleted_flag",
}


@receiver(post_migrate)
def register_sys_metadata(sender, app_config, **kwargs):
    from django.apps import apps
    from django.db import transaction

    if DISABLE_SCRIPT:
        return

    SysTable = apps.get_model("commonapp", "SysTable")
    SysField = apps.get_model("commonapp", "SysField")
    SysUser = apps.get_model("commonapp", "SysUser")
    SysUserFieldOrder = apps.get_model("commonapp", "SysUserFieldOrder")
    SysUserTableOrder = apps.get_model("commonapp", "SysUserTableOrder")
    SysLookupTable = apps.get_model("commonapp", "SysLookupTable")
    SysLookupTableItem = apps.get_model("commonapp", "SysLookupTableItem")
    SysView = apps.get_model("commonapp", "SysView")

    DEFAULT_USER_ID = 1
    preferences = ["search_results_fields", "insert_fields", "search_fields"]

    for model in app_config.get_models():
        full_name = f"{model._meta.app_label}.{model.__name__}"
        if full_name not in INCLUDE_FIELDS:
            continue

        table_name = model._meta.db_table
        tableid = table_name.replace("user_", "", 1)

        with transaction.atomic():
            # 🧱 1️⃣ SysTable - crea o aggiorna
            table_obj, _ = SysTable.objects.update_or_create(
                id=tableid,
                defaults=dict(
                    description=model._meta.verbose_name_plural.title(),
                    creationdate=timezone.now(),
                    tabletypeid=0,
                    dbtypeid=0,
                    totpages=0,
                    namefolder="000",
                    numfilesfolder=0,
                    lastupdate=timezone.now().strftime("%Y%m%d%H%M%S"),
                    workspace="ALTRO",
                ),
            )

            user = SysUser.objects.filter(id=DEFAULT_USER_ID).first()

            # 🧹 2️⃣ Pulisci campi obsoleti (con cleanup FK)
            current_field_names = {
                f.name for f in model._meta.get_fields() if hasattr(f, "column") and f.column
            }
            existing_fields = SysField.objects.filter(tableid=table_obj.id)
            existing_field_names = set(existing_fields.values_list("fieldid", flat=True))
            obsolete_fields = existing_field_names - current_field_names

            if obsolete_fields:
                # Prima rimuovi i riferimenti figli
                SysUserFieldOrder.objects.filter(
                    tableid=table_obj, fieldid__fieldid__in=obsolete_fields
                ).delete()

                # Poi rimuovi eventuali lookup collegati
                obsolete_field_objs = existing_fields.filter(fieldid__in=obsolete_fields)
                obsolete_lookup_ids = list(obsolete_field_objs.exclude(lookuptableid__isnull=True)
                                        .values_list("lookuptableid", flat=True))
                if obsolete_lookup_ids:
                    # Rimuovi item e lookup table
                    SysLookupTableItem.objects.filter(lookuptableid__in=obsolete_lookup_ids).delete()
                    SysLookupTable.objects.filter(tableid__in=obsolete_lookup_ids).delete()

                # Infine elimina i SysField obsoleti
                obsolete_field_objs.delete()


            # 🔁 3️⃣ Crea/aggiorna campi
            for f in model._meta.get_fields():
                if not hasattr(f, "column") or f.column is None:
                    continue
                if f.name in EXCLUDED_FIELDS:
                    continue

                logical_type = FIELD_TYPE_MAPPING.get(tableid, {}).get(f.name, "Parola")
                field_description = f.name.replace("_", " ").title()
                field_label = "Sistema" if f.name == "id" else "Dati"

                field_obj, _ = SysField.objects.update_or_create(
                    tableid=table_obj.id,
                    fieldid=f.name,
                    defaults=dict(
                        description=field_description,
                        fieldtypeid=logical_type,
                        fieldtypewebid=logical_type,
                        label=field_label,
                        length=getattr(f, "max_length", 255) or 255,
                    ),
                )

                # 🧩 4️⃣ Lookup: aggiorna o ricrea
                if logical_type in ["lookup", "multiselect"]:
                    lookuptableid = f"{f.name}_{tableid}"
                    field_obj.lookuptableid = lookuptableid
                    field_obj.save()

                    lookup_table, _ = SysLookupTable.objects.update_or_create(
                        tableid=lookuptableid,
                        defaults=dict(
                            description=f.name.title(),
                            itemtype="Carattere",
                            codelen=255,
                            desclen=255,
                        ),
                    )

                    # 🧹 Rimuovi item obsoleti
                    existing_items = set(
                        SysLookupTableItem.objects.filter(lookuptableid=lookuptableid)
                        .values_list("itemcode", flat=True)
                    )
                    new_values = set(LOOKUP_ITEMS_MAP.get(lookuptableid, []))
                    to_delete = existing_items - new_values
                    if to_delete:
                        SysLookupTableItem.objects.filter(lookuptableid=lookuptableid, itemcode__in=to_delete).delete()

                    # 🔄 Aggiungi nuovi item
                    for value in new_values - existing_items:
                        SysLookupTableItem.objects.create(
                            lookuptableid=lookuptableid,
                            itemcode=value,
                            itemdesc=value,
                        )

                # 👤 5️⃣ Ordine campi utente
                if user:
                    for pref in preferences:
                        SysUserFieldOrder.objects.update_or_create(
                            userid=user,
                            tableid=table_obj,
                            fieldid=field_obj,
                            typepreference=pref,
                            defaults={"fieldorder": 0},
                        )

            # 📊 6️⃣ Ordine tabella utente
            if user:
                SysUserTableOrder.objects.update_or_create(
                    userid=user,
                    tableid=table_obj,
                    defaults={"tableorder": None},
                )

            # 👁️ 7️⃣ Vista predefinita "Tutti"
            SysView.objects.update_or_create(
                tableid=table_obj,
                userid_id=1,
                query_conditions="true",
                defaults={
                    "name": "Tutti",
                    "creation": timezone.now(),
                },
            )
