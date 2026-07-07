from temba.tests import MigrationTest


class AddTelSchemeTest(MigrationTest):
    app = "channels"
    migrate_from = "0210_remove_channel_log_policy"
    migrate_to = "0211_add_tel_scheme"

    def setUpBeforeMigration(self, apps):
        # a whatsapp channel without tel -> gains tel scheme and allow_international
        self.wa = self.create_channel("WAC", "WhatsApp", "12345", schemes=["whatsapp"], config={"foo": "bar"})

        # a whatsapp channel that already has tel -> left untouched
        self.wa_tel = self.create_channel(
            "WAC", "WhatsApp+Tel", "23456", schemes=["whatsapp", "tel"], config={"allow_international": False}
        )

        # an unrelated channel type -> never touched
        self.tg = self.create_channel("TG", "Telegram", "34567", schemes=["telegram"], config={})

    def test_migration(self):
        self.wa.refresh_from_db()
        self.assertEqual(["whatsapp", "tel"], self.wa.schemes)
        self.assertEqual({"foo": "bar", "allow_international": True}, self.wa.config)

        # already had tel, so schemes and its existing config are preserved
        self.wa_tel.refresh_from_db()
        self.assertEqual(["whatsapp", "tel"], self.wa_tel.schemes)
        self.assertEqual({"allow_international": False}, self.wa_tel.config)

        # unrelated channel untouched
        self.tg.refresh_from_db()
        self.assertEqual(["telegram"], self.tg.schemes)
        self.assertEqual({}, self.tg.config)
