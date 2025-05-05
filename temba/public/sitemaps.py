from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from temba.settings import SITEMAP


class PublicViewSitemap(Sitemap):
    priority = 0.5
    changefreq = "daily"

    def items(self):
        return SITEMAP

    def location(self, item):
        return reverse(item)
