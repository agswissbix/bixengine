import os
from re import match
from bixsettings.views.businesslogic.models.table_settings import TableSettings
from bixsettings.views.businesslogic.models.field_settings import FieldSettings
from commonapp.models import *
from commonapp.bixmodels.helper_db import *
from commonapp.bixmodels.helper_sys import *
from commonapp.helper import *
from datetime import date
from django.db import transaction

bixdata_server = os.environ.get('BIXDATA_SERVER')

def cast_value(value, fieldtype):
    if value in ('', 'null', None, []):
        return None

    if isinstance(value, list):
        if fieldtype == "multiselect":
            return ','.join(map(str, value)) if value else None
        return ','.join(map(str, value))
    
    FIELDTYPES = {
        "Parola": "VARCHAR(255)",
        "Seriale": "VARCHAR(255)",
        "Data": "DATE",
        "Ora": "TIME",
        "Numero": "FLOAT",
        "lookup": "VARCHAR(255)",
        "multiselect": "VARCHAR(255)",
        "Utente": "VARCHAR(255)",
        "Memo": "TEXT",
        "html": "LONGTEXT",
        "Markdown": "LONGTEXT",
        "SimpleMarkdown": "LONGTEXT",
        "linked": "VARCHAR(255)"
    }
    sql_column_type = FIELDTYPES.get(fieldtype, "VARCHAR(255)").lower()

    try:
        if sql_column_type in ('int', 'integer'):
            return int(value)

        if sql_column_type in ('decimal', 'float', 'double'):
            return float(str(value).replace(',', '.'))

        if sql_column_type == 'boolean':
            return 1 if str(value).lower() in ('1','true','yes','on') else 0

        if sql_column_type == 'date':
            from dateutil import parser
            return parser.parse(str(value)).strftime('%Y-%m-%d')

        if sql_column_type == 'time':
            from dateutil import parser
            return parser.parse(str(value)).strftime('%H:%M')

        if sql_column_type == 'datetime':
            from dateutil import parser
            return parser.parse(str(value)).strftime('%Y-%m-%d %H:%M')

        return str(value).strip()

    except Exception:
        return None

