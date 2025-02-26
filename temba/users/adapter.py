from allauth.account.adapter import DefaultAccountAdapter

from django.utils import timezone

from temba.utils.email.send import EmailSender


class TembaAccountAdapter(DefaultAccountAdapter):
    def send_mail(self, template_prefix, email, context):

        sender = EmailSender.from_email_type(self.request.branding, "notifications")

        # prefix for allauth is account/email but we prefer users/email
        template_prefix = template_prefix.replace("account/email/", "users/email/")

        context["branding"] = self.request.branding
        context["now"] = timezone.now()

        sender.send([email], template_prefix, context)
