from django import forms

from temba.utils.validators import validate_without_html_tags


class CampaignMessageField(forms.CharField):
    default_validators = [validate_without_html_tags]
