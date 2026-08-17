from temba.tests import MigrationTest
from temba.triggers.models import Trigger


class ReleaseOptinTriggersTest(MigrationTest):
    app = "triggers"
    migrate_from = "0045_alter_trigger_id"
    migrate_to = "0046_release_optin_triggers"

    def _create_trigger(self, model, trigger_type: str, flow, **kwargs):
        return model.objects.create(
            org_id=self.org.id,
            trigger_type=trigger_type,
            flow_id=flow.id,
            priority=0,
            created_by_id=self.admin.id,
            modified_by_id=self.admin.id,
            **kwargs,
        )

    def setUpBeforeMigration(self, apps):
        # the trigger table has no uuid column at this point so use the historical model
        OldTrigger = apps.get_model("triggers", "Trigger")

        flow = self.create_flow("Test")

        self.keyword_trigger = self._create_trigger(OldTrigger, "K", flow, keywords=["join"], match_type="F")
        self.optin_trigger = self._create_trigger(OldTrigger, "I", flow)
        self.optout_trigger = self._create_trigger(OldTrigger, "O", flow, is_archived=True)

    def test_migration(self):
        self.keyword_trigger.refresh_from_db()
        self.optin_trigger.refresh_from_db()
        self.optout_trigger.refresh_from_db()

        self.assertTrue(self.keyword_trigger.is_active)
        self.assertFalse(self.optin_trigger.is_active)
        self.assertFalse(self.optout_trigger.is_active)


class BackfillTriggerUUIDsTest(MigrationTest):
    app = "triggers"
    migrate_from = "0047_trigger_uuid"
    migrate_to = "0049_alter_trigger_uuid"

    def setUpBeforeMigration(self, apps):
        flow = self.create_flow("Test")

        self.trigger1 = Trigger.create(self.org, self.admin, Trigger.TYPE_CATCH_ALL, flow)
        self.trigger2 = Trigger.create(
            self.org, self.admin, Trigger.TYPE_KEYWORD, flow, keywords=["join"], match_type=Trigger.MATCH_FIRST_WORD
        )
        self.trigger3 = Trigger.create(self.org, self.admin, Trigger.TYPE_INBOUND_CALL, flow)
        self.existing_uuid = self.trigger3.uuid

        # simulate rows which pre-date the uuid field
        Trigger.objects.filter(id__in=(self.trigger1.id, self.trigger2.id)).update(uuid=None)

    def test_migration(self):
        self.trigger1.refresh_from_db()
        self.trigger2.refresh_from_db()
        self.trigger3.refresh_from_db()

        self.assertIsNotNone(self.trigger1.uuid)
        self.assertIsNotNone(self.trigger2.uuid)
        self.assertNotEqual(self.trigger1.uuid, self.trigger2.uuid)

        # rows which already had a uuid are left alone
        self.assertEqual(self.existing_uuid, self.trigger3.uuid)
