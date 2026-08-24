from django.conf import settings
from django.core.checks import Error, register


@register()
def storage(app_configs, **kwargs):
    errors = []

    for name in ("default", "archives", "public", "staticfiles"):
        if name not in settings.STORAGES:
            errors.append(
                Error(
                    f"Missing '{name}' storage config.",
                    hint=f"Add configuration for '{name}' to STORAGES in Django settings.",
                )
            )

    if not settings.STORAGE_URL:
        errors.append(
            Error(
                "No storage URL set.",
                hint='Set STORAGE_URL in your Django settings. Should be "https://"+AWS_BUCKET_DOMAIN if using S3.',
            )
        )
    elif settings.STORAGE_URL.endswith("/"):
        errors.append(
            Error("Storage URL shouldn't end with trailing slash.", hint="Remove trailing slash in STORAGE_URL.")
        )
    return errors


@register()
def branding_emails(app_configs, **kwargs):
    errors = []

    for email_type, from_email in settings.BRAND.get("emails", {}).items():
        if isinstance(from_email, str) and from_email.startswith("smtp://"):
            errors.append(
                Error(
                    f"Branding email address for '{email_type}' is an SMTP URL.",
                    hint=f"Email addresses in BRAND are from addresses only. Move the SMTP configuration to a "
                    f"'{email_type}' entry in MAILERS in Django settings.",
                )
            )

    return errors
