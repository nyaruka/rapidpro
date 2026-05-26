import requests

from django.core.management.base import BaseCommand, CommandError
from django.urls import reverse

from temba.channels.models import Channel
from temba.channels.types.plivo.type import PlivoType
from temba.orgs.models import Org

HTTP_TIMEOUT = 10

DEFAULT_TYPES = ["PL", "VP"]


class CallbackCheckError(Exception):
    """Raised when we couldn't determine or set the callback URL for a channel."""


class Command(BaseCommand):
    help = "Audits provider-side callback URLs for active channels and optionally fixes them."

    def add_arguments(self, parser):
        parser.add_argument(
            "--channel-type",
            default=",".join(DEFAULT_TYPES),
            help="Comma-separated channel type codes to check (default: PL,VP).",
        )
        parser.add_argument("--org", type=int, help="Restrict to a single org id.")
        parser.add_argument("--channel", help="Restrict to a single channel uuid.")
        parser.add_argument("--fix", action="store_true", help="Update mismatched webhooks via the provider API.")
        parser.add_argument("--verbose", action="store_true", help="Also log channels that are already correct.")

    def handle(self, *args, **options):
        types = [t.strip().upper() for t in options["channel_type"].split(",") if t.strip()]
        unknown = [t for t in types if t not in HANDLERS]
        if unknown:
            raise CommandError(f"Unsupported channel type(s): {', '.join(unknown)}")

        qs = Channel.objects.filter(
            is_active=True,
            channel_type__in=types,
            org__is_active=True,
            org__is_suspended=False,
        ).select_related("org")

        if options["org"]:
            if not Org.objects.filter(id=options["org"]).exists():
                raise CommandError(f"No such org with id {options['org']}")
            qs = qs.filter(org_id=options["org"])

        if options["channel"]:
            qs = qs.filter(uuid=options["channel"])

        qs = qs.order_by("org_id", "id")

        fix = options["fix"]
        verbose = options["verbose"]

        totals = {"checked": 0, "ok": 0, "stale": 0, "fixed": 0, "errors": 0}

        mode = "FIX" if fix else "DRY-RUN"
        self.stdout.write(f"Checking {qs.count()} channel(s) [{mode}]...")

        for channel in qs:
            totals["checked"] += 1
            handler = HANDLERS[channel.channel_type]
            expected = expected_callback_url(channel)

            try:
                current = handler.get_current(channel)
            except CallbackCheckError as e:
                totals["errors"] += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"!! org={channel.org_id} ({channel.org.name}) "
                        f"channel={channel.id} ({channel.uuid}, {channel.name}): could not check: {e}"
                    )
                )
                continue

            if urls_equal(current, expected):
                totals["ok"] += 1
                if verbose:
                    self.stdout.write(
                        f"   org={channel.org_id} ({channel.org.name}) "
                        f"channel={channel.id} ({channel.uuid}, {channel.name}): OK ({current})"
                    )
                continue

            totals["stale"] += 1
            self.stdout.write(
                self.style.WARNING(
                    f"!= org={channel.org_id} ({channel.org.name}) "
                    f"channel={channel.id} ({channel.uuid}, {channel.name})\n"
                    f"     current:  {current}\n"
                    f"     expected: {expected}"
                )
            )

            if not fix:
                continue

            try:
                handler.set_callback(channel, expected)
                new_current = handler.get_current(channel)
            except CallbackCheckError as e:
                totals["errors"] += 1
                self.stdout.write(self.style.ERROR(f"     fix failed: {e}"))
                continue

            if urls_equal(new_current, expected):
                totals["fixed"] += 1
                self.stdout.write(self.style.SUCCESS(f"     fixed -> {new_current}"))
            else:
                totals["errors"] += 1
                self.stdout.write(self.style.ERROR(f"     fix verify failed: now {new_current}, expected {expected}"))

        self.stdout.write(
            f"Done: checked={totals['checked']} ok={totals['ok']} stale={totals['stale']} "
            f"fixed={totals['fixed']} errors={totals['errors']}"
        )


def urls_equal(a: str, b: str) -> bool:
    if a is None or b is None:
        return False
    return a.rstrip("/") == b.rstrip("/")


def expected_callback_url(channel) -> str:
    """The canonical courier URL for an inbound message webhook on this channel."""
    if channel.channel_type == "PL":
        path = reverse("courier.pl", args=[channel.uuid, "receive"])
    elif channel.channel_type == "VP":
        path = reverse("courier.vp", args=[channel.uuid])
    else:  # pragma: no cover
        path = f"/c/{channel.channel_type.lower()}/{channel.uuid}/receive"

    return f"https://{channel.callback_domain}{path}"


