from random import randint

import requests
from smartmin.views import SmartFormView, SmartModelActionView, SmartTemplateView

from django import forms
from django.conf import settings
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from temba.orgs.views import ModalMixin, OrgObjPermsMixin, OrgPermsMixin
from temba.utils.fields import InputWidget
from temba.utils.text import truncate
from temba.utils.views import ContentMenuMixin

from ...models import Channel
from ...views import ClaimViewMixin


class ClaimView(ClaimViewMixin, SmartFormView):
    class Form(ClaimViewMixin.Form):
        number = forms.CharField()
        verified_name = forms.CharField()
        phone_number_id = forms.CharField()
        waba_id = forms.CharField()
        business_id = forms.CharField()
        currency = forms.CharField()
        message_template_namespace = forms.CharField()

    form_class = Form

    def pre_process(self, request, *args, **kwargs):
        oauth_user_token = self.request.session.get(Channel.CONFIG_WHATSAPP_CLOUD_USER_TOKEN, None)
        if not oauth_user_token:
            self.remove_token_credentials_from_session()
            return HttpResponseRedirect(reverse("orgs.org_whatsapp_cloud_connect"))

        app_id = settings.FACEBOOK_APPLICATION_ID
        app_secret = settings.FACEBOOK_APPLICATION_SECRET

        url = "https://graph.facebook.com/v13.0/debug_token"
        params = {"access_token": f"{app_id}|{app_secret}", "input_token": oauth_user_token}

        response = requests.get(url, params=params)
        if response.status_code != 200:  # pragma: no cover
            self.remove_token_credentials_from_session()
            return HttpResponseRedirect(reverse("orgs.org_whatsapp_cloud_connect"))

        response_json = response.json()
        for perm in ["business_management", "whatsapp_business_management", "whatsapp_business_messaging"]:
            if perm not in response_json["data"]["scopes"]:
                self.remove_token_credentials_from_session()
                return HttpResponseRedirect(reverse("orgs.org_whatsapp_cloud_connect"))

        return super().pre_process(request, *args, **kwargs)

    def get_success_url(self):
        return reverse("channels.channel_read", args=[self.object.uuid])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        oauth_user_token = self.request.session.get(Channel.CONFIG_WHATSAPP_CLOUD_USER_TOKEN, None)
        app_id = settings.FACEBOOK_APPLICATION_ID
        app_secret = settings.FACEBOOK_APPLICATION_SECRET

        url = "https://graph.facebook.com/v13.0/debug_token"
        params = {"access_token": f"{app_id}|{app_secret}", "input_token": oauth_user_token}

        response = requests.get(url, params=params)
        if response.status_code != 200:  # pragma: no cover
            context["waba_details"] = []

        else:
            response_json = response.json()

            waba_targets = []
            granular_scopes = response_json.get("data", dict()).get("granular_scopes", [])
            for scope_dict in granular_scopes:
                if scope_dict["scope"] in ["whatsapp_business_management", "whatsapp_business_messaging"]:
                    waba_targets.extend(scope_dict.get("target_ids", []))

            seen_waba = []
            phone_numbers = []

            for target_waba in waba_targets:
                if target_waba in seen_waba:
                    continue

                seen_waba.append(target_waba)

                url = f"https://graph.facebook.com/v13.0/{target_waba}"
                params = {
                    "access_token": oauth_user_token,
                    "fields": "id,name,currency,message_template_namespace,owner_business_info,account_review_status,on_behalf_of_business_info,primary_funding_id,purchase_order_number,timezone_id",
                }
                response = requests.get(url, params=params)
                response_json = response.json()

                target_waba_details = response_json

                business_id = target_waba_details["on_behalf_of_business_info"]["id"]

                url = f"https://graph.facebook.com/v13.0/{target_waba}/phone_numbers"
                params = {"access_token": oauth_user_token}
                response = requests.get(url, params=params)
                response_json = response.json()

                target_waba_phone_numbers = response_json.get("data", [])
                for target_phone in target_waba_phone_numbers:
                    phone_numbers.append(
                        dict(
                            verified_name=target_phone["verified_name"],
                            display_phone_number=target_phone["display_phone_number"],
                            phone_number_id=target_phone["id"],
                            waba_id=target_waba_details["id"],
                            currency=target_waba_details.get("currency", "USD"),
                            business_id=business_id,
                            message_template_namespace=target_waba_details["message_template_namespace"],
                        )
                    )

            context["phone_numbers"] = phone_numbers

        context["claim_url"] = reverse("channels.types.whatsapp_cloud.claim")
        context["clear_session_token_url"] = reverse("channels.types.whatsapp_cloud.clear_session_token")
        context["connect_whatsapp_url"] = reverse("orgs.org_whatsapp_cloud_connect")
        context["facebook_app_id"] = settings.FACEBOOK_APPLICATION_ID

        claim_error = None
        if context["form"].errors:
            claim_error = context["form"].errors["__all__"][0]
        context["claim_error"] = claim_error

        # make sure we clear the session credentials if no number was granted
        if not context.get("phone_numbers", []):
            self.remove_token_credentials_from_session()

        return context

    def form_valid(self, form):
        org = self.request.org

        number = form.cleaned_data["number"]
        verified_name = form.cleaned_data["verified_name"]
        phone_number_id = form.cleaned_data["phone_number_id"]
        waba_id = form.cleaned_data["waba_id"]
        business_id = form.cleaned_data["business_id"]
        currency = form.cleaned_data["currency"]
        message_template_namespace = form.cleaned_data["message_template_namespace"]
        pin = str(randint(100000, 999999))

        name = truncate(f"{number} - {verified_name}", 64)

        config = {
            "wa_number": number,
            "wa_verified_name": verified_name,
            "wa_waba_id": waba_id,
            "wa_currency": currency,
            "wa_business_id": business_id,
            "wa_message_template_namespace": message_template_namespace,
            "wa_pin": pin,
        }

        # don't add the same number twice to the same account
        existing = Channel.objects.filter(
            is_active=True, address=phone_number_id, schemes__overlap=list(self.channel_type.schemes)
        ).first()
        if existing:  # pragma: needs cover
            if existing.org == self.request.org:
                form._errors["__all__"] = form.error_class([_("Number is already connected to this workspace")])
                return self.form_invalid(form)

            form._errors["__all__"] = form.error_class([_("Number is already connected to another workspace")])
            return self.form_invalid(form)

        # assign system user to WABA
        url = f"https://graph.facebook.com/v13.0/{waba_id}/assigned_users"
        params = {"user": f"{settings.WHATSAPP_ADMIN_SYSTEM_USER_ID}", "tasks": ["MANAGE"]}
        headers = {"Authorization": f"Bearer {settings.WHATSAPP_ADMIN_SYSTEM_USER_TOKEN}"}

        resp = requests.post(url, params=params, headers=headers)

        if resp.status_code != 200:  # pragma: no cover
            form._errors["__all__"] = form.error_class(
                [
                    _(
                        "Unable to add system user to %s, please make sure you have business admin manager privileges "
                        "on the Facebook business."
                    )
                    % waba_id
                ]
            )
            return self.form_invalid(form)

        self.object = Channel.create(
            org,
            self.request.user,
            None,
            self.channel_type,
            name=name,
            address=phone_number_id,
            config=config,
            tps=80,
        )
        self.remove_token_credentials_from_session()
        return super().form_valid(form)

    def remove_token_credentials_from_session(self):
        if Channel.CONFIG_WHATSAPP_CLOUD_USER_TOKEN in self.request.session:
            del self.request.session[Channel.CONFIG_WHATSAPP_CLOUD_USER_TOKEN]


