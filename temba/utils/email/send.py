import email.policy
import smtplib
import ssl

from django.conf import settings
from django.core.mail import DEFAULT_MAILER_ALIAS, DNS_NAME, EmailMultiAlternatives, mailers
from django.template import loader
from django.utils import timezone

from .conf import parse_smtp_url

# how long we wait when checking SMTP settings which a user has just entered
SMTP_CHECK_TIMEOUT = 10


class EmailSender:
    """
    Sends template based branded emails.
    """

    def __init__(self, branding: dict, from_email: str = None, mailer: str = DEFAULT_MAILER_ALIAS):
        self.branding = branding
        self.from_email = from_email if from_email else getattr(settings, "DEFAULT_FROM_EMAIL", "website@rapidpro.io")
        self.mailer = mailer  # alias of the mailer in the MAILERS setting used to send

    @classmethod
    def from_email_type(cls, branding: dict, email_type: str):
        """
        Creates a sender for the given type of email. The from address comes from the branding, and the email is sent
        by the mailer of the same name as the email type if one is configured, or the default mailer otherwise.
        """
        from_email = branding.get("emails", {}).get(email_type)
        mailer = email_type if email_type in mailers else DEFAULT_MAILER_ALIAS

        return cls(branding, from_email, mailer)

    def render_template(self, template_path: str, postfixes, context: dict):
        for postfix in postfixes:
            try:
                template = loader.get_template(f"{template_path}{postfix}")
                return template.render(context)
            except loader.TemplateDoesNotExist:
                pass
        return None

    def compose(self, recipients: list, template: str, context: dict, subject: str = None) -> EmailMultiAlternatives:
        """
        Composes a multi-part message rendered from templates for the text and html parts. `template` should be the
        name of the template, without .html or .txt (e.g. 'channels/email/power_charging').
        """
        context["branding"] = self.branding
        context["now"] = timezone.now()

        if not subject:
            subject = self.render_template(template, ["_subject.txt"], context)
            if not subject:  # pragma: no cover
                raise ValueError("No subject provided and subject template doesn't exist")

        # make sure our subject is a single line
        subject = " ".join(subject.splitlines()).strip()

        text = self.render_template(template, [".txt"], context)
        html = self.render_template(template, [".html", "_message.html"], context)

        if not html:  # pragma: no cover
            raise ValueError("Could not render message template for %s" % template)

        message = EmailMultiAlternatives(subject, text, self.from_email, recipients)
        message.attach_alternative(html, "text/html")
        return message

    def send(self, recipients: list, template: str, context: dict, subject: str = None):
        """
        Composes and sends a message using this sender's mailer.
        """
        self.compose(recipients, template, context, subject).send(using=self.mailer)


def send_via_smtp(smtp_url: str, message: EmailMultiAlternatives):
    """
    Sends an already composed message using the given SMTP configuration, rather than one of the configured mailers.
    Used to check SMTP settings which a user has just entered and which aren't part of this instance's configuration.
    """
    host, port, username, password, _, tls = parse_smtp_url(smtp_url)

    with smtplib.SMTP(host, port, local_hostname=DNS_NAME.get_fqdn(), timeout=SMTP_CHECK_TIMEOUT) as conn:
        if tls:
            conn.starttls(context=ssl.create_default_context())
        if username and password:
            conn.login(username, password)

        conn.send_message(message.message(policy=email.policy.SMTP))
