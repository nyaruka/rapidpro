from datetime import date

from django.db.models import Sum

from temba.tests import MigrationTest
from temba.tickets.models import Ticket, TicketDailyCount


class BackfillNewDailyCounts(MigrationTest):
    app = "tickets"
    migrate_from = "0074_squashed"
    migrate_to = "0075_backfill_new_daily_counts"

    def setUpBeforeMigration(self, apps):
        # need to create some tickets because migration noops if no tickets exist for an org
        contact = self.create_contact("Bob", phone="+1234567890")
        self.org.tickets.create(contact=contact, topic=self.org.default_ticket_topic, status=Ticket.STATUS_OPEN)
        self.org2.tickets.create(contact=contact, topic=self.org2.default_ticket_topic, status=Ticket.STATUS_OPEN)

        TicketDailyCount.objects.create(day="2025-04-01", count_type="O", scope=f"o:{self.org.id}", count=5)
        TicketDailyCount.objects.create(day="2025-04-01", count_type="O", scope=f"o:{self.org.id}", count=1)
        TicketDailyCount.objects.create(
            day="2025-04-01", count_type="A", scope=f"o:{self.org.id}:u:{self.admin.id}", count=2
        )
        TicketDailyCount.objects.create(
            day="2025-04-01", count_type="A", scope=f"o:{self.org.id}:u:{self.agent.id}", count=3
        )
        TicketDailyCount.objects.create(
            day="2025-04-01", count_type="R", scope=f"o:{self.org.id}:u:{self.admin.id}", count=1
        )
        TicketDailyCount.objects.create(
            day="2025-04-01", count_type="R", scope=f"o:{self.org.id}:u:{self.agent.id}", count=2
        )
        TicketDailyCount.objects.create(
            day="2025-04-01", count_type="R", scope=f"t:{self.org.default_ticket_team.id}", count=2  # ignored
        )

        TicketDailyCount.objects.create(day="2025-04-02", count_type="O", scope=f"o:{self.org.id}", count=10)

        TicketDailyCount.objects.create(day="2025-04-02", count_type="O", scope=f"o:{self.org2.id}", count=7)

        # existing new daily counts blown away
        self.org.daily_counts.create(day="2025-04-01", scope="tickets:opened", count=6)

        # unless they're for unrelated scopes
        self.org.daily_counts.create(day="2025-04-01", scope="foo:bar", count=123)

    def test_migration(self):
        def assert_daily_counts(org, expected: list):
            actual = org.daily_counts.values("day", "scope").annotate(total=Sum("count")).order_by("day", "scope")
            self.assertEqual(list(actual), expected)

        assert_daily_counts(
            self.org,
            [
                {"day": date(2025, 4, 1), "scope": "foo:bar", "total": 123},
                {"day": date(2025, 4, 1), "scope": f"msgs:ticketreplies:0:{self.admin.id}", "total": 1},
                {
                    "day": date(2025, 4, 1),
                    "scope": f"msgs:ticketreplies:{self.org.default_ticket_team.id}:{self.agent.id}",
                    "total": 2,
                },
                {"day": date(2025, 4, 1), "scope": f"tickets:assigned:0:{self.admin.id}", "total": 2},
                {
                    "day": date(2025, 4, 1),
                    "scope": f"tickets:assigned:{self.org.default_ticket_team.id}:{self.agent.id}",
                    "total": 3,
                },
                {"day": date(2025, 4, 1), "scope": "tickets:opened", "total": 6},
                {"day": date(2025, 4, 2), "scope": "tickets:opened", "total": 10},
            ],
        )
        assert_daily_counts(
            self.org2,
            [
                {"day": date(2025, 4, 2), "scope": "tickets:opened", "total": 7},
            ],
        )
