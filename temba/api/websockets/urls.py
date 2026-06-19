from django.urls import re_path

from .views import ConnectEndpoint, RefreshEndpoint

urlpatterns = [
    re_path(r"^connect$", ConnectEndpoint.as_view(), name="api.websockets.connect"),
    re_path(r"^refresh$", RefreshEndpoint.as_view(), name="api.websockets.refresh"),
]
