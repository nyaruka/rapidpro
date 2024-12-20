from datetime import date, datetime, timedelta

from django.conf import settings
from django.urls import reverse

from temba.tests import TembaTest
from temba.tickets.models import TicketExport


class ExportCRUDLTest(TembaTest):
    def test_download(self):
        export = TicketExport.create(
            self.org, self.admin, start_date=date.today() - timedelta(days=7), end_date=date.today(), with_fields=()
        )
        export.perform()

        self.assertEqual(1, self.admin.notifications.filter(notification_type="export:finished", is_seen=False).count())

        download_url = reverse("orgs.export_download", kwargs={"uuid": export.uuid})
        self.assertEqual(f"/export/download/{export.uuid}/", download_url)

        raw_url = export.get_raw_url()
        self.assertIn(f"{settings.STORAGE_URL}/orgs/{self.org.id}/ticket_exports/{export.uuid}.xlsx", raw_url)
        self.assertIn(f"tickets_{datetime.today().strftime(r'%Y%m%d')}.xlsx", raw_url)

        response = self.client.get(download_url)
        self.assertLoginRedirect(response)

        # user who didn't create the export and access it...
        self.login(self.editor)
        response = self.client.get(download_url)

        # which doesn't affect admin's notification
        self.assertEqual(1, self.admin.notifications.filter(notification_type="export:finished", is_seen=False).count())

        # but them accessing it will
        self.login(self.admin)
        response = self.client.get(download_url)

        self.assertEqual(0, self.admin.notifications.filter(notification_type="export:finished", is_seen=False).count())

        response = self.client.get(download_url + "?raw=1")
        self.assertRedirect(response, f"/test-default/orgs/{self.org.id}/ticket_exports/{export.uuid}.xlsx")
