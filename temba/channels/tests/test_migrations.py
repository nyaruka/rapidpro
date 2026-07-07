from temba.tests import MigrationTest


class AddTelSchemeTest(MigrationTest):
    app = "channels"
    migrate_from = "0210_remove_channel_log_policy"
    migrate_to = "0211_add_tel_scheme"

    def setUpBeforeMigration(self, apps):
        # a whatsapp channel without tel -> gains tel scheme (config left untouched)
        self.wa = self.create_channel("WAC", "WhatsApp", "12345", schemes=["whatsapp"], config={"foo": "bar"})

        # a whatsapp channel that already has tel -> left untouched
        self.wa_tel = self.create_channel(
            "WAC", "WhatsApp+Tel", "23456", schemes=["whatsapp", "tel"], config={"foo": "baz"}
        )

        # an unrelated channel type -> never touched
        self.tg = self.create_channel("TG", "Telegram", "34567", schemes=["telegram"], config={})

    def test_migration(self):
        self.wa.refresh_from_db()
        self.assertEqual(["whatsapp", "tel"], self.wa.schemes)
        self.assertEqual({"foo": "bar"}, self.wa.config)  # config unchanged

        # already had tel, so schemes and config are preserved
        self.wa_tel.refresh_from_db()
        self.assertEqual(["whatsapp", "tel"], self.wa_tel.schemes)
        self.assertEqual({"foo": "baz"}, self.wa_tel.config)

        # unrelated channel untouched
        self.tg.refresh_from_db()
        self.assertEqual(["telegram"], self.tg.schemes)
        self.assertEqual({}, self.tg.config)
