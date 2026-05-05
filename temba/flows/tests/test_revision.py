from datetime import timedelta

from django.db.models.functions import TruncDate
from django.utils import timezone

from temba.flows.models import FlowRevision
from temba.flows.tasks import trim_flow_revisions
from temba.orgs.models import User
from temba.tests import TembaTest


class FlowRevisionTest(TembaTest):
    def test_validate_legacy_definition(self):
        def validate(flow_def: dict, expected_error: str):
            with self.assertRaises(ValueError) as cm:
                FlowRevision.validate_legacy_definition(flow_def)
            self.assertEqual(expected_error, str(cm.exception))

        validate({"flow_type": "U", "nodes": []}, "unsupported flow type")
        validate(self.load_json("test_flows/legacy/invalid/not_fully_localized.json"), "non-localized flow definition")

        # base_language of null, but spec version 8
        validate(self.load_json("test_flows/legacy/invalid/no_base_language_v8.json"), "non-localized flow definition")

        # base_language of 'eng' but non localized actions
        validate(
            self.load_json("test_flows/legacy/invalid/non_localized_with_language.json"),
            "non-localized flow definition",
        )

        validate(
            self.load_json("test_flows/legacy/invalid/non_localized_ruleset.json"), "non-localized flow definition"
        )

    def test_trim_revisions(self):
        start = timezone.now()

        flow1 = self.create_flow("Flow 1")
        flow2 = self.create_flow("Flow 2")

        revision = 100
        FlowRevision.objects.all().update(revision=revision)

        # create a single old clinic revision
        FlowRevision.objects.create(
            flow=flow2,
            definition=dict(),
            revision=99,
            created_on=timezone.now() - timedelta(days=7),
            created_by=self.admin,
        )

        # make a bunch of revisions for flow 1 on the same day
        created = timezone.now().replace(hour=6) - timedelta(days=1)
        for i in range(25):
            revision -= 1
            created = created - timedelta(minutes=1)
            FlowRevision.objects.create(
                flow=flow1, definition=dict(), revision=revision, created_by=self.admin, created_on=created
            )

        # then for 5 days prior, make a few more — alternate authors and tag the changes so
        # we can verify the trim merges changes and falls back to the system user when the
        # absorbed revisions span multiple authors
        day_keepers = []  # ids of the revisions we expect trim to keep on each prior day
        for i in range(5):
            created = created - timedelta(days=1)
            for j in range(10):
                revision -= 1
                created = created - timedelta(minutes=1)
                rev = FlowRevision.objects.create(
                    flow=flow1,
                    definition=dict(),
                    revision=revision,
                    created_by=self.editor if j % 2 == 0 else self.admin,
                    changes={"tags": [f"tag{j}"]},
                    created_on=created,
                )
                # j=0 has the latest created_on within the day (loop walks back in time)
                if j == 0:
                    day_keepers.append(rev.id)

        # trim our flow revisions, should be left with original (today), 25 from yesterday, 1 per day for 5 days = 31
        self.assertEqual(76, FlowRevision.objects.filter(flow=flow1).count())
        self.assertEqual(45, FlowRevision.trim(start))
        self.assertEqual(31, FlowRevision.objects.filter(flow=flow1).count())
        self.assertEqual(
            7,
            FlowRevision.objects.filter(flow=flow1)
            .annotate(created_date=TruncDate("created_on"))
            .distinct("created_date")
            .count(),
        )

        # the kept rev for each prior day should be the latest one (highest created_on),
        # have absorbed every tag from the deleted siblings, and be attributed to the
        # system user since the absorbed work spanned both admin and editor
        system_user = User.get_system_user()
        expected_tags = [f"tag{j}" for j in range(10)]
        for keeper_id in day_keepers:
            keeper = FlowRevision.objects.get(id=keeper_id)
            self.assertEqual(expected_tags, keeper.changes["tags"])
            self.assertEqual(system_user, keeper.created_by)

        # trim our clinic flow manually, should remain unchanged
        self.assertEqual(2, FlowRevision.objects.filter(flow=flow2).count())
        self.assertEqual(0, FlowRevision.trim_for_flow(flow2.id))
        self.assertEqual(2, FlowRevision.objects.filter(flow=flow2).count())

        # call our task
        trim_flow_revisions()
        self.assertEqual(2, FlowRevision.objects.filter(flow=flow2).count())
        self.assertEqual(31, FlowRevision.objects.filter(flow=flow1).count())

        # call again (testing reading cache key)
        trim_flow_revisions()
        self.assertEqual(2, FlowRevision.objects.filter(flow=flow2).count())
        self.assertEqual(31, FlowRevision.objects.filter(flow=flow1).count())

    def test_trim_revisions_keeps_last_24h(self):
        # revisions from the last 24 hours are protected from collapsing even when there
        # are well more than 25 of them
        flow = self.create_flow("Flow 1")
        FlowRevision.objects.filter(flow=flow).update(revision=100)

        # 40 revisions all within the last 24h, spread across two calendar days
        created = timezone.now() - timedelta(minutes=1)
        revision = 100
        for i in range(40):
            revision -= 1
            created = created - timedelta(minutes=30)
            FlowRevision.objects.create(
                flow=flow, definition=dict(), revision=revision, created_by=self.admin, created_on=created
            )

        self.assertEqual(41, FlowRevision.objects.filter(flow=flow).count())
        self.assertEqual(0, FlowRevision.trim_for_flow(flow.id))
        self.assertEqual(41, FlowRevision.objects.filter(flow=flow).count())
