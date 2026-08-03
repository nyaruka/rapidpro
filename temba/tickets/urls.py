from django.conf.urls import include
from django.urls import re_path

from .views import KnowledgeCRUDL, KnowledgeItemCRUDL, ShortcutCRUDL, TeamCRUDL, TicketCRUDL, TopicCRUDL

urlpatterns = [
    re_path(r"^", include(KnowledgeCRUDL().as_urlpatterns())),
    re_path(r"^", include(KnowledgeItemCRUDL().as_urlpatterns())),
    re_path(r"^", include(ShortcutCRUDL().as_urlpatterns())),
    re_path(r"^", include(TeamCRUDL().as_urlpatterns())),
    re_path(r"^", include(TicketCRUDL().as_urlpatterns())),
    re_path(r"^", include(TopicCRUDL().as_urlpatterns())),
]
