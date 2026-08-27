import re

from smartmin.views import SmartFormView

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from temba.channels.models import Channel
from temba.channels.views import ClaimViewMixin, UpdateChannelForm

CONFIG_ALLOWED_DOMAINS = "allowed_domains"

# a domain entry is a host - dot-separated alphanumeric labels which may contain hyphens - optionally followed by a
# port (whose 1-65535 range is checked separately), e.g. "example.com" or "localhost:3000" - never a scheme or path
DOMAIN_REGEX = re.compile(r"[a-z0-9]([a-z0-9\-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9\-]*[a-z0-9])?)*(:(?P<port>\d{1,5}))?")


class ClaimView(ClaimViewMixin, SmartFormView):
    class Form(ClaimViewMixin.Form):
        pass

    form_class = Form
    readonly_servicing = False

    def form_valid(self, form):
        self.object = Channel.create(
            self.request.org, self.request.user, None, self.channel_type, name="WebChat", config={}
        )

        return super().form_valid(form)


class UpdateForm(UpdateChannelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        field = forms.CharField(
            label=_("Allowed Domains"),
            required=False,
            widget=forms.Textarea(attrs={"rows": 3}),
            help_text=_(
                "The domains of the websites that can embed this channel's chat widget, one per line or comma "
                "separated, e.g. example.com or example.com:8080. If empty, any website can embed it."
            ),
        )
        self.add_config_field(CONFIG_ALLOWED_DOMAINS, field, default=[])
        field.initial = "\n".join(field.initial or [])

    def clean_allowed_domains(self) -> list:
        domains = []
        for entry in re.split(r"[,\n]", self.cleaned_data[CONFIG_ALLOWED_DOMAINS]):
            entry = entry.strip().lower()
            if not entry:
                continue
            match = DOMAIN_REGEX.fullmatch(entry)
            if not match or (match["port"] and not 1 <= int(match["port"]) <= 65535):
                raise ValidationError(
                    _("%(domain)s is not a valid domain. Enter domains without schemes or paths, e.g. example.com."),
                    params={"domain": entry},
                )
            if entry not in domains:
                domains.append(entry)
        return domains
