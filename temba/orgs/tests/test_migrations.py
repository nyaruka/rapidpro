from datetime import datetime, timezone as tzone
from zoneinfo import ZoneInfo

from temba.notifications.models import Incident
from temba.orgs.models import Org
from temba.tests import MigrationTest


class BackfillSuspendedOnTest(MigrationTest):
    app = "orgs"
    migrate_from = "0182_remove_org_country"
    migrate_to = "0183_backfill_suspended_on"

    def create_org(self, name: str, parent=None) -> Org:
        return Org.objects.create(
            name=name,
            timezone=ZoneInfo("Africa/Kigali"),
            flow_languages=["eng"],
            parent=parent,
            created_by=self.admin,
            modified_by=self.admin,
        )

    def setUpBeforeMigration(self, apps):
        def suspend(org, suspended_on=None):
            Org.objects.filter(id=org.id).update(is_suspended=True, suspended_on=suspended_on)

        # org with an ongoing suspension incident
        suspend(self.org)
        Incident.objects.create(
            org=self.org,
            incident_type="org:suspended",
            scope="",
            started_on=datetime(2023, 6, 1, 12, 0, 0, 0, tzone.utc),
        )

        # child org suspended via its parent so no incident of its own
        self.child = self.create_org("Child", parent=self.org)
        suspend(self.child)

        # org with no incident and modified before we started recording suspension times
        self.org3 = self.create_org("Old")
        suspend(self.org3)
        Incident.objects.create(  # ended incident from a previous suspension should be ignored
            org=self.org3,
            incident_type="org:suspended",
            scope="",
            started_on=datetime(2022, 1, 1, 12, 0, 0, 0, tzone.utc),
            ended_on=datetime(2022, 2, 1, 12, 0, 0, 0, tzone.utc),
        )
        Org.objects.filter(id=self.org3.id).update(modified_on=datetime(2023, 2, 15, 12, 0, 0, 0, tzone.utc))

        # org with no incident and modified after we started recording suspension times, e.g. edited by staff
        self.org4 = self.create_org("Recently Modified")
        suspend(self.org4)
        Org.objects.filter(id=self.org4.id).update(modified_on=datetime(2026, 3, 1, 12, 0, 0, 0, tzone.utc))

        # org already with a suspension time
        self.org5 = self.create_org("Already Set")
        suspend(self.org5, suspended_on=datetime(2025, 1, 1, 12, 0, 0, 0, tzone.utc))

        # non-suspended org with a stray suspension time
        Org.objects.filter(id=self.org2.id).update(suspended_on=datetime(2025, 1, 1, 12, 0, 0, 0, tzone.utc))

    def test_migration(self):
        def assert_suspended_on(org, expected):
            org.refresh_from_db()
            self.assertEqual(expected, org.suspended_on)

        assert_suspended_on(self.org, datetime(2023, 6, 1, 12, 0, 0, 0, tzone.utc))  # from incident
        assert_suspended_on(self.child, datetime(2023, 6, 1, 12, 0, 0, 0, tzone.utc))  # from parent's incident
        assert_suspended_on(self.org3, datetime(2023, 2, 15, 12, 0, 0, 0, tzone.utc))  # from modified_on
        assert_suspended_on(self.org4, datetime(2024, 11, 15, 0, 0, 0, 0, tzone.utc))  # clamped
        assert_suspended_on(self.org5, datetime(2025, 1, 1, 12, 0, 0, 0, tzone.utc))  # unchanged
        assert_suspended_on(self.org2, None)  # cleared
