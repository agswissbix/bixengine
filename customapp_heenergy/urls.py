from django.urls import path
from .views import *

urlpatterns = [
    path('print_pdf_heenergy/', print_pdf_heenergy, name='print_pdf_heenergy'),
]