class ClearSessionToken(OrgPermsMixin, SmartTemplateView):
    permission = "channels.channel_claim"

    def pre_process(self, request, *args, **kwargs):
        if Channel.CONFIG_WHATSAPP_CLOUD_USER_TOKEN in self.request.session:
            del self.request.session[Channel.CONFIG_WHATSAPP_CLOUD_USER_TOKEN]

    def render_to_response(self, context, **response_kwargs):
        return JsonResponse({})


class RequestCode(ModalMixin, ContentMenuMixin, OrgObjPermsMixin, SmartModelActionView):
    class Form(forms.Form):
        pass

    slug_url_kwarg = "uuid"
    success_message = ""
    form_class = Form
    permission = "channels.channel_claim"
    fields = ()
    template_name = "channels/types/whatsapp_cloud/request_code.html"
    title = _("Verification Code")
    submit_button_name = _("Request Code")

    def get_queryset(self):
        return Channel.objects.filter(is_active=True, org=self.request.org, channel_type="WAC")

    def get_success_url(self):
        return reverse("channels.types.whatsapp_cloud.verify_code", args=[self.object.uuid])

    def build_content_menu(self, menu):
        obj = self.get_object()

        menu.add_link(_("Channel"), reverse("channels.channel_read", args=[obj.uuid]))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        phone_number_url = f"https://graph.facebook.com/v13.0/{self.object.address}"
        headers = {"Authorization": f"Bearer {settings.WHATSAPP_ADMIN_SYSTEM_USER_TOKEN}"}
        resp = requests.get(phone_number_url, headers=headers)

        verified_status = False
        if resp.status_code == 200:
            verified_status = resp.json().get("code_verification_status") == "VERIFIED"

        context["verified_status"] = verified_status
        return context

    def execute_action(self):
        channel = self.object

        phone_number_id = channel.address

        request_code_url = f"https://graph.facebook.com/v13.0/{phone_number_id}/request_code"
        params = {"code_method": "SMS", "language": "en_US"}
        headers = {"Authorization": f"Bearer {settings.WHATSAPP_ADMIN_SYSTEM_USER_TOKEN}"}

        resp = requests.post(request_code_url, params=params, headers=headers)

        if resp.status_code != 200:  # pragma: no cover
            phone_number_url = f"https://graph.facebook.com/v13.0/{phone_number_id}"
            resp = requests.get(phone_number_url, headers=headers)

            verified_status = False
            if resp.status_code == 200:
                verified_status = resp.json().get("code_verification_status") == "VERIFIED"

            if not verified_status:
                raise forms.ValidationError(
                    _("Failed to request phone number verification code. Please remove the channel and add it again.")
                )


