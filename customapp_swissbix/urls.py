from django.contrib import admin
from django.urls import path
from customapp_swissbix.views import *

urlpatterns = [
    path('get_activemind/', get_activemind, name='get_activemind'),
    path('save_activemind/', save_activemind, name='save_activemind')


]
