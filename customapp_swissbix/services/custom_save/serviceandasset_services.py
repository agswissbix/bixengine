from commonapp.bixmodels.user_record import UserRecord
from django.db import connection

class ServiceAndAssetService:
    @staticmethod
    def process_serviceandasset(recordid: str) -> list:
        record_serviceandasset = UserRecord('serviceandasset', recordid)
        company_id = record_serviceandasset.values.get('recordidcompany_')
        product_id = record_serviceandasset.values.get('recordidproduct_')

        if not company_id or not product_id:
            return []

        tot_qty = 0

        # Calculate from all completed deals for this company and product
        sql_qty = f"""
            SELECT SUM(CAST(dl.quantity AS DECIMAL(10,2))) 
            FROM user_dealline dl 
            JOIN user_deal d ON dl.recordiddeal_ = d.recordid_ 
            WHERE d.recordidcompany_ = '{company_id}'
              AND d.projectcompleted = 'Si' 
              AND dl.recordidproduct_ = '{product_id}' 
              AND dl.deleted_ = 'N' AND d.deleted_ = 'N'
        """
        with connection.cursor() as cursor:
            cursor.execute(sql_qty)
            row = cursor.fetchone()
            if row and row[0]:
                tot_qty += float(row[0])

        # Calculate from asset_transactions
        transactions = record_serviceandasset.get_linkedrecords_dict('asset_transactions')
        if transactions:
            for trans in transactions:
                try:
                    delta = float(trans.get('transaction') or 0)
                    tot_qty += delta
                except (ValueError, TypeError):
                    continue

        record_serviceandasset.values['quantity'] = tot_qty
        record_serviceandasset.save()

        # Update deallines linked to this serviceandasset
        sql_update_links = f"""
            UPDATE user_dealline dl
            JOIN user_deal d ON dl.recordiddeal_ = d.recordid_
            SET dl.recordidserviceandasset_ = '{record_serviceandasset.recordid}'
            WHERE d.recordidcompany_ = '{company_id}' 
              AND dl.recordidproduct_ = '{product_id}' 
              AND dl.deleted_ = 'N' AND d.deleted_ = 'N'
        """
        with connection.cursor() as cursor:
            cursor.execute(sql_update_links)

        return []

    @staticmethod
    def get_recalculated_quantity(group_field: str, group_value: str, product_id: str, exclude_deal_id: str) -> float:
        sql_qty = f"""
            SELECT SUM(CAST(dl.quantity AS DECIMAL(10,2))) 
            FROM user_dealline dl 
            JOIN user_deal d ON dl.recordiddeal_ = d.recordid_ 
            WHERE d.{group_field} = '{group_value}'
        """
        if group_field == 'recordidcompany_':
            sql_qty += " AND d.projectcompleted = 'Si' "
            
        sql_qty += f"""
              AND dl.recordidproduct_ = '{product_id}' 
              AND dl.deleted_ = 'N' AND d.deleted_ = 'N'
              AND d.recordid_ != '{exclude_deal_id}'
        """
        tot_qty = 0
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute(sql_qty)
            row = cursor.fetchone()
            if row and row[0]:
                tot_qty = float(row[0])
        return tot_qty

    @staticmethod
    def process_service_and_assets_from_deal(deal_record: UserRecord, dealline_records: list):
        included_subcategories = {
            'data_security', 'mobile_security', 'infrastructure', 
            'sophos', 'microsoft', 'firewall', 'service_and_asset'
        }
        
        from django.db import connection
        
        for dl_dict in dealline_records:
            product = UserRecord('product', dl_dict['recordidproduct_'], load_fields=False)
            if product and product.recordid and product.values.get('subcategory') in included_subcategories:
                
                tot_qty = ServiceAndAssetService.get_recalculated_quantity(
                    'recordidcompany_', deal_record.values.get('recordidcompany_'), 
                    dl_dict['recordidproduct_'], deal_record.recordid
                )
                        
                try:
                    curr_qty = float(dl_dict.get('quantity') or 0)
                    tot_qty += curr_qty
                except (ValueError, TypeError):
                    pass

                sql = f"""
                    SELECT recordid_ FROM user_serviceandasset 
                    WHERE recordidcompany_ = {deal_record.values.get('recordidcompany_')} 
                    AND recordidproduct_ = {dl_dict['recordidproduct_']} 
                    AND deleted_ = 'N'
                """
                with connection.cursor() as cursor:
                    cursor.execute(sql)
                    row = cursor.fetchone()
                    if row:
                        record_serviceandasset = UserRecord('serviceandasset', row[0])
                        transactions = record_serviceandasset.get_linkedrecords_dict('asset_transactions')
                        if transactions:
                            for trans in transactions:
                                try:
                                    delta = float(trans.get('transaction') or 0)
                                    tot_qty += delta
                                except (ValueError, TypeError):
                                    continue
                    else:
                        record_serviceandasset = UserRecord('serviceandasset')
                        record_serviceandasset.values['recordidcompany_'] = deal_record.values.get('recordidcompany_')
                        record_serviceandasset.values['recordidproduct_'] = dl_dict['recordidproduct_']
                        company = UserRecord('company', deal_record.values.get('recordidcompany_'), load_fields=False)
                        record_serviceandasset.values['reference'] = f"{company.values.get('companyname')} - {product.values.get('name')}"

                        
                    record_serviceandasset.values['quantity'] = tot_qty
                    record_serviceandasset.values['description'] = dl_dict.get('name')
                    record_serviceandasset.values['type'] = product.values.get('category')
                    record_serviceandasset.values['sector'] = product.values.get('category')
                    record_serviceandasset.save()
                    
                    sql_update_links = f"""
                        UPDATE user_dealline dl
                        JOIN user_deal d ON dl.recordiddeal_ = d.recordid_
                        SET dl.recordidserviceandasset_ = '{record_serviceandasset.recordid}'
                        WHERE d.recordidcompany_ = '{deal_record.values.get("recordidcompany_")}' 
                          AND dl.recordidproduct_ = '{dl_dict['recordidproduct_']}' 
                          AND dl.deleted_ = 'N' AND d.deleted_ = 'N'
                    """
                    with connection.cursor() as cursor:
                        cursor.execute(sql_update_links)
