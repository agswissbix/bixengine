from django.contrib import admin
from django.urls import path
from customapp_telefonoamico.views import *

urlpatterns = [
    path('test/', test, name='test'),
    path('get_shifts_and_volunteers_telefono/', get_shifts_and_volunteers_telefono, name='get_shifts_and_volunteers_telefono'),
    path('get_shifts_and_volunteers_chat/', get_shifts_and_volunteers_chat, name='get_shifts_and_volunteers_chat'),
    path('save_shift/', save_shift, name='save_shift'),
    path('delete_shift/', delete_shift, name='delete_shift'),
    
    
]
