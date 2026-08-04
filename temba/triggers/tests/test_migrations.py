from temba.tests import MigrationTest
from temba.triggers.models import Trigger


class ReleaseOptinTriggersTest(MigrationTest):
    app = "triggers"
    migrate_from = "0045_alter_trigger_id"
    migrate_to = "0046_release_optin_triggers"

    def _create_trigger(self, trigger_type: str, flow, **kwargs):
        return Trigger.objects.create(
            org=self.org,
            trigger_type=trigger_type,
            flow=flow,
            priority=0,
            created_by=self.admin,
            modified_by=self.admin,
            **kwargs,
        )

    def setUpBeforeMigration(self, apps):
        flow = self.create_flow("Test")

        self.keyword_trigger = self._create_trigger("K", flow, keywords=["join"], match_type="F")
        self.optin_trigger = self._create_trigger("I", flow)
        self.optout_trigger = self._create_trigger("O", flow, is_archived=True)

    def test_migration(self):
        self.keyword_trigger.refresh_from_db()
        self.optin_trigger.refresh_from_db()
        self.optout_trigger.refresh_from_db()

        self.assertTrue(self.keyword_trigger.is_active)
        self.assertFalse(self.optin_trigger.is_active)
        self.assertFalse(self.optout_trigger.is_active)
