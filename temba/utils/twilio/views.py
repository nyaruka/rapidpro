from smartmin.views import SmartUpdateView
from twilio.rest import Client as TwilioClient

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from temba.channels.models import Channel
from temba.orgs.views import ModalMixin, OrgPermsMixin
from temba.utils.fields import InputWidget


class UpdateCredentials(OrgPermsMixin, SmartUpdateView):
    class Form(forms.ModelForm):
        account_sid = forms.CharField(help_text=_("Your Twilio Account SID"), required=True, widget=InputWidget())
        account_token = forms.CharField(help_text=_("Your Twilio Account Token"), required=True, widget=InputWidget())

        def clean(self):
            account_sid = self.cleaned_data.get("account_sid", None)
            account_token = self.cleaned_data.get("account_token", None)

            if not account_sid:  # pragma: needs cover
                raise ValidationError(_("You must enter your Twilio Account SID"))

            if not account_token:
                raise ValidationError(_("You must enter your Twilio Account Token"))

            try:
                client = TwilioClient(account_sid, account_token)

                # get the actual primary auth tokens from twilio and use them
                account = client.api.account.fetch()
                self.cleaned_data["account_sid"] = account.sid
                self.cleaned_data["account_token"] = account.auth_token
            except Exception:
                raise ValidationError(
                    _("The Twilio account SID and Token seem invalid. Please check them again and retry.")
                )

            return self.cleaned_data

        class Meta:
            model = Channel
            fields = ("account_sid", "account_token")

    slug_url_kwarg = "uuid"
    success_url = "uuid@channels.channel_read"
    form_class = Form
    permission = "channels.channel_claim"
    fields = ("account_sid", "account_token")
    title = _("Update Twilio Credentials")
    success_message = "Updated"

    def derive_initial(self):
        initial = super().derive_initial()

        initial["account_sid"] = self.object.config.get(Channel.CONFIG_ACCOUNT_SID, "")
        initial["account_token"] = self.object.config.get(Channel.CONFIG_AUTH_TOKEN, "")
        return initial

    def get_queryset(self):
        return self.request.org.channels.filter(is_active=True, channel_type__in=["T", "TMS", "TWA"])

    def form_valid(self, form):
        org = self.request.org
        data = form.cleaned_data

        client = TwilioClient(data["account_sid"], data["account_token"])

        channel_uuid = self.object.uuid
        phone_number = self.object.address

        # TMS does not have application to associate with and no validation
        if self.object.channel_type == "TMS":
            pass

        # TWA needs we validate the number belong on the Twilio account
        elif self.object.channel_type == "TWA":
            twilio_phones = client.api.incoming_phone_numbers.stream(phone_number=phone_number)
            twilio_phone = next(twilio_phones, None)
            if not twilio_phone:
                raise Exception(
                    _(
                        "Phone number not found on your Twilio Account. "
                        "Only existing Twilio WhatsApp number are supported"
                    )
                )

        # For twilio channels make sure we validate the number belong on the Twilio account and update its application
        elif self.object.channel_type == "T":
            callback_domain = org.get_brand_domain()
            base_url = "https://" + callback_domain
            receive_url = base_url + reverse("courier.t", args=[channel_uuid, "receive"])
            status_url = base_url + reverse("mailroom.ivr_handler", args=[channel_uuid, "status"])
            voice_url = base_url + reverse("mailroom.ivr_handler", args=[channel_uuid, "incoming"])

            config_app_id = self.object.config.get(Channel.CONFIG_APPLICATION_SID, "")
            if config_app_id:
                try:
                    twilio_app = client.api.applications.get(sid=config_app_id).fetch()
                except Exception:
                    twilio_app = client.api.applications.create(
                        friendly_name="%s/%s" % (callback_domain.lower(), channel_uuid),
                        sms_method="POST",
                        sms_url=receive_url,
                        voice_method="POST",
                        voice_url=voice_url,
                        status_callback_method="POST",
                        status_callback=status_url,
                        voice_fallback_method="GET",
                        voice_fallback_url=f"{settings.STORAGE_URL}/voice_unavailable.xml",
                    )

            is_short_code = len(self.object.address) <= 6
            if is_short_code:
                short_codes = client.api.short_codes.stream(short_code=phone_number)
                short_code = next(short_codes, None)

                if short_code:
                    number_sid = short_code.sid
                    app_url = (
                        "https://" + callback_domain + "%s" % reverse("courier.t", args=[channel_uuid, "receive"])
                    )
                    client.api.short_codes.get(number_sid).update(sms_url=app_url, sms_method="POST")
                else:  # pragma: no cover
                    raise Exception(
                        _(
                            "Short code not found on your Twilio Account. "
                            "Please check you own the short code and Try again"
                        )
                    )
            else:
                if twilio_phone:

                    client.api.incoming_phone_numbers.get(twilio_phone.sid).update(
                        voice_application_sid=twilio_app.sid, sms_application_sid=twilio_app.sid
                    )
                else:  # pragma: needs cover
                    raise Exception(
                        _(
                            "Phone number not found on your Twilio Account. "
                            "Please check you own the phone number and Try again"
                        )
                    )

            self.object.config[Channel.CONFIG_APPLICATION_SID] = twilio_app.sid

        self.object.config[Channel.CONFIG_ACCOUNT_SID] = data["account_sid"]
        self.object.config[Channel.CONFIG_AUTH_TOKEN] = data["account_token"]
        self.object.save(update_fields=("config", "modified_on"))
        return super().form_valid(form)
