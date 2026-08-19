from django.conf.urls import include
from django.urls import re_path

from .android.views import register, sync
from .models import Channel
from .views import ChannelCRUDL

# we iterate all our channel types, finding all the URLs they want to wire in
type_urls = []

for ch_type in Channel.get_types():
    channel_urls = ch_type.get_urls()
    for u in channel_urls:
        u.name = "channels.types.%s.%s" % (ch_type.slug, u.name)

    if channel_urls:
        type_urls.append(re_path("^%s/" % ch_type.slug, include(channel_urls)))


urlpatterns = [
    re_path(r"^channels/", include(ChannelCRUDL().as_urlpatterns())),
    re_path(r"^channels/types/", include(type_urls)),
    re_path(r"^relayers/relayer/sync/(\d+)/$", sync, {}, "sync"),
    re_path(r"^relayers/relayer/register/$", register, {}, "register"),
]
