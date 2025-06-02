from django.contrib import admin
from django.urls import path
from customapp_pitservice.views import *

urlpatterns = [
    path('stampa_bollettino/', stampa_bollettino, name='stampa_bollettino'),
    path('stampa_bollettino_test/', stampa_bollettino_test, name='stampa_bollettino_test'),
    path('stampa_gasoli/', stampa_gasoli, name='stampa_gasoli'),
    path('crea_lista_lavanderie/', crea_lista_lavanderie, name='crea_lista_lavanderie'),
    path('prepara_email/', prepara_email, name='prepara_email'),
    
    
]
