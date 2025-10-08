from commonapp.views import dictfetchall
from bixsettings.views.businesslogic.settings_business_logic import *
from bixsettings.views.helpers.helperdb import Helperdb
from django.http import JsonResponse
from django.db.models.query import QuerySet
from bixsettings.views.businesslogic.models.table_settings import TableSettings
from bixsettings.views.businesslogic.models.field_settings import *
from bixsettings.views.helpers.helperdb import *


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


def settings_table_fields(request):
    data = json.loads(request.body)
    tableid = data.get('tableid')
    userid = data.get('userid')

    fields = list(SysField.objects.filter(tableid=tableid).values())

    for field in fields[:]:  # usa [:] per evitare problemi durante la rimozione
        # Rimuovi i campi con fieldid che termina con "_"
        if field['fieldid'].endswith('_'):
            fields.remove(field)
            continue

        # Recupera l'ordine dell'utente per questo campo
        user_field_conf = SysUserFieldOrder.objects.filter(
            tableid=tableid,
            fieldid=field['id'],
            userid=userid
        ).first()

        # Aggiungi solo l'order (None se non esiste)
        field['order'] = user_field_conf.fieldorder if user_field_conf else None

    return JsonResponse({
        "fields": fields
    })


def settings_table_settings(request):
    tableid = json.loads(request.body).get('tableid')
    tablesettings_obj = TableSettings(tableid=tableid, userid=1)
    tablesettings = tablesettings_obj.get_settings()

    return JsonResponse({"tablesettings": tablesettings})


def settings_table_fields_settings_save(request):
    data = json.loads(request.body)

    settings_list = data.get('settings')
    userid = data.get('userid')
    tableid = data.get('tableid')

    tablesettings_obj = TableSettings(tableid=tableid, userid=1)
    # esempio fieldsettings_obj.settings['obbligatorio']['value']=True
    # esempio fieldsettings_obj.save()
    # dict con tutt i i settings. vedi te come compilarlo fieldsettings_obj.settings

    for setting in settings_list:
        old_value = tablesettings_obj.settings[setting['name']]['value']
        new_value = setting['value']
        if new_value != old_value:
            old_value = new_value

    tablesettings_obj.save()

    return HttpResponse({'success': True})



def settings_table_usertables_save(request):
    data = json.loads(request.body)
    userid = data.get('userid')
    workspaces = data.get('workspaces', {})

    for workspace_key, workspace_data in workspaces.items():
        tables = workspace_data.get('tables', [])
        for table in tables:
            table_id = table.get('id')
            order = table.get('order')

            if table_id is None:
                continue  # Salta eventuali tabelle senza id

            # Recupera o crea il record esistente
            user_table_order = SysUserTableOrder.objects.filter(
                userid=userid,
                tableid=table_id
            ).first()

            if user_table_order is None:
                return JsonResponse({'success': False, 'error': f'Table with id {table_id} not found for user {userid}'})
            
            if user_table_order.tableorder == order:
                continue

            user_table_order.tableorder = order
            user_table_order.save()

    return JsonResponse({'success': True})

def settings_table_tablefields_save(request):
    data = json.loads(request.body)
    tableid = data.get('tableid')
    userid = data.get('userid')
    fields = data.get('fields', [])

    for field in fields:
        fieldid = field.get("id")
        order = field.get("order")

        if not fieldid:
            continue  # skip campi non validi

        order_value = order if order is not None else None

        user_table_order = SysUserFieldOrder.objects.filter(
            userid=userid,
            tableid=tableid,
            fieldid=fieldid,
        ).all()

        if user_table_order is None:
            return JsonResponse({'success': False, 'error': f'Table with id {tableid} not found for user {userid}'})
        
        for t in user_table_order:
            if t.fieldorder == order_value:
                continue

            t.fieldorder = order_value
            t.save()

    return JsonResponse({'success': True})


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
    new_field = SysField(
        tableid=tableid_obj,
        fieldid=fieldid,
        description=fielddescription,
        fieldtypewebid=fieldtype,
        label=label,
        length=255,
    )

    new_field.save()

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
    fieldsettings_obj = FieldSettings(tableid=tableid, fieldid=fieldid, userid=userid)

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
    if items:
        items = items
    else:
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