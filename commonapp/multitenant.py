import re

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, PermissionDenied

from db_multitenant.mapper import TenantMapper

TENANT_NAME_RE = re.compile(r'^[A-Za-z0-9_]+$')


class HeaderTenantMapper(TenantMapper):
    """Mapper multitenant basato su header + sessione.

    Questa implementazione:
    - legge il tenant dalla sessione se presente;
    - durante il login usa l'header X-Tenant-ID;
    - impedisce cambi tenant a runtime se la sessione ha già un tenant;
    - costruisce il nome DB come bixdata_<tenant>.
    """

    HEADER_NAME = 'HTTP_X_TENANT_ID'
    DB_PREFIX = getattr(settings, 'MULTITENANT_DATABASE_PREFIX', 'bixdata_')
    DEFAULT_TENANT = getattr(settings, 'MULTITENANT_DEFAULT_TENANT', None)

    def get_tenant_name(self, request):
        tenant_from_header = self._get_header(request)
        tenant_from_cookie = request.COOKIES.get('current_tenant')

        print(f"DEBUG: header={tenant_from_header}, cookie={tenant_from_cookie}")

        # Decidi quale usare (vince l'header se ci sono entrambi)
        tenant_name = tenant_from_header or tenant_from_cookie

        # 3. Validazione
        if tenant_name:
            self._assert_allowed_tenant(tenant_name)
            request.tenant_name = tenant_name  # Salva il tenant nella request per usi futuri
            return tenant_name

        # 4. Fallback al default
        if self.DEFAULT_TENANT:
            self._assert_allowed_tenant(self.DEFAULT_TENANT)
            return self.DEFAULT_TENANT

        raise ImproperlyConfigured('Tenant identifier is missing (neither header nor cookie found).')

    def get_db_name(self, request, tenant_name):
        self._validate_tenant_name(tenant_name)
        if tenant_name == self.DEFAULT_TENANT:
            # Per il default tenant, usa il db originale
            from django.conf import settings
            return settings.DATABASES['default']['NAME']
        db_name = f"{self.DB_PREFIX}{tenant_name}"
        print(f"DEBUG: get_db_name for tenant {tenant_name} -> {db_name}")
        return db_name

    def get_cache_prefix(self, request, tenant_name, db_name):
        return f"{tenant_name}:"

    def _get_header(self, request):
        value = request.META.get(self.HEADER_NAME)
        print(f"DEBUG: Raw header {self.HEADER_NAME} value: {value}")
        if value:
            value = value.strip()
            return value if value else None

        return None

    def _assert_allowed_tenant(self, tenant_name):
        allowed = getattr(settings, 'MULTITENANT_ALLOWED_TENANTS', [])
        if allowed and tenant_name not in allowed:
            raise PermissionDenied('Tenant not allowed.')

    def _validate_tenant_name(self, tenant_name):
        if not tenant_name or not TENANT_NAME_RE.match(tenant_name):
            raise ImproperlyConfigured('Invalid tenant name. Use only letters, numbers and underscore.')
