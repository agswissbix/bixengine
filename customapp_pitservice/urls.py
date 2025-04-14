from django.contrib import admin
from django.urls import path
from customapp_pitservice.views import *

urlpatterns = [
    path('stampa_bollettini/', stampa_bollettini, name='stampa_bollettini'),
    
]
