from datetime import datetime
from importlib import resources
from zoneinfo import ZoneInfo

from timezone_field import TimeZoneFormField as BaseTimeZoneFormField

# legacy timezone aliases which aren't in zone.tab and are no longer offered as choices but may still exist in old data
ALIAS_TIMEZONE_COUNTRY = {
    "America/Montreal": "CA",
    "Canada/Atlantic": "CA",
    "Canada/Central": "CA",
    "Canada/Eastern": "CA",
    "Canada/Mountain": "CA",
    "Canada/Newfoundland": "CA",
    "Canada/Pacific": "CA",
    "GMT": "",
    "US/Alaska": "US",
    "US/Arizona": "US",
    "US/Central": "US",
    "US/Eastern": "US",
    "US/Hawaii": "US",
    "US/Mountain": "US",
    "US/Pacific": "US",
    "UTC": "",
}


def _zone_tab_countries() -> dict:
    """
    Parses the IANA zone.tab file into a mapping of timezone name to country code.
    """
    zones = {}
    for line in (resources.files("tzdata.zoneinfo") / "zone.tab").read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            code, _, name = line.split("\t")[:3]
            zones[name] = code
    return zones


_ZONE_TAB_COUNTRIES = _zone_tab_countries()

TIMEZONE_COUNTRY = _ZONE_TAB_COUNTRIES | ALIAS_TIMEZONE_COUNTRY

# the timezones we offer as choices - the zone.tab zones plus UTC
COMMON_TIMEZONES = sorted(set(_ZONE_TAB_COUNTRIES) | {"UTC"})

PRETTY_TIMEZONE_CHOICES = []

for tz in COMMON_TIMEZONES:
    now = datetime.now(ZoneInfo(tz))
    ofs = now.strftime("%z")
    PRETTY_TIMEZONE_CHOICES.append((int(ofs), tz, "(GMT%s) %s" % (ofs, tz)))

PRETTY_TIMEZONE_CHOICES.sort()
PRETTY_TIMEZONE_CHOICES = [(tz, label) for ofs, tz, label in PRETTY_TIMEZONE_CHOICES]


class TimeZoneFormField(BaseTimeZoneFormField):
    def __init__(self, *args, **kwargs):
        kwargs["choices"] = PRETTY_TIMEZONE_CHOICES

        super().__init__(*args, **kwargs)


def timezone_to_country_code(tz) -> str:
    return TIMEZONE_COUNTRY.get(str(tz), "")


def country_timezones(country_code: str) -> list:
    """
    Gets the timezone names for the given country code - intentionally includes legacy aliases (e.g. US/Pacific)
    which may still exist in old data.
    """
    return sorted(tz for tz, code in TIMEZONE_COUNTRY.items() if code == country_code)
