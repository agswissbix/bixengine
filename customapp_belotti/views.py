from django.shortcuts import render
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
import pyodbc
import environ
from django.conf import settings
from commonapp.bixmodels.user_record import *
from commonapp.bixmodels.user_table import *
from commonapp.bixmodels.helper_db import *
from commonapp.helper import *
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from datetime import datetime, date

# Initialize environment variables
env = environ.Env()
environ.Env.read_env()

def dictfetchall(cursor):
        "Return all rows from a cursor as a dict"
        columns = [col[0] for col in cursor.description]
        return [
            dict(zip(columns, row))
            for row in cursor.fetchall()
        ]


def sync_utenti_adiutobixdata(request):
    try:
        DRIVER = env('DB_DRIVER')
        SERVER = env('DB_SERVER')
        DATABASE = env('DB_NAME')
        UID = env('DB_USER')
        PWD = env('DB_PASSWORD')
        conn = pyodbc.connect(
            f"DRIVER={DRIVER};"
            f"SERVER={SERVER};"
            f"DATABASE={DATABASE};"
            f"UID={UID};"
            f"PWD={PWD};",
            timeout=5
        )
        cursor = conn.cursor()

        data = []
        try:
            cursor.execute("SELECT  * FROM A1014")
            rows = dictfetchall(cursor)

            for row in rows:
                utente_bix = row['F1053']
                
                # Verifica se il record esiste in base a utentebixdata
                sql_check = f"SELECT recordid_ FROM user_sync_adiuto_utenti WHERE utentebixdata = '{utente_bix}'"
                existing = HelpderDB.sql_query_value(sql_check, 'recordid_')

                if existing:
                    # Se esiste, aggiorna
                    record = UserRecord('sync_adiuto_utenti', recordid=existing)
                else:
                    # Altrimenti crea un nuovo record
                    record = UserRecord('sync_adiuto_utenti')

                # Imposta i valori
                record.values['utentebixdata'] = utente_bix  # Chiave logica
                record.values['utenteadiuto'] = row['F1052']
                record.values['gruppo'] = row['F1050']
                record.values['email'] = row['F1017']
                record.values['nome'] = row['F1054']
                # ... aggiungi altri campi se necessario

                record.save()

        except pyodbc.ProgrammingError as e:
            return JsonResponse({"success": False, "error": f"Errore nella query SQL: {str(e)}"})
        except Exception as e:
            return JsonResponse({"success": False, "error": f"Errore durante l'esecuzione della query: {str(e)}"})
        finally:
            cursor.close()

    except pyodbc.InterfaceError as e:
        return JsonResponse({"success": False, "error": f"Errore di connessione (InterfaceError): {str(e)}"})
    except pyodbc.OperationalError as e:
        return JsonResponse({"success": False, "error": f"Errore operativo nella connessione al database: {str(e)}"})
    except Exception as e:
        return JsonResponse({"success": False, "error": f"Errore generico di connessione: {str(e)}"})
    finally:
        try:
            if conn:
                conn.close()
        except NameError:
            pass  # conn non definita se la connessione è fallita

    return JsonResponse({"success": True, "rows": rows})


