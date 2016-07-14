from django.utils.translation import ugettext_lazy as _

from smartmin.views import SmartListView, SmartReadView, SmartCRUDL
from temba.events.models import AirtimeEvent
from temba.orgs.views import OrgPermsMixin


class AirtimeEventMixin(OrgPermsMixin):
    def get_status(self, obj):
        return obj.get_status_display()

    def derive_queryset(self, **kwargs):
        org = self.derive_org()
        return AirtimeEvent.objects.filter(org=org)

    def get_transaction_id(self, obj):
        if obj.transaction_id:
            return obj.transaction_id
        return "--"

    def get_channel(self, obj):
        if obj.channel:
            return obj.channel
        return "--"


class AirtimeEventCRUDL(SmartCRUDL):
    model = AirtimeEvent
    actions = ('list', 'read')

    class List(AirtimeEventMixin, SmartListView):
        fields = ('transaction_id', 'status', 'channel', 'amount', 'created_on')
        title = _("Recent Airtime Transfer Events")
        default_order = ('-created_on',)

        def get_context_data(self, **kwargs):
            context = super(AirtimeEventCRUDL.List, self).get_context_data(**kwargs)
            context['org'] = self.request.user.get_org()
            return context

    class Read(AirtimeEventMixin, SmartReadView):
        fields = ('transaction_id', 'status', 'channel', 'amount', 'created_on')
