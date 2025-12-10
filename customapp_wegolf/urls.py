from django.contrib import admin
from django.urls import path
from customapp_wegolf.views import *
from customapp_wegolf.customfunc import *
from customapp_wegolf.script import *

urlpatterns = [
    path('sync_notifications/', sync_notifications, name='sync_notifications'),

    path('check_data_anonymous/', check_data_anonymous, name='check_data_anonymous'),
    path('get_filtered_clubs/', get_filtered_clubs, name='get_filtered_clubs'),
    path('get_wegolf_welcome_data/', get_wegolf_welcome_data, name='get_wegolf_welcome_data'),
    path('get_benchmark_filters/', get_benchmark_filters, name='get_benchmark_filters'),
    path('get_documents/', get_documents, name='get_documents'),
    path('get_projects/', get_projects, name='get_projects'),
    path('like_project/', like_project, name='like_project'),
    path('unlike_project/', unlike_project, name='unlike_project'),
    path('get_language/', get_language, name='get_language'),
    path('get_notifications/', get_notifications, name='get_notifications'),
    path('mark_all_notifications_read/', mark_all_notifications_read, name='mark_all_notifications_read'),
    path('mark_notification_read/', mark_notification_read, name='mark_notification_read'),
    path('mark_notification_hidden/', mark_notification_hidden, name='mark_notification_hidden'),
    path('request_new_project/', request_new_project, name='request_new_project'),
    path('request_new_document/', request_new_document, name='request_new_document'),    
    path('sync_translation_fields/', sync_translation_fields, name='sync_translation_fields'),
    path('sync_translation_dashboards/', sync_translation_dashboards, name='sync_translation_dashboards'),
    path('get_languages/', get_languages, name='get_languages'),
    path('update_club_settings/', update_club_settings, name='update_club_settings'),
    path('get_settings_data/', get_settings_data, name='get_settings_data'),
    path('get_data_formats/', get_data_formats, name='get_data_formats')
    
    
]
