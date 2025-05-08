from django.urls import reverse

from temba.contacts.models import ContactExport
from temba.notifications.types.builtin import ExportFinishedNotificationType
from temba.tests import CRUDLTestMixin, TembaTest


class NotificationCRUDLTest(TembaTest, CRUDLTestMixin):
    def test_read(self):
        export = ContactExport.create(self.org, self.editor)
        export.perform()

        ExportFinishedNotificationType.create(export)

        notification = self.editor.notifications.get(export=export, is_seen=False)

        read_url = reverse("notifications.notification_read", args=[notification.id])

        self.assertRequestDisallowed(read_url, [None, self.admin])

        self.login(self.editor)
        response = self.client.get(read_url)
        self.assertRedirect(response, f"/export/download/{export.uuid}/")

        notification.refresh_from_db()
        self.assertTrue(notification.is_seen)
