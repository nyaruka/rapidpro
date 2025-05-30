from django.contrib.sitemaps.views import sitemap
from django.urls import re_path
from django.views.decorators.csrf import csrf_exempt

from temba.settings import DEBUG

from .sitemaps import PublicViewSitemap
from .views import Android, DemoGenerateCoupon, DemoOrderStatus, Forgetme, IndexView, Style, Welcome, WelcomeRedirect

sitemaps = {"public": PublicViewSitemap}

urlpatterns = [
    re_path(r"^$", IndexView.as_view(), {}, "public.public_index"),
    re_path(r"^sitemap\.xml$", sitemap, {"sitemaps": sitemaps}, name="public.sitemaps"),
    re_path(r"^welcome/$", Welcome.as_view(), {}, "public.public_welcome"),
    re_path(r"^android/$", Android.as_view(), {}, "public.public_android"),
    re_path(r"^public/forgetme/$", Forgetme.as_view(), {}, "public.public_forgetme"),
    re_path(r"^public/welcome/$", WelcomeRedirect.as_view(), {}, "public.public_welcome_redirect"),
    re_path(r"^demo/status/$", csrf_exempt(DemoOrderStatus.as_view()), {}, "demo.order_status"),
    re_path(r"^demo/coupon/$", csrf_exempt(DemoGenerateCoupon.as_view()), {}, "demo.generate_coupon"),
]

if DEBUG:  # pragma: needs cover
    urlpatterns.append(re_path(r"^style/$", Style.as_view(), {}, "public.public_style")),
