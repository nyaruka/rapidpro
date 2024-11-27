import smtplib

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template import loader
from django.utils import timezone

from .conf import parse_smtp_url


class EmailSender:
    """
    Sends template based branded emails.
    """

    def __init__(self, branding: dict, connection, from_email: str = None, org=None):
        self.branding = branding
        self.connection = connection  # can be none to use default Django email connection
        self.from_email = from_email if from_email else getattr(settings, "DEFAULT_FROM_EMAIL", "website@rapidpro.io")
        self.org = org

    @classmethod
    def from_email_type(cls, branding: dict, email_type: str, org=None):
        """
        Creates a sender from the given email type setting in the given branding.
        """
        email_cfg = branding.get("emails", {}).get(email_type)
        if email_cfg and email_cfg.startswith("smtp://"):
            return cls.from_smtp_url(branding, email_cfg)

        return cls(branding, connection=None, from_email=email_cfg, org=org)

    @classmethod
    def from_smtp_url(cls, branding: dict, smtp_url: str, org=None):
        """
        Creates a sender from the given SMTP configuration URL.
        """
        host, port, username, password, from_email, tls = parse_smtp_url(smtp_url)

        connection = get_connection(
            None,
            fail_silently=False,
            host=host,
            port=port,
            username=username,
            password=password,
            use_tls=tls,
        )

        return cls(branding, connection, from_email, org=org)

    def send(self, recipients: list, subject: str, template: str, context: dict):
        """
        Sends a multi-part email rendered from templates for the text and html parts. `template` should be the name of
        the template, without .html or .txt (e.g. 'channels/email/power_charging').
        """
        from temba.notifications.incidents.builtin import OrgSMTPFailedIncidentType

        html_template = loader.get_template(template + ".html")
        text_template = loader.get_template(template + ".txt")

        context["subject"] = subject
        context["branding"] = self.branding
        context["now"] = timezone.now()

        html = html_template.render(context)
        text = text_template.render(context)
        try:
            send_email(recipients, subject, text, html, self.from_email, self.connection)
        except smtplib.SMTPException as e:
            # Do not create incident for SMTP settings test, raise the error for the view to show validation error
            if template == "orgs/email/smtp_test":
                raise e

            OrgSMTPFailedIncidentType.get_or_create(self.org)
            return
        except Exception as e:
            raise e
        OrgSMTPFailedIncidentType.find_and_end(self.org)


def send_email(recipients: list, subject: str, text: str, html: str, from_email: str, connection=None):
    """
    Actually sends the email. Having this as separate function makes testing multi-part emails easier
    """
    if settings.SEND_EMAILS:
        message = EmailMultiAlternatives(subject, text, from_email, recipients, connection=connection)
        message.attach_alternative(html, "text/html")
        message.send()
    else:  # pragma: no cover
        # just print to console if we aren't meant to send emails
        print("------------- Skipping sending email, SEND_EMAILS is False -------------")
        print(f"To: {', '.join(recipients)}")
        print(f"From: {from_email}")
        print(f"Subject: {subject}")
        print()
        print(text)
        print("------------------------------------------------------------------------")
