import json
import datetime
from django.contrib.auth.decorators import login_required
import time
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.db import connection, connections
from django.http import JsonResponse
from django.contrib.auth.models import Group, Permission, User, Group
from django_user_agents.utils import get_user_agent
from django import template
from bs4 import BeautifulSoup
from django.db.models import OuterRef, Subquery
from functools import wraps
import pandas as pd
from commonapp.bixmodels.user_record import *
from commonapp.bixmodels.helper_db import HelpderDB
from typing import List, Any
import re
from typing import Any, List, Tuple, Dict
import time
import functools # <-- Aggiungi se non c'è
from datetime import date, timedelta
from dateutil import parser
from dateutil.relativedelta import relativedelta



def login_required_api(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        print("sessionid:", request.COOKIES.get("sessionid"))
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        return view_func(request, *args, **kwargs)
    return wrapped




## PARSER PER CONVERTIRE LE CONDIZIONI DEGLI ALERT IN CONDIZIONI UTILIZZABILI A CODICE
_OPERATOR_FUNCS = {
    '=':  lambda a, b: a == b,
    '!=': lambda a, b: a != b,
    '<':  lambda a, b: a <  b,
    '<=': lambda a, b: a <= b,
    '>':  lambda a, b: a >  b,
    '>=': lambda a, b: a >= b,
}

# Match singolo confronto: <field> <op> <value>
# value: 'stringa' | -12.34 | 56 | true | false
_SINGLE_CMP_RE = re.compile(
    r"""\s*
        (?P<field>[A-Za-z_][A-Za-z0-9_]*)
        \s*(?P<op>=|!=|<=|>=|<|>)
        \s*(?P<value>
              '(?:[^']|'')*'      # stringa tra apici, '' = escape di '
            | -?\d+\.\d+          # float
            | -?\d+               # int
            | (?i:true|false)     # booleani
        )
        \s*
    """,
    re.VERBOSE
)

_AND_RE = re.compile(r'\s+(?i:AND)\s+')

def _coerce_value(raw: str) -> Any:
    # Stringa tra apici singoli (supporta '' come apice letterale)
    if raw.startswith("'") and raw.endswith("'"):
        return raw[1:-1].replace("''", "'")
    # Integer
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    # Float
    if re.fullmatch(r"-?\d+\.\d+", raw):
        return float(raw)
    # Booleani
    low = raw.lower()
    if low in ('true', 'false'):
        return low == 'true'
    # Fallback: stringa così com'è
    return raw


# =================================================================
#  DECORATOR PER LA MISURAZIONE DEL TEMPO DI ESECUZIONE
# =================================================================
def timing_decorator(func):
    """
    Un decorator che stampa su console il tempo di esecuzione 
    della funzione a cui è applicato.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        print(f"⏱️  Esecuzione di '{func.__name__}'...")
        start_time = time.perf_counter()
        
        # Esegue la funzione originale
        result = func(*args, **kwargs)
        
        end_time = time.perf_counter()
        total_time = end_time - start_time
        
        print(f"✅  '{func.__name__}' eseguita in {total_time:.4f} secondi.")
        return result
    return wrapper


# =================================================================
#  CONTEXT MANAGER PER LA MISURAZIONE DI BLOCCHI DI CODICE
# =================================================================
class CodeTimer:
    """
    Un context manager per misurare il tempo di esecuzione di un blocco di codice.

    Uso:
        with CodeTimer("Nome del blocco"):
            # Il tuo codice da misurare
            time.sleep(1)
    """
    def __init__(self, name="Blocco di codice"):
        self.name = name
        self.start_time = None

    def __enter__(self):
        """Viene eseguito all'inizio del blocco 'with'."""
        self.start_time = time.perf_counter()
        print(f"⏱️  [INIZIO] Esecuzione di '{self.name}'...")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Viene eseguito alla fine del blocco 'with'."""
        elapsed_time = time.perf_counter() - self.start_time
        print(f"✅  [FINE] '{self.name}' eseguito in {elapsed_time:.4f} secondi.")






class Helper:

    @classmethod     
    def isempty(cls, var):
        if not var or var == 'None' or var == 'null':
            return True
        else:
            return False
        
    @classmethod
    def set_log(userid,action,tableid='',recordid='',informations=''):
        
        try:
            # Ottenere la data nel formato YYYY-MM-DD
            date_now = datetime.now().strftime("%Y-%m-%d")

            # Ottenere l'ora nel formato HH:MM
            time_now = datetime.now().strftime("%H:%M")

            record_log=UserRecord('log')
            record_log.values['date']=date_now
            record_log.values['date']=time_now
            return True

        except Exception as e:
            return False
    
    @classmethod
    def get_userid(cls,request):
        django_userid=request.user.id
        userid = 0
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM sys_user WHERE bixid = %s", [django_userid])
            row = cursor.fetchone()
            if row:
                userid = row[0]
        return userid
    
    @classmethod
    def get_username(cls,request):
        django_userid=request.user.id
        userid = 0
        with connection.cursor() as cursor:
            cursor.execute("SELECT username FROM sys_user WHERE bixid = %s", [django_userid])
            row = cursor.fetchone()
            if row:
                userid = row[0]
        return userid
    

    #TODO activeserver e cliente_id sono la stessa cosa
    @classmethod
    def get_activeserver(cls,request):
        activeServer = HelpderDB.sql_query_row("SELECT value FROM sys_settings WHERE setting='cliente_id'")
        return activeServer
    
    @classmethod
    def get_cliente_id(cls):
        cliente_id = HelpderDB.sql_query_value("SELECT value FROM sys_settings WHERE setting='cliente_id'", 'value')
        return cliente_id
    
    @classmethod
    def get_chart_colors(cls):
        colors = [
        "#4E79A7", "#F28E2B", "#E15759", "#59A14F", 
        "#B07AA1", "#76B7B2", "#9C755F", "#D67073", 
        "#8CD17D", "#3B5998", "#FFB96A", "#A8DADC", 
        "#DAA520", "#43A047", "#FF9DA7", "#EDC948", 
        "#000000", "#808080", "#5F5F5F", "#BAB0AC"
        ]
        return colors
    
    @classmethod
    def check_mydata_completeness(cls, recordidgolfclub, selected_years, labels=['Soci'], localized_labels=[]):
        # 1. Prepara i mappaggi tra campi tecnici e label visualizzate
        # Creiamo una lista di oggetti per mantenere l'associazione corretta
        field_mappings = []
        for i, label in enumerate(labels):
            # Normalizzazione per il DB
            clean_name = label.strip().replace('-', '').lower()
            field_name = f"prog_{clean_name}"
            
            # Localizzazione per l'output (fallback alla label originale se manca la traduzione)
            display_name = localized_labels[i] if i < len(localized_labels) else label
            
            field_mappings.append({
                "tech_field": field_name,
                "display_label": display_name,
                "original_label": label
            })

        # 2. Recupera tutti i progressi del golf club
        sql = """
            SELECT *
            FROM user_golfdataprogress
            WHERE recordidgolfclub_ = %s AND deleted_ = 'N'
        """
        # Nota: Assumi che HelpderDB sia la tua utility interna
        all_rows = HelpderDB.sql_query(sql, [recordidgolfclub])

        # Trasformo i record in un dizionario indicizzato per anno
        rows_by_year = {}
        for row in all_rows:
            raw_year = row["anno"]
            if isinstance(raw_year, float):
                year = str(int(raw_year)) if raw_year.is_integer() else str(raw_year)
            else:
                year = str(raw_year)
            rows_by_year[year] = row

        # Normalizzo gli anni selezionati a string
        selected_years_str = [str(y) for y in selected_years]

        missing_years = []
        wrong_values = {}

        # 3. Controllo anno per anno
        for year in selected_years_str:

            # --- A. Verifico che il record esista ---
            if year not in rows_by_year:
                missing_years.append(year)
                continue

            row = rows_by_year[year]

            # --- B. Verifico ogni campo usando il mapping ---
            for mapping in field_mappings:
                tech_field = mapping["tech_field"]
                display_label = mapping["display_label"]
                original_label = mapping["original_label"]
                
                value = row.get(tech_field)

                # Controllo validità (deve essere 100)
                if value is None or float(value) != 100:
                    if year not in wrong_values:
                        wrong_values[year] = {}
                    
                    # Usiamo la label localizzata come chiave per l'errore
                    wrong_values[year][original_label] = value

        # 4. Risultato finale
        complete = len(missing_years) == 0 and len(wrong_values) == 0

        return {
            "complete": complete,
            "missing_years": missing_years,
            "wrong_values": wrong_values
        }
    
    @classmethod
    def get_labels_fields_chart(cls, chart_config):
        tableid = chart_config.get("from_table")
        field_ids = []

        # --- recupero alias nei datasets ---
        for ds in chart_config.get("datasets", []):
            if "alias" in ds:
                field_ids.append(ds["alias"])

        # --- recupero alias nei datasets2 (se presenti) ---
        for ds in chart_config.get("datasets2", []):
            if "alias" in ds:
                field_ids.append(ds["alias"])

        # --- recupero alias nel group_by_field ---
        gb = chart_config.get("group_by_field")
        if gb and "alias" in gb:
            field_ids.append(gb["alias"])

        labels = []

        # --- esecuzione query sys_field per ciascun fieldid ---
        sql = """
            SELECT label 
            FROM sys_field
            WHERE tableid = %s AND fieldid = %s
        """

        exclude_labels = ['golfclub', 'Dati']

        for fieldid in field_ids:
            label = HelpderDB.sql_query_value(sql, 'label', [tableid, fieldid])
            if not label or label in labels or label in exclude_labels:
                continue
            labels.append(label)

        return labels
    
    @classmethod
    def pivot_to_nested_array(cls,
        pivot_df: pd.DataFrame,
        include_key_in_leaf: bool = True
    ) -> List[Any]:
        """
        Converte un pivot table (anche con MultiIndex) in una lista di liste
        annidata, raggruppata in base a *tutti* i livelli di indice.

        Ogni elemento del risultato segue questo schema ricorsivo:
            [chiave_livello_0,
                [chiave_livello_1,
                    [chiave_livello_2,
                        ...
                            [chiave_ultimo_livello, valori_m1, valori_m2, ...]
                        ...
                    ]
                ]
            ]

        Parametri
        ---------
        pivot_df : pandas.DataFrame
            Il pivot table da convertire. Può avere sia indice semplice sia MultiIndex.
        include_key_in_leaf : bool, default=True
            Se True, l’ultima lista (foglia) conterrà anche la chiave dell’ultimo
            livello di indice. Se False, in fondo troverai solo i valori.

        Ritorna
        -------
        List[Any]
            La struttura annidata descritta sopra.
        """

        # -----  CASO 1: indice a un solo livello  --------------------------------
        if not isinstance(pivot_df.index, pd.MultiIndex):
            leaf_rows = []
            for key, row in pivot_df.iterrows():
                values = row.values.tolist()
                leaf_rows.append([key] + values if include_key_in_leaf else values)
            return leaf_rows

        # -----  CASO 2: indice a più livelli  ------------------------------------
        level_names = pivot_df.index.names          # p.es. ['cliente', 'stabile', 'info']

        def _recurse(df: pd.DataFrame, level: int) -> List[Any]:
            current_level = level_names[level]
            groups = []
            # Important: groupby(level=level, sort=False) mantiene l’ordine originale
            for key, sub_df in df.groupby(level=level, sort=False):
                if level == len(level_names) - 1:   # siamo alla foglia
                    vals = sub_df.values.flatten().tolist()
                    leaf = ([key] + vals) if include_key_in_leaf else vals
                    groups.append(leaf)
                else:
                    groups.append([key, _recurse(sub_df, level + 1)])
            return groups

        return _recurse(pivot_df, 0)
    

    @classmethod
    def safe_float(cls,value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
        

    @classmethod
    def parse_sql_like_and(cls,expr: str) -> List[Tuple[str, str, Any]]:
        """
        Parsea una condizione del tipo:
        "status='Active' AND userid=1 AND qt>=10"
        Restituisce: [ ('status','=', 'Active'), ('userid','=',1), ('qt','>=',10) ]
        """
        parts = _AND_RE.split(expr.strip())
        result: List[Tuple[str, str, Any]] = []

        # Se 'AND' appare nel mezzo di una stringa tra apici, lo split non lo rompe:
        # perché lo split richiede spazi intorno ( \s+AND\s+ ).
        # Se hai casi limite con AND attaccato, puoi rafforzare il formato input.
        pos = 0
        for part in parts:
            m = _SINGLE_CMP_RE.fullmatch(part)
            if not m:
                raise ValueError(f"Condizione non valida vicino a: {part!r}")
            field = m.group('field')
            op = m.group('op')
            val = _coerce_value(m.group('value'))
            result.append((field, op, val))
        return result

    @classmethod
    def to_iso_datetime(cls, date_value, time_value):
        if not date_value:
            return None

        # --- Parsing della data ---
        if isinstance(date_value, str):
            try:
                date_obj = datetime.datetime.strptime(date_value, '%d/%m/%Y').date()
            except ValueError:
                date_obj = datetime.datetime.strptime(date_value, '%Y-%m-%d').date()
        else:
            date_obj = date_value  # già datetime.date

        # --- Parsing dell'orario ---
        time_obj = datetime.time(0, 0)
        if isinstance(time_value, str):
            time_str = time_value.strip()
            if time_str:
                # Normalizziamo eventuale punto in due punti
                time_str = time_str.replace('.', ':')
                # Proviamo diversi formati possibili
                for fmt in ('%H:%M:%S', '%H:%M'):
                    try:
                        time_obj = datetime.datetime.strptime(time_str, fmt).time()
                        break
                    except ValueError:
                        continue
        elif isinstance(time_value, datetime.time):
            time_obj = time_value

        # --- Combiniamo data e ora ---
        dt = datetime.datetime.combine(date_obj, time_obj)
        return dt.isoformat()

    @classmethod
    def evaluate_and_conditions(cls,fieldmap: Dict[str, Any], conds: List[Tuple[str,str,Any]]) -> bool:
        """
        fieldmap: mappa fieldid -> valore del record (già estratto)
        conds: lista di (fieldid, op, value) da confrontare tutti in AND
        """
        for field, op, rhs in conds:
            lhs = fieldmap.get(field, None)

            # Se il campo non esiste o è None, la condizione fallisce
            if lhs is None:
                return False

            # Prova a coerzionare i tipi in modo ragionevole:
            # - Se RHS è numerico, prova a trasformare LHS in numero.
            # - Altrimenti confronta come stringhe/booleani così come sono.
            try:
                if isinstance(rhs, (int, float)):
                    if isinstance(lhs, str):
                        if re.fullmatch(r"-?\d+\.\d+", lhs):
                            lhs = float(lhs)
                        elif re.fullmatch(r"-?\d+", lhs):
                            lhs = int(lhs)
                        else:
                            return False  # rhs numerico ma lhs non numerico
                elif isinstance(rhs, bool):
                    if isinstance(lhs, str):
                        if lhs.lower() in ('true', 'false'):
                            lhs = (lhs.lower() == 'true')
                        else:
                            return False

                # Esegui il confronto
                cmp_func = _OPERATOR_FUNCS[op]
                if not cmp_func(lhs, rhs):
                    return False

            except Exception:
                # Tipo non confrontabile o errore: condizione fallisce
                return False

        return True

    
    def compute_dealline_fields(fields, UserRecord):
        """
        Calcola i campi price, expectedcost, expectedmargin per una riga dealline.
        Ritorna SOLO i campi calcolati e quelli che vengono auto-derivati da recordidproduct.
        """
        updated = {}

        quantity = fields.get('quantity', 0)
        unitprice = fields.get('unitprice', 0)
        unitexpectedcost = fields.get('unitexpectedcost', 0)

        # Se arriva un product id, recupera i valori
        recordidproduct = fields.get('recordidproduct_', None)
        if recordidproduct:
            product = UserRecord('product', recordidproduct)
            if product and product.values:
                if unitprice in ['', None]:
                    updated['unitprice'] = product.values.get('price', 0)
                    unitprice = updated['unitprice']

                if unitexpectedcost in ['', None]:
                    updated['unitexpectedcost'] = product.values.get('cost', 0)
                    unitexpectedcost = updated['unitexpectedcost']

        # Normalize values
        try: quantity = float(quantity)
        except: quantity = 0
        try: unitprice = float(unitprice)
        except: unitprice = 0
        try: unitexpectedcost = float(unitexpectedcost)
        except: unitexpectedcost = 0

        updated['price'] = round(quantity * unitprice, 2)
        updated['expectedcost'] = round(quantity * unitexpectedcost, 2)
        updated['expectedmargin'] = round(updated['price'] - updated['expectedcost'], 2)

        return updated
    
    def get_changed_fields(new_record, old_record):
        """
        Confronta i valori tra un nuovo e un vecchio record, 
        rilevando solo le modifiche dei valori per le chiavi comuni.
        
        Args:
            new_record (UserRecord): Il record più recente.
            old_record (UserRecord): Il record precedente.
            
        Returns:
            dict: Un dizionario con i campi modificati, 
                nel formato {'chiave': {'old': vecchio_valore, 'new': nuovo_valore}}.
        """
        changed_fields = {}
        
        new_values = new_record.values
        old_values = old_record.values
        
        common_keys = new_values.keys() & old_values.keys()
        
        for key in common_keys:
            new_value = new_values[key]
            old_value = old_values[key]
            
            # Confrontiamo i valori.
            if new_value != old_value:
                changed_fields[key] = {
                    'old': old_value,
                    'new': new_value
                }

        return changed_fields


    # ==========================
    #  DEADLINE METHODS
    # ==========================

    @classmethod
    def save_record_deadline(cls, tableid, current_recordid, recordid, userid, deadline_updates):
        from bixsettings.views.businesslogic.models.table_settings import TableSettings
        from commonapp.models import SysTable
        from commonapp.bixmodels.user_record import UserRecord

        try:
            # Recupero eventuale deadline esistente
            deadline_recordid = None
            if recordid:
                sql = """
                    SELECT recordid_
                    FROM user_deadline
                    WHERE tableid = %s
                    AND recordidtable = %s
                    LIMIT 1
                """
                deadline_recordid = HelpderDB.sql_query_value(
                    sql,
                    'recordid_',
                    (tableid, current_recordid)
                )

            deadline_record = UserRecord('deadline', deadline_recordid, userid)

            # Recupero descrizione tabella in modo sicuro
            label_table = "Record"
            try:
                table_obj = SysTable.objects.filter(id=tableid).first()
                if table_obj:
                    label_table = table_obj.description
            except Exception:
                pass

            deadline_record.values['tableid'] = tableid
            deadline_record.values['recordidtable'] = current_recordid
            deadline_record.values['description'] = label_table
            deadline_record.values['notice_days'] = 2

            # Recupero actions in modo sicuro
            deadline_record.values['actions'] = ""
            try:
                settings_obj = TableSettings(tableid).get_specific_settings('deadline_actions')
                if settings_obj and 'deadline_actions' in settings_obj:
                    deadline_record.values['actions'] = settings_obj['deadline_actions'].get('value', "")
            except Exception as e:
                print(f"Errore recupero actions deadline: {e}")

            for key, value in deadline_updates.items():
                deadline_record.values[key] = value

            start_date = deadline_record.values.get('date_start')
            frequency_label = deadline_record.values.get('frequency')
            frequency_months = deadline_record.values.get('frequency_months')

            # 🔹 Calcolo data scadenza
            if start_date:
                try:
                    if isinstance(start_date, str):
                        # Tenta parsing sicuro
                        try:
                            start_date_obj = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
                        except ValueError:
                            # Se fallisce formato standard, prova parser dateutil o fallback
                            start_date_obj = parser.parse(start_date).date()
                    elif isinstance(start_date, (datetime.date, datetime.datetime)):
                         start_date_obj = start_date
                    else:
                        start_date_obj = None

                    if start_date_obj:
                        deadline_date = None

                        # 🔹 Caso 1: frequenza testuale
                        if frequency_label and isinstance(frequency_label, str):
                            frequency_map = {
                                "mensile": relativedelta(months=1),
                                "trimestrale": relativedelta(months=3),
                                "semestrale": relativedelta(months=6),
                                "annuale": relativedelta(years=1),
                            }
                            
                            delta = frequency_map.get(frequency_label.lower())
                            if delta:
                                deadline_date = start_date_obj + delta

                        # 🔹 Caso 2: mesi numerici
                        elif frequency_months:
                            try:
                                value = float(frequency_months)

                                months_val = int(value)  # parte intera
                                fractional_part = value - months_val  # parte decimale

                                days_val = round(fractional_part * 30)  # mese medio = 30 giorni

                                deadline_date = start_date_obj + relativedelta(
                                    months=months_val,
                                    days=days_val
                                )
                            except (ValueError, TypeError):
                                pass

                        if deadline_date:
                            deadline_record.values['date_deadline'] = deadline_date.strftime("%Y-%m-%d")
                except Exception as e:
                    print(f"Errore calcolo data scadenza: {e}")

            # Calcolo STATUS
            deadline_date_str = deadline_record.values.get('date_deadline')
            if deadline_date_str and isinstance(deadline_date_str, str):
                try:
                    deadline_date = datetime.datetime.strptime(deadline_date_str, "%Y-%m-%d").date()
                    today = date.today()
                    days_remaining = (deadline_date - today).days

                    notice_days_val = deadline_record.values.get('notice_days')
                    try:
                        notice_days = int(notice_days_val)
                    except (ValueError, TypeError):
                        notice_days = 0

                    if days_remaining < 0:
                        status = "Scaduto"
                    elif days_remaining <= notice_days:
                        status = "In scadenza"
                    else:
                        status = "Attivo"

                    deadline_record.values['status'] = status
                    deadline_record.save()
                    
                except Exception as e:
                    print(f"Errore calcolo status deadline: {e}")

        except Exception as e:
            print(f"Errore generale gestione deadline in save_record_deadline: {e}")

    @classmethod
    def check_all_deadlines(cls):
        from commonapp.bixmodels.user_table import UserTable
        from commonapp.bixmodels.user_record import UserRecord

        actions_to_trigger = []
        condition_list = []
        records = UserTable('deadline').get_records(conditions_list=condition_list)
        today = date.today()

        for record in records:
            recordid = record['recordid_']
            rec = UserRecord('deadline', recordid)

            deadline_date = rec.values.get('date_deadline')
            if not deadline_date:
                continue  # Salta record senza data

            days_remaining = (deadline_date - today).days

            # Notice days sicuro
            try:
                notice_days = int(rec.values.get('notice_days') or 0)
            except (ValueError, TypeError):
                notice_days = 0

            # Determinazione status
            if days_remaining < 0:
                new_status = "Scaduto"
                if rec.values.get('frequency') or rec.values.get('frequency_months'):
                    # TODO: implementare logica corretta per la data di scadenza
                    new_status = "Attivo"
                    try:
                        months = float(rec.values.get('frequency_months') or 0)
                    except ValueError:
                        months = 0
                    rec.values['date_deadline'] = rec.values['date_deadline'] + timedelta(days=months * 30)
            elif days_remaining <= notice_days:
                new_status = "In scadenza"
            else:
                new_status = "Attivo"

            old_status = rec.values.get('status')

            # Aggiorna status se cambiato
            if new_status != old_status:
                rec.values['status'] = new_status
                rec.values['notification_sent'] = 'No'
                rec.save()

            # Invio notifiche solo se necessario
            if new_status != "Attivo" and rec.values.get('notification_sent') != 'Si':

                actions_raw = rec.values.get('actions', '')
                if actions_raw is None:
                    actions_raw = ''
                actions = [a.strip() for a in actions_raw.split(',') if a.strip()]

                for action_str in actions:
                    match_obj = re.match(r"(\w+)(?:\((.*)\))?", action_str)
                    if not match_obj:
                        continue

                    action_name = match_obj.group(1)
                    action_params = match_obj.group(2)
                    
                    actions_to_trigger.append({
                        'action_name': action_name,
                        'action_params': action_params,
                        'recordid': recordid,
                        'deadline_date': deadline_date
                    })

                rec.values['notification_sent'] = 'Si'
                rec.save()

        return actions_to_trigger