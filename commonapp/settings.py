from commonapp.views import dictfetchall
from bixsettings.views.businesslogic.settings_business_logic import *
from bixsettings.views.helpers.helperdb import Helperdb
from django.http import JsonResponse
from django.db.models.query import QuerySet
from bixsettings.views.businesslogic.models.table_settings import TableSettings
from bixsettings.views.businesslogic.models.field_settings import *
from bixsettings.views.helpers.helperdb import *
from django.db import transaction
from django.db.models.functions import Coalesce
from django.db.models import F, OuterRef, Subquery, IntegerField
from django.utils import timezone


def get_users_and_groups(request):
    """
    API per ottenere la lista di utenti e gruppi.
    Restituisce un JSON con due liste separate.
    """

    try:
        # Esegui la query una sola volta
        all_sys_users = Helperdb.sql_query("SELECT * FROM sys_user")

        users = []
        groups = []

        # Filtra e separa gli utenti e i gruppi
        for user_data in all_sys_users:
            if user_data.get('description') == 'Gruppo':
                groups.append(user_data)
            else:
                users.append(user_data)
        
        # Restituisci i dati in formato JSON
        return JsonResponse({
            "success": True,
            "users": users,
            "groups": groups
        })
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)
    

def settings_table_usertables(request):
    data = json.loads(request.body)
    userid = data.get('userid', None)
    bl = SettingsBusinessLogic()

    workspaces = bl.get_user_tables(userid)

    if not workspaces:
        return JsonResponse({ "workspaces": [] })
    
    for key, value in workspaces.items():
        if isinstance(value.get('tables'), QuerySet):
            workspaces[key]['tables'] = list(value['tables'])

    return JsonResponse(workspaces)


type_preference_options = [
    "view_fields",
    "insert_fields",
    "search_results_fields",
    "linked_columns",
    "search_fields",
    "badge_fields",
    "report_fields",
    "kanban_fields",
]

def settings_table_fields(request):
    data = json.loads(request.body)
    tableid = data.get('tableid')
    userid = data.get('userid')
    typepreference = data.get('typepreference', None)

    if typepreference is None or typepreference not in type_preference_options:
        return JsonResponse({"error": "typepreference is required"}, status=400)

    fields = list(SysField.objects.filter(tableid=tableid).values())

    for field in fields[:]:  # usa [:] per evitare problemi durante la rimozione
        # Rimuovi i campi con fieldid che termina con "_"
        if field['fieldid'].endswith('_'):
            fields.remove(field)
            continue

        user_field_conf = SysUserFieldOrder.objects.filter(
            tableid=tableid,
            fieldid=field['id'],
            userid=userid,
            typepreference=typepreference
        ).first()

        # Aggiungi solo l'order (None se non esiste)
        field['order'] = user_field_conf.fieldorder if user_field_conf else None

    return JsonResponse({
        "fields": fields
    })


def settings_table_settings(request):
    tableid = json.loads(request.body).get('tableid')
    userid = json.loads(request.body).get('userid')
    tablesettings_obj = TableSettings(tableid=tableid, userid=userid)
    tablesettings = tablesettings_obj.get_settings()

    return JsonResponse({"tablesettings": tablesettings})


def settings_table_fields_settings_save(request):
    data = json.loads(request.body)

    settings_list = data.get('settings')
    userid = data.get('userid')
    tableid = data.get('tableid')

    tablesettings_obj = TableSettings(tableid=tableid, userid=userid)

    for setting in settings_list:
        tablesettings_obj.settings[setting['name']]['value'] = setting['value']

    tablesettings_obj.save()

    return HttpResponse({'success': True})



def settings_table_usertables_save(request):
    data = json.loads(request.body)
    userid = data.get('userid')
    workspaces = data.get('workspaces', {})

    user = SysUser.objects.filter(id=userid).first()
    if not user:
        return JsonResponse({"error": "User not found"}, status=404)

    errors = []

    for workspace_key, workspace_data in workspaces.items():
        tables = workspace_data.get('tables', [])
        for table in tables:
            table_id = table.get('id')
            order = table.get('order')

            if table_id is None:
                continue

            table = SysTable.objects.filter(id=table_id).first()
            if not table:
                errors.append({"error": "Table not found", "table_id": table_id})
                continue

            # Recupera o crea il record esistente
            user_table_order, created = SysUserTableOrder.objects.get_or_create(
                userid=user,
                tableid=table
            )

            user_table_order.tableorder = order
            user_table_order.save()

    return JsonResponse({'success': True, 'errors': errors})

