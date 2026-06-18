from django.conf import settings
from django.core.checks import Error, register


@register()
def websockets_auth_secret(app_configs, **kwargs):
    errors = []

    if not settings.WEBSOCKETS_AUTH_SECRET:
        errors.append(
            Error(
                "WEBSOCKETS_AUTH_SECRET is not set.",
                hint="Set WEBSOCKETS_AUTH_SECRET in Django settings to the shared secret configured on the "
                "realtime messaging server. The websockets API refuses requests without it.",
            )
        )

    return errors
