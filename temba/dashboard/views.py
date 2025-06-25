from datetime import datetime, timedelta

from smartmin.views import SmartTemplateView

from django.db.models import Q, Sum
from django.http import JsonResponse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from temba.channels.models import ChannelCount
from temba.orgs.models import Org
from temba.orgs.views.mixins import OrgPermsMixin
from temba.utils.views.mixins import ChartViewMixin, SpaMixin


class Home(SpaMixin, OrgPermsMixin, SmartTemplateView):
    """
    The main dashboard view
    """

    title = _("Dashboard")
    permission = "orgs.org_dashboard"
    template_name = "dashboard/home.html"
    menu_path = "/settings/dashboard"


class MessageHistory(OrgPermsMixin, ChartViewMixin, SmartTemplateView):
    """
    Endpoint to expose message history by day as JSON for temba-chart
    """

    permission = "orgs.org_dashboard"
    default_chart_period = (-timedelta(days=30), timedelta(days=1))

    def get_chart_data(self, since, until) -> tuple[list, list]:
        orgs = []
        org = self.derive_org()
        if org:
            orgs = Org.objects.filter(Q(id=org.id) | Q(parent=org))

        # get all our counts for that period
        daily_counts = ChannelCount.objects.filter(scope__in=[ChannelCount.SCOPE_TEXT_IN, ChannelCount.SCOPE_TEXT_OUT])
        daily_counts = daily_counts.filter(day__gte=since).filter(day__lte=until)

        if orgs or not self.request.user.is_support:
            daily_counts = daily_counts.filter(channel__org__in=orgs)

        daily_counts = list(
            daily_counts.values("day", "scope").order_by("day", "scope").annotate(count_sum=Sum("count"))
        )

        # collect all dates and values by scope
        dates_set = set()
        values_by_scope = {
            ChannelCount.SCOPE_TEXT_IN: {},
            ChannelCount.SCOPE_TEXT_OUT: {},
        }

        for count in daily_counts:
            dates_set.add(count["day"])
            values_by_scope[count["scope"]][count["day"]] = count["count_sum"]  # create sorted list of dates
        labels = sorted(list(dates_set))

        return [d.strftime("%Y-%m-%d") for d in labels], [
            {
                "label": "Incoming",
                "data": [values_by_scope[ChannelCount.SCOPE_TEXT_IN].get(d, 0) for d in labels],
            },
            {
                "label": "Outgoing",
                "data": [values_by_scope[ChannelCount.SCOPE_TEXT_OUT].get(d, 0) for d in labels],
            },
        ]


class WorkspaceStats(OrgPermsMixin, SmartTemplateView):
    permission = "orgs.org_dashboard"

    def get_period(self):
        """Get the date range from request parameters or use defaults"""
        since = self.request.GET.get("since")
        until = self.request.GET.get("until")

        if since:
            since = datetime.fromisoformat(since.replace("Z", "+00:00")).date()
        else:
            since = timezone.now().date() - timedelta(days=30)

        if until:
            until = datetime.fromisoformat(until.replace("Z", "+00:00")).date()
        else:
            until = timezone.now().date()

        return since, until

    def render_to_response(self, context, **response_kwargs):
        orgs = []
        org = self.derive_org()
        if org:
            orgs = Org.objects.filter(Q(id=org.id) | Q(parent=org))

        since, until = self.get_period()

        # get all our counts for that period
        daily_counts = ChannelCount.objects.filter(
            scope__in=[
                ChannelCount.SCOPE_TEXT_IN,
                ChannelCount.SCOPE_TEXT_OUT,
            ]
        )

        daily_counts = daily_counts.filter(day__gte=since).filter(day__lte=until)

        if orgs or not self.request.user.is_support:
            daily_counts = daily_counts.filter(channel__org__in=orgs)

        categories = []
        inbound = []
        outbound = []

        for org in orgs:
            org_daily_counts = list(
                daily_counts.filter(channel__org_id=org.id)
                .values("scope")
                .order_by("scope")
                .annotate(count_sum=Sum("count"))
            )

            # ignore orgs with no activity in this period
            if not org_daily_counts:
                continue

            inbound_count, outbound_count = 0, 0

            for count in org_daily_counts:
                if count["scope"] == ChannelCount.SCOPE_TEXT_IN:
                    inbound_count = count["count_sum"]
                elif count["scope"] == ChannelCount.SCOPE_TEXT_OUT:
                    outbound_count = count["count_sum"]

            categories.append(org.name)
            inbound.append(inbound_count)
            outbound.append(outbound_count)

        return JsonResponse(
            {
                "period": [since, until],
                "data": {
                    "labels": categories,
                    "datasets": [{"label": "Incoming", "data": inbound}, {"label": "Outgoing", "data": outbound}],
                },
            }
        )
