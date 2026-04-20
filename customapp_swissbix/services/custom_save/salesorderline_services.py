from commonapp.bixmodels.user_record import UserRecord
from commonapp.helper import Helper

class SalesOrderLineService:
    @staticmethod
    def process_salesorderline(recordid: str) -> list:
        sol_record = UserRecord('salesorderline', recordid)
        product_id = sol_record.values.get('recordidproduct_')
        records_to_save = []
        
        if product_id:
            product = UserRecord('product', product_id, load_fields=False)
            if product and product.recordid:
                try:
                    unit_cost = float(product.values.get('cost') or 0)
                except (ValueError, TypeError):
                    unit_cost = 0.0
                    
                try:
                    quantity = float(sol_record.values.get('quantity') or 0)
                except (ValueError, TypeError):
                    quantity = 0.0
                    
                total_cost = unit_cost * quantity
                sol_record.values['cost'] = total_cost
                
                # Attiva calcolo del margine cercando i campi standard
                price_val = sol_record.values.get('price')
                if price_val is None:
                    price_val = sol_record.values.get('amount')
                if price_val is None:
                    price_val = sol_record.values.get('total')
                try:
                    price = float(price_val or 0)
                except (ValueError, TypeError):
                    price = 0.0
                    
                sol_record.values['margin'] = price - total_cost
                sol_record.save()
                
        # Controlla asset_transactions collegate
        asset_transactions = sol_record.get_linkedrecords_dict(linkedtable='asset_transactions')

                
        if not asset_transactions:
            company_id = sol_record.values.get('recordidcompany_')
            
            try:
                quantity = float(sol_record.values.get('quantity') or 0)
            except (ValueError, TypeError):
                quantity = 0.0
                
            new_asset_transaction = UserRecord('asset_transactions')
            new_asset_transaction.values['recordidcompany_'] = company_id
            new_asset_transaction.values['recordidproduct_'] = product_id
            new_asset_transaction.values['transaction'] = quantity
            new_asset_transaction.values['recordidsalesorderline_'] = sol_record.recordid
            new_asset_transaction.save()
            records_to_save.append(('asset_transactions', new_asset_transaction.recordid))
            
        return records_to_save
