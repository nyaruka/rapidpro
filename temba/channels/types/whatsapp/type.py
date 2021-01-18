import json
import mimetypes

import requests
from django_redis import get_redis_connection

from django.conf.urls import url
from django.forms import ValidationError
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _

from temba.channels.models import Channel
from temba.channels.types.whatsapp.views import (
    ClaimView,
    DetailsView,
    RefreshView,
    SyncLogsView,
    TemplatesView,
    UpdateAboutView,
    UpdateBusinessProfileView,
    UpdateProfilePhotoView,
)
from temba.contacts.models import URN
from temba.templates.models import TemplateTranslation
from temba.utils import rcache

from ...models import ChannelType

# Mapping from WhatsApp status to RapidPro status
STATUS_MAPPING = dict(
    PENDING=TemplateTranslation.STATUS_PENDING,
    APPROVED=TemplateTranslation.STATUS_APPROVED,
    REJECTED=TemplateTranslation.STATUS_REJECTED,
)

# This maps from WA iso-639-2 codes to our internal 639-3 codes
LANGUAGE_MAPPING = dict(
    af=("afr", None),  # Afrikaans
    sq=("sqi", None),  # Albanian
    ar=("ara", None),  # Arabic
    az=("aze", None),  # Azerbaijani
    bn=("ben", None),  # Bengali
    bg=("bul", None),  # Bulgarian
    ca=("cat", None),  # Catalan
    zh_CN=("zho", "CN"),  # Chinese (CHN)
    zh_HK=("zho", "HK"),  # Chinese (HKG)
    zh_TW=("zho", "TW"),  # Chinese (TAI)
    hr=("hrv", None),  # Croatian
    cs=("ces", None),  # Czech
    da=("dah", None),  # Danish
    nl=("nld", None),  # Dutch
    en=("eng", None),  # English
    en_GB=("eng", "GB"),  # English (UK)
    en_US=("eng", "US"),  # English (US)
    et=("est", None),  # Estonian
    fil=("fil", None),  # Filipino
    fi=("fin", None),  # Finnish
    fr=("fra", None),  # French
    de=("deu", None),  # German
    el=("ell", None),  # Greek
    gu=("gul", None),  # Gujarati
    ha=("hau", None),  # Hausa
    he=("enb", None),  # Hebrew
    hi=("hin", None),  # Hindi
    hu=("hun", None),  # Hungarian
    id=("ind", None),  # Indonesian
    ga=("gle", None),  # Irish
    it=("ita", None),  # Italian
    ja=("jpn", None),  # Japanese
    kn=("kan", None),  # Kannada
    kk=("kaz", None),  # Kazakh
    ko=("kor", None),  # Korean
    lo=("lao", None),  # Lao
    lv=("lav", None),  # Latvian
    lt=("lit", None),  # Lithuanian
    ml=("mal", None),  # Malayalam
    mk=("mkd", None),  # Macedonian
    ms=("msa", None),  # Malay
    mr=("mar", None),  # Marathi
    nb=("nob", None),  # Norwegian
    fa=("fas", None),  # Persian
    pl=("pol", None),  # Polish
    pt_BR=("por", "BR"),  # Portuguese (BR)
    pt_PT=("por", "PT"),  # Portuguese (POR)
    pa=("pan", None),  # Punjabi
    ro=("ron", None),  # Romanian
    ru=("rus", None),  # Russian
    sr=("srp", None),  # Serbian
    sk=("slk", None),  # Slovak
    sl=("slv", None),  # Slovenian
    es=("spa", None),  # Spanish
    es_AR=("spa", "AR"),  # Spanish (ARG)
    es_ES=("spa", "ES"),  # Spanish (SPA)
    es_MX=("spa", "MX"),  # Spanish (MEX)
    sw=("swa", None),  # Swahili
    sv=("swe", None),  # Swedish
    ta=("tam", None),  # Tamil
    te=("tel", None),  # Telugu
    th=("tha", None),  # Thai
    tr=("tur", None),  # Turkish
    uk=("ukr", None),  # Ukrainian
    ur=("urd", None),  # Urdu
    uz=("uzb", None),  # Uzbek
    vi=("vie", None),  # Vietnamese]
    zu=("zul", None),  # Zulu
)

CONFIG_FB_BUSINESS_ID = "fb_business_id"
CONFIG_FB_ACCESS_TOKEN = "fb_access_token"
CONFIG_FB_NAMESPACE = "fb_namespace"
CONFIG_FB_TEMPLATE_LIST_DOMAIN = "fb_template_list_domain"

