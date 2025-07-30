# bixscheduler/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_schedule, name='lista_schedule'),
    path('aggiungi/', views.aggiungi_scheduler, name='aggiungi_scheduler'),
    path('delete/<int:schedule_id>/', views.delete_scheduler, name='delete_scheduler'),
    path('run/<int:schedule_id>/', views.run_scheduler_now, name='run_scheduler_now'),
    path('toggle/<int:schedule_id>/', views.toggle_scheduler, name='toggle_scheduler'),
    path('loading/', views.get_render_loading, name='loading'),
]
