from datetime import date

from temba.orgs.models import OrgMembership, OrgRole
from temba.tests import TembaTest
from temba.tickets.models import Team, TicketDailyCount, export_ticket_stats


class TicketDailyCountTest(TembaTest):
    def test_model(self):
        sales = Team.create(self.org, self.admin, "Sales")
        self.org.add_user(self.agent, OrgRole.AGENT, team=sales)
        self.org.add_user(self.editor, OrgRole.AGENT, team=sales)

        self._record_opening(self.org, date(2022, 4, 30))
        self._record_opening(self.org, date(2022, 5, 3))
        self._record_assignment(self.org, self.admin, date(2022, 5, 3))
        self._record_reply(self.org, self.admin, date(2022, 5, 3))

        self._record_reply(self.org, self.editor, date(2022, 5, 4))
        self._record_reply(self.org, self.agent, date(2022, 5, 4))

        self._record_reply(self.org, self.admin, date(2022, 5, 5))
        self._record_reply(self.org, self.admin, date(2022, 5, 5))
        self._record_opening(self.org, date(2022, 5, 5))
        self._record_reply(self.org, self.agent, date(2022, 5, 5))

        def assert_counts():
            # openings tracked at org scope
            self.assertEqual(3, TicketDailyCount.get_by_org(self.org, TicketDailyCount.TYPE_OPENING).total())
            self.assertEqual(
                2, TicketDailyCount.get_by_org(self.org, TicketDailyCount.TYPE_OPENING, since=date(2022, 5, 1)).total()
            )
            self.assertEqual(
                1, TicketDailyCount.get_by_org(self.org, TicketDailyCount.TYPE_OPENING, until=date(2022, 5, 1)).total()
            )
            self.assertEqual(0, TicketDailyCount.get_by_org(self.org2, TicketDailyCount.TYPE_OPENING).total())
            self.assertEqual(
                [(date(2022, 4, 30), 1), (date(2022, 5, 3), 1), (date(2022, 5, 5), 1)],
                TicketDailyCount.get_by_org(self.org, TicketDailyCount.TYPE_OPENING).day_totals(),
            )
            self.assertEqual(
                [(4, 1), (5, 2)], TicketDailyCount.get_by_org(self.org, TicketDailyCount.TYPE_OPENING).month_totals()
            )

            # assignments tracked at org+user scope
            self.assertEqual(
                1, TicketDailyCount.get_by_users(self.org, [self.admin], TicketDailyCount.TYPE_ASSIGNMENT).total()
            )
            self.assertEqual(
                0, TicketDailyCount.get_by_users(self.org, [self.agent], TicketDailyCount.TYPE_ASSIGNMENT).total()
            )
            self.assertEqual(
                {self.admin: 1, self.agent: 0},
                TicketDailyCount.get_by_users(
                    self.org, [self.admin, self.agent], TicketDailyCount.TYPE_ASSIGNMENT
                ).scope_totals(),
            )
            self.assertEqual(
                [(date(2022, 5, 3), 1)],
                TicketDailyCount.get_by_users(self.org, [self.admin], TicketDailyCount.TYPE_ASSIGNMENT).day_totals(),
            )

            # replies tracked at org scope, team scope and user-in-org scope
            self.assertEqual(6, TicketDailyCount.get_by_org(self.org, TicketDailyCount.TYPE_REPLY).total())
            self.assertEqual(0, TicketDailyCount.get_by_org(self.org2, TicketDailyCount.TYPE_REPLY).total())
            self.assertEqual(3, TicketDailyCount.get_by_teams([sales], TicketDailyCount.TYPE_REPLY).total())
            self.assertEqual(
                3, TicketDailyCount.get_by_users(self.org, [self.admin], TicketDailyCount.TYPE_REPLY).total()
            )
            self.assertEqual(
                1, TicketDailyCount.get_by_users(self.org, [self.editor], TicketDailyCount.TYPE_REPLY).total()
            )
            self.assertEqual(
                2, TicketDailyCount.get_by_users(self.org, [self.agent], TicketDailyCount.TYPE_REPLY).total()
            )

        assert_counts()
        self.assertEqual(19, TicketDailyCount.objects.count())

        TicketDailyCount.squash()

        assert_counts()
        self.assertEqual(14, TicketDailyCount.objects.count())

        workbook = export_ticket_stats(self.org, date(2022, 4, 30), date(2022, 5, 6))
        self.assertEqual(["Tickets"], workbook.sheetnames)
        self.assertExcelRow(
            workbook.active, 1, ["", "Opened", "Replies", "Reply Time (Secs)"] + ["Assigned", "Replies"] * 4
        )
        self.assertExcelRow(workbook.active, 2, [date(2022, 4, 30), 1, 0, "", 0, 0, 0, 0, 0, 0, 0, 0])
        self.assertExcelRow(workbook.active, 3, [date(2022, 5, 1), 0, 0, "", 0, 0, 0, 0, 0, 0, 0, 0])
        self.assertExcelRow(workbook.active, 4, [date(2022, 5, 2), 0, 0, "", 0, 0, 0, 0, 0, 0, 0, 0])
        self.assertExcelRow(workbook.active, 5, [date(2022, 5, 3), 1, 1, "", 1, 1, 0, 0, 0, 0, 0, 0])
        self.assertExcelRow(workbook.active, 6, [date(2022, 5, 4), 0, 2, "", 0, 0, 0, 1, 0, 1, 0, 0])
        self.assertExcelRow(workbook.active, 7, [date(2022, 5, 5), 1, 3, "", 0, 2, 0, 1, 0, 0, 0, 0])

    def _record_opening(self, org, d: date):
        TicketDailyCount.objects.create(count_type=TicketDailyCount.TYPE_OPENING, scope=f"o:{org.id}", day=d, count=1)

    def _record_assignment(self, org, user, d: date):
        TicketDailyCount.objects.create(
            count_type=TicketDailyCount.TYPE_ASSIGNMENT, scope=f"o:{org.id}:u:{user.id}", day=d, count=1
        )

    def _record_reply(self, org, user, d: date):
        TicketDailyCount.objects.create(count_type=TicketDailyCount.TYPE_REPLY, scope=f"o:{org.id}", day=d, count=1)

        team = OrgMembership.objects.get(org=org, user=user).team
        if team:
            TicketDailyCount.objects.create(
                count_type=TicketDailyCount.TYPE_REPLY, scope=f"t:{team.id}", day=d, count=1
            )
        TicketDailyCount.objects.create(
            count_type=TicketDailyCount.TYPE_REPLY, scope=f"o:{org.id}:u:{user.id}", day=d, count=1
        )
