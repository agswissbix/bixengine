from django.contrib import admin
from django.urls import path



from customapp_winteler.views import *

urlpatterns = [
    path('winteler_wip_barcode_scan/', winteler_wip_barcode_scan, name='winteler_wip_barcode_scan'),
    path('sync_wipbarcode_bixdata_adiuto/', sync_wipbarcode_bixdata_adiuto, name='sync_wipbarcode_bixdata_adiuto'),
    

    
]
