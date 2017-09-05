import phonenumbers
from django import forms
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from smartmin.views import SmartFormView

from temba.channels.models import Channel
from temba.channels.views import BaseClaimNumberMixin, ClaimViewMixin, NEXMO_SUPPORTED_COUNTRIES, \
    NEXMO_SUPPORTED_COUNTRY_CODES
from temba.orgs.models import Org
from temba.utils import analytics


class ClaimView(BaseClaimNumberMixin, SmartFormView):

    class Form(ClaimViewMixin.Form):
        country = forms.ChoiceField(choices=NEXMO_SUPPORTED_COUNTRIES)
        phone_number = forms.CharField(help_text=_("The phone number being added"))

        def clean_phone_number(self):
            if not self.cleaned_data.get('country', None):  # pragma: needs cover
                    raise ValidationError(_("That number is not currently supported."))

            phone = self.cleaned_data['phone_number']
            phone = phonenumbers.parse(phone, self.cleaned_data['country'])

            return phonenumbers.format_number(phone, phonenumbers.PhoneNumberFormat.E164)

    form_class = Form

    def pre_process(self, *args, **kwargs):
        org = Org.objects.get(pk=self.request.user.get_org().pk)
        try:
            client = org.get_nexmo_client()
        except Exception:  # pragma: needs cover
            client = None

        if client:
            return None
        else:  # pragma: needs cover
            return HttpResponseRedirect(reverse('channels.channel_claim'))

    def is_valid_country(self, country_code):
        return country_code in NEXMO_SUPPORTED_COUNTRY_CODES

    def is_messaging_country(self, country):
        return country in [c[0] for c in NEXMO_SUPPORTED_COUNTRIES]

    def get_search_url(self):
        return reverse('channels.channel_search_nexmo')

    def get_claim_url(self):
        return reverse('channels.channel_claim_nexmo')

    def get_supported_countries_tuple(self):
        return NEXMO_SUPPORTED_COUNTRIES

    def get_search_countries_tuple(self):
        return NEXMO_SUPPORTED_COUNTRIES

    def get_existing_numbers(self, org):
        client = org.get_nexmo_client()
        if client:
            account_numbers = client.get_numbers(size=100)

        numbers = []
        for number in account_numbers:
            if number['type'] == 'mobile-shortcode':  # pragma: needs cover
                phone_number = number['msisdn']
            else:
                parsed = phonenumbers.parse(number['msisdn'], number['country'])
                phone_number = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
            numbers.append(dict(number=phone_number, country=number['country']))

        return numbers

    def claim_number(self, user, phone_number, country, role):
        analytics.track(user.username, 'temba.channel_claim_nexmo', dict(number=phone_number))

        # add this channel
        channel = Channel.add_nexmo_channel(user.get_org(),
                                            user,
                                            country,
                                            phone_number)

        return channel
