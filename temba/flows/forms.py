from django import forms
from django.utils.translation import gettext_lazy as _

from temba.utils.validators import validate_without_html_tags


class FlowKeywordTriggerField(forms.CharField):
    default_validators = [validate_without_html_tags]

    def __init__(self, **kwargs):
        label = kwargs.pop("label", _("Global keyword triggers"))
        help_text = kwargs.pop("help_text", _("When a user sends any of these keywords they will begin this flow"))

        super().__init__(label=label, help_text=help_text, **kwargs)