class UserRecord:

    context=""
    def __init__(self, tableid, recordid=None, userid=1, master_tableid="", master_recordid="", _prefetched_data=None):
        self.tableid = tableid
        self.recordid = recordid
        self.userid = userid
        self.master_tableid = master_tableid
        self.master_recordid = master_recordid
        self.values = {}
        self.fields = {} # Conterrà le definizioni arricchite con 'value' e 'convertedvalue'
        
        if _prefetched_data:
            # --- Caso OTTIMIZZATO ---
            self.values = _prefetched_data['values']
            self.recordid = self.values.get('recordid_')
            field_definitions = _prefetched_data['fields_definitions']
            # NUOVO: estrai le mappe di dati pre-caricati
            eager_loaded_data = _prefetched_data.get('eager_loaded_data', {})

            for fieldid, definition_template in field_definitions.items():
                field_instance = definition_template.copy()
                if fieldid.startswith('_'):
                    # Se fieldid è '_esempio', la chiave per il valore diventa 'esempio_'
                    value_key = f"{fieldid[1:]}_"
                else:
                    # Altrimenti, usa il fieldid così com'è
                    value_key = fieldid

                # Recupera il valore usando la chiave determinata
                raw_value = self.values.get(value_key, "")

                field_instance['value'] = raw_value
                
                # MODIFICATO: Calcola il valore convertito usando i dati eager-loaded
                field_instance['convertedvalue'] = self._convert_display_value(
                    field_instance, eager_loaded_data
                )
                
                # NUOVO: Arricchiamo il field con dati utili al frontend
                if field_instance.get('fieldtypewebid') == 'Utente' and raw_value:
                    try:
                        field_instance['userid'] = int(raw_value)
                    except (ValueError, TypeError):
                        pass
                elif field_instance.get('keyfieldlink') and (table_link := field_instance.get('tablelink')):
                    record_link_id = self.values.get(f"recordid{table_link}_")
                    if record_link_id:
                        field_instance['linkedmaster_tableid'] = table_link
                        field_instance['linkedmaster_recordid'] = record_link_id

                self.fields[fieldid] = field_instance
        else:
            # --- Caso NON OTTIMIZZATO (fallback alla logica originale) ---
            self._fetch_field_definitions_from_db()
            if recordid:
                self._fetch_record_values_from_db()
                self._populate_fields_with_values() # Questo ora chiamerà il _convert_display_value aggiornato

    def _populate_fields_with_values(self):
        """ Popola il campo 'value' e 'convertedvalue' in self.fields usando self.values (logica di fallback) """
        if not self.values: return
        for fieldid, field_def in self.fields.items():
            value = self.values.get(fieldid, "")
            self.fields[fieldid]['value'] = value
            # Passa un dizionario vuoto perché in questo branch non abbiamo dati eager
            self.fields[fieldid]['convertedvalue'] = self._convert_display_value(field_def, {})

    def _convert_display_value(self, field_definition, eager_data):
        """
        MODIFICATO: Converte il valore grezzo in valore display.
        Prioritizza l'uso di dati pre-caricati (eager_data).
        Esegue query al DB solo come fallback se eager_data non è disponibile.
        """
        raw_value = field_definition.get('value')
        if raw_value is None: return ""

        field_type = field_definition.get('fieldtypewebid')
        table_link = field_definition.get('tablelink')
        
        try:
            # CASO: Utente
            if field_type == 'Utente' and raw_value:
                user_id = int(raw_value)
                # Prova a usare i dati pre-caricati
                if 'sys_user' in eager_data:
                    return eager_data['sys_user'].get(user_id, raw_value)
                # Fallback: query al DB
                sql = f"SELECT firstname, lastname FROM sys_user WHERE id='{user_id}'"
                user = HelpderDB.sql_query_row(sql)
                return f"{user['firstname']} {user['lastname']}" if user else raw_value

            # CASO: Campo collegato
            elif table_link and field_definition.get('keyfieldlink'):
                # L'ID del record collegato si trova in un'altra colonna di self.values
                linked_record_id = self.values.get(f"recordid{table_link}_")
                if not linked_record_id:
                    return raw_value # o ""
                
                # Prova a usare i dati pre-caricati
                if table_link in eager_data:
                    return eager_data[table_link].get(linked_record_id, linked_record_id)
                # Fallback: query al DB
                keyfield = field_definition['keyfieldlink']
                sql = f"SELECT {keyfield} FROM user_{table_link} WHERE recordid_='{linked_record_id}'"
                return HelpderDB.sql_query_value(sql, keyfield) or linked_record_id

            # CASO: Data
            elif field_type == 'Data' and raw_value:
                if isinstance(raw_value, datetime.date):
                    return raw_value.strftime('%d/%m/%Y')
                elif isinstance(raw_value, str):
                    try:
                        return datetime.datetime.strptime(raw_value.split(' ')[0], '%Y-%m-%d').strftime('%d/%m/%Y')
                    except (ValueError, TypeError):
                        return raw_value
                return raw_value

            # Altri casi non modificati
            else:
                return raw_value
                
        except Exception as e:
            print(f"Error converting value for field {field_definition.get('fieldid')}: {e}")
            return raw_value

    def _fetch_field_definitions_from_db(self):
        """ Recupera definizioni e settings dei campi dal DB (logica originale) """
        # Metti qui la logica originale di __init__ per recuperare da sys_field e sys_user_field_settings
        if self.tableid:
            fields_db = HelpderDB.sql_query(f"SELECT * FROM sys_field WHERE tableid='{self.tableid}'")
            temp_fields = {}
            for field in fields_db:
                # Recupera settings e default (potrebbe essere ottimizzato anche qui)
                sql_settings = f"SELECT * FROM sys_user_field_settings WHERE fieldid='{field['fieldid']}' AND tableid='{self.tableid}' AND userid='{str(self.userid)}'" # Usa self.userid
                field['settings'] = HelpderDB.sql_query(sql_settings)
                sql_default = f"SELECT value FROM sys_user_field_settings WHERE settingid='default' AND fieldid='{field['fieldid']}' AND tableid='{self.tableid}' AND userid='{str(self.userid)}'" # Usa self.userid
                field['defaultvalue'] = HelpderDB.sql_query_value(sql_default, 'value')
                temp_fields[field['fieldid']] = field
            self.fields = temp_fields # Inizializza self.fields con le definizioni base

    def _fetch_record_values_from_db(self):
        """ Recupera i valori del record specifico dal DB (logica originale) """
        if self.recordid:
            self.values = HelpderDB.sql_query_row(f"SELECT * FROM user_{self.tableid} WHERE recordid_='{self.recordid}'")
            if not self.values:
                print(f"Attenzione: Record {self.recordid} non trovato nella tabella user_{self.tableid}")
                self.values = {} # Evita errori successivi

    

    def _apply_master_record_defaults(self):
        """ Applica i valori dal master record se è un nuovo record """
        # Aggiunta del controllo per master_tableid e master_recordid
        if not self.recordid and self.master_tableid and self.master_recordid:
            master_fieldid = f"recordid{self.master_tableid}_" # Convenzione da UserTable
            if master_fieldid in self.fields:
                # Imposta il valore di default nel dizionario 'fields'
                self.fields[master_fieldid]['value'] = self.master_recordid
                self.fields[master_fieldid]['convertedvalue'] = self.master_recordid # Assumendo che sia l'ID
                # Potresti voler aggiornare anche self.values per coerenza, anche se è vuoto
                # self.values[master_fieldid] = self.master_recordid

   
    def save_record_for_event(self, event_body_content=""):
        event_exist = UserEvents.objects.filter(recordidtable=self.recordid, tableid=self.tableid, deleted_flag='N').first()
        event_record = UserRecord('events', event_exist.record_id if event_exist else None)

        tablesettings_obj = TableSettings(tableid=self.tableid, userid=self.userid)
        tablesettings = tablesettings_obj.get_settings()

        title_field = tablesettings.get('table_planner_title_field').get('value')
        date_from_field = tablesettings.get('table_planner_date_from_field').get('value')
        date_to_field = tablesettings.get('table_planner_date_to_field').get('value')
        time_from_field = tablesettings.get('table_planner_time_from_field').get('value')
        time_to_field = tablesettings.get('table_planner_time_to_field').get('value')

        from_date = self.values[date_from_field] if date_from_field else None
        if from_date:
            start_str = self.values.get(time_from_field)
            end_str = self.values.get(time_to_field)
            to_date = self.values.get(date_to_field) or from_date
            duration = self.values.get('duration')

            # Default se non presenti
            if not start_str and not end_str:
                start_str = "08:00"
                end_str = "17:00"

            start_date = from_date
            end_date = to_date

            start_time = None
            end_time = None

            if start_str:
                start_time = datetime.datetime.strptime(start_str, "%H:%M").time()
            if end_str:
                end_time = datetime.datetime.strptime(end_str, "%H:%M").time()

            start_datetime = datetime.datetime.combine(start_date, start_time or datetime.time(0, 0))
            end_datetime = datetime.datetime.combine(end_date, end_time or datetime.time(0, 0))

            duration_task = 1
            if duration and int(duration) > 0:
                duration_task = int(duration)

            if not end_str:
                end_datetime = start_datetime + datetime.timedelta(hours=duration_task)
            elif not start_str:
                start_datetime = end_datetime - datetime.timedelta(hours=duration_task)

            # Salvo nei valori dell’evento
            event_record.values['start_date'] = start_datetime
            event_record.values['end_date'] = end_datetime

        owner_email = SysUser.objects.filter(id=self.userid).values('email').first()

        event_record.values['recordidtable'] = self.recordid
        event_record.values['tableid'] = self.tableid
        event_record.values['subject'] = self.fields[title_field]['convertedvalue'] if title_field else 'No Title'
        event_record.values['userid'] = self.userid
        event_record.values['timezone'] = 'Europe/Zurich'
        event_record.values['body_content'] = event_body_content
        event_record.values['owner'] = owner_email.get('email')
        event_record.values['organizer_email'] = owner_email.get('email')

        event_record.save()

        return event_record

    def get_record_badge_fields(self):
        return_fields=[]
        sql = f"SELECT sys_field.* FROM sys_field join sys_user_field_order on sys_field.fieldid=sys_user_field_order.fieldid WHERE sys_field.tableid='{self.tableid}' AND sys_user_field_order.userid=1 AND sys_user_field_order.tableid='{self.tableid}' AND typePreference='campiFissi' AND sys_user_field_order.fieldorder IS NOT NULL ORDER BY sys_user_field_order.fieldorder asc"
        fields = HelpderDB.sql_query(sql)
        for field in fields:
            fieldid = field['fieldid']
            return_field={}
            return_field['fieldid']=fieldid
            return_field['value']=self.values[fieldid]
            return_fields.append(return_field)
        return return_fields
    
    @timing_decorator
    def get_record_results_fields(self):
        return_fields=[]
        sql = f"SELECT sys_field.* FROM sys_field join sys_user_field_order on sys_field.id=sys_user_field_order.fieldid WHERE sys_field.tableid='{self.tableid}' AND sys_user_field_order.userid=1 AND sys_user_field_order.tableid='{self.tableid}' AND typePreference='search_results_fields' AND sys_user_field_order.fieldorder IS NOT NULL ORDER BY sys_user_field_order.fieldorder asc"
        fields = HelpderDB.sql_query(sql)
        for field in fields:
            fieldid = field['fieldid']
            value=self.values[fieldid]
            if fieldid.startswith('_') and not Helper.isempty(field['keyfieldlink']):
                value=self.values[fieldid.lstrip('_') + '_']
                field['fieldtypeid']='standard'
                sql=f"SELECT {field['keyfieldlink']} FROM user_{field['tablelink']} WHERE recordid_='{value}' "
                newvalue=HelpderDB.sql_query_value(sql,field['keyfieldlink'])
                value=newvalue
            
            if field['fieldtypewebid']=='Utente':
                if value:
                    sql=f"SELECT firstname,lastname FROM sys_user WHERE id='{value}' "
                    user=HelpderDB.sql_query_row(sql)
                    newvalue=user['firstname']
                    value=newvalue

            if field['fieldtypeid']=='Data':
                if value:
                    if isinstance(value, str):
                        newvalue = datetime.datetime.strptime(value, '%Y-%m-%d').strftime('%d/%m/%Y')
                    else:
                        newvalue = value.strftime('%d/%m/%Y')
                    value=newvalue
            
            return_field={}
            return_field['type']='standard'
            return_field['fieldid']=fieldid
            return_field['value']=value
            return_fields.append(return_field) 
        return return_fields
        
    
    def get_fields_plain(self):
        fields_plain=self.fields
        return self.fields_plain
    
    def get_fields_detailed(self):
        fields_detailed=[]
        print(self.tableid)
        for fieldid, field in self.fields.items():
            print(fieldid)
            if(not Helper.isempty(field['tablelink']) and Helper.isempty(field['keyfieldlink'])):
                field['fieldtypeid']='Linked'
            if field['fieldtypeid']!='Linked':
                field_detailed={}
                field_detailed['tableid']="1"
                field_detailed['fieldid']="test1"+self.recordid
                field_detailed['fieldorder']="1"
                field_detailed['description']=field['description']  
                if self.recordid!="":
                    field_detailed['value']={"code": self.values[fieldid], "value": self.values[fieldid]}
                else:
                    field_detailed['value']={"code": "", "value": ""}
                
                field_detailed['fieldtype']="Parola"
                field_detailed['settings']={
                    "calcolato": "false",
                    "default": "",
                    "nascosto": "false",
                    "obbligatorio": "false"
                }
                fields_detailed.append(field_detailed)

        return fields_detailed
    
    def save_old(self):
        # NOT USED
        if self.recordid:
            counter=0
            sql=f"UPDATE user_{self.tableid} SET "
            for fieldid,value in self.values.items():
                if counter>0:
                    sql=sql+","
                if value!=None:  
                    if type(value)==str:
                        value = value.replace("'", "''")  
                    if isinstance(value, list):
                        value = ','.join(map(str, value))
                    sql=sql+f" `{fieldid}`='{value}' "
                else:
                    sql=sql+f" `{fieldid}`=null "
                counter+=1
            sql=sql+f" WHERE recordid_='{self.recordid}'"  
            HelpderDB.sql_execute(sql) 
        else:
            sqlmax=f"SELECT MAX(recordid_) as max_recordid FROM user_{self.tableid}"
            result=HelpderDB.sql_query_row(sqlmax)
            max_recordid=result['max_recordid'] if result else None
            if max_recordid is None:
                next_recordid = '00000000000000000000000000000001'
            else:
                next_recordid = str(int(max_recordid) + 1).zfill(32)
            
            sqlmax=f"SELECT MAX(id) as max_id FROM user_{self.tableid}"
            result=HelpderDB.sql_query_row(sqlmax)
            max_id=result['max_id'] if result else None
            if max_id is None:
                next_id = 1
            else:
                next_id = max_id+1

            sqlmax=f"SELECT MAX(linkedorder_) as max_order FROM user_{self.tableid}"
            result=HelpderDB.sql_query_row(sqlmax)
            max_order=result['max_order'] if result else None
            if max_order is None:
                next_order = 1
            else:
                next_order = max_order+1
            
            current_datetime=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sqlinsert=f"INSERT INTO user_{self.tableid} (recordid_,creatorid_,creation_,id,linkedorder_) VALUES ('{next_recordid}',{self.userid},'{current_datetime}',{next_id},{next_order}) "
            HelpderDB.sql_execute(sqlinsert)
            self.values['id']=next_id
            self.recordid=next_recordid
            self.values['linkedorder_'] = next_order
            self.save_old()

    def _generate_next_values(self):
        sql = f"""
            SELECT 
                MAX(recordid_) as max_recordid,
                MAX(id) as max_id,
                MAX(linkedorder_) as max_order
            FROM user_{self.tableid}
            FOR UPDATE
        """

        result = HelpderDB.sql_query_row(sql)

        max_recordid = result['max_recordid']
        max_id = result['max_id']
        max_order = result['max_order']

        next_recordid = (
            '00000000000000000000000000000001'
            if max_recordid is None
            else str(int(max_recordid) + 1).zfill(32)
        )

        next_id = 1 if max_id is None else max_id + 1
        next_order = 1 if max_order is None else max_order + 1

        return next_recordid, next_id, next_order

    def save(self):
        errors = self._normalize_and_validate_values()
        if errors:
            print(f"Validation errors during save for {self.tableid}: {errors}")

        try:
            with transaction.atomic():

                # =====================================================
                # UPDATE
                # =====================================================
                if self.recordid:

                    if not self.values:
                        return True

                    fields_sql = []
                    params_list = []

                    for fieldid, value in self.values.items():
                        if value is not None:
                            fields_sql.append(f"`{fieldid}`=%s")
                            params_list.append(value)
                        else:
                            fields_sql.append(f"`{fieldid}`=NULL")

                    sql = f"""
                        UPDATE user_{self.tableid}
                        SET {', '.join(fields_sql)}
                        WHERE recordid_=%s
                    """

                    params_list.append(self.recordid)

                    HelpderDB.sql_execute_safe(sql, params_list)

                # =====================================================
                # INSERT
                # =====================================================
                else:
                    next_recordid, next_id, next_order = self._generate_next_values()

                    sqlinsert = f"""
                        INSERT INTO user_{self.tableid}
                        (recordid_, creatorid_, creation_, id, linkedorder_)
                        VALUES (%s, %s, NOW(), %s, %s)
                    """

                    params_list = [
                        next_recordid,
                        self.userid,
                        next_id,
                        next_order
                    ]

                    HelpderDB.sql_execute_safe(sqlinsert, params_list)

                    # aggiorno oggetto
                    self.recordid = next_recordid
                    self.values['id'] = next_id
                    self.values['linkedorder_'] = next_order

                    self.save()

                return True

        except Exception as e:
            print(f"Errore salvataggio record {self.tableid} ({self.recordid}): {e}")
            return False
        
    def _normalize_and_validate_values(self):
        errors = {}

        # Recupera tutti i fieldtype in una query unica
        field_ids = tuple(self.values.keys())
        if not field_ids:
            return errors

        placeholders = ",".join(["%s"] * len(field_ids))

        sql = f"""
            SELECT fieldid, fieldtypewebid
            FROM sys_field
            WHERE tableid = %s
            AND fieldid IN ({placeholders})
        """

        results = HelpderDB.sql_query(sql, (self.tableid, *field_ids))
        field_types = {row["fieldid"]: row["fieldtypewebid"] for row in results}

        for fieldid, raw_value in list(self.values.items()):
            # skip protetti di sistema
            if fieldid in ('id', 'recordid_', 'creatorid_', 'creation_', 'lastupdaterid_', 'lastupdate_', 'totpages_', 'firstpagefilename_', 'recordstatus_', 'deleted_', 'linkedorder_'):
                continue

            fieldtype = field_types.get(fieldid)
            if not fieldtype:
                del self.values[fieldid]
                continue

            normalized = cast_value(raw_value, fieldtype)

            if normalized is None and raw_value not in ('', None, []):
                errors[fieldid] = f"Valore non valido: {raw_value}"
                del self.values[fieldid]
                continue

            # --- Validazione Utente ---
            if fieldtype == 'Utente' and normalized:
                exists = HelpderDB.sql_query_value(
                    "SELECT 1 FROM sys_user WHERE id = %s",
                    '1',
                    (normalized,)
                )
                if not exists:
                    normalized = None

            # --- Validazione Data ---
            if fieldtype == 'Data' and normalized:
                try:
                    from dateutil import parser
                    dt_obj = parser.parse(str(normalized))
                    normalized = dt_obj.strftime('%Y-%m-%d')
                except Exception:
                    normalized = None

            # Validazione FK
            if fieldid.endswith('_') and normalized:
                fk_table = fieldid.removeprefix("recordid").rsplit('_', 1)[0]
                sql = f"""
                    SELECT 1 FROM user_{fk_table}
                    WHERE recordid_ = %s
                    LIMIT 1
                """
                exists = HelpderDB.sql_query_value(sql, '1', (normalized,))
                if not exists:
                    normalized = None

            self.values[fieldid] = normalized

        return errors

    def get_linked_tables(self, typepreference='keylabel', step_id=None):
        """
        Restituisce le linked tables ordinate per fieldorder, includendo step_id e il numero di record correlati.
        """

        user_orders_qs = (
            SysUserOrder.objects.filter(
                tableid=self.tableid,
                typepreference=typepreference,
                userid=self.userid,
                fieldorder__isnull=False
            )
            .order_by('fieldorder')
        )

        if not user_orders_qs.exists():
            user_orders_qs = (
                SysUserOrder.objects.filter(
                    tableid=self.tableid,
                    typepreference=typepreference,
                    userid=1,
                    fieldorder__isnull=False
                )
                .order_by('fieldorder')
            )

        # Se passo uno step_id, filtro anche per quello
        if step_id:
            user_orders_qs = user_orders_qs.filter(step_id=step_id)

        # Recupera tutti gli ID di tabelle collegate (stringhe)
        linked_ids = [uo.fieldid for uo in user_orders_qs if uo.fieldid]

        # --- Recupera tutte le SysTable corrispondenti
        tables_map = {
            str(t.id): t for t in SysTable.objects.filter(id__in=linked_ids)
        }

        linked_tables = []

        for uo in user_orders_qs:
            linked_tableid = uo.fieldid  # è una stringa!
            linked_table = tables_map.get(linked_tableid)

            if not linked_table:
                continue  # evita errori se manca corrispondenza

            description = linked_table.description
            step = uo.step_id
            order = uo.fieldorder

            # Conta record collegati nella tabella dinamica user_<linked_tableid>
            counter = 0
            if linked_tableid:
                table_name = f"user_{linked_tableid}"
                tablesettings = TableSettings(linked_tableid, self.userid)
                can_view = tablesettings.get_specific_settings('view')['view']

                where_clauses = f"recordid{self.tableid}_ = '{self.recordid}' AND deleted_ = 'N' "

                if can_view['value'] == 'true' and 'where_list' in can_view:
                    where_clauses += (f" AND {can_view['where_list']}")
                sql = f"""
                    SELECT COUNT(recordid_) AS counter
                    FROM {table_name}
                    WHERE {where_clauses}
                """
                counter = HelpderDB.sql_query_value(sql, 'counter')

            linked_tables.append({
                "tableid": linked_tableid,
                "description": description,
                "step_id": step,
                "rowsCount": counter,
                "order": order
            })

        return linked_tables
    

    def get_badge_fields(self):
        badge_fields=[]
        if not self.recordid=='':
            sql=f"""
                SELECT f.*
                FROM sys_user_field_order AS fo LEFT JOIN sys_field AS f ON fo.tableid=f.tableid AND fo.fieldid=f.id

                WHERE fo.tableid='{self.tableid}' AND typepreference='badge_fields' AND fo.fieldorder IS NOT NULL AND fo.userid={self.userid} ORDER BY fieldorder
            """
            fields=HelpderDB.sql_query(sql)
            
            for field in fields:
                fieldid=field['fieldid']
                value=self.values[fieldid]
                badge_fields.append({"fieldid":fieldid,"value":value})
        return badge_fields
    
    def get_record_card_fields(self, typepreference='insert_fields', step_id=''):
        #TODO
        if self.tableid=='pitticket' and self.master_tableid=='telefonate' and self.recordid=='':
            record_telefonate=UserRecord('telefonate',self.master_recordid)
            self.values['assegnatoda']=self.userid
            self.values['recordidstabile_']=(record_telefonate.values.get('recordidstabile_','') or '')
            self.values['titolorichiesta']="ticket da telefonata - "+ (record_telefonate.values.get('chi','') or '')
            self.values['personariferimento'] = (record_telefonate.values.get('chi') or '') + " " + (record_telefonate.values.get('telefono') or '')
            self.values['richiesta']=(record_telefonate.values.get('motivo_chiamata','') or '')
        

        fieldsettings_obj = FieldSettings(tableid=self.tableid, userid=self.userid)
        all_field_settings = fieldsettings_obj.get_all_settings()
            
        step_condition = ""
        if step_id:
            step_condition = f"AND fo.step_id='{step_id}'"

        sql = f"""
            SELECT f.*
            FROM sys_user_field_order AS fo
            LEFT JOIN sys_field AS f ON fo.tableid=f.tableid AND fo.fieldid=f.id
            WHERE fo.tableid='{self.tableid}'
            AND fo.typepreference='{typepreference}'
            {step_condition}
            AND fo.fieldorder IS NOT NULL
            AND fo.userid={self.userid}
            ORDER BY fo.fieldorder
        """
        fields=HelpderDB.sql_query(sql)
        if not fields:
            sql = f"""
                SELECT f.*
                FROM sys_user_field_order AS fo
                LEFT JOIN sys_field AS f ON fo.tableid=f.tableid AND fo.fieldid=f.id
                WHERE fo.tableid='{self.tableid}'
                AND fo.typepreference='{typepreference}'
                {step_condition}
                AND fo.fieldorder IS NOT NULL
                AND fo.userid=1
                ORDER BY fo.fieldorder
            """
            fields = HelpderDB.sql_query(sql)

        insert_fields = []

        for field in fields:
            insert_field = {}

            fieldid = field['fieldid']
            if fieldid and fieldid.startswith("_"):
                fieldid = fieldid[1:] + "_"

            value = self.values.get(fieldid, '')

            insert_field['tableid']="1"
            insert_field['fieldid']=fieldid
            insert_field['fieldorder']="1"
            insert_field['description']=field['description']
            insert_field["label"]= field['label']
            insert_field['value']={"code": value, "value": value}
            insert_field["fieldtypewebid"]= ""
            insert_field["lookuptableid"]= field['lookuptableid']
            insert_field["tablelink"]= field['tablelink']
            insert_field['linked_mastertable']=field['tablelink']

            # Settings specifici del campo
            current_field_settings = all_field_settings.get(fieldid, {})

            # Defaults base
            insert_field['settings'] = {
                "calcolato": "false",
                "default": "",
                "nascosto": "false",
                "obbligatorio": "false"
            }

            # Applica override (solo value)
            for setting_name, setting_data in current_field_settings.items():
                has_permission = fieldsettings_obj.has_permission_for_record(setting_data, self.recordid)
                insert_field['settings'][setting_name] = 'true' if has_permission else 'false'
                if setting_name == 'default':
                    insert_field['settings'][setting_name] = setting_data.get('value', '')
            
            defaultvalue = insert_field['settings'].get('default', '')
            defaultcode = defaultvalue

            if fieldid in {
                'unitprice',
                'quantity',
                'unitexpectedcost',
                'recordidproduct_'
            }:
                insert_field['hasDependencies'] = True

            if self.tableid == 'assenze' and fieldid == 'giorni':
                insert_field['hasDependencies'] = True

            fieldtype=field['fieldtypewebid']
            if not Helper.isempty(field['keyfieldlink']):
                fieldtype='linkedmaster'
                if(field['tablelink']==self.master_tableid):
                    sql=f"SELECT recordid_,{field['keyfieldlink']} FROM user_{field['tablelink']} where recordid_='{self.master_recordid}' "
                    linked_recordid=HelpderDB.sql_query_value(sql,'recordid_')
                    linked_key=HelpderDB.sql_query_value(sql,field['keyfieldlink'])
                    defaultcode=linked_recordid
                    defaultvalue=linked_key
                
                if(value!=""):
                    sql=f"SELECT recordid_,{field['keyfieldlink']} FROM user_{field['tablelink']} where recordid_='{value}' "
                    linked_recordid=HelpderDB.sql_query_value(sql,'recordid_')
                    linked_key=HelpderDB.sql_query_value(sql,field['keyfieldlink'])
                    insert_field['value']={"code": linked_recordid, "value": linked_key}

            if field['fieldtypewebid'] == 'Data':
                fieldtype='Data'
                #defaultvalue=self.fields[fieldid]['defaultvalue']
                #if defaultvalue == '$today$':
                #TODO RENDERE DINAMICO CON I SETTINGS
                if self.tableid == 'telefonate' and fieldid == 'data': 
                    defaultcode=date.today().strftime('%Y-%m-%d')
                    defaultvalue=date.today().strftime('%Y-%m-%d')
                
                
                if defaultvalue == '$today$':
                    defaultcode=date.today().strftime('%Y-%m-%d')
                    defaultvalue=date.today().strftime('%Y-%m-%d')
                    
            #TODO RENDERE DINAMICO CON I SETTINGS
            if self.tableid == 'telefonate' and fieldid == 'ora_inizio':
                defaultcode = datetime.datetime.now().strftime("%H:%M")
                defaultvalue = datetime.datetime.now().strftime("%H:%M")

            if field['fieldtypewebid'] == 'Utente':
                fieldtype='Utente'
                lookupitemsusers=[]
                users=HelperSys.get_users()
                for user in users:
                    lookupitemsuser={}
                    lookupitemsuser['userid']=user['id']
                    lookupitemsuser['firstname']=user['firstname']
                    lookupitemsuser['lastname']=user['lastname']
                    lookupitemsuser['link']=''
                    lookupitemsuser['linkdefield']=''
                    lookupitemsuser['linkedvalue']=''
                    lookupitemsusers.append(lookupitemsuser)
                insert_field['lookupitemsuser']=lookupitemsusers
                defaultcode=self.userid
                defaultvalue=self.userid

            if field['fieldtypewebid'] == 'Memo':
                fieldtype='Memo'
            if field['fieldtypewebid'] == 'html':
                fieldtype='html'
            if field['fieldtypewebid'] == 'markdown':
                fieldtype='markdown'
            if field['fieldtypewebid'] == 'simple-markdown':
                fieldtype='simple-markdown'
            

            if field['fieldtypewebid'] == 'file':
                fieldtype='Attachment'

            if not Helper.isempty(field['lookuptableid']):
                fieldtype='Categoria' 
                items=HelpderDB.sql_query(f"SELECT * FROM sys_lookup_table_item WHERE lookuptableid='{field['lookuptableid']}'")
                insert_field['lookupitems']=items
                if field['fieldtypewebid'] == 'multiselect':
                    insert_field['fieldtypewebid']='multiselect'
                    fieldtype='multiselect'

            insert_field['fieldtype']=fieldtype
            

            if self.recordid=='' and value=='':
                insert_field['value']={"code": defaultcode, "value": defaultvalue}

            insert_fields.append(insert_field)


        return insert_fields


    def get_field(self,field_key):
        if field_key in self.fields:
            if (self.fields[field_key] is None  or self.fields[field_key]=='None'):
                return ''  
            else:
                return self.fields[field_key]      
        else:
            return ''


    def get_linkedrecords_dict(self,linkedtable):
        #TODO custom da gestire diversamente
        if linkedtable=='salesorderline':
            records=HelpderDB.sql_query(f"SELECT * FROM user_{linkedtable} WHERE recordid{self.tableid}_='{self.recordid}' AND deleted_='N' AND status='In Progress'")
        #TODO custom da gestire diversamente
        elif linkedtable=='dealline':
            records=HelpderDB.sql_query(f"SELECT * FROM user_{linkedtable} WHERE recordid{self.tableid}_='{self.recordid}' AND deleted_='N' ORDER BY name DESC")
        else:
            records=HelpderDB.sql_query(f"SELECT * FROM user_{linkedtable} WHERE recordid{self.tableid}_='{self.recordid}' AND deleted_='N'")
        return records 