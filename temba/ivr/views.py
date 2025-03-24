from smartmin.views import SmartCRUDL

from django.utils.translation import gettext_lazy as _

from temba.orgs.views.base import BaseListView
from temba.utils.views.mixins import SpaMixin

from .models import Call


class CallCRUDL(SmartCRUDL):
    model = Call
    actions = ("list",)

    class List(SpaMixin, BaseListView):
        title = _("Calls")
        menu_path = "/msg/calls"
        default_order = ("-created_on",)
        select_related = ("contact", "channel")
