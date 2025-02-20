from django.contrib import admin
from django.urls import path
from customapp_telefonoamico.views import *

urlpatterns = [
    path('test/', test, name='test'),
    path('get_shifts_and_volunteers/', get_shifts_and_volunteers, name='get_shifts_and_volunteers'),
    path('save_shift/', save_shift, name='save_shift'),
    path('delete_shift/', delete_shift, name='delete_shift'),
    
    
]
