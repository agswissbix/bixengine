# bixengine/urls.py
from django.contrib import admin
from django.urls import path, include
from commonapp.views import *
from bixengine.core.admin import custom_admin_site

urlpatterns = [
    path('admin/', custom_admin_site.urls), 
    path('login/', custom_admin_site.login, name='admin_login'),
    path('logout/', custom_admin_site.logout, name='admin_logout'),    path('auth/login/', login_view, name='login'),
    path('auth/logout/', logout_view, name='logout'),
    path('auth/user/', user_info, name='user_info'),

    path('commonapp/', include('commonapp.urls')),
    path('customapp_telefonoamico/', include('customapp_telefonoamico.urls')),
    path('customapp_winteler/', include('customapp_winteler.urls')),
    path('customapp_pitservice/', include('customapp_pitservice.urls')),
    path('customapp_belotti/', include('customapp_belotti.urls')),
    path('settings/', include('bixsettings.urls')),

    # ✅ App migrati da bixadmin
    path('scheduler/', include('bixscheduler.urls')),
    path('monitoring/', include('bixmonitoring.urls')),
]
