from smartmin.views import SmartCRUDL, SmartListView

from django.http import HttpResponseRedirect
from django.utils.translation import gettext_lazy as _

from temba.orgs.views.base import BaseReadView
from temba.orgs.views.mixins import OrgPermsMixin
from temba.utils.views.mixins import SpaMixin

from .models import Incident, Notification


class NotificationCRUDL(SmartCRUDL):
    model = Notification
    actions = ("read",)

    class Read(BaseReadView):
        def has_permission(self, request, *args, **kwargs):
            return self.request.user.is_authenticated

        def derive_queryset(self, **kwargs):
            return self.request.user.notifications.filter(org=self.request.org)

        def render_to_response(self, context, **response_kwargs):
            obj = self.get_object()
            obj.clear()

            return HttpResponseRedirect(obj.get_target_url())


class IncidentCRUDL(SmartCRUDL):
    model = Incident
    actions = ("list",)

    class List(OrgPermsMixin, SpaMixin, SmartListView):
        default_order = "-started_on"
        title = _("Incidents")
        menu_path = "/settings/incidents"

        def get_queryset(self, **kwargs):
            return super().get_queryset(**kwargs).filter(org=self.request.org).exclude(ended_on=None)

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            context["ongoing"] = (
                Incident.objects.filter(org=self.request.org, ended_on=None)
                .select_related("org", "channel")
                .order_by("-started_on")
            )
            return context
