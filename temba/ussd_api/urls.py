from django.urls import path, re_path
from .views import USSDCallBack, SendURL, WebHookTester

urlpatterns = [
    re_path(r"^ussd/api/send-url", SendURL.as_view(), name="send_url"),
    re_path(r"^ussd/api/call-back", USSDCallBack.as_view(), name="callback"),
    re_path(r"ussd/api/webhook", WebHookTester.as_view(), name='webhook')
]


