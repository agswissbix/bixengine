from django.contrib import admin
from django.urls import path, include
from commonapp.views import *

urlpatterns = [
    path('admin/', admin.site.urls),
    path('auth/csrf/', get_csrf_token, name='get_csrf_token'),
    path('auth/login/', login_view, name='login'),
    path('auth/logout/', logout_view, name='logout'),
    path('auth/user/', user_info, name='user_info'),
    path('commonapp/', include('commonapp.urls')),
    path('customapp_pitservice/', include('customapp_pitservice.urls')),
]
