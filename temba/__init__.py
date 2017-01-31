from __future__ import absolute_import

# This will make sure the app is always imported when
# Django starts so that shared_task will use this app.
from .temba_celery import app as celery_app  # noqa

# Patch django-modeltranslation's get_language to not check the active language is configured in Django
from modeltranslation import utils

utils.get_language = lambda: utils._get_language()
