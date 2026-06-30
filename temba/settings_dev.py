# -----------------------------------------------------------------------------------
# Sample RapidPro settings file, this should allow you to deploy RapidPro locally on
# a PostgreSQL database.
#
# The following are requirements:
#     - a postgreSQL database named 'temba', with a user name 'temba' and
#       password 'temba' (with postgis extensions installed)
#     - a valkey instance listening on localhost
# -----------------------------------------------------------------------------------

import os
import warnings

from .settings_common import *  # noqa

DEBUG = True

# allow all hosts in dev
ALLOWED_HOSTS = ["*"]

INTERNAL_IPS = ("127.0.0.1",)

COMPONENTS_DEV_MODE = bool(os.environ.get("COMPONENTS_DEV_MODE"))
COMPONENTS_DEV_URL = os.environ.get("COMPONENTS_DEV_URL", "")

# -----------------------------------------------------------------------------------
# Mailroom - localhost for dev, no auth token
# -----------------------------------------------------------------------------------
MAILROOM_URL = os.environ.get("MAILROOM_URL", "http://localhost:8091")
MAILROOM_AUTH_TOKEN = os.environ.get("MAILROOM_AUTH_TOKEN")

# -----------------------------------------------------------------------------------
# WebSockets - shared secret for the realtime messaging server (must match its config)
# -----------------------------------------------------------------------------------
WEBSOCKETS_AUTH_SECRET = "topsecret"

# -----------------------------------------------------------------------------------
# In development, add in extra logging for exceptions and the debug toolbar
# -----------------------------------------------------------------------------------
MIDDLEWARE = ("temba.middleware.ExceptionMiddleware",) + MIDDLEWARE

# -----------------------------------------------------------------------------------
# In development, perform background tasks in the web thread (synchronously)
# -----------------------------------------------------------------------------------
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# -----------------------------------------------------------------------------------
# This setting throws an exception if a naive datetime is used anywhere. (they should
# always contain a timezone)
# -----------------------------------------------------------------------------------
warnings.filterwarnings(
    "error", r"DateTimeField .* received a naive datetime", RuntimeWarning, r"django\.db\.models\.fields"
)

# -----------------------------------------------------------------------------------
# Make our sitestatic URL be our static URL on development
# -----------------------------------------------------------------------------------
STATIC_URL = "/static/"
