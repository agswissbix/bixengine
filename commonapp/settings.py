from bixsettings.views.businesslogic.settings_business_logic import *
from bixsettings.views.helpers.helperdb import Helperdb
from django.http import JsonResponse
from django.db.models.query import QuerySet

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
    tables = list(SysTable.objects.values())

    for field in fields:
        if field['fieldid'][-1] == '_':
            fields.remove(field)

    return JsonResponse({
        "fields": fields,
        "tables": tables
    })