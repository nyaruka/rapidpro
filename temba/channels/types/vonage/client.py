import time

from vonage import Auth, Vonage
from vonage_application.common import Capabilities, Voice, VoiceUrl, VoiceWebhooks
from vonage_application.requests import ApplicationConfig
from vonage_http_client.errors import AuthenticationError, HttpRequestError, RateLimitedError
from vonage_numbers.requests import (
    ListOwnedNumbersFilter,
    NumberParams,
    SearchAvailableNumbersFilter,
    UpdateNumberParams,
)

from django.urls import reverse


class VonageClient:
    """
    Wrapper for the actual Vonage client that adds some functionality and retries
    """

    RATE_LIMIT_BACKOFFS = [1, 3, 6]  # backoff times in seconds when we're rate limited

    def __init__(self, api_key: str, api_secret: str):
        self.base = Vonage(Auth(api_key=api_key, api_secret=api_secret))

    def check_credentials(self) -> bool:
        try:
            self.base.account.get_balance()
            return True
        except AuthenticationError:
            return False

    def get_numbers(self, pattern: str = None, size: int = 10) -> list:
        # v4 requires a search strategy whenever a pattern is given, and 0 (starts with) is the narrowest, which
        # suits us because we're always looking for a specific number rather than browsing
        pattern = str(pattern).strip("+") if pattern else None
        filter = ListOwnedNumbersFilter(size=size, pattern=pattern, search_pattern=0 if pattern is not None else None)

        numbers, _, _ = self._with_retry(self.base.numbers.list_owned_numbers, filter)

        return [n.model_dump() for n in numbers]

    def search_numbers(self, country, pattern):
        numbers = []

        for features in ("SMS", "VOICE"):
            found, _, _ = self._with_retry(
                self.base.numbers.search_available_numbers,
                SearchAvailableNumbersFilter(country=country, pattern=pattern, search_pattern=1, features=features),
            )
            numbers += [n.model_dump() for n in found]

        return numbers

    def buy_number(self, country, number):
        self._with_retry(self.base.numbers.buy_number, NumberParams(country=country, msisdn=number.lstrip("+")))

    def update_number(self, country, number, mo_url, app_id):
        params = UpdateNumberParams(country=country, msisdn=number.lstrip("+"), mo_http_url=mo_url, app_id=app_id)

        self._with_retry(self.base.numbers.update_number, params)

    def create_application(self, domain, channel_uuid):
        name = "%s/%s" % (domain, channel_uuid)
        answer_url = reverse("mailroom.ivr_handler", args=[channel_uuid, "incoming"])
        event_url = reverse("mailroom.ivr_handler", args=[channel_uuid, "status"])

        config = ApplicationConfig(
            name=name,
            capabilities=Capabilities(
                voice=Voice(
                    webhooks=VoiceWebhooks(
                        answer_url=VoiceUrl(address=f"https://{domain}{answer_url}", http_method="POST"),
                        event_url=VoiceUrl(address=f"https://{domain}{event_url}", http_method="POST"),
                    )
                )
            ),
        )

        app = self._with_retry(self.base.application.create_application, config)

        # the private key is only returned when the application is created and isn't a field on the keys model
        return app.id, getattr(app.keys, "private_key", None) if app.keys else None

    def delete_application(self, app_id):
        try:
            self._with_retry(self.base.application.delete_application, app_id)
        except HttpRequestError:
            # possible application no longer exists
            pass

    def _with_retry(self, func, *args):
        """
        Utility to perform something using the API, and if it errors with a rate-limit response, try again
        after a small delay.
        """

        backoffs = self.RATE_LIMIT_BACKOFFS.copy()

        while True:
            try:
                return func(*args)
            except RateLimitedError:
                if not backoffs:
                    raise

                time.sleep(backoffs[0])
                backoffs = backoffs[1:]
