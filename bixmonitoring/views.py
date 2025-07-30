from django.http import HttpResponse, JsonResponse
import sys
import importlib
from datetime import datetime, timedelta
from django.db import connection
from django.shortcuts import redirect, render

from commonapp.bixmodels.user_record import UserRecord



def lista_monitoring(request):
    cliente_id = request.GET.get('cliente_id', 'all')
    tipo = request.GET.get('tipo', 'services')
    parametro = request.GET.get('parametro', 'all')
    periodo = request.GET.get("periodo")

    if parametro != 'all':
        parametro = parametro.split(',')
    else:
        parametro = []

    only_params = request.GET.get('only_params', 'false') == 'true'

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if only_params:
            _, _, parametri = get_distinct_values(cliente_id, tipo)
            return JsonResponse({'parametri': parametri})
        else:
            parametri = get_filtered_values(cliente_id, tipo, parametro, periodo)
            data = {
                'parametri': [{'nome': p[0], 'valore': p[1], 'data': p[2], 'ora': p[3]} for p in parametri],
                'tipo': tipo,
            }
            return JsonResponse(data)

    cliente_ids, tipi, parametri = get_distinct_values(cliente_id, tipo)
    context = {
        'cliente_ids': cliente_ids,
        'tipi': tipi,
        'parametri': parametri,
    }
    return render(request, 'lista_monitoring.html', context)

def get_output(func, output, run_at, cliente_id):
    print(f"DEBUG - Tipo output: {type(output)}; Valore output: {output}")

    if not isinstance(output, dict):
        output = {
            'status': 'success',
            'value': {'result': output},
            'type': 'unknown'
        }

    # output è un dict, estraiamo i valori
    status = output.get('status', '')
    output_type = output.get('type', '')
    values = output.get('value', {})

    # Se value è un dict o altro, converti in stringa JSON per salvarlo come testo
    import json
    valore_num = json.dumps(values)

    # run_at è un datetime? Se no converti
    if not isinstance(run_at, datetime):
        run_at = datetime.now()

    # Salvataggio su sys_monitoring
    salva_sys_monitoring(run_at, func, output_type, output, cliente_id)

    # Salvataggio su user_monitoring
    salva_user_monitoring(status, run_at, func, output_type, values, cliente_id)

def salva_user_monitoring(status, run_at, func, output_type, values, cliente_id):
    data = run_at.date().isoformat()
    ora = run_at.strftime("%H:%M:%S")

    for parametro, valore in values.items():
        record = UserRecord("monitoring")  # crea nuovo record nella tabella user_monitoring

        record.values["recordstatus_"] = status
        record.values["data"] = data
        record.values["ora"] = ora
        record.values["funzione"] = func
        record.values["tipo"] = output_type
        record.values["client_id"] = cliente_id
        record.values["parametro"] = parametro

        if output_type in ['counters', 'folders']:
            record.values["valore_num"] = valore
        elif output_type == 'dates':
            record.values["valore_data"] = valore
        elif output_type == 'services':
            record.values["valore_stringa"] = valore
        else:
            record.values["valore_stringa"] = str(valore)

        record.save()

def salva_sys_monitoring(run_at, func, output_type, output, cliente_id):
    data = run_at.date().isoformat()  
    ora = run_at.strftime("%H:%M:%S") 

    with connection.cursor() as cursor:
        cursor.execute("""
            INSERT INTO sys_monitoring (data, ora, client_id, funzione, tipo, output)
            VALUES (%s, %s, %s, %s, %s, %s);
        """, [data, ora, cliente_id, func, output_type, output])

def get_distinct_values(cliente_id=None, tipo=None):
    with connection.cursor() as cursor:
        # Recupero client_id
        cursor.execute("""
            SELECT DISTINCT client_id 
            FROM user_monitoring 
            ORDER BY client_id
        """)
        cliente_ids = [row[0].capitalize() if row[0] else '' for row in cursor.fetchall()]
        
        # Recupero tipi, escludendo 'no_output'
        cursor.execute("""
            SELECT DISTINCT tipo 
            FROM user_monitoring 
            WHERE LOWER(tipo) != 'no_output'
            ORDER BY tipo
        """)
        tipi = [row[0].capitalize() if row[0] else '' for row in cursor.fetchall()]

        # Filtro dei parametri con esclusione di 'no_output'
        query = """
            SELECT DISTINCT parametro 
            FROM user_monitoring 
            WHERE LOWER(tipo) != 'no_output'
        """
        params = []
        if cliente_id and cliente_id.lower() != 'all':
            query += " AND client_id = %s"
            params.append(cliente_id)
        if tipo and tipo.lower() != 'all':
            query += " AND tipo = %s"
            params.append(tipo)
        query += " ORDER BY parametro"

        cursor.execute(query, params)
        parametri = [row[0] for row in cursor.fetchall()]

    return cliente_ids, tipi, parametri

def get_filtered_values(client_id, tipo, parametro, periodo=None):
    # Normalizza parametro in lista di valori validi
    if isinstance(parametro, list):
        param_list = [p.strip() for p in parametro if p.strip() and p.strip().lower() != 'all']
    elif isinstance(parametro, str):
        param_list = [p.strip() for p in parametro.split(',') if p.strip() and p.strip().lower() != 'all']
    else:
        param_list = []

    # Calcola la data di inizio per il filtro temporale
    data_inizio = None
    today = datetime.today().date()

    if periodo == 'oggi':
        data_inizio = today
    elif periodo == 'settimana':
        data_inizio = today - timedelta(days=7)
    elif periodo == 'mese':
        data_inizio = today - timedelta(days=30)

    with connection.cursor() as cursor:
        tipo_lower = tipo.lower()
        value_column = 'valore_num' if tipo_lower in ['folders', 'counters'] else 'valore_stringa'

        if tipo_lower == 'services':
            # Solo il valore più recente per ogni parametro
            sql = f"""
            SELECT um.parametro, um.{value_column}, um.data, um.ora
            FROM user_monitoring um
            INNER JOIN (
                SELECT parametro, MAX(CONCAT(data, ' ', ora)) AS max_datetime
                FROM user_monitoring
                WHERE (%s = 'all' OR client_id = %s)
                  AND (%s = 'all' OR tipo = %s)
                  {'' if not param_list else 'AND parametro IN %s'}
                GROUP BY parametro
            ) latest ON um.parametro = latest.parametro 
                     AND CONCAT(um.data, ' ', um.ora) = latest.max_datetime
            WHERE (%s = 'all' OR um.client_id = %s)
              AND (%s = 'all' OR um.tipo = %s)
              {'' if not param_list else 'AND um.parametro IN %s'}
            ORDER BY um.parametro
            """
            params = [client_id, client_id, tipo, tipo]
            if param_list:
                params.append(tuple(param_list))
            params.extend([client_id, client_id, tipo, tipo])
            if param_list:
                params.append(tuple(param_list))

        else:
            # Query per folders, counters, ecc.
            sql = f"""
            SELECT parametro, {value_column}, data, ora 
            FROM user_monitoring
            WHERE (%s = 'all' OR client_id = %s)
              AND (%s = 'all' OR tipo = %s)
            """
            params = [client_id, client_id, tipo, tipo]

            if param_list:
                placeholders = ','.join(['%s'] * len(param_list))
                sql += f" AND parametro IN ({placeholders})"
                params += param_list

            if data_inizio:
                sql += " AND data >= %s"
                params.append(data_inizio)

            sql += " ORDER BY data DESC"

        cursor.execute(sql, params)
        results = cursor.fetchall()

    return results



