from datetime import datetime, timezone as tzone

from temba.airtime.models import AirtimeTransfer
from temba.tests import MigrationTest


class UpdateTransferUUIDsTest(MigrationTest):
    app = "airtime"
    migrate_from = "0037_squashed"
    migrate_to = "0038_update_transfer_uuids"

    def setUpBeforeMigration(self, apps):
        contact = self.create_contact("Ann")

        self.transfer1 = AirtimeTransfer.objects.create(
            uuid="47f26cfc-f3f2-4e13-bea9-36555aaf7cea",
            org=self.org,
            status=AirtimeTransfer.STATUS_SUCCESS,
            contact=contact,
            recipient="tel:+250700000003",
            currency="RWF",
            desired_amount="1100",
            actual_amount="1000",
            created_on=datetime(2025, 8, 11, 20, 36, 41, 114764, tzinfo=tzone.utc),
        )
        self.transfer2 = AirtimeTransfer.objects.create(
            uuid="01989ad9-7c1a-7b8d-a59e-141c265730dc",
            org=self.org,
            status=AirtimeTransfer.STATUS_FAILED,
            sender="tel:+250700000002",
            contact=contact,
            recipient="tel:+250700000003",
            currency="USD",
            desired_amount="1100",
            actual_amount="0",
            created_on=datetime(2025, 8, 11, 20, 36, 41, 116000, tzinfo=tzone.utc),
        )

    def test_migration(self):
        self.transfer1.refresh_from_db()
        self.transfer2.refresh_from_db()

        self.assertTrue(str(self.transfer1.uuid).startswith("01989ad9-7c1a-7"))
        self.assertEqual("01989ad9-7c1a-7b8d-a59e-141c265730dc", str(self.transfer2.uuid))  # unchanged
