from django.contrib import admin
from django.urls import path
from customapp_swissbix.views import *
from customapp_swissbix.bixverifytest import issue_qr_token, verify_qr_token

urlpatterns = [
    path('get_activemind/', get_activemind, name='get_activemind'),
    path('save_activemind/', save_activemind, name='save_activemind'),
    path('print_pdf_activemind/', print_pdf_activemind, name='print_pdf_activemind'),
    path('get_services_activemind/', get_services_activemind, name='get_services_activemind'),
    path('get_conditions_activemind/', get_conditions_activemind, name='get_conditions_activemind'),
    path("qr/issue", issue_qr_token, name="issue_qr_token"),
    path("qr/verify", verify_qr_token, name="verify_qr_token"),
    path('get_record_badge_swissbix_company/', get_record_badge_swissbix_company, name='get_record_badge_swissbix_company'),
    
]
