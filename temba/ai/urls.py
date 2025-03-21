from django.conf.urls import include
from django.urls import re_path

from .models import LLM
from .views import LLMCRUDL

# build up all the type specific urls
type_urls = []
for llm_type in LLM.get_types():
    llm_urls = llm_type.get_urls()
    for u in llm_urls:
        u.name = "ai.types.%s.%s" % (llm_type.slug, u.name)

    if llm_urls:
        type_urls.append(re_path("^%s/" % llm_type.slug, include(llm_urls)))

urlpatterns = [
    re_path(r"^", include(LLMCRUDL().as_urlpatterns())),
    re_path(r"^ai/types/", include(type_urls)),
]
