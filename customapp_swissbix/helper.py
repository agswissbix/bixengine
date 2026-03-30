import re
import logging
from django.db.models import F
import base64
import os
from commonapp.bixmodels.user_record import UserRecord
from commonapp.models import SysLookupTableItem

logger = logging.getLogger(__name__)

class HelperSwissbix:
    
    # Cache per evitare query ripetitive sulla stessa tabella di lookup
    _first_option_cache = None

    @classmethod
    def to_base64(cls, path):
        """Converte immagine locale in Base64 per l'incorporamento nel PDF."""
        if path and os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    return f"data:image/png;base64,{base64.b64encode(f.read()).decode('utf-8')}"
            except Exception as e:
                print(f"Errore conversione Base64: {e}")
        return None

    @classmethod
    def get_first_contractual_option(cls):
        """Recupera e cachea il primo item code per contractual_planning."""
        if cls._first_option_cache is None:
            item = SysLookupTableItem.objects.filter(
                lookuptableid='type_contractual_planning'
            ).order_by(F('itemorder').asc(nulls_last=True), 'itemcode').first()
            cls._first_option_cache = item.itemcode if item else False
        return cls._first_option_cache

    @classmethod
    def check_solo_pianificabili(cls, action):
        """Verifica se il record è legato al primo tipo di contractual_planning."""
        recordid = action.get('recordid')
        if not recordid:
            return False

        deadline = UserRecord('deadline', recordid)
        deadline_values = deadline.values or {}

        # 1. Validazione legame con contractual_planning
        if deadline_values.get("tableid") != "contractual_planning" or not deadline_values.get("recordidtable"):
            return False

        # 2. Recupero record collegato
        linked = UserRecord('contractual_planning', deadline_values.get("recordidtable"))
        linked_type = (linked.values or {}).get("type")

        if not linked_type:
            return False
        
        # 3. Confronto con la prima opzione definita nel sistema
        first_option_code = cls.get_first_contractual_option()
        return linked_type == first_option_code

    # Mappa delle funzioni disponibili
    CONDITIONS_LIBRARY = {
        "solo_pianificabili": "check_solo_pianificabili",
    }

    @classmethod
    def evaluate_condition_string(cls, condition_str, action):
        """
        Risolve stringhe logiche tipo: "solo_pianificabili AND !altra_cond"
        Sostituisce eval() con una logica di rimpiazzo booleano sicura.
        """
        if not condition_str:
            return True

        # 1. Identifichiamo i token (nomi delle funzioni)
        # Escludiamo parole chiave logiche
        tokens = re.findall(r'\b(?!(?:AND|OR|NOT)\b)\w+\b', condition_str)
        
        # 2. Risolviamo i valori booleani
        mapping = {}
        for token in set(tokens): # set() per evitare doppie chiamate
            method_name = cls.CONDITIONS_LIBRARY.get(token)
            if method_name and hasattr(cls, method_name):
                method = getattr(cls, method_name)
                mapping[token] = "True" if method(action) else "False"
            else:
                logger.warning(f"Condizione '{token}' non trovata nella library.")
                mapping[token] = "False"

        # 3. Trasformazione stringa per valutazione sicura
        # Ordiniamo i token per lunghezza decrescente per evitare sostituzioni parziali
        prepared_expr = condition_str.replace('!', ' not ').replace('AND', ' and ').replace('OR', ' or ')
        
        for token in sorted(mapping.keys(), key=len, reverse=True):
            prepared_expr = re.sub(rf'\b{token}\b', mapping[token], prepared_expr)

        try:
            # eval() qui è più sicuro perché operiamo solo su stringhe "True", "False", "and", "or", "not"
            # create appositamente da noi, ma restiamo cauti.
            allowed_names = {"True": True, "False": False}
            return eval(prepared_expr, {"__builtins__": {}}, allowed_names)
        except Exception as e:
            logger.error(f"Errore nel parsing della condizione '{condition_str}': {e}")
            return False

    @classmethod
    def compute_dealline_fields(cls, fields, UserRecord):
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