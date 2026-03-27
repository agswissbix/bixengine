import uuid
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from datetime import datetime, date, timedelta, time
from django.views.decorators.csrf import csrf_exempt
import json
from django.conf import settings
from django.core.files.storage import default_storage
from django.contrib.auth.decorators import login_required
from functools import wraps

from bixsettings.views.businesslogic.models.table_settings import TableSettings
from .bixmodels.user_record import *
from .bixmodels.user_table import *
from commonapp.models import SysCustomFunction, SysUser, SysUserSettings, SysTable
from django.db.models import F, OuterRef, Subquery
from commonapp.helper import *

import re
import os
import mimetypes
import environ
import logging
from pathlib import Path
import json
from django.http import JsonResponse
from commonapp.bixmodels.helper_db import *
from commonapp.views import custom_save_record_fields

env = environ.Env()
environ.Env.read_env()

logger = logging.getLogger(__name__)

def fieldsupdate(request):
    data = json.loads(request.body)
    params = data.get('params',{})
    tableid= params.get('tableid',None)
    recordid= params.get('recordid',None)
    old_record = UserRecord(tableid, recordid)
    for param, value in params.items():
        if param in ['tableid','recordid']:
            continue
        old_value=old_record.values.get(param,None)
        value=str(value).replace("'","''")
        if value == '$today$':
            value = datetime.date.today().strftime('%Y-%m-%d')
        if value.startswith('$dateadd:') and value.endswith('$'):
            try:
                # Rimuovi l'ultimo '$' e prendi la parte dopo ':'
                days_str = value.split(':')[1].replace('$', '')
                days = int(days_str)
                value = (datetime.date.today() + datetime.timedelta(days=days)).strftime('%Y-%m-%d')
            except (ValueError, IndexError):
                # Gestione errore se il numero non è valido o il formato è errato
                pass
        HelpderDB.sql_execute(f"UPDATE user_{tableid} SET {param}='{value}' WHERE recordid_='{recordid}' ")
    fields= params
    #TODO verificare cosa fa questa parte di codice
    dealline_record = UserRecord(tableid, recordid)
    changed_fields = Helper.get_changed_fields(dealline_record, old_record)
    if "linkedorder_" not in changed_fields:
        custom_save_record_fields(tableid, recordid, old_record)
    return JsonResponse({'status': 'ok', 'message': 'Fields updated successfully.'})

