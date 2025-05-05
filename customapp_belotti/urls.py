from django.contrib import admin
from django.urls import path
from customapp_belotti.views import *

urlpatterns = [
    path('sync_utenti_adiutobixdata/', sync_utenti_adiutobixdata, name='sync_utenti_adiutobixdata'),
    path('sync_formularigruppo_adiutobixdata/', sync_formularigruppo_adiutobixdata, name='sync_formularigruppo_adiutobixdata'),
    path('sync_prodotti_adiutobixdata/', sync_prodotti_adiutobixdata, name='sync_prodotti_adiutobixdata'),
   
    
]
