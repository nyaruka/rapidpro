from allauth.account.forms import AddEmailForm, ChangePasswordForm, SignupForm

from django import forms
from django.utils.translation import gettext_lazy as _

from temba.orgs.models import Org
from temba.users.models import User
from temba.utils import analytics
from temba.utils.timezones import TimeZoneFormField


class TembaSignupForm(SignupForm):

    first_name = forms.CharField(
        max_length=User._meta.get_field("first_name").max_length,
        label="",
        widget=forms.TextInput(attrs={"placeholder": _("First name")}),
    )

    last_name = forms.CharField(
        max_length=User._meta.get_field("last_name").max_length,
        label="",
        widget=forms.TextInput(
            attrs={
                "placeholder": _("Last name"),
            }
        ),
    )

    workspace = forms.CharField(
        label=_("Workspace"),
        help_text=_("A workspace is usually the name of a company or project"),
        widget=forms.TextInput(
            attrs={
                "placeholder": _("My Company, Inc."),
            }
        ),
    )

    timezone = TimeZoneFormField(widget=forms.widgets.HiddenInput())

    field_order = ["first_name", "last_name", "email", "password1", "workspace"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].help_text = "At least 8 characters or more"

    def save(self, request):
        user = super(TembaSignupForm, self).save(request)

        org = Org.create(user, self.cleaned_data["workspace"], self.cleaned_data["timezone"])
        analytics.identify(user, brand=request.branding, org=org)
        analytics.track(user, "temba.org_signup", properties=dict(org=org.name))

        return user


class TembaChangePasswordForm(ChangePasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].help_text = "At least 8 characters or more"


class TembaAddEmailForm(AddEmailForm):

    def clean_email(self):

        # check if email is already in use
        if User.objects.filter(email__iexact=self.cleaned_data["email"]).exists():
            raise forms.ValidationError(_("This email is already in use"))

        return super().clean_email()
