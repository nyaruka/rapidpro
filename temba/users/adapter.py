from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.models import EmailAddress
from allauth.core import context as allauth_context
from allauth.mfa.adapter import DefaultMFAAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.signals import social_account_added

from django.contrib import messages
from django.dispatch import receiver
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from temba.orgs.models import Invitation
from temba.orgs.views.views import switch_to_org
from temba.users.models import User
from temba.utils.email.send import EmailSender


class InviteAdapterMixin:
    def post_login(self, request, user, *, email_verification, signal_kwargs, email, signup, redirect_url):
        # if we are working with an invite, mark it as accepted
        secret = request.session.pop("invite_secret", None)
        if secret:
            invite = Invitation.objects.filter(secret=secret, is_active=True).first()
            if invite:
                # this can happen if a SSO with a different email address is used
                if user.email != invite.email:  # pragma: no cover
                    messages.add_message(
                        self.request,
                        messages.WARNING,
                        _(f"To accept this invitation, please login with {invite.email}."),
                    )
                else:
                    invite.accept(user)
                    switch_to_org(request, user)

        return super().post_login(
            request,
            user,
            email_verification=email_verification,
            signal_kwargs=signal_kwargs,
            email=email,
            signup=signup,
            redirect_url=redirect_url,
        )

    def is_open_for_signup(self, request, sociallogin=None):
        # if we have a signup invite, we need to allow signups
        secret = request.GET.get("invite", request.session.get("invite_secret", None))

        if secret and Invitation.objects.filter(secret=secret, is_active=True).exists():
            return True

        return "signups" in request.branding.get("features")


class TembaAccountAdapter(InviteAdapterMixin, DefaultAccountAdapter):
    def send_mail(self, template_prefix, email, context):

        # our emails need some additional context
        context["branding"] = self.request.branding
        context["now"] = timezone.now()

        sender = EmailSender.from_email_type(self.request.branding, "notifications")
        sender.send([email], template_prefix, context)


class TembaSocialAccountAdapter(InviteAdapterMixin, DefaultSocialAccountAdapter):  # pragma: no cover

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        extra = sociallogin.account.extra_data
        email = extra.get("email") or extra.get("preferred_username") or extra.get("upn")
        if not user.email:
            user.email = email
        if "email" not in data and email:
            data["email"] = email
        return user

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        email = user.email
        if email:
            EmailAddress.objects.update_or_create(
                user=user,
                email=email,
                defaults={"verified": True, "primary": True},
            )
        return user

    def pre_social_login(self, request, sociallogin):
        # extract email from various possible fields
        email = None
        if hasattr(sociallogin, "account") and hasattr(sociallogin.account, "extra_data"):
            extra_data = sociallogin.account.extra_data
            # check multiple possible email fields
            email = (
                extra_data.get("email")
                or extra_data.get("upn")  # azure ad uses upn
                or extra_data.get("preferred_username")
            )

        # if we have an email but no email_addresses set, create one
        if email and not sociallogin.email_addresses:
            sociallogin.email_addresses = [EmailAddress(email=email, verified=True, primary=True)]

        # if user exists, connect the social account
        if email and not sociallogin.is_existing:
            user = User.objects.filter(email=email).first()
            if user:
                sociallogin.connect(request, user)


@receiver(social_account_added)
def update_user_profile_picture(request, sociallogin, **kwargs):  # pragma: no cover
    user = sociallogin.user
    user.fetch_avatar(sociallogin.account.get_avatar_url())


class TembaMFAAdapter(DefaultMFAAdapter):
    def _get_site_name(self) -> str:
        return allauth_context.request.get_host()

    def build_totp_url(self, user, secret: str) -> str:
        url = super().build_totp_url(user, secret)

        # some totp clients support images in the QR code
        url = f"{url}&image={self.request.branding.get("logos").get("favico")}"
        return url