@transaction.atomic
def settings_table_tablefields_save(request):
    data = json.loads(request.body)
    tableid = data.get('tableid')
    userid = data.get('userid')
    fields = data.get('fields', [])
    typepreference = data.get('typepreference', None)

    if typepreference is None or typepreference not in type_preference_options:
        return JsonResponse({"error": "typepreference is required"}, status=400)

    user = SysUser.objects.filter(id=userid).first()
    if not user:
        return JsonResponse({"error": "User not found"}, status=404)
    
    table = SysTable.objects.filter(id=tableid).first()
    if not table:
        return JsonResponse({"error": "Table not found"}, status=404)

    for field in fields:
        fieldid = field.get("id")
        order = field.get("order")

        if not fieldid:
            continue

        field = SysField.objects.filter(tableid=table.id, id=fieldid).first()
        if not field:
            continue

        order_value = order if order is not None else None

        user_table_order, created = SysUserFieldOrder.objects.get_or_create(
            userid=user,
            tableid=table,
            fieldid=field,
            typepreference=typepreference,
        )

        user_table_order.fieldorder = order_value
        user_table_order.save()

    return JsonResponse({'success': True})


@transaction.atomic
def settings_table_fields_settings_fields_save(request):
    data = json.loads(request.body)
    settings_list = data.get('settings', {})
    userid = data.get('userid')
    tableid = data.get('tableid')
    fieldid = data.get('fieldid')
    record_field = data.get('record')
    items = data.get('items', [])

    field_description = record_field.get('description')
    field_label = record_field.get('label')

    # Aggiorna descrizione e label del campo
    field_record = SysField.objects.filter(tableid=tableid, id=fieldid).first()
    if not field_record:
        return JsonResponse({"success": False, "error": "Campo non trovato"}, status=404)

    field_record.description = str(field_description)
    field_record.label = str(field_label)
    field_record.save()

    lookuptableid = None
    if field_record.lookuptableid:
        lookuptableid = field_record.lookuptableid.tableid
        
    if lookuptableid is None:
        items = []

    # --- Gestione Lookup Items ---
    new_items = [item for item in items if item.get("status") == "new"]
    deleted_items = [item for item in items if item.get("status") == "deleted"]
    changed_items = [item for item in items if item.get("status") == "changed"]

    if deleted_items:
        SysLookupTableItem.objects.filter(
            lookuptableid=lookuptableid,
            itemcode__in=[item["itemcode"] for item in deleted_items if item.get("itemcode")]
        ).delete()

    for item in changed_items:
        SysLookupTableItem.objects.filter(
            lookuptableid=lookuptableid,
            itemcode=item.get("itemcode")
        ).update(
            itemcode=item.get("itemdesc", ""), 
            itemdesc=item.get("itemdesc", "")
        )

    new_lookup_items = [
        SysLookupTableItem(
            lookuptableid=lookuptableid,
            itemcode=item.get("itemcode") or f"new_{i}",
            itemdesc=item.get("itemdesc", "")
        )
        for i, item in enumerate(new_items)
    ]
    if new_lookup_items:
        SysLookupTableItem.objects.bulk_create(new_lookup_items)

    # Gestione settings personalizzati
    # Se esiste già → aggiorna, altrimenti crea
    fieldsettings_obj = FieldSettings(tableid=tableid, fieldid=field_record.fieldid, userid=userid)

    # Aggiorna le chiavi presenti nel dizionario settings
    settings_dict = fieldsettings_obj.settings or {}

    for key, value in settings_list.items():
        # Ogni valore è un dict con {"type": "...", "value": "..."}
        if key not in settings_dict:
            settings_dict[key] = {}
        settings_dict[key].update(value)

    # for setting in settings_list:
        # fieldsettings_obj.settings[setting['name']]['value'] = setting['value']

    fieldsettings_obj.settings = settings_dict
    fieldsettings_obj.save()

    return JsonResponse({
        'success': True, 
        'fieldsettings': fieldsettings_obj.get_settings(), 
        'record': {"label": field_record.label, "description": field_record.description},
        'items': list(SysLookupTableItem.objects.filter(lookuptableid=lookuptableid).values())
    })


