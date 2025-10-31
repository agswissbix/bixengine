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
    path('sync_freshdesk_tickets/', sync_freshdesk_tickets, name='sync_freshdesk_tickets'),
    path('sync_bexio_contacts/', sync_bexio_contacts, name='sync_bexio_contacts'),
    path('sync_bexio_orders/', sync_bexio_orders, name='sync_bexio_orders'),
    path('sync_bexio_positions_example/', sync_bexio_positions_example, name='sync_bexio_positions_example'),
    path('sync_bexio_positions/', sync_bexio_positions, name='sync_bexio_positions'),
    path('sync_bexio_invoices/', sync_bexio_invoices, name='sync_bexio_invoices'),
    path('syncdata/', syncdata, name='syncdata'),
    path('get_scheduler_logs/', get_scheduler_logs, name='get_scheduler_logs'),
    path('get_fields_swissbix_deal/', get_fields_swissbix_deal, name='get_fields_swissbix_deal'),
    path('get_system_assurance_activemind/', get_system_assurance_activemind, name='get_system_assurance_activemind'),
    path('print_timesheet/', print_timesheet, name='print_timesheet'),
    path('sync_graph_calendar/', sync_graph_calendar, name='sync_graph_calendar'),
    
    
    
    
]
