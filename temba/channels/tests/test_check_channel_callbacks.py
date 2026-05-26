from io import StringIO
from unittest.mock import patch

import responses

from django.core.management import call_command
from django.core.management.base import CommandError

from temba.channels.management.commands.check_channel_callbacks import (
    PlivoHandler,
    ViberPublicHandler,
    expected_callback_url,
    urls_equal,
)
from temba.channels.models import Channel
from temba.channels.types.plivo.type import PlivoType
from temba.tests import TembaTest
from temba.utils import json


def run(*args, **kwargs):
    """Run the management command capturing stdout."""
    out = StringIO()
    err = StringIO()
    call_command("check_channel_callbacks", *args, stdout=out, stderr=err, **kwargs)
    return out.getvalue() + err.getvalue()


PLIVO_CONFIG = {
    PlivoType.CONFIG_AUTH_ID: "auth-id",
    PlivoType.CONFIG_AUTH_TOKEN: "auth-token",
    PlivoType.CONFIG_APP_ID: "app-id",
}

PLIVO_GET_URL = "https://api.plivo.com/v1/Account/auth-id/Application/app-id/"
VIBER_GET_URL = "https://chatapi.viber.com/pa/get_account_info"
VIBER_SET_URL = "https://chatapi.viber.com/pa/set_webhook"


