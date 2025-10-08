from django.contrib import admin
from django.urls import path
from customapp_swissbix.views import *
from customapp_swissbix.customfunc import *
from customapp_swissbix.script import *
from customapp_swissbix.bixverifytest import issue_qr_token, verify_qr_token

urlpatterns = [
    path('get_activemind/', get_activemind, name='get_activemind'),
    path('save_activemind/', save_activemind, name='save_activemind'),
    path('print_pdf_activemind/', print_pdf_activemind, name='print_pdf_activemind'),
    path('get_services_activemind/', get_services_activemind, name='get_services_activemind'),
    path('get_products_activemind/', get_products_activemind, name='get_products_activemind'),
    path('get_conditions_activemind/', get_conditions_activemind, name='get_conditions_activemind'),
    path("qr/issue", issue_qr_token, name="issue_qr_token"),
    path("qr/verify", verify_qr_token, name="verify_qr_token"),
    path('get_record_badge_swissbix_company/', get_record_badge_swissbix_company, name='get_record_badge_swissbix_company'),
    path('get_record_badge_swissbix_deals/', get_record_badge_swissbix_deals, name='get_record_badge_swissbix_deals'),
    path('get_record_badge_swissbix_project/', get_record_badge_swissbix_project, name='get_record_badge_swissbix_project'),
    path('stampa_offerta/', stampa_offerta, name='stampa_offerta'),
    path('deal_update_status/', deal_update_status, name='deal_update_status'),
    path('printing_katun_xml_extract_rows/', printing_katun_xml_extract_rows, name='printing_katun_xml_extract_rows'),
    path('printing_katun_bexio_api_set_invoice/', printing_katun_bexio_api_set_invoice, name='printing_katun_bexio_api_set_invoice'),
    path('get_satisfation/', get_satisfation, name='get_satisfation'),
    path('update_deals/', update_deals, name='update_deals'),
    
    
]