def sync_prodotti_adiutobixdata(request):
    try:
        DRIVER = env('DB_DRIVER')
        SERVER = env('DB_SERVER')
        DATABASE = env('DB_NAME')
        UID = env('DB_USER')
        PWD = env('DB_PASSWORD')
        conn = pyodbc.connect(
            f"DRIVER={DRIVER};"
            f"SERVER={SERVER};"
            f"DATABASE={DATABASE};"
            f"UID={UID};"
            f"PWD={PWD};",
            timeout=5
        )
        cursor = conn.cursor()

        data = []
        try:
            cursor.execute("SELECT  * FROM VA1009 WHERE FENA<>0")
            rows = dictfetchall(cursor)

            for row in rows:
                codice = row['F1029']
                
                # Verifica se il record esiste in base a utentebixdata
                sql_check = f"SELECT recordid_ FROM user_sync_adiuto_prodotti WHERE codice = '{codice}'"
                existing = HelpderDB.sql_query_value(sql_check, 'recordid_')

                if existing:
                    # Se esiste, aggiorna
                    record = UserRecord('sync_adiuto_prodotti', recordid=existing)
                else:
                    # Altrimenti crea un nuovo record
                    record = UserRecord('sync_adiuto_prodotti')

                # Imposta i valori
                record.values['codice'] = codice  # Chiave logica
                record.values['descrizione'] = row['F1030']
                record.values['formato'] = row['F1031']
                record.values['categoria'] = row['F1032']
                record.values['gruppo'] = row['F1033']
                # ... aggiungi altri campi se necessario

                record.save()

        except pyodbc.ProgrammingError as e:
            return JsonResponse({"success": False, "error": f"Errore nella query SQL: {str(e)}"})
        except Exception as e:
            return JsonResponse({"success": False, "error": f"Errore durante l'esecuzione della query: {str(e)}"})
        finally:
            cursor.close()

    except pyodbc.InterfaceError as e:
        return JsonResponse({"success": False, "error": f"Errore di connessione (InterfaceError): {str(e)}"})
    except pyodbc.OperationalError as e:
        return JsonResponse({"success": False, "error": f"Errore operativo nella connessione al database: {str(e)}"})
    except Exception as e:
        return JsonResponse({"success": False, "error": f"Errore generico di connessione: {str(e)}"})
    finally:
        try:
            if conn:
                conn.close()
        except NameError:
            pass  # conn non definita se la connessione è fallita

    return JsonResponse({"success": True, "rows": rows})


def sync_formularigruppo_adiutobixdata(request):
    try:
        DRIVER = env('DB_DRIVER')
        SERVER = env('DB_SERVER')
        DATABASE = env('DB_NAME')
        UID = env('DB_USER')
        PWD = env('DB_PASSWORD')
        conn = pyodbc.connect(
            f"DRIVER={DRIVER};"
            f"SERVER={SERVER};"
            f"DATABASE={DATABASE};"
            f"UID={UID};"
            f"PWD={PWD};",
            timeout=5
        )
        cursor = conn.cursor()

        data = []
        try:
            cursor.execute("SELECT  * FROM A1012")
            rows = dictfetchall(cursor)

            for row in rows:
                gruppo = row['F1050']
                
                # Verifica se il record esiste in base a utentebixdata
                sql_check = f"SELECT recordid_ FROM user_sync_adiuto_formularigruppo WHERE gruppo = '{gruppo}'"
                existing = HelpderDB.sql_query_value(sql_check, 'recordid_')

                if existing:
                    # Se esiste, aggiorna
                    record = UserRecord('sync_adiuto_formularigruppo', recordid=existing)
                else:
                    # Altrimenti crea un nuovo record
                    record = UserRecord('sync_adiuto_formularigruppo')

                # Imposta i valori
                record.values['gruppo'] = gruppo  # Chiave logica
                record.values['formulari'] = row['F1033']
                # ... aggiungi altri campi se necessario

                record.save()

        except pyodbc.ProgrammingError as e:
            return JsonResponse({"success": False, "error": f"Errore nella query SQL: {str(e)}"})
        except Exception as e:
            return JsonResponse({"success": False, "error": f"Errore durante l'esecuzione della query: {str(e)}"})
        finally:
            cursor.close()

    except pyodbc.InterfaceError as e:
        return JsonResponse({"success": False, "error": f"Errore di connessione (InterfaceError): {str(e)}"})
    except pyodbc.OperationalError as e:
        return JsonResponse({"success": False, "error": f"Errore operativo nella connessione al database: {str(e)}"})
    except Exception as e:
        return JsonResponse({"success": False, "error": f"Errore generico di connessione: {str(e)}"})
    finally:
        try:
            if conn:
                conn.close()
        except NameError:
            pass  # conn non definita se la connessione è fallita

    return JsonResponse({"success": True, "rows": rows})



