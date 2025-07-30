# bixadmin/core/admin.py

from django.contrib.admin import AdminSite
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin, GroupAdmin
from django.shortcuts import redirect
from django.urls import reverse
from django.http import HttpResponseRedirect


class CustomAdminSite(AdminSite):
    site_header = "BixAdmin"
    site_title = "BixAdmin Portal"
    index_title = "Benvenuto in BixAdmin"

    def login(self, request, extra_context=None):
        """
        Gestisce il login e redirect a /settings/tables dopo il login
        """
        if request.user.is_authenticated:
            return redirect('/settings/tables')
        
        # Se è una richiesta POST (tentativo di login)
        if request.method == 'POST':
            response = super().login(request, extra_context=extra_context)
            # Se il login è andato a buon fine e c'è un redirect
            if hasattr(response, 'status_code') and response.status_code == 302:
                return redirect('/settings/tables')
            return response
        
        # Per richieste GET, mostra la pagina di login normale
        return super().login(request, extra_context=extra_context)

    def index(self, request, extra_context=None):
        """
        Mostra la pagina index normale dell'admin
        """
        return super().index(request, extra_context=extra_context)
    
    def logout(self, request, extra_context=None):
        """
        Gestisce il logout e redirect diretto alla pagina di login
        """
        from django.contrib.auth import logout
        from django.contrib.admin.sites import AdminSite
        
        # Eseguiamo il logout manualmente
        logout(request)
        
        # Redirect diretto senza passare per altri metodi
        return redirect('/login/')


# Istanza del custom admin
custom_admin_site = CustomAdminSite(name='custom_admin')

# Registra i modelli che vuoi mostrare nell'admin
custom_admin_site.register(User, UserAdmin)
custom_admin_site.register(Group, GroupAdmin)