@csrf_exempt
@login_required_api
def check_csv_compatibility(request):
    try:
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
        
        tableid = request.POST.get('tableid')
        if not tableid:
            return JsonResponse({'error': 'Table ID required'}, status=400)
            
        if 'file' not in request.FILES:
            return JsonResponse({'error': 'No file uploaded'}, status=400)
            
        csv_file = request.FILES['file']
        
        # Save temp file
        import uuid
        import os
        from django.conf import settings
        
        file_token = str(uuid.uuid4())
        filename = f"{file_token}.csv"
        upload_dir = os.path.join(settings.STATIC_ROOT, 'csv_imports')
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, filename)
        
        with open(file_path, 'wb+') as destination:
            for chunk in csv_file.chunks():
                destination.write(chunk)
                
        # Read headers
        import csv
        encodings_to_try = ['utf-8-sig', 'latin-1', 'cp1252']
        headers = None
        
        for encoding in encodings_to_try:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    reader = csv.reader(f, delimiter=';') # Try semicolon first
                    try:
                        headers = next(reader, None)
                    except StopIteration:
                         break # Empty file?

                    # If only one column, maybe it's comma separated
                    if headers and len(headers) == 1 and ',' in headers[0]:
                        f.seek(0)
                        reader = csv.reader(f, delimiter=',')
                        headers = next(reader, None)
                    
                    # If we successfully read headers, break
                    if headers:
                        print(f"Successfully read CSV with encoding: {encoding}")
                        break
            except UnicodeDecodeError:
                continue
            except Exception as e:
                print(f"Error reading with encoding {encoding}: {e}")
                continue
        
        if not headers:
             return JsonResponse({'error': 'Could not read file. Invalid encoding or empty file.'}, status=400)
            
        # Get compatible fields
        # Using UserTable to get fields configuration
        
        all_fields = HelpderDB.sql_query(f"SELECT * FROM sys_field WHERE tableid='{tableid}'")
        
        compatible = []
        incompatible = []
        
        # Normalize for comparison
        normalized_fields = {}
        for field in all_fields:
            normalized_fields[field['fieldid'].lower()] = field['fieldid']
            normalized_fields[field['description'].lower()] = field['fieldid']
            
        for header in headers:
            clean_header = header.strip()
            norm_header = clean_header.lower()
            
            if norm_header in normalized_fields:
                compatible.append({
                    'header': clean_header,
                    'fieldid': normalized_fields[norm_header]
                })
            else:
                incompatible.append(clean_header)
                
        return JsonResponse({
            'success': True,
            'token': file_token,
            'compatible': compatible,
            'incompatible': incompatible,
            'total_rows': 0 # We could count them but let's keep it fast
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@login_required_api
def import_csv_data(request):
    try:
        print("DEBUG: import_csv_data STARTED")
        if request.method != 'POST':
            print("DEBUG: Method not allowed")
            return JsonResponse({'error': 'Method not allowed'}, status=405)
            
        data = json.loads(request.body)
        token = data.get('token')
        tableid = data.get('tableid')
        print(f"DEBUG: token={token}, tableid={tableid}")
        
        if not token or not tableid:
            print("DEBUG: Token or tableid missing")
            return JsonResponse({'error': 'Token and tableid required'}, status=400)
            
        import os
        from django.conf import settings
        import csv
        
        file_path = os.path.join(settings.STATIC_ROOT, 'csv_imports', f"{token}.csv")
        print(f"DEBUG: file_path={file_path}")
        
        if not os.path.exists(file_path):
            print("DEBUG: File not found")
            return JsonResponse({'error': 'File expired or not found'}, status=404)
            
        # Re-analyze headers/mapping (assuming simple auto-match for now as per "field compatibility" prompt)
        # Ideally frontend sends the confirmed mapping, but for now we re-derive or trust the same logic
        
        userid = Helper.get_userid(request)
        all_fields = HelpderDB.sql_query(f"SELECT * FROM sys_field WHERE tableid='{tableid}'")
        normalized_fields = {}
        for field in all_fields:
            normalized_fields[field['fieldid'].lower()] = field
            normalized_fields[field['description'].lower()] = field
            
        success_count = 0
        error_count = 0
        
        encodings_to_try = ['utf-8-sig', 'latin-1', 'cp1252']
        file_opened = False
        
        for encoding in encodings_to_try:
            try:
                print(f"DEBUG: Trying encoding {encoding}...")
                with open(file_path, 'r', encoding=encoding) as f:
                    # Check if readable
                    line = f.readline()
                    delimiter = ';' if ';' in line else ','
                    print(f"DEBUG: Detected delimiter: '{delimiter}'")
                    f.seek(0)
                    
                    reader = csv.DictReader(f, delimiter=delimiter)
                    
                    # If here, file is readable
                    file_opened = True
                    print(f"DEBUG: Importing with encoding: {encoding}")
                    
                    row_idx = 0
                    for row in reader:
                        row_idx += 1
                        print(f"DEBUG: processing row {row_idx}")
                        # Construct record data
                        record_values = {}
                        
                        for header, value in row.items():
                            if not header: continue
                            norm_header = header.strip().lower()
                            
                            if norm_header in normalized_fields:
                                field_def = normalized_fields[norm_header]
                                fieldid = field_def['fieldid']
                                
                                # Basic type conversion could go here
                                record_values[fieldid] = value
                                
                        if record_values:
                            try:
                                _save_record_data(
                                    tableid,
                                    None,
                                    record_values,
                                    None,
                                )
                                success_count += 1
                            except Exception as e:
                                print(f"DEBUG: Error saving row: {e}")
                                error_count += 1
                    
                    break # Success, exit loop
                    
            except UnicodeDecodeError:
                print(f"DEBUG: UnicodeDecodeError for {encoding}")
                continue
            except Exception as e:
                print(f"DEBUG: Error processing file with {encoding}: {str(e)}")
                if encoding == encodings_to_try[-1]:
                     return JsonResponse({'error': f"Error processing file: {str(e)}"}, status=500)
                continue
                
        if not file_opened:
             print("DEBUG: Could not read file with any encoding")
             return JsonResponse({'error': "Could not read file with standard encodings."}, status=400)
            
        # Clean up
        try:
            os.remove(file_path)
            print("DEBUG: File removed")
        except:
            print("DEBUG: Failed to remove file")
            pass
            
        print(f"DEBUG: Finished. Imported: {success_count}, Errors: {error_count}")
        return JsonResponse({
            'success': True,
            'imported': success_count,
            'errors': error_count
        })
        
    except Exception as e:
        print(f"DEBUG: Exception in import_csv_data: {e}")
        return JsonResponse({'error': str(e)}, status=500)