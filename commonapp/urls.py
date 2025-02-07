from django.contrib import admin
from django.urls import path
from commonapp.views import *

urlpatterns = [
    path('examplepost/', get_examplepost, name='examplepost'),
]
