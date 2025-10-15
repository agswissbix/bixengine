# bixscheduler/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('get/', views.lista_schedule_get, name='lista_schedule_get'),
    path('add/', views.aggiungi_scheduler, name='aggiungi_scheduler'),
    path('delete/', views.delete_scheduler, name='delete_scheduler'),
    path('run/', views.run_scheduler_now, name='run_scheduler_now'),
    path('toggle/', views.toggle_scheduler, name='toggle_scheduler'),
    path('save/', views.lista_schedule_post, name='lista_schedule_post'),  # Reusing lista_schedule for save
    path('run_function/', views.run_function, name='run_function'),
    
]
