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
from typing import List, Any

def login_required_api(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        print("sessionid:", request.COOKIES.get("sessionid"))
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
        return view_func(request, *args, **kwargs)
    return wrapped

class Helper:

    @classmethod     
    def isempty(cls, var):
        if var is None or var=='None' or var=='' or var=='null' or var==0:
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
    
