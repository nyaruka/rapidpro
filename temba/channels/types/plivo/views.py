import phonenumbers
import plivo
import pycountry
from django.core.exceptions import ValidationError
from django import forms
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from smartmin.views import SmartFormView

from temba.channels.models import Channel
from temba.channels.views import BaseClaimNumberMixin, ClaimViewMixin, PLIVO_SUPPORTED_COUNTRIES
from temba.channels.views import PLIVO_SUPPORTED_COUNTRY_CODES
from temba.utils import analytics


class ClaimView(BaseClaimNumberMixin, SmartFormView):

    class Form(ClaimViewMixin.Form):
        country = forms.ChoiceField(choices=PLIVO_SUPPORTED_COUNTRIES)
        phone_number = forms.CharField(help_text=_("The phone number being added"))

        def clean_phone_number(self):
            if not self.cleaned_data.get('country', None):  # pragma: needs cover
                raise ValidationError(_("That number is not currently supported."))

            phone = self.cleaned_data['phone_number']
            phone = phonenumbers.parse(phone, self.cleaned_data['country'])

            return phonenumbers.format_number(phone, phonenumbers.PhoneNumberFormat.E164)

    form_class = Form

    def pre_process(self, *args, **kwargs):
        client = self.get_valid_client()

        if client:
            return None
        else:
            return HttpResponseRedirect(reverse('channels.channel_claim'))

    def get_valid_client(self):
        auth_id = self.request.session.get(Channel.CONFIG_PLIVO_AUTH_ID, None)
        auth_token = self.request.session.get(Channel.CONFIG_PLIVO_AUTH_TOKEN, None)

        try:
            client = plivo.RestAPI(auth_id, auth_token)
            validation_response = client.get_account()
            if validation_response[0] != 200:
                client = None
        except plivo.PlivoError:  # pragma: needs cover
            client = None

        return client

    def is_valid_country(self, country_code):
        return country_code in PLIVO_SUPPORTED_COUNTRY_CODES

    def is_messaging_country(self, country):
        return country in [c[0] for c in PLIVO_SUPPORTED_COUNTRIES]

    def get_search_url(self):
        return reverse('channels.channel_search_plivo')

    def get_claim_url(self):
        return reverse('channels.claim_plivo')

    def get_supported_countries_tuple(self):
        return PLIVO_SUPPORTED_COUNTRIES

    def get_search_countries_tuple(self):
        return PLIVO_SUPPORTED_COUNTRIES

    def get_existing_numbers(self, org):
        client = self.get_valid_client()

        account_numbers = []
        if client:
            status, data = client.get_numbers()

            if status == 200:
                for number_dict in data['objects']:

                    region = number_dict['region']
                    country_name = region.split(',')[-1].strip().title()
                    country = pycountry.countries.get(name=country_name).alpha_2

                    if len(number_dict['number']) <= 6:
                        phone_number = number_dict['number']
                    else:
                        parsed = phonenumbers.parse('+' + number_dict['number'], None)
                        phone_number = phonenumbers.format_number(parsed,
                                                                  phonenumbers.PhoneNumberFormat.INTERNATIONAL)

                    account_numbers.append(dict(number=phone_number, country=country))

        return account_numbers

    def claim_number(self, user, phone_number, country, role):

        auth_id = self.request.session.get(Channel.CONFIG_PLIVO_AUTH_ID, None)
        auth_token = self.request.session.get(Channel.CONFIG_PLIVO_AUTH_TOKEN, None)

        # add this channel
        channel = Channel.add_plivo_channel(user.get_org(),
                                            user,
                                            country,
                                            phone_number,
                                            auth_id,
                                            auth_token)

        analytics.track(user.username, 'temba.channel_claim_plivo', dict(number=phone_number))

        return channel

    def remove_api_credentials_from_session(self):
        if Channel.CONFIG_PLIVO_AUTH_ID in self.request.session:
            del self.request.session[Channel.CONFIG_PLIVO_AUTH_ID]
        if Channel.CONFIG_PLIVO_AUTH_TOKEN in self.request.session:
            del self.request.session[Channel.CONFIG_PLIVO_AUTH_TOKEN]
