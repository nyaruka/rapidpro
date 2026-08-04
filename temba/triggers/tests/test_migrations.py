from temba.tests import MigrationTest
from temba.triggers.models import Trigger


class DeleteOptinTriggersTest(MigrationTest):
    app = "triggers"
    migrate_from = "0045_alter_trigger_id"
    migrate_to = "0046_delete_optin_triggers"

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
        self.assertTrue(Trigger.objects.filter(id=self.keyword_trigger.id).exists())
        self.assertFalse(Trigger.objects.filter(id=self.optin_trigger.id).exists())
        self.assertFalse(Trigger.objects.filter(id=self.optout_trigger.id).exists())
