from django.urls import re_path

from .views import TembaLoginView, TembaSignupView, UserSettingsView

urlpatterns = [
    re_path(r"accounts/login", view=TembaLoginView.as_view(), name="account_login"),
    re_path(r"accounts/signup", view=TembaSignupView.as_view(), name="account_signup"),
    re_path(r"^user/settings/$", view=UserSettingsView.as_view(), name="users.user_settings"),
]
