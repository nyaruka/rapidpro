from django.urls import re_path

from .views import GlobalCRUDL, name_to_key

urlpatterns = GlobalCRUDL().as_urlpatterns()
urlpatterns += [
    re_path(r"^utils/name_to_key/$", name_to_key, name="utils.name_to_key"),
]
