from __future__ import unicode_literals, absolute_import

import phonenumbers
from django import forms
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from phonenumbers.phonenumberutil import region_code_for_number
from smartmin.views import SmartFormView
from twilio import TwilioRestException

from temba.orgs.models import ACCOUNT_SID
from temba.utils import analytics
from temba.utils.timezones import timezone_to_country_code
from ...models import Channel
from ...views import ClaimViewMixin, TWILIO_SUPPORTED_COUNTRIES, BaseClaimNumberMixin, ALL_COUNTRIES
from ...views import TWILIO_SEARCH_COUNTRIES


class ClaimView(BaseClaimNumberMixin, SmartFormView):
    class Form(ClaimViewMixin.Form):
        country = forms.ChoiceField(choices=ALL_COUNTRIES)
        phone_number = forms.CharField(help_text=_("The phone number being added"))

        def clean_phone_number(self):
            phone = self.cleaned_data['phone_number']

            # short code should not be formatted
            if len(phone) <= 6:
                return phone

            phone = phonenumbers.parse(phone, self.cleaned_data['country'])
            return phonenumbers.format_number(phone, phonenumbers.PhoneNumberFormat.E164)

    form_class = Form

    def __init__(self, channel_type):
        super(ClaimView, self).__init__(channel_type)
        self.account = None
        self.client = None

    def pre_process(self, *args, **kwargs):
        org = self.request.user.get_org()
        try:
            self.client = org.get_twilio_client()
            if not self.client:
                return HttpResponseRedirect(reverse('channels.channel_claim'))
            self.account = self.client.accounts.get(org.config_json()[ACCOUNT_SID])
        except TwilioRestException:
            return HttpResponseRedirect(reverse('channels.channel_claim'))

    def get_search_countries_tuple(self):
        return TWILIO_SEARCH_COUNTRIES

    def get_supported_countries_tuple(self):
        return ALL_COUNTRIES

    def get_search_url(self):
        return reverse('channels.channel_search_numbers')

    def get_claim_url(self):
        return reverse('channels.claim_twilio')

    def get_context_data(self, **kwargs):
        context = super(ClaimView, self).get_context_data(**kwargs)
        context['account_trial'] = self.account.type.lower() == 'trial'
        return context

    def get_existing_numbers(self, org):
        client = org.get_twilio_client()
        if client:
            twilio_account_numbers = client.phone_numbers.list()
            twilio_short_codes = client.sms.short_codes.list()

        numbers = []
        for number in twilio_account_numbers:
            parsed = phonenumbers.parse(number.phone_number, None)
            numbers.append(dict(number=phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL),
                                country=region_code_for_number(parsed)))

        org_country = timezone_to_country_code(org.timezone)
        for number in twilio_short_codes:
            numbers.append(dict(number=number.short_code, country=org_country))

        return numbers

    def is_valid_country(self, country_code):
        return True

    def is_messaging_country(self, country):
        return country in [c[0] for c in TWILIO_SUPPORTED_COUNTRIES]

    def claim_number(self, user, phone_number, country, role):
        analytics.track(user.username, 'temba.channel_claim_twilio', properties=dict(number=phone_number))

        # add this channel
        return Channel.add_twilio_channel(user.get_org(), user, phone_number, country, role)
