# bixmonitoring/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_monitoring, name='lista_monitoring'),
]
