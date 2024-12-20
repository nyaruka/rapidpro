from datetime import date

from temba.tests import TembaTest
from temba.tickets.models import TicketDailyTiming, export_ticket_stats
from temba.tickets.tasks import squash_ticket_counts


class TicketDailyTimingTest(TembaTest):
    def test_model(self):
        self._record_first_reply(self.org, date(2022, 4, 30), 60)
        self._record_first_reply(self.org, date(2022, 5, 1), 60)
        self._record_first_reply(self.org, date(2022, 5, 1), 120)
        self._record_first_reply(self.org, date(2022, 5, 1), 180)
        self._record_first_reply(self.org, date(2022, 5, 2), 11)
        self._record_first_reply(self.org, date(2022, 5, 2), 70)
        self._record_last_close(self.org, date(2022, 5, 1), 100)
        self._record_last_close(self.org, date(2022, 5, 1), 100, undo=True)
        self._record_last_close(self.org, date(2022, 5, 1), 200)
        self._record_last_close(self.org, date(2022, 5, 1), 300)
        self._record_last_close(self.org, date(2022, 5, 2), 100)

        def assert_timings():
            self.assertEqual(6, TicketDailyTiming.get_by_org(self.org, TicketDailyTiming.TYPE_FIRST_REPLY).total())
            self.assertEqual(
                [(date(2022, 4, 30), 1), (date(2022, 5, 1), 3), (date(2022, 5, 2), 2)],
                TicketDailyTiming.get_by_org(self.org, TicketDailyTiming.TYPE_FIRST_REPLY).day_totals(),
            )
            self.assertEqual(
                [(date(2022, 4, 30), 60.0), (date(2022, 5, 1), 120.0), (date(2022, 5, 2), 40.5)],
                TicketDailyTiming.get_by_org(self.org, TicketDailyTiming.TYPE_FIRST_REPLY).day_averages(rounded=False),
            )

            self.assertEqual(3, TicketDailyTiming.get_by_org(self.org, TicketDailyTiming.TYPE_LAST_CLOSE).total())
            self.assertEqual(
                [(date(2022, 5, 1), 2), (date(2022, 5, 2), 1)],
                TicketDailyTiming.get_by_org(self.org, TicketDailyTiming.TYPE_LAST_CLOSE).day_totals(),
            )
            self.assertEqual(
                [(date(2022, 5, 1), 250.0), (date(2022, 5, 2), 100.0)],
                TicketDailyTiming.get_by_org(self.org, TicketDailyTiming.TYPE_LAST_CLOSE).day_averages(),
            )

        assert_timings()

        squash_ticket_counts()

        assert_timings()

        workbook = export_ticket_stats(self.org, date(2022, 4, 30), date(2022, 5, 4))
        self.assertEqual(["Tickets"], workbook.sheetnames)
        self.assertExcelRow(
            workbook.active, 1, ["", "Opened", "Replies", "Reply Time (Secs)"] + ["Assigned", "Replies"] * 4
        )
        self.assertExcelRow(workbook.active, 2, [date(2022, 4, 30), 0, 0, 60, 0, 0, 0, 0, 0, 0, 0, 0])
        self.assertExcelRow(workbook.active, 3, [date(2022, 5, 1), 0, 0, 120, 0, 0, 0, 0, 0, 0, 0, 0])
        self.assertExcelRow(workbook.active, 4, [date(2022, 5, 2), 0, 0, 40, 0, 0, 0, 0, 0, 0, 0, 0])
        self.assertExcelRow(workbook.active, 5, [date(2022, 5, 3), 0, 0, "", 0, 0, 0, 0, 0, 0, 0, 0])

    def _record_first_reply(self, org, d: date, seconds: int):
        TicketDailyTiming.objects.create(
            count_type=TicketDailyTiming.TYPE_FIRST_REPLY, scope=f"o:{org.id}", day=d, count=1, seconds=seconds
        )

    def _record_last_close(self, org, d: date, seconds: int, undo: bool = False):
        count, seconds = (-1, -seconds) if undo else (1, seconds)

        TicketDailyTiming.objects.create(
            count_type=TicketDailyTiming.TYPE_LAST_CLOSE, scope=f"o:{org.id}", day=d, count=count, seconds=seconds
        )
