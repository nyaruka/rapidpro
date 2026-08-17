from temba.channels.models import Channel
from temba.contacts.models import URN
from temba.notifications.models import Incident
from temba.templates.models import TemplateTranslation
from temba.tests import MigrationTest
from temba.triggers.models import Trigger


class ReleaseLegacyWhatsAppChannelsTest(MigrationTest):
    app = "channels"
    migrate_from = "0214_remove_channelevent_optin"
    migrate_to = "0215_release_legacy_whatsapp_channels"

    def setUpBeforeMigration(self, apps):
        # the legacy types no longer exist so these channels have to be created directly
        self.wa = self._create_legacy_channel("WA", "Legacy WhatsApp", "1234")
        self.d3 = self._create_legacy_channel("D3", "Legacy 360Dialog", "2345")
        self.wac = self.create_channel("WAC", "Cloud WhatsApp", "3456")

        # triggers on both a legacy channel and the cloud channel
        flow = self.create_flow("Test")
        self.wa_trigger = self._create_trigger(flow, self.wa)
        self.wac_trigger = self._create_trigger(flow, self.wac)

        # open incidents on both a legacy channel and the cloud channel
        self.wa_incident = self._create_incident(self.wa)
        self.wac_incident = self._create_incident(self.wac)

        # a template whose base translation is from a legacy channel, and which has a cloud channel translation in the
        # org's primary language with different variables to its other remaining translation
        self.template1 = self.create_template(
            "greeting",
            [
                self._create_translation(self.wa, "eng-US", variables=[{"type": "text"}]),
                self._create_translation(self.wac, "eng-US"),
                self._create_translation(self.wac, "fra", variables=[{"type": "text"}]),
            ],
        )
        self._set_base(self.template1, self.wa, "eng-US")

        # a template whose only remaining translation won't be in the org's primary language
        self.template2 = self.create_template(
            "farewell",
            [self._create_translation(self.d3, "eng-US"), self._create_translation(self.wac, "fra")],
        )
        self._set_base(self.template2, self.d3, "eng-US")

        # a template which only has legacy channel translations
        self.template3 = self.create_template("reminder", [self._create_translation(self.d3, "eng-US")])

    def _create_legacy_channel(self, channel_type: str, name: str, address: str):
        return Channel.objects.create(
            org=self.org,
            channel_type=channel_type,
            name=name,
            address=address,
            config={"fb_namespace": "foo"},
            role=Channel.DEFAULT_ROLE,
            schemes=[URN.WHATSAPP_SCHEME],
            created_by=self.admin,
            modified_by=self.admin,
        )

    def _create_trigger(self, flow, channel):
        return Trigger.objects.create(
            org=self.org,
            trigger_type=Trigger.TYPE_NEW_CONVERSATION,
            flow=flow,
            channel=channel,
            priority=0,
            created_by=self.admin,
            modified_by=self.admin,
        )

    def _create_incident(self, channel):
        return Incident.objects.create(
            org=self.org, incident_type="channel:templates_failed", scope=str(channel.uuid), channel=channel
        )

    def _create_translation(self, channel, locale: str, variables: list = None):
        return TemplateTranslation(
            channel=channel,
            locale=locale,
            status=TemplateTranslation.STATUS_APPROVED,
            external_id="1234",
            external_locale="en_US",
            namespace="",
            components=[{"name": "body", "type": "body/text", "content": "Hi", "variables": {}}],
            variables=variables or [],
        )

    def _set_base(self, template, channel, locale: str):
        template.base_translation = template.translations.get(channel=channel, locale=locale)
        template.save(update_fields=("base_translation",))

        # start with all translations compatible so we can see the migration recalculate them
        template.translations.update(is_compatible=True)

    def test_migration(self):
        self.wa.refresh_from_db()
        self.d3.refresh_from_db()
        self.wac.refresh_from_db()

        self.assertFalse(self.wa.is_active)
        self.assertFalse(self.d3.is_active)
        self.assertTrue(self.wac.is_active)  # not a legacy type so untouched

        self.wa_trigger.refresh_from_db()
        self.wac_trigger.refresh_from_db()

        self.assertFalse(self.wa_trigger.is_active)
        self.assertTrue(self.wa_trigger.is_archived)
        self.assertTrue(self.wac_trigger.is_active)
        self.assertFalse(self.wac_trigger.is_archived)

        self.wa_incident.refresh_from_db()
        self.wac_incident.refresh_from_db()

        self.assertIsNotNone(self.wa_incident.ended_on)
        self.assertIsNone(self.wac_incident.ended_on)

        # translations from the legacy channels are gone, those from the cloud channel remain
        self.assertEqual(0, TemplateTranslation.objects.filter(channel__in=(self.wa, self.d3)).count())
        self.assertEqual(3, TemplateTranslation.objects.filter(channel=self.wac).count())

        # template with a cloud translation in the org's primary language uses that as its new base
        self.template1.refresh_from_db()
        self.assertEqual(self.wac, self.template1.base_translation.channel)
        self.assertEqual("eng-US", self.template1.base_translation.locale)

        # and its remaining translations have had their compatibility recalculated against that new base
        self.assertTrue(self.template1.translations.get(locale="eng-US").is_compatible)
        self.assertFalse(self.template1.translations.get(locale="fra").is_compatible)

        # template without one falls back to its oldest remaining translation
        self.template2.refresh_from_db()
        self.assertEqual(self.wac, self.template2.base_translation.channel)
        self.assertEqual("fra", self.template2.base_translation.locale)

        # template with no remaining translations is left without a base
        self.template3.refresh_from_db()
        self.assertIsNone(self.template3.base_translation)
