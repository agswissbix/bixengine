from django.contrib import admin
from django.urls import path
from commonapp.views import *

urlpatterns = [
    path('check_csrf', check_csrf, name='check_csrf'),
    path('examplepost/', get_examplepost, name='examplepost'),
    path('get_sidebarmenu_items/', get_sidebarmenu_items, name='get_sidebarmenu_items'),
    path('test_connection/', test_connection, name='test_connection'),
    
]
