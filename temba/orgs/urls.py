from django.conf.urls import include
from django.urls import re_path

from .models import IntegrationType
from .views import ExportCRUDL, InvitationCRUDL, OrgCRUDL, OrgImportCRUDL, UserCRUDL, check_login

urlpatterns = OrgCRUDL().as_urlpatterns()
urlpatterns += OrgImportCRUDL().as_urlpatterns()
urlpatterns += UserCRUDL().as_urlpatterns()
urlpatterns += InvitationCRUDL().as_urlpatterns()
urlpatterns += ExportCRUDL().as_urlpatterns()

# we iterate all our integration types, finding all the URLs they want to wire in
integration_type_urls = []

for integration in IntegrationType.get_all():
    integration_urls = integration.get_urls()
    for u in integration_urls:
        u.name = f"integrations.{integration.slug}.{u.name}"

    if integration_urls:
        integration_type_urls.append(re_path("^%s/" % integration.slug, include(integration_urls)))

urlpatterns += [
    re_path(r"^login/$", check_login, name="orgs.check_login"),
    re_path(r"^integrations/", include(integration_type_urls)),
]
