from django.contrib import admin
from django.urls import path
from commonapp.views import login_view, logout_view, user_info, get_csrf_token

urlpatterns = [
    path('admin/', admin.site.urls),
    path('auth/csrf/', get_csrf_token, name='get_csrf_token'),
    path('auth/login/', login_view, name='login'),
    path('auth/logout/', logout_view, name='logout'),
    path('auth/user/', user_info, name='user_info'),
]