@csrf_exempt
@api_view(['POST'])
def belotti_salva_formulario(request):
    """
    Esempio di funzione che riceve un barcode lotto (barcodeLotto)
    e una lista di barcode wip (barcodeWipList).
    """
    print("Fun: belotti_salva_formulario")
    # Estraggo i dati dal body della richiesta
    formType = request.data.get('formType', "")
    username = Helper.get_username(request)
    userid = Helper.get_userid(request)
    utenteadiuto=HelpderDB.sql_query_value(
        f"SELECT utenteadiuto FROM user_sync_adiuto_utenti WHERE utentebixdata = '{username}'",
        'utenteadiuto'
    )   
    record_richiesta=UserRecord('richieste')
    record_richiesta.values['tiporichiesta']=formType
    record_richiesta.values['data'] = datetime.now().strftime("%Y-%m-%d")
    record_richiesta.values['stato'] = 'Richiesta inviata'
    record_richiesta.values['utentebixdata'] = userid
    record_richiesta.values['utenteadiuto'] = utenteadiuto
    record_richiesta.save()

    completeOrder = request.data.get('completeOrder', [])
    for order_row in completeOrder:
        categoria=order_row.get('title', None)
        
        products=order_row.get('products', [])
        for product in products:
            codice=product.get('id', None)
            descrizione=product.get('name', None)
            quantita=product.get('quantity', None)
            if not Helper.isempty(quantita):
                if quantita > 0:
                    record_richieste_righedettaglio = UserRecord('richieste_righedettaglio')
                    record_richieste_righedettaglio.values['recordidrichieste_'] = record_richiesta.recordid
                    record_richieste_righedettaglio.values['codice'] =codice
                    record_richieste_righedettaglio.values['prodotto'] = descrizione
                    record_richieste_righedettaglio.values['quantita'] = quantita
                    record_richieste_righedettaglio.values['categoria'] = categoria
                    record_richieste_righedettaglio.save()
                    print(product)
                else:
                    print("Vuoto")

    return Response(
        {
            "message": "Dati salvati!",
        },
        status=status.HTTP_200_OK
    )
def test_sync_fatture_sirioadiuto(request):
    source_conn_str = (
        f"DRIVER={{Pervasive ODBC Unicode Interface}};"
        f"ServerName={os.environ.get('SIRIO_DB_SERVER')};"
        f"DBQ={os.environ.get('SIRIO_DB_NAME')};"
        f"UID={os.environ.get('SIRIO_DB_USER')};"
    )

    try:
        src_conn = pyodbc.connect(source_conn_str, timeout=5)
        src_cursor = src_conn.cursor()

        src_cursor.execute("SELECT TOP 1000 * FROM Documenti ORDER BY id_sirio DESC")
        columns = [column[0] for column in src_cursor.description]
        rows = src_cursor.fetchall()

        data = [dict(zip(columns, row)) for row in rows]

        return JsonResponse({'status': 'success', 'rows': data}, safe=False)

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

    finally:
        try:
            src_cursor.close()
            src_conn.close()
        except:
            pass


