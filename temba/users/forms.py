from allauth.account.forms import AddEmailForm, ChangePasswordForm, LoginForm, SignupForm

from django import forms
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from temba.orgs.models import Invitation, Org
from temba.orgs.views.utils import switch_to_org
from temba.users.models import User
from temba.utils.timezones import TimeZoneFormField


class InviteFormMixin:

    def __init__(self, secret, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.secret = secret

    @cached_property
    def invite(self):
        if self.secret:
            return Invitation.objects.filter(secret=self.secret, is_active=True).first()
        return None


class TembaSignupForm(InviteFormMixin, SignupForm):

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
        widget=forms.TextInput(attrs={"placeholder": _("My Company, Inc.")}),
    )

    timezone = TimeZoneFormField(widget=forms.widgets.HiddenInput())

    field_order = ["first_name", "last_name", "email", "password1", "workspace"]

    def __init__(self, secret, *args, **kwargs):
        super().__init__(secret, *args, **kwargs)
        if self.invite:
            self.fields["email"].widget = forms.widgets.HiddenInput()
            self.fields["workspace"].widget = forms.widgets.HiddenInput()
            self.fields["workspace"].help_text = ""

    def clean_email(self):
        if self.invite:
            return self.invite.email
        return super().clean_email()

    def save(self, request):
        # remove our invite from the session
        if "invite_secret" in request.session:
            del request.session["invite_secret"]

        if self.invite:
            request.session["account_verified_email"] = self.invite.email
        user = super(TembaSignupForm, self).save(request)

        # if we have an invite, accept it
        if self.invite:
            self.invite.accept(user)
            org = self.invite.org
        else:
            # otherwise, create a new org for us
            org = Org.create(user, self.cleaned_data["workspace"], self.cleaned_data["timezone"])

        switch_to_org(request, org)
        return user


class TembaLoginForm(InviteFormMixin, LoginForm):
    def __init__(self, secret, *args, **kwargs):
        super().__init__(secret, *args, **kwargs)
        if self.invite:
            self.fields["login"].widget = forms.widgets.HiddenInput()

    def clean_login(self):
        if self.invite:
            return self.invite.email

        # this is tested by allauth
        return super().clean_login()  # pragma: no cover


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
