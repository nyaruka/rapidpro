from smartmin.views import SmartFormView

from django import forms
from django.utils.translation import gettext_lazy as _

from temba.channels.models import Channel
from temba.channels.views import ALL_COUNTRIES, ClaimViewMixin
from temba.contacts.models import URN
from temba.utils.fields import SelectWidget


class ClaimView(ClaimViewMixin, SmartFormView):
    class Form(ClaimViewMixin.Form):
        country = forms.ChoiceField(
            choices=ALL_COUNTRIES,
            widget=SelectWidget(attrs={"searchable": True}),
            label=_("Country"),
            help_text=_("The country this channel will be used in"),
        )
        address = forms.CharField(label=_("Service ID"), help_text=_("The service ID as provided by Mtarget"))
        username = forms.CharField(label=_("Username"), help_text=_("The username for your API account"))
        password = forms.CharField(label=_("Password"), help_text=_("The password for your API account"))

    form_class = Form
    template_name = "channels/channel_claim_form.html"

    def form_valid(self, form):
        data = form.cleaned_data
        config = {Channel.CONFIG_USERNAME: data["username"], Channel.CONFIG_PASSWORD: data["password"]}

        self.object = Channel.create(
            org=self.request.org,
            user=self.request.user,
            country=data["country"],
            channel_type=self.channel_type,
            name=data["address"],
            address=data["address"],
            config=config,
            schemes=[URN.TEL_SCHEME],
        )

        return super().form_valid(form)