def sync_fatture_sirioadiutoBAK(request):
    src_db_name=os.environ.get('SIRIO_DB_NAME')
    source_conn_str = (
        f"DRIVER={{Pervasive ODBC Unicode Interface}};"
        f"ServerName={os.environ.get('SIRIO_DB_SERVER')};"
        f"DBQ={src_db_name};"
        f"UID={os.environ.get('SIRIO_DB_USER')};"
    )

    src_db_name=os.environ.get('SIRIO_DB_NAME_2')
    source_conn_str_2 = (
        f"DRIVER={{Pervasive ODBC Unicode Interface}};"
        f"ServerName={os.environ.get('SIRIO_DB_SERVER')};"
        f"DBQ={src_db_name_2};"
        f"UID={os.environ.get('SIRIO_DB_USER')};"
    )

    target_conn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={os.environ.get('ADIUTO_DB_SERVER')};"
        f"DATABASE={os.environ.get('ADIUTO_DB_NAME')};"
        f"UID={os.environ.get('ADIUTO_DB_USER')};"
        f"PWD={os.environ.get('ADIUTO_DB_PASSWORD')};"
    )

    try:
        data=[]
        src_conn = pyodbc.connect(source_conn_str, timeout=5)
        tgt_conn = pyodbc.connect(target_conn_str, timeout=5)
        src_cursor = src_conn.cursor()
        tgt_cursor = tgt_conn.cursor()

        src_cursor.execute("SELECT TOP 10 * FROM Documenti ORDER BY id_sirio DESC")
        columns = [column[0] for column in src_cursor.description]
        rows = src_cursor.fetchall()

        count = 0
        for row in rows:
            merge_sql = f"""
            MERGE dbo.T_SIRIO_FATTUREFORNITORE AS T
            USING (SELECT {sql_safe(row.barcode_adiuto)} AS barcode_adiuto,
              {sql_safe(row.id_sirio)} AS id_sirio,
              {sql_safe(row.numero_fattura)} AS numero_fattura,
              {sql_safe(row.titolo)} AS titolo,
              {sql_safe(row.data_fattura)} AS data_fattura,
              {sql_safe(row.data_scadenza)} AS data_scadenza,
              {sql_safe(row.importo)} AS importo,
              {sql_safe(row.sigla_valuta)} AS sigla_valuta,
              {sql_safe(row.tipo_documento)} AS tipo_documento,
              {sql_safe(row.id_fornitore)} AS id_fornitore,
              {sql_safe(row.nome_fornitore)} AS nome_fornitore,
              {sql_safe(row.indirizzo_fornitore)} AS indirizzo_fornitore,
              {sql_safe(row.altro_indirizzo_fornitore)} AS altro_indirizzo_fornitore,
              {sql_safe(row.via_fornitore)} AS via_fornitore,
              {sql_safe(row.npa_fornitore)} AS npa_fornitore,
              {sql_safe(row.luogo_fornitore)} AS luogo_fornitore,
              {sql_safe(row.telefono_fornitore)} AS telefono_fornitore,
              {sql_safe(row.altro_telefono_fornitore)} AS altro_telefono_fornitore,
              {sql_safe(row.email_fornitore)} AS email_fornitore) AS S
            ON T.id_sirio = S.id_sirio AND T.numero_fattura = S.numero_fattura

            WHEN MATCHED THEN
                UPDATE SET
                    barcode_adiuto = S.barcode_adiuto,
                    titolo = S.titolo,
                    data_fattura = S.data_fattura,
                    data_scadenza = S.data_scadenza,
                    importo = S.importo,
                    sigla_valuta = S.sigla_valuta,
                    tipo_documento = S.tipo_documento,
                    id_fornitore = S.id_fornitore,
                    nome_fornitore = S.nome_fornitore,
                    indirizzo_fornitore = S.indirizzo_fornitore,
                    altro_indirizzo_fornitore = S.altro_indirizzo_fornitore,
                    via_fornitore = S.via_fornitore,
                    npa_fornitore = S.npa_fornitore,
                    luogo_fornitore = S.luogo_fornitore,
                    telefono_fornitore = S.telefono_fornitore,
                    altro_telefono_fornitore = S.altro_telefono_fornitore,
                    email_fornitore = S.email_fornitore

            WHEN NOT MATCHED THEN
                INSERT (barcode_adiuto, id_sirio, numero_fattura, titolo, data_fattura,
                        data_scadenza, importo, sigla_valuta, tipo_documento, id_fornitore,
                        nome_fornitore, indirizzo_fornitore, altro_indirizzo_fornitore,
                        via_fornitore, npa_fornitore, luogo_fornitore, telefono_fornitore,
                        altro_telefono_fornitore, email_fornitore)
                VALUES (S.barcode_adiuto, S.id_sirio, S.numero_fattura, S.titolo,
                        S.data_fattura, S.data_scadenza, S.importo, S.sigla_valuta,
                        S.tipo_documento, S.id_fornitore, S.nome_fornitore,
                        S.indirizzo_fornitore, S.altro_indirizzo_fornitore,
                        S.via_fornitore, S.npa_fornitore, S.luogo_fornitore,
                        S.telefono_fornitore, S.altro_telefono_fornitore,
                        S.email_fornitore);
            """

            # Esegui il merge
            #tgt_cursor.execute(merge_sql)
            count += 1
            rows = src_cursor.fetchall()

            data.append([dict(zip(columns, row)) for row in rows])

            return JsonResponse({'status': 'success', 'rows': data}, safe=False)
        #tgt_conn.commit()
        return JsonResponse({'status': 'success', 'imported_rows': count})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

    finally:
        try:
            src_cursor.close()
            src_conn.close()
            tgt_cursor.close()
            tgt_conn.close()
        except:
            pass


