from datetime import date
from io import StringIO

from django.core.management import call_command

from temba.archives.models import Archive
from temba.tests import TembaTest


class SearchArchivesTest(TembaTest):
    def test_command(self):
        self.create_archive(
            Archive.TYPE_FLOWRUN,
            "D",
            date(2020, 8, 1),
            [{"id": 1, "created_on": "2020-07-30T10:00:00Z"}, {"id": 2, "created_on": "2020-07-30T15:00:00Z"}],
        )

        out = StringIO()
        call_command("search_archives", self.org.id, "run", where="", limit=10, stdout=out)

        self.assertIn('"id": 1', out.getvalue())
        self.assertIn("Fetched 2 records in", out.getvalue())


class ArchivesToHistoryTest(TembaTest):
    def test_command(self):
        # run archive should be ignored
        self.create_archive(
            Archive.TYPE_FLOWRUN,
            "D",
            date(2025, 8, 1),
            [{"id": 1, "created_on": "2020-07-30T10:00:00Z"}, {"id": 2, "created_on": "2020-07-30T15:00:00Z"}],
        )

        # message archive with old types
        self.create_archive(
            Archive.TYPE_MSG,
            "D",
            date(2015, 1, 1),
            [
                {
                    # regular incoming message
                    "id": 1,
                    "broadcast": None,
                    "contact": {"uuid": "dbe1460e-7e97-4db4-9944-3d8d20792a2d", "name": "Ann"},
                    "urn": "twitter:kinyarwandanet",
                    "channel": {"uuid": "d0c17405-a902-4a06-8fb8-5b067a582283", "name": "@rowanseymour"},
                    "direction": "in",
                    "type": "inbox",
                    "status": "handled",
                    "visibility": "visible",
                    "text": "sawa",
                    "attachments": [],
                    "labels": [],
                    "created_on": "2014-11-04T23:50:31+00:00",
                    "sent_on": None,
                    "modified_on": "2014-11-04T23:50:33.052089+00:00",
                },
                {
                    # IVR incoming message
                    "id": 2,
                    "broadcast": None,
                    "contact": {"uuid": "c33599af-2d97-4299-904d-2ea2d50921bb", "name": "Bob"},
                    "urn": "tel:+1234567890",
                    "channel": {"uuid": "d0c17405-a902-4a06-8fb8-5b067a582283", "name": "Twilio"},
                    "direction": "in",
                    "type": "ivr",
                    "status": "handled",
                    "visibility": "visible",
                    "text": "who's there?",
                    "attachments": [],
                    "labels": [],
                    "created_on": "2014-11-04T23:50:31+00:00",
                    "sent_on": None,
                    "modified_on": "2014-11-04T23:50:33.052089+00:00",
                },
                {
                    # old surveyor style message with no channel and no urn
                    "id": 3,
                    "broadcast": None,
                    "contact": {"uuid": "b9f65adb-efa4-4497-8527-7a7ff02df99c", "name": "Cat"},
                    "urn": None,
                    "channel": None,
                    "direction": "in",
                    "type": "flow",
                    "status": "handled",
                    "visibility": "visible",
                    "text": "sawa 2",
                    "attachments": [],
                    "labels": [],
                    "created_on": "2014-11-04T23:50:31+00:00",
                    "sent_on": None,
                    "modified_on": "2014-11-04T23:50:33.052089+00:00",
                },
            ],
        )

        # message archive with new types
        self.create_archive(
            Archive.TYPE_MSG,
            "D",
            date(2025, 1, 1),
            [
                {
                    # unsendable message (no urn or channel)
                    "id": 5297,
                    "broadcast": 107746936,
                    "contact": {"uuid": "d1f205ca-b299-4f41-8fb9-c19cbdb758e9", "name": "Rowan"},
                    "urn": None,
                    "channel": None,
                    "flow": None,
                    "direction": "out",
                    "type": "text",
                    "status": "failed",
                    "visibility": "visible",
                    "text": "Testing",
                    "attachments": [],
                    "labels": [],
                    "created_on": "2025-04-02T17:00:02.931134+00:00",
                    "sent_on": None,
                    "modified_on": "2025-04-02T17:00:02.931523+00:00",
                },
                {
                    "id": 5307,
                    "broadcast": 23564,
                    "contact": {"uuid": "a32d1f60-eb92-49c7-9161-4dd78e6a8b9e", "name": "Rowan"},
                    "urn": "telegram:742307595",
                    "channel": {"uuid": "ce4959aa-8c85-41a4-b53e-14c3f6852f90", "name": "RapidPro Test"},
                    "flow": {"uuid": "448bb9d0-af76-4657-96b5-aa033805542d", "name": "Post Deploy Child"},
                    "direction": "out",
                    "type": "text",
                    "status": "wired",
                    "visibility": "visible",
                    "text": "A cat uses its whiskers for measuring distances.",
                    "attachments": [],
                    "labels": [],
                    "created_on": "2025-04-08T14:52:49.053541+00:00",
                    "sent_on": "2025-04-08T14:52:53.773715+00:00",
                    "modified_on": "2025-04-08T14:52:53.773715+00:00",
                },
            ],
        )

        # update 2015 archives
        output = self._call(
            "archives_to_history", "update", "--org", str(self.org.id), "--since", "2015-01-01", "--until", "2015-12-31"
        )
        self.assertIn("updating archives for 'Nyaruka'", output)
        self.assertIn("rewriting D@2015-01-01", output)
        self.assertIn("OK (3 records, 3 updated)", output)

        # can run again and no updates needed
        # output = self._call(
        #    "archives_to_history", "update", "--org", str(self.org.id), "--since", "2015-01-01", "--until", "2015-12-31"
        # )
        # self.assertIn("updating archives for 'Nyaruka'", output)
        # self.assertIn("rewriting D@2015-01-01", output)
        # self.assertIn("OK (3 records, 0 updated)", output)

        # update 2025 archives
        output = self._call(
            "archives_to_history", "update", "--org", str(self.org.id), "--since", "2025-01-01", "--until", "2025-12-31"
        )
        self.assertIn("updating archives for 'Nyaruka'", output)
        self.assertIn("rewriting D@2025-01-01", output)
        self.assertIn("OK (2 records, 2 updated)", output)

    def _call(self, cmd, *args) -> str:
        out = StringIO()
        call_command(cmd, *args, stdout=out)
        return out.getvalue()
