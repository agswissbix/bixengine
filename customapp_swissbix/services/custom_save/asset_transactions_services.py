from commonapp.bixmodels.user_record import UserRecord
from commonapp.bixmodels.user_table import UserTable
from commonapp.helper import Helper
from .deal_services import DealService
from django.db import connection

class AssetTransactionsService:
    @staticmethod
    def process_asset_transactions(recordid: str) -> list:
        asset_transactions_record = UserRecord('asset_transactions', recordid)
        serviceandasset_recordid = asset_transactions_record.values.get('recordidserviceandasset_')
        
        if serviceandasset_recordid:
            return [('serviceandasset', serviceandasset_recordid)]
            
        company_id = asset_transactions_record.values.get('recordidcompany_')
        product_id = asset_transactions_record.values.get('recordidproduct_')
        
        if company_id and product_id:
            sql = f"""
                SELECT recordid_ FROM user_serviceandasset 
                WHERE recordidcompany_ = '{company_id}' 
                AND recordidproduct_ = '{product_id}' 
                AND deleted_ = 'N'
            """
            with connection.cursor() as cursor:
                cursor.execute(sql)
                row = cursor.fetchone()
                
            if row:
                serviceandasset_recordid = str(row[0])
            else:
                record_serviceandasset = UserRecord('serviceandasset')
                record_serviceandasset.values['recordidcompany_'] = company_id
                record_serviceandasset.values['recordidproduct_'] = product_id
                
                company = UserRecord('company', company_id, load_fields=False)
                product = UserRecord('product', product_id, load_fields=False)
                
                company_name = company.values.get('companyname') if company and company.recordid else ''
                product_name = product.values.get('name') if product and product.recordid else ''
                
                if company_name or product_name:
                    record_serviceandasset.values['reference'] = f"{company_name} - {product_name}"
                    
                if product and product.recordid:
                    record_serviceandasset.values['description'] = product.values.get('name')
                    record_serviceandasset.values['type'] = product.values.get('category')
                    record_serviceandasset.values['sector'] = product.values.get('category')
                    
                record_serviceandasset.save()
                serviceandasset_recordid = record_serviceandasset.recordid
                
            asset_transactions_record.values['recordidserviceandasset_'] = serviceandasset_recordid
            asset_transactions_record.save()
            return [('serviceandasset', serviceandasset_recordid)]
            
        return []
