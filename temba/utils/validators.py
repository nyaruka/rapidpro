import bleach
import regex

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_without_html_tags(value):
    if not value:
        return

    clean_value = bleach.clean(
        text=value, tags=[], attributes={}, styles=[], protocols=[], strip=True, strip_comments=True
    )

    # if bleach had to change anything in the input we consider it as invalid
    if value != clean_value:
        raise ValidationError(_("Input must not contain HTML tags."), code="invalid")


def validate_full_domain(value):
    """
    Fully validates a domain name as compilant with the standard rules:
        - Composed of series of labels concatenated with dots, as are all domain names.
        - Each label must be between 1 and 63 characters long.
        - The entire hostname (including the delimiting dots) has a maximum of 255 characters.
        - Only characters 'a' through 'z' (in a case-insensitive manner), the digits '0' through '9'.
        - Labels can't start or end with a hyphen.

    Adapted from: https://stackoverflow.com/a/17822192
    """
    HOSTNAME_LABEL_PATTERN = regex.compile("(?!-)[A-Z\d-]+(?<!-)$", regex.IGNORECASE | regex.V0)

    if not value:
        return

    if len(value) > 255:
        raise ValidationError(_("The domain name cannot be composed of more than 255 characters."))

    if value[-1:] == ".":
        value = value[:-1]  # strip exactly one dot from the right, if present

    for label in value.split("."):
        if len(label) > 63:
            raise ValidationError(
                _("The label '%(label)s' is too long (maximum is 63 characters).") % {"label": label}
            )
        if not HOSTNAME_LABEL_PATTERN.match(label):
            raise ValidationError(_("Unallowed characters in label '%(label)s'.") % {"label": label})
