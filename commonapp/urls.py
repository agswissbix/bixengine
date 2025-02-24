from django.contrib import admin
from django.urls import path
from commonapp.views import *

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
    
    
]
