from django.urls import re_path

from .views import ConnectEndpoint

urlpatterns = [
    re_path(r"^connect$", ConnectEndpoint.as_view(), name="api.websockets.connect"),
]
