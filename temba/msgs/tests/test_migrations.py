from temba.msgs.models import Broadcast
from temba.tests import MigrationTest


class UpdateQuickRepliesTest(MigrationTest):
    app = "msgs"
    migrate_from = "0285_delete_systemlabelcount"
    migrate_to = "0286_update_quick_replies"

    def setUpBeforeMigration(self, apps):
        def create_broadcast(translations, is_active=True):
            return Broadcast.objects.create(org=self.org, translations=translations, is_active=is_active)

        self.bcast1 = create_broadcast(  # active broadcast with quick replies as strings
            {
                "eng": {"text": "Hi there", "quick_replies": ["yes", "no"]},
                "spa": {"text": "Hola", "quick_replies": ["si", "no"]},
            }
        )
        self.bcast2 = create_broadcast(  # active broadcast with quick replies already as objects
            {"eng": {"text": "Hi there", "quick_replies": [{"text": "yes"}, {"text": "no"}]}}
        )
        self.bcast3 = create_broadcast({"eng": {"text": "Hi there"}})  # active broadcast with no quick replies
        self.bcast4 = create_broadcast(  # inactive broadcast with quick replies as strings
            {"eng": {"text": "Hi there", "quick_replies": ["yes", "no"]}},
            is_active=False,
        )

    def test_migration(self):
        def assert_translations(bcast, expected: dict):
            bcast.refresh_from_db()
            self.assertEqual(bcast.translations, expected)

        assert_translations(
            self.bcast1,
            {
                "eng": {"text": "Hi there", "quick_replies": [{"text": "yes"}, {"text": "no"}]},
                "spa": {"text": "Hola", "quick_replies": [{"text": "si"}, {"text": "no"}]},
            },
        )
        assert_translations(
            self.bcast2,
            {"eng": {"text": "Hi there", "quick_replies": [{"text": "yes"}, {"text": "no"}]}},  # unchanged
        )
        assert_translations(self.bcast3, {"eng": {"text": "Hi there"}})  # unchanged
        assert_translations(self.bcast4, {"eng": {"text": "Hi there", "quick_replies": ["yes", "no"]}})  # unchanged
