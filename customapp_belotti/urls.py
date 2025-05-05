from django.contrib import admin
from django.urls import path
from customapp_belotti.views import *

urlpatterns = [
    path('sync_utenti_adiutobixdata/', sync_utenti_adiutobixdata, name='sync_utenti_adiutobixdata'),
   
    
]
