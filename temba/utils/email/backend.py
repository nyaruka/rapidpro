import email.policy
import smtplib
import ssl
from email.utils import getaddresses
from functools import cache

from django.core.mail import DNS_NAME
from django.core.mail.backends.base import BaseEmailBackend

from .conf import parse_smtp_url

CUSTOM_SMTP_MAILER_ALIAS = "custom_smtp"


@cache
def get_ssl_context():
    # loads the system CA bundle so worth caching, and MAILERS constructs a new backend instance per send
    return ssl.create_default_context()


class CustomSMTPBackend(BaseEmailBackend):
    """
    An email backend which sends each message using the SMTP configuration URL attached to it. Used for email which
    needs to be sent with per-workspace SMTP configuration rather than by the statically configured default mailer.
    """

    def __init__(self, timeout=10, **kwargs):
        super().__init__(**kwargs)
        self.timeout = timeout

    def send_messages(self, email_messages) -> int:
        # parse configs up front so that a bad message can't abort a batch part way through sending
        to_send = []
        for message in email_messages:
            host, port, username, password, _, tls = parse_smtp_url(getattr(message, "smtp_url", None))
            if not host:
                raise ValueError("Messages sent with the custom SMTP mailer require an attached SMTP URL.")
            to_send.append((message, host, port, username, password, tls))

        num_sent = 0
        for message, host, port, username, password, tls in to_send:
            recipients = [a for _, a in getaddresses(message.recipients()) if a]
            if not recipients:
                continue

            with smtplib.SMTP(host, port, local_hostname=DNS_NAME.get_fqdn(), timeout=self.timeout) as conn:
                if tls:
                    conn.starttls(context=get_ssl_context())
                if username and password:
                    conn.login(username, password)

                # pass the envelope explicitly as smtplib would otherwise derive it from the message headers which
                # never include bcc recipients
                conn.send_message(
                    message.message(policy=email.policy.SMTP),
                    from_addr=getaddresses([message.from_email])[0][1],
                    to_addrs=recipients,
                )
                num_sent += 1

        return num_sent
