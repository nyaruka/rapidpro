from django.urls import re_path

from .views import ConnectEndpoint, RefreshEndpoint, SubRefreshEndpoint, SubscribeEndpoint

urlpatterns = [
    re_path(r"^connect$", ConnectEndpoint.as_view(), name="api.websockets.connect"),
    re_path(r"^refresh$", RefreshEndpoint.as_view(), name="api.websockets.refresh"),
    re_path(r"^subscribe$", SubscribeEndpoint.as_view(), name="api.websockets.subscribe"),
    re_path(r"^sub_refresh$", SubRefreshEndpoint.as_view(), name="api.websockets.sub_refresh"),
]
