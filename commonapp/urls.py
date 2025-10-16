from django.contrib import admin
from django.urls import path
from django.conf.urls.static import static
from django.conf import settings
from commonapp.views import *
from commonapp.settings import *
from django.views.static import serve
from django.views.decorators.cache import never_cache
from bixscheduler import views

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
    path('get_table_filters/', get_table_filters, name='get_table_filters'),
    path('get_calendar_records/', get_calendar_records, name='get_calendar_records'),
    path('get_records_matrixcalendar/', get_records_matrixcalendar, name='get_records_matrixcalendar'),
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
    path('get_table_active_tab/', get_table_active_tab, name='get_table_active_tab'),
    path('get_favorite_tables/', get_favorite_tables, name='get_favorite_tables'),
    path('save_favorite_tables/', save_favorite_tables, name='save_favorite_tables'),
    path('script_winteler_load_t_wip/', script_winteler_load_t_wip, name='script_winteler_load_t_wip'),
    path('script_update_serviceandasset_domains_info/', script_update_serviceandasset_domains_info, name='script_update_serviceandasset_domains_info'),
    path('script_update_serviceandasset_domains_info/<str:dominio>/', script_update_serviceandasset_domains_info, name='script_update_serviceandasset_domains_info_dominio'),
    path('get_dashboard_data/', get_dashboard_data, name='get_dashboard_data'),
    path('script_add_golfclub/', script_add_golfclub, name='script_add_golfclub'),
    path('script_test/', script_test, name='script_test'),
    path('sign_timesheet/', sign_timesheet, name='sign_timesheet'),
    path('update_user_profile_pic/', update_user_profile_pic, name='update_user_profile_pic'),
    path('get_dashboard_blocks/', get_dashboard_blocks, name='get_dashboard_blocks'),
    path('save_dashboard_disposition/', save_dashboard_disposition, name='save_dashboard_disposition'),
    path('add_dashboard_block/', add_dashboard_block, name='add_dashboard_block'),
    path('save_form_data/', save_form_data, name='save_form_data'),
    path('get_form_fields/', get_form_fields, name='get_form_fields'),
    path('download_trattativa/', download_trattativa, name='download_trattativa'),
    path('trasferta_pdf/', trasferta_pdf, name='trasferta_pdf'),
    path('loading/', loading, name='loading'),
    path('new_dashboard/', new_dashboard, name='new_dashboard'),
    path('logout_view/', logout_view, name='logout_view'),
    path('delete_dashboard_block/', delete_dashboard_block, name='delete_dashboard_block'),
    path('get_user_theme/', get_user_theme, name='get_user_theme'),
    path('set_user_theme/', set_user_theme, name='set_user_theme'),
    path('stampa_pdf_test/', stampa_pdf_test, name='stampa_pdf_test'),
    path('get_user_id/', get_user_id, name='get_user_id'),
    path('get_custom_functions/', get_custom_functions, name='get_custom_functions'),
    path('get_table_records_kanban/', get_table_records_kanban, name='get_table_records_kanban'),
    path('save_newuser/', save_newuser, name='save_newuser'),
    path('get_user_settings_api/', get_user_settings_api, name='get_user_settings_api'),
    path('save_user_settings_api/', save_user_settings_api, name='save_user_settings_api'),
    path('get_users/', get_users, name='get_users'),
    path('calculate_dependent_fields/', calculate_dependent_fields, name='calculate_dependent_fields'),
    path('get_filter_options/', get_filter_options, name='get_filter_options'),
    path('get_chart_data/', get_chart_data, name='get_chart_data'),
    path('get_calendar_data/', get_calendar_data, name='get_calendar_data'),
    path('save_calendar_event/', save_calendar_event, name='save_calendar_event'),
    path('fieldsupdate/', fieldsupdate, name='fieldsupdate'),
    
    
     # ------------------  Settings views --------------------------------- 
    path('get_users_and_groups_api/', get_users_and_groups, name='get_users_and_groups'),
    path('settings_table_usertables/', settings_table_usertables, name='settings_table_usertables'),
    path('settings_table_fields/', settings_table_fields, name='settings_table_fields'),
    path('settings_table_settings/', settings_table_settings, name='settings_table_settings'),
    path('settings_table_fields_settings_save/', settings_table_fields_settings_save, name='settings_table_fields_settings_save'),
    path('settings_table_fields_settings_block/', settings_table_fields_settings_block, name='settings_table_fields_settings_block'),
    path('settings_table_usertables_save/', settings_table_usertables_save, name='settings_table_usertables_save'),
    path('settings_table_tablefields_save/', settings_table_tablefields_save, name='settings_table_tablefields_save'),
    path('settings_table_fields_new_field/', settings_table_fields_new_field, name='settings_table_fields_new_field'),
    path('settings_table_fields_settings_fields_save/', settings_table_fields_settings_fields_save, name='settings_table_fields_settings_fields_save'),
    path('settings_table_linkedtables/', settings_table_linkedtables, name='settings_table_linkedtables'),
    path('settings_table_linkedtables_save/', settings_table_linkedtables_save, name='settings_table_linkedtables_save'),
    path('save_new_table/', save_new_table, name='save_new_table'),
    path('get_master_linked_tables/', get_master_linked_tables, name='get_master_linked_tables'),
    
    
    # ------------------  WeGolf views ---------------------------------
    path('get_filtered_clubs/', get_filtered_clubs, name='get_filtered_clubs'),
    path('get_benchmark_filters/', get_benchmark_filters, name='get_benchmark_filters'),
    path('update_club_settings/', update_club_settings, name='update_club_settings'),
    path('get_settings_data/', get_settings_data, name='get_settings_data'),
    path('settings_table_steps/', settings_table_steps, name='settings_table_steps'),
    path('settings_table_newstep/', settings_table_newstep, name='settings_table_newstep'),
    path('settings_table_steps_save/', settings_table_steps_save, name='settings_table_steps_save'),
]


urlpatterns += static(settings.UPLOADS_URL, document_root=settings.UPLOADS_ROOT)
urlpatterns += static(settings.TEMPFILE_URL, document_root=settings.TEMPFILE_ROOT)