class VerifyCode(ModalMixin, ContentMenuMixin, OrgObjPermsMixin, SmartModelActionView):
    class Form(forms.Form):
        code = forms.CharField(
            min_length=6, required=True, help_text=_("The 6-digits number verification code"), widget=InputWidget()
        )

    slug_url_kwarg = "uuid"
    success_url = "uuid@channels.channel_read"
    form_class = Form
    permission = "channels.channel_claim"
    fields = ("code",)
    template_name = "channels/types/whatsapp_cloud/verify_code.html"
    title = _("Verify Number")
    submit_button_name = _("Verify Number")

    def build_content_menu(self, menu):
        obj = self.get_object()

        menu.add_link(_("Channel"), reverse("channels.channel_read", args=[obj.uuid]))

    def get_queryset(self):
        return Channel.objects.filter(is_active=True, org=self.request.org, channel_type="WAC")

    def execute_action(self):

        form = self.form
        channel = self.object

        code = form.data["code"]

        phone_number_id = channel.address
        wa_number = channel.config.get("wa_number")
        waba_id = channel.config.get("wa_waba_id")
        wa_pin = channel.config.get("wa_pin")

        request_code_url = f"https://graph.facebook.com/v13.0/{phone_number_id}/verify_code"
        params = {"code": f"{code}"}
        headers = {"Authorization": f"Bearer {settings.WHATSAPP_ADMIN_SYSTEM_USER_TOKEN}"}

        resp = requests.post(request_code_url, params=params, headers=headers)

        if resp.status_code != 200:  # pragma: no cover
            raise forms.ValidationError(_("Failed to verify phone number with code %s") % code)

        # register numbers
        url = f"https://graph.facebook.com/v13.0/{channel.address}/register"
        data = {"messaging_product": "whatsapp", "pin": wa_pin}

        resp = requests.post(url, data=data, headers=headers)

        if resp.status_code != 200:  # pragma: no cover
            raise forms.ValidationError(
                _("Unable to register phone %s with ID %s from WABA with ID %s")
                % (wa_number, channel.address, waba_id)
            )