class CheckChannelCallbacksTest(TembaTest):
    def setUp(self):
        super().setUp()

        self.plivo = self.create_channel("PL", "Plivo Channel", "+12345550100", config=dict(PLIVO_CONFIG))
        self.viber = self.create_channel(
            "VP", "Viber Channel", "viberAddr", schemes=["viber"], config={"auth_token": "viber-token"}
        )

        self.plivo_expected = expected_callback_url(self.plivo)
        self.viber_expected = expected_callback_url(self.viber)

    def test_helpers(self):
        self.assertTrue(urls_equal("https://a/c/pl/x/receive", "https://a/c/pl/x/receive/"))
        self.assertFalse(urls_equal("https://a/c/pl/x/receive", "https://b/c/pl/x/receive"))
        self.assertFalse(urls_equal(None, "https://a/"))

        self.assertEqual(self.plivo_expected, f"https://app.rapidpro.io/c/pl/{self.plivo.uuid}/receive")
        self.assertEqual(self.viber_expected, f"https://app.rapidpro.io/c/vp/{self.viber.uuid}/receive")

    @responses.activate
    def test_correct_urls_silent(self):
        responses.add(responses.GET, PLIVO_GET_URL, json={"message_url": self.plivo_expected}, status=200)
        responses.add(responses.POST, VIBER_GET_URL, json={"status": 0, "webhook": self.viber_expected}, status=200)

        out = run()

        self.assertIn("Checking 2 channel(s) [DRY-RUN]", out)
        self.assertNotIn("!=", out)
        self.assertNotIn("!!", out)
        self.assertIn("ok=2", out)
        self.assertIn("stale=0", out)
        self.assertIn("errors=0", out)

    @responses.activate
    def test_correct_urls_verbose(self):
        responses.add(responses.GET, PLIVO_GET_URL, json={"message_url": self.plivo_expected}, status=200)
        responses.add(responses.POST, VIBER_GET_URL, json={"status": 0, "webhook": self.viber_expected}, status=200)

        out = run("--verbose")

        self.assertIn("OK", out)
        self.assertIn(str(self.plivo.id), out)
        self.assertIn(str(self.viber.id), out)

    @responses.activate
    def test_stale_url_reported_no_fix(self):
        stale_plivo = "https://www.textit.in/handlers/plivo/receive/" + str(self.plivo.uuid)
        stale_viber = "https://www.rapidpro.io/handlers/viber_public/" + str(self.viber.uuid)
        responses.add(responses.GET, PLIVO_GET_URL, json={"message_url": stale_plivo}, status=200)
        responses.add(responses.POST, VIBER_GET_URL, json={"status": 0, "webhook": stale_viber}, status=200)

        out = run()

        self.assertIn(stale_plivo, out)
        self.assertIn(stale_viber, out)
        self.assertIn(self.plivo_expected, out)
        self.assertIn(self.viber_expected, out)
        self.assertIn("stale=2", out)
        self.assertIn("fixed=0", out)

        # no fix calls should have happened — only the GETs
        self.assertEqual(len(responses.calls), 2)

    @responses.activate
    def test_fix_plivo_calls_update_endpoint(self):
        stale = "https://www.textit.in/handlers/plivo/receive/" + str(self.plivo.uuid)
        # 1) initial GET → stale
        responses.add(responses.GET, PLIVO_GET_URL, json={"message_url": stale}, status=200)
        # 2) POST to update
        responses.add(responses.POST, PLIVO_GET_URL, json={"message": "changed"}, status=202)
        # 3) GET to verify → now expected
        responses.add(responses.GET, PLIVO_GET_URL, json={"message_url": self.plivo_expected}, status=200)

        out = run("--fix", "--channel-type", "PL")

        self.assertIn("fixed=1", out)
        self.assertIn("errors=0", out)
        self.assertIn(f"fixed -> {self.plivo_expected}", out)

        post_calls = [c for c in responses.calls if c.request.method == "POST"]
        self.assertEqual(len(post_calls), 1)
        body = json.loads(post_calls[0].request.body)
        self.assertEqual(body, {"message_url": self.plivo_expected})
        # basic auth header should be present
        self.assertIn("Authorization", post_calls[0].request.headers)

    @responses.activate
    def test_fix_viber_preserves_event_types(self):
        stale = "https://www.rapidpro.io/handlers/viber_public/" + str(self.viber.uuid)
        configured_events = ["delivered", "subscribed", "unsubscribed"]
        # get_account_info: initial fetch (stale) + pre-set fetch (still stale) + post-set verify (correct)
        responses.add(
            responses.POST,
            VIBER_GET_URL,
            json={"status": 0, "webhook": stale, "event_types": configured_events},
            status=200,
        )
        responses.add(
            responses.POST,
            VIBER_GET_URL,
            json={"status": 0, "webhook": stale, "event_types": configured_events},
            status=200,
        )
        responses.add(
            responses.POST,
            VIBER_SET_URL,
            json={"status": 0, "status_message": "ok"},
            status=200,
        )
        responses.add(
            responses.POST,
            VIBER_GET_URL,
            json={"status": 0, "webhook": self.viber_expected, "event_types": configured_events},
            status=200,
        )

        out = run("--fix", "--channel-type", "VP")

        self.assertIn("fixed=1", out)
        self.assertIn("errors=0", out)

        set_calls = [c for c in responses.calls if c.request.url == VIBER_SET_URL]
        self.assertEqual(len(set_calls), 1)
        body = json.loads(set_calls[0].request.body)
        self.assertEqual(body["url"], self.viber_expected)
        self.assertEqual(body["event_types"], configured_events)
        self.assertTrue(body["send_name"])
        self.assertTrue(body["send_photo"])
        self.assertEqual(set_calls[0].request.headers.get("X-Viber-Auth-Token"), "viber-token")

    @responses.activate
    def test_api_error_does_not_crash(self):
        # plivo fails, viber succeeds
        responses.add(responses.GET, PLIVO_GET_URL, status=500, body="boom")
        responses.add(
            responses.POST,
            VIBER_GET_URL,
            json={"status": 0, "webhook": self.viber_expected},
            status=200,
        )

        out = run()

        self.assertIn("could not check", out)
        self.assertIn("errors=1", out)
        self.assertIn("ok=1", out)
        self.assertIn("checked=2", out)

    @responses.activate
    def test_viber_api_status_nonzero_is_error(self):
        responses.add(responses.GET, PLIVO_GET_URL, json={"message_url": self.plivo_expected}, status=200)
        responses.add(
            responses.POST,
            VIBER_GET_URL,
            json={"status": 3, "status_message": "Invalid auth token"},
            status=200,
        )

        out = run()

        self.assertIn("Invalid auth token", out)
        self.assertIn("errors=1", out)

    def test_filter_by_org(self):
        # other org has a plivo channel that should be excluded
        self.create_channel("PL", "Other", "+12025550111", org=self.org2, config=dict(PLIVO_CONFIG))

        with patch("requests.get") as g:
            g.return_value = _mock_response(200, {"message_url": self.plivo_expected})
            with patch("requests.post") as p:
                p.return_value = _mock_response(200, {"status": 0, "webhook": self.viber_expected})

                out = run("--org", str(self.org.id))

        self.assertIn("Checking 2 channel(s)", out)  # only this org's PL + VP, not org2's

    def test_filter_by_channel(self):
        with patch("requests.get") as g:
            g.return_value = _mock_response(200, {"message_url": self.plivo_expected})

            out = run("--channel", str(self.plivo.uuid), "--channel-type", "PL")

        self.assertIn("Checking 1 channel(s)", out)
        self.assertIn("ok=1", out)

    def test_suspended_org_skipped(self):
        self.org.is_suspended = True
        self.org.save(update_fields=("is_suspended",))

        out = run()

        self.assertIn("Checking 0 channel(s)", out)

    def test_inactive_channel_skipped(self):
        self.plivo.is_active = False
        self.plivo.save(update_fields=("is_active",))
        self.viber.is_active = False
        self.viber.save(update_fields=("is_active",))

        out = run()

        self.assertIn("Checking 0 channel(s)", out)

    def test_unknown_channel_type_errors(self):
        with self.assertRaises(CommandError):
            run("--channel-type", "NONESUCH")

    def test_unknown_org_errors(self):
        with self.assertRaises(CommandError):
            run("--org", "999999")

    def test_missing_plivo_config_reported_as_error(self):
        self.plivo.config = {}
        self.plivo.save(update_fields=("config",))

        # no viber channel queries either, just make sure plivo is the one with the error
        with patch("requests.post") as p:
            p.return_value = _mock_response(200, {"status": 0, "webhook": self.viber_expected})
            out = run()

        self.assertIn("missing config key", out)
        self.assertIn("errors=1", out)


