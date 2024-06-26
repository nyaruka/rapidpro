from smartmin.views import SmartCRUDL, SmartListView

from django.http import Http404
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from temba.channels.models import Channel
from temba.orgs.views import OrgObjPermsMixin
from temba.utils.views import ContentMenuMixin, SpaMixin

from .models import TemplateTranslation


class TemplateTranslationCRUDL(SmartCRUDL):
    model = TemplateTranslation
    actions = ("channel",)
    path = "template"

    class Channel(SpaMixin, ContentMenuMixin, OrgObjPermsMixin, SmartListView):
        permission = "channels.channel_read"
        status_icons = {
            TemplateTranslation.STATUS_PENDING: "template_pending",
            TemplateTranslation.STATUS_APPROVED: "template_approved",
            TemplateTranslation.STATUS_REJECTED: "template_rejected",
            TemplateTranslation.STATUS_UNSUPPORTED: "template_unsupported",
        }

        @classmethod
        def derive_url_pattern(cls, path, action):
            return r"^%s/%s/(?P<channel>[^/]+)/$" % (path, action)

        def build_content_menu(self, menu):
            menu.add_link(_("Sync Logs"), reverse("request_logs.httplog_channel", args=[self.channel.uuid]))

        def derive_menu_path(self):
            return f"/settings/channels/{self.channel.uuid}"

        def get_object_org(self):
            return self.channel.org

        @cached_property
        def channel(self):
            try:
                return Channel.objects.get(is_active=True, uuid=self.kwargs["channel"])
            except Channel.DoesNotExist:
                raise Http404("Channel not found")

        def derive_queryset(self, **kwargs):
            return (
                super()
                .derive_queryset(**kwargs)
                .filter(channel=self.channel, is_active=True)
                .order_by("template__name")
            )

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            context["channel"] = self.channel
            context["status_icons"] = self.status_icons
            return context
