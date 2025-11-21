from django.contrib import admin
from django.urls import path
from customapp_wegolf.views import *
from customapp_wegolf.customfunc import *
from customapp_wegolf.script import *

urlpatterns = [
    path('sync_notifications/', sync_notifications, name='sync_notifications'),
    
    
    
]
