from datetime import date, timedelta

from django.core.files.storage import default_storage
from django.utils import timezone

from temba.orgs.models import Export
from temba.orgs.tasks import trim_exports
from temba.tests import TembaTest
from temba.tickets.models import TicketExport


class ExportTest(TembaTest):
    def test_trim_task(self):
        export1 = TicketExport.create(
            self.org, self.admin, start_date=date.today() - timedelta(days=7), end_date=date.today(), with_fields=()
        )
        export2 = TicketExport.create(
            self.org, self.admin, start_date=date.today() - timedelta(days=7), end_date=date.today(), with_fields=()
        )
        export1.perform()
        export2.perform()

        self.assertTrue(default_storage.exists(export1.path))
        self.assertTrue(default_storage.exists(export2.path))

        # make export 1 look old
        export1.created_on = timezone.now() - timedelta(days=100)
        export1.save(update_fields=("created_on",))

        trim_exports()

        self.assertFalse(Export.objects.filter(id=export1.id).exists())
        self.assertTrue(Export.objects.filter(id=export2.id).exists())

        self.assertFalse(default_storage.exists(export1.path))
        self.assertTrue(default_storage.exists(export2.path))
