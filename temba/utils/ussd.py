import re
import threading

from django.conf import settings
from django.db import models
from django.utils import timezone

from temba.orgs.models import User

_thread_locals = threading.local()


def set_current_user(user):
    _thread_locals.user = user


def get_current_user():
    return getattr(_thread_locals, 'user', None)


def remove_current_user():
    _thread_locals.user = None


class AuthSignature(models.Model):
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, editable=False,
                                   related_name='%(class)s_created')
    modified_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, editable=False,
                                    related_name='%(class)s_modified')
    created_on = models.DateTimeField(auto_now_add=True, db_index=True)
    modified_on = models.DateTimeField(auto_now=True, db_index=True)
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        user = get_current_user()
        if user and user.is_authenticated:
            self.modified_by = user
            self.modified_on = timezone.now()
            if not self.id:
                self.created_by = user
        super(AuthSignature, self).save(*args, **kwargs)

    class Meta:
        abstract = True


def standard_urn(urn):
    if len(str(urn)) < 10:
        raise Exception(f"Invalid msisdn length, given msisdn is {urn} if length {len(str(urn))} and required is 10 "
                        f"digits")
    urn = urn.strip()
    urn = urn
    if urn[0] == "0":
        # add prefix
        urn = re.sub('0', settings.DEFAULT_COUNTRY_CODE, urn, 1)  # TODO must support other countries
    elif urn[0] == "+":
        # add prefix
        urn = urn[1:]  # remove the + it causes problems
    else:
        urn = urn
    return urn
