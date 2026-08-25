import email.policy
import smtplib
import ssl

from django.core.mail import DNS_NAME
from django.core.mail.backends.base import BaseEmailBackend

from .conf import parse_smtp_url

DYNAMIC_MAILER_ALIAS = "dynamic"


class DynamicEmailBackend(BaseEmailBackend):
    """
    An email backend which sends each message using the SMTP configuration URL attached to it. Used for email which
    needs to be sent with per-workspace SMTP configuration rather than by the statically configured default mailer.
    """

    def __init__(self, timeout=10, **kwargs):
        super().__init__(**kwargs)
        self.timeout = timeout

    def send_messages(self, email_messages) -> int:
        num_sent = 0

        for message in email_messages:
            smtp_url = getattr(message, "smtp_url", None)
            if not smtp_url:
                raise ValueError("Messages sent with the dynamic mailer require an attached SMTP URL.")

            host, port, username, password, _, tls = parse_smtp_url(smtp_url)

            with smtplib.SMTP(host, port, local_hostname=DNS_NAME.get_fqdn(), timeout=self.timeout) as conn:
                if tls:
                    conn.starttls(context=ssl.create_default_context())
                if username and password:
                    conn.login(username, password)

                conn.send_message(message.message(policy=email.policy.SMTP))
                num_sent += 1

        return num_sent
