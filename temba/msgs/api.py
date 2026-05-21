from django.db.models import Q

from temba.api.internal.serializers import ModelAsJsonSerializer
from temba.api.internal.views import BaseEndpoint
from temba.api.support import CreatedOnCursorPagination, SearchCountMixin, SentOnCursorPagination
from temba.api.views import ListAPIMixin

from .models import Msg, MsgFolder


class MessagesEndpoint(ListAPIMixin, BaseEndpoint):
    """
    Messages for the current org, used by the message list components. A folder is selected with the `folder` query
    param (one of `inbox`, `handled`, `archived`, `outbox`, `sent` or `failed`, defaulting to `inbox`) — alternatively
    pass `label=<uuid>` to filter by a user-defined label. An optional `search` param filters by message text or
    contact name. Each item is serialized via Msg.as_json().
    """

    class Pagination(SearchCountMixin, CreatedOnCursorPagination):
        """
        The sent folder is ordered by sent date; all other folders by creation date. Searches additionally include a
        `count` on the response via SearchCountMixin so the list UI can surface "N results".
        """

        # DRF's CursorPagination ignores `?page_size=` unless the subclass opts in. The list component sends
        # `page_size` to size each request to the visible viewport, so honor it — with a default that matches the
        # component's own default and a cap that keeps a hostile/oversized client request from pulling 50k rows.
        page_size = 50
        page_size_query_param = "page_size"
        max_page_size = 500

        def get_ordering(self, request, queryset, view=None):
            if request.query_params.get("folder", "").lower() == "sent":
                return SentOnCursorPagination.ordering
            return CreatedOnCursorPagination.ordering

    model = Msg
    serializer_class = ModelAsJsonSerializer
    pagination_class = Pagination

    FOLDERS = {
        "inbox": MsgFolder.INBOX,
        "handled": MsgFolder.HANDLED,
        "archived": MsgFolder.ARCHIVED,
        "outbox": MsgFolder.OUTBOX,
        "sent": MsgFolder.SENT,
        "failed": MsgFolder.FAILED,
    }

    def derive_queryset(self):
        # `label` takes precedence — the filter view passes a label UUID rather than a folder name, and the visible
        # messages for that label aren't a MsgFolder slice.
        # `org` and `channel` are select_related because Msg.as_json reads self.org (for contact display) and
        # self.channel.is_active/uuid (for the channel-log link gated on the channels.channel_logs perm).
        label_uuid = self.request.query_params.get("label")
        if label_uuid:
            label = self.request.org.msgs_labels.filter(uuid=label_uuid).first()
            if not label:
                return Msg.objects.none()
            return (
                Msg.objects.filter(org=self.request.org, labels=label, visibility=Msg.VISIBILITY_VISIBLE)
                .select_related("contact", "channel", "flow", "org")
                .prefetch_related("labels")
            )

        folder = self.FOLDERS.get(self.request.query_params.get("folder", "inbox").lower())
        if not folder:
            return Msg.objects.none()

        return (
            folder.get_queryset(self.request.org)
            .select_related("contact", "channel", "flow", "org")
            .prefetch_related("labels")
        )

    def filter_queryset(self, queryset):
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(Q(text__icontains=search) | Q(contact__name__icontains=search))

        return queryset
