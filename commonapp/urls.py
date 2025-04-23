from django.contrib import admin
from django.urls import path
from django.conf import settings
from commonapp.views import *
from django.views.static import serve
from django.views.decorators.cache import never_cache

urlpatterns = [
    path('examplepost/', get_examplepost, name='examplepost'),
    path('test_connection/', test_connection, name='test_connection'),
    path('test_connection_get_csrf', test_connection_get_csrf, name='test_connection_get_csrf'),
    path('test_connection_post/', test_connection_post, name='test_connection_post'),
    path('get_csrf', get_csrf, name='get_csrf'),
    path('check_csrf', check_csrf, name='check_csrf'),
    path('get_sidebarmenu_items/', get_sidebarmenu_items, name='get_sidebarmenu_items'),
    path('verify_2fa/', verify_2fa, name='verify_2fa'),
    path('enable_2fa/', enable_2fa, name='enable_2fa'),
    path('disable_2fa/', disable_2fa, name='disable_2fa'),
    path('change_password/', change_password, name='change_password'),
    path('get_active_server/', get_active_server, name='get_active_server'),
    path('delete_record/', delete_record, name='delete_record'),
    path('get_table_records/', get_table_records, name='get_table_records'),
    path('get_pitservice_pivot_lavanderia/', get_pitservice_pivot_lavanderia, name='get_pitservice_pivot_lavanderia'),
    path('save_record_fields/', save_record_fields, name='save_record_fields'),
    path('get_table_views/', get_table_views, name='get_table_views'),
    path('get_record_badge/', get_record_badge, name='get_record_badge'),
    path('get_record_card_fields/', get_record_card_fields, name='get_record_card_fields'),
    path('get_record_linked_tables/', get_record_linked_tables, name='get_record_linked_tables'),
    path('prepara_email/', prepara_email, name='prepara_email'),
    path('save_email/', save_email, name='save_email'),
    path('get_input_linked/', get_input_linked, name='get_input_linked'),
    path('stampa_bollettini_test/', stampa_bollettini_test, name='stampa_bollettini_test'),
    path('send_emails/', send_emails, name='send_emails'),
    path('get_form_data/', get_form_data, name='get_form_data'),
    path('export_excel/', export_excel, name='export_excel'),
    path('get_record_attachments/', get_record_attachments, name='get_record_attachments'),    
    path('get_card_active_tab/', get_card_active_tab, name='get_card_active_tab'),
    path('get_favorite_tables/', get_favorite_tables, name='get_favorite_tables'),

    # Serve i file media senza cache
    path(
        'commonapp/media/<path:path>',
        never_cache(serve),
        {'document_root': settings.MEDIA_ROOT},
    ),
]
