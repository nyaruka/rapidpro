from datetime import date, datetime, timedelta

from django.conf import settings
from django.urls import reverse

from temba.contacts.models import ContactExport
from temba.flows.models import ResultsExport
from temba.msgs.models import MessageExport
from temba.tests import TembaTest
from temba.tests.crudl import CRUDLTestMixin
from temba.tickets.models import TicketExport


class ExportCRUDLTest(TembaTest, CRUDLTestMixin):
    def test_download_contact_export(self):
        group = self.create_group("Testers", contacts=[])
        export = ContactExport.create(self.org, self.admin, group=group)
        export.perform()

        download_url = reverse("orgs.export_download", kwargs={"uuid": export.uuid})
        self.assertEqual(f"/export/download/{export.uuid}/", download_url)

        self.assertRequestDisallowed(download_url, [None, self.agent])
        response = self.assertReadFetch(download_url, [self.editor, self.admin])
        self.assertContains(response, "Testers")

        raw_url = export.get_raw_url()
        self.assertIn(f"{settings.STORAGE_URL}/orgs/{self.org.id}/contact_exports/{export.uuid}.xlsx", raw_url)
        self.assertIn(f"contacts_{datetime.today().strftime(r'%Y%m%d')}.xlsx", raw_url)

        response = self.client.get(download_url + "?raw=1")
        self.assertRedirect(response, f"/test-default/orgs/{self.org.id}/contact_exports/{export.uuid}.xlsx")

    def test_download_message_export(self):
        label = self.create_label("Sales")
        export = MessageExport.create(
            self.org, self.editor, start_date=date.today(), end_date=date.today(), label=label
        )
        export.perform()

        download_url = reverse("orgs.export_download", kwargs={"uuid": export.uuid})
        self.assertEqual(f"/export/download/{export.uuid}/", download_url)

        self.assertRequestDisallowed(download_url, [None, self.agent])
        response = self.assertReadFetch(download_url, [self.editor, self.admin])
        self.assertContains(response, "Sales")

        raw_url = export.get_raw_url()
        self.assertIn(f"{settings.STORAGE_URL}/orgs/{self.org.id}/message_exports/{export.uuid}.xlsx", raw_url)
        self.assertIn(f"messages_{datetime.today().strftime(r'%Y%m%d')}.xlsx", raw_url)

        response = self.client.get(download_url + "?raw=1")
        self.assertRedirect(response, f"/test-default/orgs/{self.org.id}/message_exports/{export.uuid}.xlsx")

    def test_download_results_export(self):
        flow1 = self.create_flow("Test Flow 1")
        flow2 = self.create_flow("Test Flow 2")
        export = ResultsExport.create(
            self.org,
            self.editor,
            start_date=date.today(),
            end_date=date.today(),
            flows=[flow1, flow2],
            with_fields=(),
            with_groups=(),
            responded_only=True,
            extra_urns=(),
        )
        export.perform()

        download_url = reverse("orgs.export_download", kwargs={"uuid": export.uuid})
        self.assertEqual(f"/export/download/{export.uuid}/", download_url)

        self.assertRequestDisallowed(download_url, [None, self.agent])
        response = self.assertReadFetch(download_url, [self.editor, self.admin])
        self.assertContains(response, "Test Flow 1")
        self.assertContains(response, "Test Flow 2")

        raw_url = export.get_raw_url()
        self.assertIn(f"{settings.STORAGE_URL}/orgs/{self.org.id}/results_exports/{export.uuid}.xlsx", raw_url)
        self.assertIn(f"results_{datetime.today().strftime(r'%Y%m%d')}.xlsx", raw_url)

        response = self.client.get(download_url + "?raw=1")
        self.assertRedirect(response, f"/test-default/orgs/{self.org.id}/results_exports/{export.uuid}.xlsx")

    def test_download_ticket_export(self):
        export = TicketExport.create(
            self.org, self.admin, start_date=date.today() - timedelta(days=7), end_date=date.today(), with_fields=()
        )
        export.perform()

        download_url = reverse("orgs.export_download", kwargs={"uuid": export.uuid})
        self.assertEqual(f"/export/download/{export.uuid}/", download_url)

        self.assertRequestDisallowed(download_url, [None, self.agent])
        self.assertReadFetch(download_url, [self.editor, self.admin])

        raw_url = export.get_raw_url()
        self.assertIn(f"{settings.STORAGE_URL}/orgs/{self.org.id}/ticket_exports/{export.uuid}.xlsx", raw_url)
        self.assertIn(f"tickets_{datetime.today().strftime(r'%Y%m%d')}.xlsx", raw_url)

        response = self.client.get(download_url + "?raw=1")
        self.assertRedirect(response, f"/test-default/orgs/{self.org.id}/ticket_exports/{export.uuid}.xlsx")
