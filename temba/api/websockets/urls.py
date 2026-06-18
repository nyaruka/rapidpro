from django.urls import re_path

from .views import ConnectEndpoint, SubscribeEndpoint

urlpatterns = [
    re_path(r"^connect$", ConnectEndpoint.as_view(), name="api.websockets.connect"),
    re_path(r"^subscribe$", SubscribeEndpoint.as_view(), name="api.websockets.subscribe"),
]