def sync_fatture_sirioadiuto(request):
    

    sirio_server = os.environ.get('SIRIO_DB_SERVER')
    sirio_user   = os.environ.get('SIRIO_DB_USER')

    adiuto_server = os.environ.get('ADIUTO_DB_SERVER')
    adiuto_db     = os.environ.get('ADIUTO_DB_NAME')
    adiuto_user   = os.environ.get('ADIUTO_DB_USER')
    adiuto_pwd    = os.environ.get('ADIUTO_DB_PASSWORD')

     # Quali campi tratti come "date" e "decimal"
    VARCHAR50_DATE_FIELDS    = {'data_fattura', 'data_scadenza'}
    
    def build_sirio_conn_str(db_name: str) -> str:
        return (
            f"DRIVER={{Pervasive ODBC Unicode Interface}};"
            f"ServerName={sirio_server};"
            f"DBQ={db_name};"
            f"UID={sirio_user};"
        )
    
    def get_sirio_db_names() -> list[str]:
        # Preferito: variabile singola CSV
        csv = os.environ.get('SIRIO_DB_NAMES')
        return [x.strip() for x in csv.split(',') if x.strip()]
    
    def _normalize_date_to_112(v: Any) -> str | None:
        """Rende una data come stringa 'YYYYMMDD' (112). Restituisce None se vuoto."""
        if v is None:
            return None
        if isinstance(v, (datetime, date)):
            return v.strftime('%Y%m%d')

        if isinstance(v, str):
            s = v.strip()
            if not s:
                return None
            # già YYYYMMDD
            if re.fullmatch(r'\d{8}', s):
                return s
            # YYYY-MM-DD o YYYY/MM/DD
            m = re.fullmatch(r'(\d{4})[-/](\d{2})[-/](\d{2})', s)
            if m:
                return f'{m.group(1)}{m.group(2)}{m.group(3)}'
            # DD-MM-YYYY o DD/MM/YYYY
            m = re.fullmatch(r'(\d{2})[-/](\d{2})[-/](\d{4})', s)
            if m:
                return f'{m.group(3)}{m.group(2)}{m.group(1)}'
        # fallback: non riconosciuto → stringa "così com'è"
        return str(v)

    def to_varchar50(field: str, value: Any) -> str | None:
        """Normalizza il valore per l'insert/update in una colonna VARCHAR(50)."""
        if value is None:
            return None

        if field in VARCHAR50_DATE_FIELDS:
            out = _normalize_date_to_112(value)
            return out[:50] if out else None


        # Default: stringa trim + cut
        s = str(value).strip()
        return s[:50] if s else None


    target_conn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={adiuto_server};"
        f"DATABASE={adiuto_db};"
        f"UID={adiuto_user};"
        f"PWD={adiuto_pwd};"
    )

    select_sql = """
        SELECT TOP 5000 
            barcode_adiuto,
            id_sirio,
            numero_fattura,
            titolo,
            data_fattura,
            data_scadenza,
            importo,
            sigla_valuta,
            tipo_documento,
            id_fornitore,
            nome_fornitore,
            indirizzo_fornitore,
            altro_indirizzo_fornitore,
            via_fornitore,
            npa_fornitore,
            luogo_fornitore,
            telefono_fornitore,
            altro_telefono_fornitore,
            email_fornitore
        FROM Documenti
        ORDER BY id_sirio DESC
    """

    base_fields = [
        "barcode_adiuto",
        "id_sirio",
        "numero_fattura",
        "titolo",
        "data_fattura",
        "data_scadenza",
        "importo",
        "sigla_valuta",
        "tipo_documento",
        "id_fornitore",
        "nome_fornitore",
        "indirizzo_fornitore",
        "altro_indirizzo_fornitore",
        "via_fornitore",
        "npa_fornitore",
        "luogo_fornitore",
        "telefono_fornitore",
        "altro_telefono_fornitore",
        "email_fornitore",
    ]

    all_fields = base_fields + ["db_name"]

    placeholders = ",".join(["?"] * len(all_fields))
    columns_list = ",".join(all_fields)


   

    merge_sql = f"""
    MERGE dbo.T_SIRIO_FATTUREFORNITORE AS T
    USING (VALUES ({placeholders})) AS S({columns_list})
        -- Consigliato: includi db_name nella ON per distinguere le sorgenti
        ON T.id_sirio = S.id_sirio
    AND T.numero_fattura = S.numero_fattura
    AND T.db_name = S.db_name
    WHEN MATCHED THEN
        UPDATE SET
            barcode_adiuto = S.barcode_adiuto,
            titolo = S.titolo,
            data_fattura = S.data_fattura,
            data_scadenza = S.data_scadenza,
            importo = S.importo,
            sigla_valuta = S.sigla_valuta,
            tipo_documento = S.tipo_documento,
            id_fornitore = S.id_fornitore,
            nome_fornitore = S.nome_fornitore,
            indirizzo_fornitore = S.indirizzo_fornitore,
            altro_indirizzo_fornitore = S.altro_indirizzo_fornitore,
            via_fornitore = S.via_fornitore,
            npa_fornitore = S.npa_fornitore,
            luogo_fornitore = S.luogo_fornitore,
            telefono_fornitore = S.telefono_fornitore,
            altro_telefono_fornitore = S.altro_telefono_fornitore,
            email_fornitore = S.email_fornitore
            -- Nota: non aggiorno T.db_name perché è parte della ON ed è "identità" della riga
    WHEN NOT MATCHED THEN
        INSERT ({columns_list})
        VALUES ({columns_list});
    """

    try:
        db_names = get_sirio_db_names()
        total_count = 0
        per_source = []
        preview_rows = []   # facoltativo: ritorna i records letti (per debug)
        errors = []
        with pyodbc.connect(target_conn_str, timeout=5) as tgt_conn:
            with tgt_conn.cursor() as tgt_cursor:

                for db_name in db_names:
                    processed = 0
                    try:
                        with pyodbc.connect(build_sirio_conn_str(db_name), timeout=5) as src_conn:
                            with src_conn.cursor() as src_cursor:
                                src_cursor.execute(select_sql)
                                rows = src_cursor.fetchall()

                                # opzionale: preview (lista piatta di dict)
                                columns = [c[0] for c in src_cursor.description]
                                preview_rows.extend(
                                    [{'db': db_name, **dict(zip(columns, r))} for r in rows]
                                )

                                for r in rows:
                                    # --- RAW (in base all’ordine definito da base_fields) ---
                                    raw_values = [getattr(r, fld, None) for fld in base_fields]

                                    # --- NORMALIZZAZIONE PER VARCHAR(50) (come per la MERGE) ---
                                    params_base = tuple(
                                        to_varchar50(fld, val) for fld, val in zip(base_fields, raw_values)
                                    )

                                    # Se vuoi anche vedere la preview, usa i valori normalizzati:
                                    normalized_map = {
                                        fld: val for fld, val in zip(base_fields, params_base)
                                    }
                                    normalized_map['db_name'] = db_name
                                    preview_rows.append(normalized_map)

                                    # --- PARAMS PER LA MERGE (se/quando la esegui) ---
                                    params = params_base + (db_name,)
                                    tgt_cursor.execute(merge_sql, params)
                                    processed += 1

                        # commit per singola sorgente (così le precedenti restano valide anche se una fallisce)
                        tgt_conn.commit()

                    except Exception as e:
                        # rollback della sorgente corrente
                        tgt_conn.rollback()
                        errors.append({'db': db_name, 'message': str(e)})

                    total_count += processed
                    per_source.append({'db': db_name, 'imported_rows': processed})

        resp = {
            'status': 'success',
            'imported_rows': total_count,
            'by_source': per_source,
            'rows_preview': preview_rows,  # rimuovi in produzione se non serve
        }
        if errors:
            resp['errors'] = errors
        return JsonResponse(resp, safe=False)

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})





