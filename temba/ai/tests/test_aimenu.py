from django.urls import reverse

from temba.ai.models import KnowledgeBase
from temba.orgs.models import Org
from temba.tests import CRUDLTestMixin, TembaTest


class AIMenuTest(TembaTest, CRUDLTestMixin):
    def test_menu(self):
        menu_url = reverse("ai.ai_menu")

        self.assertRequestDisallowed(menu_url, [None, self.agent])
        self.assertPageMenu(menu_url, self.admin, ["Models (0)"])

        # orgs with the agents feature also see their knowledge bases
        self.org.features = [Org.FEATURE_AGENTS]
        self.org.save(update_fields=("features",))

        KnowledgeBase.create_website(self.org, self.admin, "Acme Help", "https://help.acme.com/")

        self.assertPageMenu(menu_url, self.admin, ["Models (0)", "Knowledge (1)"])