def settings_table_fields_new_field(request):
    data = json.loads(request.body)

    tableid = data.get("tableid")
    userid = data.get("userid")
    fieldid = data.get("fieldid")
    fielddescription = data.get("fielddescription")
    fieldtype = data.get("fieldtype")
    label = data.get("label", "Dati")

    if not all([tableid, fieldid, fielddescription, fieldtype]):
        return JsonResponse({"success": False, "error": "Dati mancanti o non validi"}, status=400)

    # Evita duplicati
    if SysField.objects.filter(tableid=tableid, fieldid=fieldid).first() is not None:
        return JsonResponse({"success": False, "error": "Campo già esistente"}, status=400)

    tableid_obj = SysTable.objects.filter(id=tableid).first()

    # Caso base
    new_field = SysField.objects.create(
        tableid=tableid_obj.id,
        fieldid=fieldid,
        description=fielddescription,
        fieldtypewebid=fieldtype,
        label=label,
        length=255,
    )

    # Se è un campo Categoria → crea lookup table e relative opzioni
    if fieldtype == "Categoria":
        lookuptableid = f"{fieldid}_{tableid}"
        lookup_table = SysLookupTable.objects.create(
            description=fieldid,
            tableid=lookuptableid,
            itemtype="Carattere",
            codelen=255,
            desclen=255
        )

        values = data.get("valuesArray", [])
        for v in values:
            desc = v.get("description")
            if desc:
                SysLookupTableItem.objects.create(
                    lookuptableid=lookuptableid,
                    itemcode=desc,
                    itemdesc=desc
                )

    # Se è un Checkbox → crea lookup Si/No
    elif fieldtype == "Checkbox":
        lookuptableid = f"{fieldid}_{tableid}"
        SysLookupTable.objects.create(
            description=fieldid,
            tableid=lookuptableid,
            itemtype="Carattere",
            codelen=255,
            desclen=255
        )
        SysLookupTableItem.objects.bulk_create([
            SysLookupTableItem(lookuptableid=lookuptableid, itemcode="Si", itemdesc="Si"),
            SysLookupTableItem(lookuptableid=lookuptableid, itemcode="No", itemdesc="No"),
        ])

    return JsonResponse({"success": True})


def settings_table_fields_settings_block(request):
    data = json.loads(request.body)
    tableid = data.get('tableid')
    fieldid = data.get('fieldid')
    userid = int(data.get('userid'))

    field_record = SysField.objects.filter(tableid=tableid, id=fieldid).first()
    if not field_record:
        return JsonResponse({"error": "Field not found"}, status=404)

    fieldsettings_obj = FieldSettings(tableid=tableid, fieldid=field_record.fieldid, userid=userid)

    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT * FROM sys_field WHERE tableid = '{tableid}' AND id = '{fieldid}'"
        )
        record = dictfetchall(cursor)

        if record[0]['lookuptableid'] != '':
            cursor.execute(
                f"SELECT * FROM sys_lookup_table_item WHERE lookuptableid = '{record[0]['lookuptableid']}'"
            )
            items = dictfetchall(cursor)

    fieldsettings = fieldsettings_obj.get_settings()

    # Settings standarduser
    # fieldsettings_obj = FieldSettings(tableid=tableid, fieldid=fieldid, userid=1)

    # with connection.cursor() as cursor:
    #     cursor.execute(
    #         f"SELECT * FROM sys_field WHERE tableid = '{tableid}' AND id = '{fieldid}'"
    #     )
    #     record = dictfetchall(cursor)

    #     if record[0]['lookuptableid'] != '':
    #         cursor.execute(
    #             f"SELECT * FROM sys_lookup_table_item WHERE lookuptableid = '{record[0]['lookuptableid']}'"
    #         )
    #         items = dictfetchall(cursor)

    record = record
    if not items:
        items = ''

    return JsonResponse({
        "fieldsettings": fieldsettings,
        "record": record[0],
        "items": items,
        # "hierarchy": {
        #     "standarduser": bl.get_standarduser_hierarchy(),
        #     "groups": bl.get_groups_hierarchy(),
        #     "user": bl.get_user_hierarchy(userid),
        # }
    })


def settings_table_linkedtables(request):
    data = json.loads(request.body)
    tableid = data.get('tableid')
    userid = data.get('userid')

    # Subquery per prendere il fieldorder dell'utente se esiste
    user_order_subquery = SysUserOrder.objects.filter(
        tableid=OuterRef('tableid'),
        fieldid=OuterRef('tablelinkid'),
        userid=userid
    ).values('fieldorder')[:1]

    linked_qs = (
        SysTableLink.objects
        .filter(tableid=tableid)
        .select_related('tablelinkid')  # segue FK per accedere alla descrizione
        .annotate(fieldorder=Subquery(user_order_subquery, output_field=IntegerField()))
        .order_by(Coalesce('fieldorder', 9999))
    )

    # Costruiamo la lista per React nel formato richiesto
    linked_tables = [
        {
            "tablelinkid": link.tablelinkid.id if hasattr(link.tablelinkid, 'id') else link.tablelinkid,
            "description": getattr(link.tablelinkid, 'description', ''),
            "fieldorder": link.fieldorder,
        }
        for link in linked_qs
    ]

    return JsonResponse({
        "success": True,
        "linked_tables": linked_tables
    })