def sql_safe(value):
    if value is None:
        return "NULL"

    if isinstance(value, (datetime, date)):
        return f"'{value.strftime('%Y%m%d')}'"

    if isinstance(value, (int, float)):
        return str(value)

    # qualunque altro tipo → cast a str, escape singoli apici
    cleaned = str(value).replace("'", "''")
    return f"'{cleaned}'"




def sync_richieste_bixdataadiuto(request):
    print("Fun: sync_richieste_bixdataadiuto")
    target_conn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={os.environ.get('ADIUTO_DB_SERVER')};"
        f"DATABASE={os.environ.get('ADIUTO_DB_NAME')};"
        f"UID={os.environ.get('ADIUTO_DB_USER')};"
        f"PWD={os.environ.get('ADIUTO_DB_PASSWORD')};"
    )
    print(target_conn_str)

    try:
        tgt_conn = pyodbc.connect(target_conn_str, timeout=5)
        tgt_cursor = tgt_conn.cursor()

        richieste_table = UserTable('richieste')
        rows = richieste_table.get_records(
            conditions_list={"stato='Richiesta inviata'"},
        )
        count = 0
        print("Numero di richieste da importare:")
        print(len(rows))
        for row in rows:
            
            merge_sql = f"""
                INSERT INTO dbo.T_BIXDATA_RICHIESTE (recordid_, tiporichiesta, datarichiesta, utentebixdata, utenteadiuto, idrichiesta)
                SELECT {sql_safe(row['recordid_'])}, {sql_safe(row['tiporichiesta'])}, {sql_safe(row['data'])}, {sql_safe(row['utentebixdata'])}, {sql_safe(row['utenteadiuto'])}, {sql_safe(row['id'])}
                WHERE NOT EXISTS (
                    SELECT 1 FROM dbo.T_BIXDATA_RICHIESTE WHERE recordid_ = {sql_safe(row['recordid_'])}
                )
            """
            # Esegui il merge
            tgt_cursor.execute(merge_sql)
            count += 1

            # righe di dettaglio
            richieste_righedettaglio_table = UserTable('richieste_righedettaglio')
            rows_dettagli = richieste_righedettaglio_table.get_records(
                conditions_list={f"recordidrichieste_={row['recordid_']}"}
            )
            for row_dettaglio in rows_dettagli:
                merge_sql_righe = f"""
                    INSERT INTO dbo.T_BIXDATA_RICHIESTE_DETTAGLI (recordid_, recordidrichieste_, codice, descrizione, quantita, categoria)
                    SELECT {sql_safe(row_dettaglio['recordid_'])}, {sql_safe(row_dettaglio['recordidrichieste_'])}, {sql_safe(row_dettaglio['codice'])}, {sql_safe(row_dettaglio['prodotto'])}, {sql_safe(row_dettaglio['quantita'])}, {sql_safe(row_dettaglio['categoria'])}
                    WHERE NOT EXISTS (
                        SELECT 1 FROM dbo.T_BIXDATA_RICHIESTE_DETTAGLI WHERE recordid_ = {sql_safe(row_dettaglio['recordid_'])}
                    )
                """
                tgt_cursor.execute(merge_sql_righe)
            

        tgt_conn.commit()
        return JsonResponse({'status': 'success', 'imported_rows': count})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

    finally:
        try:
            tgt_cursor.close()
            tgt_conn.close()
        except:
            pass

