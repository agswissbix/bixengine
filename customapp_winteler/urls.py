from django.contrib import admin
from django.urls import path



from customapp_winteler.views import *

urlpatterns = [
    path('winteler_wip_barcode_scan/', winteler_wip_barcode_scan, name='winteler_wip_barcode_scan'),
    path('sync_wipbarcode_bixdata_adiuto/', sync_wipbarcode_bixdata_adiuto, name='sync_wipbarcode_bixdata_adiuto'),
    path('script_update_wip_status/', script_update_wip_status, name='script_update_wip_status'),
    path('sync_plesk_adiuto/', sync_plesk_adiuto, name='sync_plesk_adiuto'),
    
    
    path('save_service_man/', save_service_man, name='save_service_man'),
    path('get_service_man/', get_service_man, name='get_service_man'),
    path('save_checklist/', save_checklist, name='save_checklist'),
    path('save_nota_spesa/', save_nota_spesa, name='save_nota_spesa'),
    path('save_preventivo_carrozzeria/', save_preventivo_carrozzeria, name='save_preventivo_carrozzeria'),
    path('save_nuova_auto/', save_nuova_auto, name='save_nuova_auto'),
    path('save_prova_auto/', save_prova_auto, name='save_prova_auto'),
    path('get_prove_auto/', get_prove_auto, name='get_prove_auto'),
    path('search_scheda_auto/', search_scheda_auto, name='search_scheda_auto'),
    
]
