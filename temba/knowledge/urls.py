from django.conf.urls import include
from django.urls import re_path

from .views import KnowledgeCRUDL, KnowledgeItemCRUDL

urlpatterns = [
    re_path(r"^", include(KnowledgeCRUDL().as_urlpatterns())),
    re_path(r"^", include(KnowledgeItemCRUDL().as_urlpatterns())),
]
