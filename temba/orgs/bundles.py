from __future__ import unicode_literals

from decimal import Decimal

WELCOME_TOPUP_SIZE = 1000

BUNDLES = (dict(cents="2000", credits=1000, feature=""),
           dict(cents="4000", credits=2500, feature=""),
           dict(cents="14000", credits=10000, feature=""),
           dict(cents="25000", credits=20000, feature=""),
           dict(cents="55000", credits=50000, feature=""),
           dict(cents="100000", credits=100000, feature="Additional Users"),
           dict(cents="225000", credits=250000, feature=""),
           dict(cents="400000", credits=500000, feature=""),
           dict(cents="700000", credits=1000000, feature="Subaccounts & Credit Distribution"))

for b in BUNDLES:
    b['description'] = "$%d - %d Credits" % (int(b['cents']) / 100, b['credits'])
    b['dollars'] = int(b['cents']) / 100
    b['per_credit'] = per_credit = (Decimal(b['cents']) / Decimal(b['credits'])).quantize(Decimal(".1"))

BUNDLE_MAP = dict()
for b in BUNDLES:
    BUNDLE_MAP[b['cents']] = b

# a map of our price in US cents vs the number of messages you purchase for
# that price
BUNDLE_CHOICES = [(b['cents'], b['description']) for b in BUNDLES]