TEMPLATE_LIST_URL = "https://%s/v3.3/%s/message_templates"

DOCKER_PROFILE_ABOUT_GROUP = "docker_profile_about"
DOCKER_BUSINESS_PROFILE_GROUP = "docker_business_profile"
DOCKER_PROFILE_PHOTO_GROUP = "docker_profile_photo"


class WhatsAppType(ChannelType):
    """
    A WhatsApp Channel Type
    """

    extra_links = [
        dict(name=_("Message Templates"), link="channels.types.whatsapp.templates"),
        dict(name=_("WhatsApp Details"), link="channels.types.whatsapp.details"),
    ]

    code = "WA"
    category = ChannelType.Category.SOCIAL_MEDIA

    courier_url = r"^wa/(?P<uuid>[a-z0-9\-]+)/(?P<action>receive)$"

    name = "WhatsApp"
    icon = "icon-whatsapp"

    claim_blurb = _("If you have an enterprise WhatsApp account, you can connect it to communicate with your contacts")
    claim_view = ClaimView

    schemes = [URN.WHATSAPP_SCHEME]
    max_length = 4096
    attachment_support = True

    def is_available_to(self, user):
        return user.groups.filter(name="Beta")

    def get_urls(self):
        return [
            self.get_claim_url(),
            url(r"^(?P<uuid>[a-z0-9\-]+)/refresh$", RefreshView.as_view(), name="refresh"),
            url(r"^(?P<uuid>[a-z0-9\-]+)/templates$", TemplatesView.as_view(), name="templates"),
            url(r"^(?P<uuid>[a-z0-9\-]+)/sync_logs$", SyncLogsView.as_view(), name="sync_logs"),
            url(r"^(?P<uuid>[a-z0-9\-]+)/details$", DetailsView.as_view(), name="details"),
            url(r"^(?P<uuid>[a-z0-9\-]+)/about$", UpdateAboutView.as_view(), name="about"),
            url(r"^(?P<uuid>[a-z0-9\-]+)/photo$", UpdateProfilePhotoView.as_view(), name="photo"),
            url(
                r"^(?P<uuid>[a-z0-9\-]+)/business_profile$",
                UpdateBusinessProfileView.as_view(),
                name="business_profile",
            ),
        ]

    def deactivate(self, channel):
        # deactivate all translations associated with us
        TemplateTranslation.trim(channel, [])

    def activate(self, channel):
        domain = channel.org.get_brand_domain()
        headers = {"Authorization": "Bearer %s" % channel.config[Channel.CONFIG_AUTH_TOKEN]}

        # first set our callbacks
        payload = {"webhooks": {"url": "https://" + domain + reverse("courier.wa", args=[channel.uuid, "receive"])}}
        resp = requests.patch(
            channel.config[Channel.CONFIG_BASE_URL] + "/v1/settings/application", json=payload, headers=headers
        )

        if resp.status_code != 200:
            raise ValidationError(_("Unable to register callbacks: %s", resp.content))

        # update our quotas so we can send at 15/s
        payload = {
            "messaging_api_rate_limit": ["15", "54600", "1000000"],
            "contacts_scrape_rate_limit": "1000000",
            "contacts_api_rate_limit": ["15", "54600", "1000000"],
        }
        resp = requests.patch(
            channel.config[Channel.CONFIG_BASE_URL] + "/v1/settings/application", json=payload, headers=headers
        )

        if resp.status_code != 200:
            raise ValidationError(_("Unable to configure channel: %s", resp.content))

    def profile_about(self, channel):
        return "BAR"
        redis_conn = get_redis_connection()
        cache_key = str(channel.uuid)

        cached = rcache.get(redis_conn, DOCKER_PROFILE_ABOUT_GROUP, cache_key)
        if cached is not None:  # pragma: no cover
            return cached

        return self.fetch_profile_about(channel)

    def fetch_profile_about(self, channel):
        headers = {"Authorization": "Bearer %s" % channel.config[Channel.CONFIG_AUTH_TOKEN]}
        try:
            response = requests.get(
                channel.config[Channel.CONFIG_BASE_URL] + "/v1/settings/profile/about", headers=headers
            )
        except Exception as e:
            raise Exception("error reaching server") from e
        about = response.json().get("settings", {}).get("profile", {}).get("about", {}).get("text")
        if about:
            redis_conn = get_redis_connection()
            cache_key = str(channel.uuid)
            rcache.set(redis_conn, DOCKER_PROFILE_ABOUT_GROUP, cache_key, about)
        return about

    def set_profile_about(self, channel, about):
        headers = {"Authorization": "Bearer %s" % channel.config[Channel.CONFIG_AUTH_TOKEN]}
        payload = {"text": about}

        try:
            response = requests.patch(
                channel.config[Channel.CONFIG_BASE_URL] + "/v1/settings/profile/about", json=payload, headers=headers
            )
        except Exception as e:
            raise Exception("error reaching server") from e

        if response.status_code != 200:
            try:
                raise Exception(response.json()["errors"][0]["title"])
            except KeyError as e:
                raise Exception("error parsing response") from e

        self.fetch_profile_about(channel)

    def profile_photo_url(self, channel):
        return "https://ureport.in/sitestatic/img/u-report-global-logo-white.png"
        redis_conn = get_redis_connection()
        cache_key = str(channel.uuid)

        cached = rcache.get(redis_conn, DOCKER_PROFILE_PHOTO_GROUP, cache_key)
        if cached is not None:  # pragma: no cover
            return cached

        return self.fetch_profile_photo_url(channel)

    def fetch_profile_photo_url(self, channel):
        headers = {"Authorization": "Bearer %s" % channel.config[Channel.CONFIG_AUTH_TOKEN]}
        try:
            response = requests.get(
                channel.config[Channel.CONFIG_BASE_URL] + "/v1/settings/profile/photo?format=link", headers=headers
            )
        except Exception as e:
            raise Exception("error reaching server") from e

        photo_link = response.json().get("settings", {}).get("profile", {}).get("photo", {}).get("link")
        if photo_link:
            redis_conn = get_redis_connection()
            cache_key = str(channel.uuid)
            rcache.set(redis_conn, DOCKER_PROFILE_PHOTO_GROUP, cache_key, photo_link)
        return photo_link

    def set_profile_photo(self, channel, uploaded_image):
        mime_type = mimetypes.guess_type(uploaded_image.name)[0]

        headers = {"Authorization": "Bearer %s" % channel.config[Channel.CONFIG_AUTH_TOKEN]}
        headers["Content-Type"] = mime_type

        try:
            response = requests.post(
                channel.config[Channel.CONFIG_BASE_URL] + "/v1/settings/profile/photo",
                data=uploaded_image.file,
                headers=headers,
            )
        except Exception as e:
            raise Exception("error reaching server") from e

        if response.status_code not in [200, 201]:
            try:
                raise Exception(response.json()["errors"][0]["title"])
            except KeyError as e:
                raise Exception("error parsing response") from e

        self.fetch_profile_photo_url(channel)

    def business_profile(self, channel):
        return dict(description="Foo")

        redis_conn = get_redis_connection()
        cache_key = str(channel.uuid)

        cached = rcache.get(redis_conn, DOCKER_BUSINESS_PROFILE_GROUP, cache_key)
        if cached is not None:  # pragma: no cover
            return json.loads(cached)

        return self.fetch_business_profile(channel)

    def fetch_business_profile(self, channel):
        headers = {"Authorization": "Bearer %s" % channel.config[Channel.CONFIG_AUTH_TOKEN]}
        try:
            response = requests.get(
                channel.config[Channel.CONFIG_BASE_URL] + "/v1/settings/business/profile", headers=headers
            )
        except Exception as e:
            raise Exception("error reaching server") from e

        business_profile = response.json().get("settings", {}).get("business", {}).get("profile", {})
        if business_profile:
            redis_conn = get_redis_connection()
            cache_key = str(channel.uuid)
            rcache.set(redis_conn, DOCKER_BUSINESS_PROFILE_GROUP, cache_key, json.dumps(business_profile))
        return business_profile

    def set_business_profile(self, channel, business_profile):

        headers = {"Authorization": "Bearer %s" % channel.config[Channel.CONFIG_AUTH_TOKEN]}
        payload = business_profile

        try:
            response = requests.patch(
                channel.config[Channel.CONFIG_BASE_URL] + "/v1/settings/business/profile",
                json=payload,
                headers=headers,
            )
        except Exception as e:
            raise Exception("error reaching server") from e

        if response.status_code != 200:
            try:
                raise Exception(response.json()["errors"][0]["title"])
            except KeyError as e:
                raise Exception("error parsing response") from e

        self.fetch_business_profile(channel)