def send_order(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode('utf-8'))
            print("Dati ricevuti dal frontend:", data)  # <-- stampa in console


            formType = data.get('formType', "")
            username = Helper.get_username(request)
            userid = Helper.get_userid(request)
            utenteadiuto=HelpderDB.sql_query_value(
                f"SELECT utenteadiuto FROM user_sync_adiuto_utenti WHERE utentebixdata = '{username}'",
                'utenteadiuto'
            )   
            record_richiesta=UserRecord('richieste')
            record_richiesta.values['tiporichiesta']= formType
            record_richiesta.values['data'] = datetime.now().strftime("%Y-%m-%d")
            record_richiesta.values['stato'] = 'Richiesta inviata'
            record_richiesta.values['utentebixdata'] = userid
            record_richiesta.values['utenteadiuto'] = utenteadiuto
            record_richiesta.save()
            print("Record richiesta salvato:", record_richiesta.values)

            recordid_richiesta = record_richiesta.recordid

            for order_row in data.get('items', []):
                record_riga = UserRecord('richieste_righedettaglio')
                record_riga.values['recordidrichieste_'] = recordid_richiesta
                record_riga.values['codice'] = order_row.get('id', "")
                record_riga.values['prodotto'] = order_row.get('name', "")
                record_riga.values['quantita'] = order_row.get('quantity', 0)
                record_riga.values['categoria'] = order_row.get('categoria', "")
                diottria=order_row.get('diottria', "")
                record_riga.values['diottria'] = diottria
                colore= order_row.get('colore', "")
                record_riga.values['colore'] =colore
                boxdl= order_row.get('boxdl', "")
                record_riga.values['boxdl'] = boxdl
                referenza= order_row.get('referenza', "")
                record_riga.values['referenza'] = referenza
                raggio= order_row.get('raggio', "")
                record_riga.values['raggio'] = raggio
                sph= order_row.get('sph', "")
                record_riga.values['sph'] = sph
                diametro= order_row.get('diametro', "")
                record_riga.values['diametro'] = diametro
                record_riga.values['dettagli'] = f"Colore: {colore}, BoxDL: {boxdl}, Referenza: {referenza}, Raggio: {raggio}, SPH: {sph}, Diametro: {diametro}"
                record_riga.save()
            return JsonResponse({"success": True, "recordid_richiesta": recordid_richiesta})

        except Exception as e:
            print("Errore nella gestione della richiesta:", e)
            return JsonResponse({"success": False, "error": str(e)}, status=400)
    else:
        return JsonResponse({"success": False, "error": "Metodo non consentito"}, status=405)


def belotti_conferma_ricezione(request):
    try:
        data = json.loads(request.body)
        recordid = data.get('recordid', None)
        if not recordid:
            return JsonResponse({"success": False, "error": "recordid mancante"}, status=400)
        record = UserRecord('richieste', recordid=recordid)
        if not record:
            return JsonResponse({"success": False, "error": "Record non trovato"}, status=404)

        record.values['stato'] = 'Merce Ricevuta'
        record.save()

        return JsonResponse({"success": True, "message": "Stato aggiornato a 'Merce Ricevuta'", "record": record.values})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)