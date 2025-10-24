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

    