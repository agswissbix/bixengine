from django.contrib import admin
from django.urls import path



from customapp_winteler.views import *

urlpatterns = [
    path('winteler_wip_barcode_scan/', winteler_wip_barcode_scan, name='winteler_wip_barcode_scan'),

    
]
