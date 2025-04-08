from allauth.account.adapter import DefaultAccountAdapter
from allauth.core import context as allauth_context
from allauth.mfa.adapter import DefaultMFAAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.signals import social_account_added

from django.dispatch import receiver
from django.utils import timezone

from temba.utils.email.send import EmailSender


class TembaAccountAdapter(DefaultAccountAdapter):
    def send_mail(self, template_prefix, email, context):

        # our emails need some additional context
        context["branding"] = self.request.branding
        context["now"] = timezone.now()

        sender = EmailSender.from_email_type(self.request.branding, "notifications")
        sender.send([email], template_prefix, context)

    def is_open_for_signup(self, request):
        return "signups" in request.branding.get("features")


class TembaSocialAccountAdapter(DefaultSocialAccountAdapter):
    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        user.fetch_avatar(sociallogin.account.get_avatar_url())
        return user


@receiver(social_account_added)
def update_user_profile_picture(request, sociallogin, **kwargs):
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
