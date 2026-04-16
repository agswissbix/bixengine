from commonapp.bixmodels.user_record import UserRecord
from commonapp.bixmodels.user_table import UserTable
from commonapp.helper import Helper
from .deal_services import DealService

class AssetTransactionsService:
    @staticmethod
    def process_asset_transactions(recordid: str) -> list:
        asset_transactions_record = UserRecord('asset_transactions', recordid)
        serviceandasset_recordid = asset_transactions_record.values.get('recordidserviceandasset_')
        serviceandasset_record = UserRecord('serviceandasset', serviceandasset_recordid) if serviceandasset_recordid else None
        deallines = serviceandasset_record.get_linkedrecords_dict('dealline')
        if deallines:
            for dl in deallines:
                if dl.get('deleted_') == 'N':
                    # DealService._process_service_and_assets()
                    return [('dealline', dl['recordid_'])]
        return []