@transaction.atomic
def settings_table_linkedtables_save(request):
    data = json.loads(request.body)
    tableid = data.get('tableid')
    userid = data.get('userid')
    fields = data.get('fields')

    if not all([tableid, userid, fields]):
        return JsonResponse({'success': False, 'error': 'Missing parameters'}, status=400)

    errors = []

    user = SysUser.objects.filter(id=userid).first()
    if not user:
        return JsonResponse({"error": "User not found"}, status=404)
    
    table = SysTable.objects.filter(id=tableid).first()
    if not table:
        return JsonResponse({"error": "Table not found"}, status=404)

    for field in fields:
        fieldid = field.get("tablelinkid")
        order = field.get("fieldorder")

        if not fieldid:
            continue

        field = SysTable.objects.filter(id=fieldid).first()
        if not field:
            errors.append({"error": "Linked table not found", "tablelinkid": fieldid})
            continue

        order_value = order if order is not None else None

        user_table_order, created = SysUserOrder.objects.get_or_create(
            userid=user,
            tableid=table,
            fieldid=fieldid,
            typepreference='keylabel'
        )

        user_table_order.fieldorder = order_value
        user_table_order.save()

    return JsonResponse({'success': True})


from django.db import connection, transaction
from django.http import JsonResponse
from .models import *

def save_new_table(request):
    data = json.loads(request.body)
    tableid = data.get('tableid')
    userid = data.get('userid')
    description = data.get('description')
    workspace = data.get('workspace', 'ALTRO')

    table_exists = SysTable.objects.filter(id=tableid).first() is not None
    if table_exists:
        return JsonResponse({'success': False, 'error': 'Table ID already exists'}, status=400)
    
    # Inserisci la nuova riga in sys_table (ORM)
    table = SysTable.objects.create(
        id=tableid,
        description=description,
        workspace=workspace,
        creationdate=timezone.now(),
        tabletypeid='0',
        dbtypeid='0',
        totpages=0,
        namefolder='000',
        numfilesfolder='0'
    )

    # Creazione della tabella fisica sul DB (SQL raw)
    # Non si può fare con ORM, quindi rimane raw SQL
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            CREATE TABLE user_{tableid} (
                recordid_ CHAR(32) PRIMARY KEY,
                creatorid_ INT(11) NOT NULL,
                creation_ DATETIME NOT NULL,
                lastupdaterid_ INT(11),
                lastupdate_ DATETIME,
                totpages_ INT(11),
                firstpagefilename_ VARCHAR(255),
                recordstatus_ VARCHAR(255),
                deleted_ CHAR(1) DEFAULT 'N',
                id INT(11)
            ) CHARACTER SET utf8 COLLATE utf8_general_ci
            """
        )

    with transaction.atomic():
        # Inserisci il campo di sistema "id" in sys_field (ORM)
        field = SysField.objects.create(
            tableid=tableid,
            fieldid='id',
            fieldtypeid='Seriale',
            fieldtypewebid='Seriale',
            label='Sistema',
            description='ID'
        )

        user = SysUser.objects.filter(id=userid).first()
        if not user:
            return JsonResponse({'success': False, 'error': 'User not found'}, status=404)
        print(type(user))


        # Imposta l'ordine dei campi per l'utente (ORM)
        preferences = ['search_results_fields', 'insert_fields', 'search_fields']
        for pref in preferences:
            SysUserFieldOrder.objects.create(
                userid=user,
                tableid=table,
                fieldid=field,
                fieldorder=0,
                typepreference=pref
            )

        # Crea la vista "Tutti" (ORM)
        view = SysView.objects.create(
            name='Tutti',
            userid=user,
            tableid=table,
            query_conditions='true'
        )

        # Imposta le impostazioni utente della tabella (ORM)
        SysUserTableSettings.objects.bulk_create([
            SysUserTableSettings(userid=user, tableid=table, settingid='default_viewid', value=view.id),
            SysUserTableSettings(userid=user, tableid=table, settingid='default_recordtab', value='Fields'),
        ])

    # Risposta JSON
    return JsonResponse({'success': True})