class PlivoHandler:
    @staticmethod
    def _creds(channel):
        config = channel.config
        try:
            auth_id = config[PlivoType.CONFIG_AUTH_ID]
            auth_token = config[PlivoType.CONFIG_AUTH_TOKEN]
            app_id = config[PlivoType.CONFIG_APP_ID]
        except KeyError as e:
            raise CallbackCheckError(f"missing config key {e.args[0]}")
        return auth_id, auth_token, app_id

    @classmethod
    def get_current(cls, channel) -> str:
        auth_id, auth_token, app_id = cls._creds(channel)
        url = f"https://api.plivo.com/v1/Account/{auth_id}/Application/{app_id}/"
        try:
            resp = requests.get(url, auth=(auth_id, auth_token), timeout=HTTP_TIMEOUT)
        except requests.RequestException as e:
            raise CallbackCheckError(f"plivo GET failed: {e}")

        if resp.status_code != 200:
            raise CallbackCheckError(f"plivo GET returned HTTP {resp.status_code}: {resp.text[:200]}")

        try:
            return resp.json().get("message_url") or ""
        except ValueError as e:
            raise CallbackCheckError(f"plivo GET returned non-JSON: {e}")

    @classmethod
    def set_callback(cls, channel, expected: str) -> None:
        auth_id, auth_token, app_id = cls._creds(channel)
        url = f"https://api.plivo.com/v1/Account/{auth_id}/Application/{app_id}/"
        try:
            resp = requests.post(
                url,
                json={"message_url": expected},
                auth=(auth_id, auth_token),
                timeout=HTTP_TIMEOUT,
            )
        except requests.RequestException as e:
            raise CallbackCheckError(f"plivo POST failed: {e}")

        if resp.status_code not in (200, 202):
            raise CallbackCheckError(f"plivo POST returned HTTP {resp.status_code}: {resp.text[:200]}")


class ViberPublicHandler:
    DEFAULT_EVENT_TYPES = ["delivered", "failed", "conversation_started"]

    @staticmethod
    def _token(channel) -> str:
        token = channel.config.get("auth_token")
        if not token:
            raise CallbackCheckError("missing config key auth_token")
        return token

    @classmethod
    def _account_info(cls, channel) -> dict:
        token = cls._token(channel)
        try:
            resp = requests.post(
                "https://chatapi.viber.com/pa/get_account_info",
                headers={"X-Viber-Auth-Token": token},
                timeout=HTTP_TIMEOUT,
            )
        except requests.RequestException as e:
            raise CallbackCheckError(f"viber get_account_info failed: {e}")

        if resp.status_code != 200:
            raise CallbackCheckError(f"viber get_account_info returned HTTP {resp.status_code}: {resp.text[:200]}")

        try:
            data = resp.json()
        except ValueError as e:
            raise CallbackCheckError(f"viber get_account_info returned non-JSON: {e}")

        if data.get("status") != 0:
            raise CallbackCheckError(
                f"viber get_account_info returned status={data.get('status')} message={data.get('status_message')!r}"
            )
        return data

    @classmethod
    def get_current(cls, channel) -> str:
        return cls._account_info(channel).get("webhook") or ""

    @classmethod
    def set_callback(cls, channel, expected: str) -> None:
        token = cls._token(channel)
        # preserve existing event_types so we don't silently drop a category the user had on
        try:
            info = cls._account_info(channel)
            event_types = info.get("event_types") or cls.DEFAULT_EVENT_TYPES
        except CallbackCheckError:
            event_types = cls.DEFAULT_EVENT_TYPES

        try:
            resp = requests.post(
                "https://chatapi.viber.com/pa/set_webhook",
                json={
                    "url": expected,
                    "event_types": event_types,
                    "send_name": True,
                    "send_photo": True,
                },
                headers={"X-Viber-Auth-Token": token},
                timeout=HTTP_TIMEOUT,
            )
        except requests.RequestException as e:
            raise CallbackCheckError(f"viber set_webhook failed: {e}")

        if resp.status_code != 200:
            raise CallbackCheckError(f"viber set_webhook returned HTTP {resp.status_code}: {resp.text[:200]}")

        try:
            data = resp.json()
        except ValueError as e:
            raise CallbackCheckError(f"viber set_webhook returned non-JSON: {e}")

        if data.get("status") != 0:
            raise CallbackCheckError(
                f"viber set_webhook returned status={data.get('status')} message={data.get('status_message')!r}"
            )


HANDLERS = {
    "PL": PlivoHandler,
    "VP": ViberPublicHandler,
}
