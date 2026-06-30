from .settings_dev import *  # noqa
from .settings_dev import STATIC_URL

COMPRESS_ENABLED = True
COMPRESS_OFFLINE = True
COMPRESS_CSS_HASHING_METHOD = "content"
COMPRESS_OFFLINE_CONTEXT = dict(
    STATIC_URL=STATIC_URL, base_template="frame.html", brand=BRAND, debug=False, testing=False
)
