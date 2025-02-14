from django.contrib import admin
from django.urls import path
from commonapp.views import *

urlpatterns = [
    path('check_csrf', check_csrf, name='check_csrf'),
    path('examplepost/', get_examplepost, name='examplepost'),
    path('get_sidebarmenu_items/', get_sidebarmenu_items, name='get_sidebarmenu_items'),
    path('test_connection/', test_connection, name='test_connection'),
    path('verify_2fa/', verify_2fa, name='verify_2fa'),
    path('enable_2fa/', enable_2fa, name='enable_2fa'),
    path('disable_2fa/', disable_2fa, name='disable_2fa'),
    
    
]
