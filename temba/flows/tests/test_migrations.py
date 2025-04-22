from temba.tests import MigrationTest


class MigrationTest(MigrationTest):
    app = "flows"
    migrate_from = "0383_flow_info_ivr_retrry"
    migrate_to = "0384_backfill_ivr_retry"

    def setUpBeforeMigration(self, apps):
        self.flow1 = self.create_flow("Flow 1", flow_type="M")

        self.flow2 = self.create_flow("Flow 2", flow_type="V")
        self.flow2.metadata = {"ivr_retry": 123}
        self.flow2.save(update_fields=["metadata"])

        self.flow3 = self.create_flow("Flow 3", flow_type="V")
        self.flow3.metadata = {}
        self.flow3.save(update_fields=["metadata"])

    def test_migration(self):
        def assert_ivr_retry(flow, expected):
            flow.refresh_from_db()
            self.assertEqual(flow.ivr_retry, expected)

        assert_ivr_retry(self.flow1, None)
        assert_ivr_retry(self.flow2, 123)
        assert_ivr_retry(self.flow3, None)
