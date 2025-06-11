from unittest.mock import MagicMock, patch

from django.template import Engine, Template
from django.urls import reverse

from temba.tests import TembaTest

from .base import AnalyticsBackend


class AnalyticsTest(TembaTest):
    def setUp(self):
        super().setUp()

    @patch("temba.utils.analytics.base.get_backends")
    def test_get_hook_html(self, mock_get_backends):
        good = MagicMock()
        good.slug = "good"
        good.get_hook_template.return_value = "good/frame_top.html"
        mock_get_backends.return_value = [BadBackend(), good]

        real_get_template = Engine.get_default().get_template

        def get_template(name):
            if name == "good/frame_top.html":
                return Template('<script>alert("good")</script>\n')
            elif name == "bad/frame_top.html":
                return Template('<script>alert("bad")</script>\n')
            else:
                return real_get_template(name)

        with patch("django.template.engine.Engine.get_template", wraps=get_template):
            self.login(self.admin)
            response = self.client.get(reverse("orgs.org_workspace"))

            self.assertContains(
                response,
                """<!-- begin hook for bad -->
<script>alert("bad")</script>
<!-- end hook for bad -->
<!-- begin hook for good -->
<script>alert("good")</script>
<!-- end hook for good -->""",
            )


class BadBackend(AnalyticsBackend):
    slug = "bad"
    hook_templates = {"frame-top": "bad/frame_top.html"}