class HandlerTest(TembaTest):
    def setUp(self):
        super().setUp()
        self.plivo = self.create_channel("PL", "Plivo Channel", "+12345550100", config=dict(PLIVO_CONFIG))
        self.viber = self.create_channel(
            "VP", "Viber Channel", "viberAddr", schemes=["viber"], config={"auth_token": "viber-token"}
        )

    @responses.activate
    def test_plivo_get_current_non_json(self):
        responses.add(responses.GET, PLIVO_GET_URL, body="not json", status=200)
        from temba.channels.management.commands.check_channel_callbacks import CallbackCheckError

        with self.assertRaises(CallbackCheckError):
            PlivoHandler.get_current(self.plivo)

    @responses.activate
    def test_viber_set_webhook_falls_back_to_defaults_when_account_info_unavailable(self):
        # First account-info fetch fails (used as preserve-events fetch), set still proceeds with defaults
        responses.add(responses.POST, VIBER_GET_URL, status=500, body="boom")
        responses.add(responses.POST, VIBER_SET_URL, json={"status": 0, "status_message": "ok"}, status=200)

        ViberPublicHandler.set_callback(self.viber, "https://example/c/vp/x/receive")

        set_calls = [c for c in responses.calls if c.request.url == VIBER_SET_URL]
        body = json.loads(set_calls[0].request.body)
        self.assertEqual(body["event_types"], ViberPublicHandler.DEFAULT_EVENT_TYPES)


def _mock_response(status, body):
    """Build a minimal requests.Response stand-in for tests that patch the requests funcs directly."""
    from unittest.mock import Mock

    m = Mock()
    m.status_code = status
    m.text = json.dumps(body) if isinstance(body, (dict, list)) else str(body)
    m.json.return_value = body if isinstance(body, (dict, list)) else {}
    return m


# touch reactivate_fb_channels import to ensure new module doesn't break sibling commands
_ = Channel
