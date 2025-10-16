from django.contrib import admin
from django.urls import path



from customapp_winteler.views import *

urlpatterns = [
    path('winteler_wip_barcode_scan/', winteler_wip_barcode_scan, name='winteler_wip_barcode_scan'),
    path('sync_wipbarcode_bixdata_adiuto/', sync_wipbarcode_bixdata_adiuto, name='sync_wipbarcode_bixdata_adiuto'),
    path('script_update_wip_status/', script_update_wip_status, name='script_update_wip_status'),
    path('sync_plesk_adiuto/', sync_plesk_adiuto, name='sync_plesk_adiuto'),
    
    
    path('save_service_man/', save_service_man, name='save_service_man'),
    
]
