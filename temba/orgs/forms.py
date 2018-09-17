from django import forms
from django.contrib.auth.models import User

from temba.orgs.models import Org
from temba.utils.validators import validate_without_html_tags


class OrgNameField(forms.CharField):
    default_validators = [validate_without_html_tags]

    def __init__(self, **kwargs):
        max_length = kwargs.pop("max_length", Org._meta.get_field("name").max_length)

        super().__init__(max_length=max_length, **kwargs)


class UserFirstNameField(forms.CharField):
    default_validators = [validate_without_html_tags]

    def __init__(self, **kwargs):
        max_length = kwargs.pop("max_length", User._meta.get_field("first_name").max_length)

        super().__init__(max_length=max_length, **kwargs)


class UserLastNameField(forms.CharField):
    default_validators = [validate_without_html_tags]

    def __init__(self, **kwargs):
        max_length = kwargs.pop("max_length", User._meta.get_field("last_name").max_length)

        super().__init__(max_length=max_length, **kwargs)


class UserEmailField(forms.EmailField):
    def __init__(self, **kwargs):
        max_length = kwargs.pop("max_length", User._meta.get_field("username").max_length)

        super().__init__(max_length=max_length, **kwargs)
