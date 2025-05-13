from django.core.exceptions import ValidationError
from django.core.validators import validate_email


def is_valid_address(address):
    """
    Very loose email address check
    """
    if not address:
        return False

    try:
        validate_email(address)
    except ValidationError:
        return False

    return True
