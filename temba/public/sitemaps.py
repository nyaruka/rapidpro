from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class PublicViewSitemap(Sitemap):
    priority = 0.5
    changefreq = "daily"

    def items(self):
        return settings.SITEMAP

    def location(self, item):
        return reverse(item)
