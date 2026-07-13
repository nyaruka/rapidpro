from rest_framework.pagination import PageNumberPagination

from django.db.models import Q
from django.http import HttpResponse

from temba.api.internal.serializers import ModelAsJsonSerializer
from temba.api.internal.views import BaseEndpoint
from temba.api.views import ListAPIMixin

from .models import Trigger
from .views import Folder

# Match BaseListView: 50 rows per page with a cap that keeps an oversized client request from pulling 50k rows, and
# the same 1000 char search cap (rejected with 413).
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 500
SEARCH_MAX_LENGTH = 1_000


class TriggersEndpoint(ListAPIMixin, BaseEndpoint):
    """
    Triggers for the current org, used by the trigger list component. A folder is selected with the `folder` query
    param — `active` (default), `archived`, or one of the type folder slugs (`messages`, `schedule`, `calls`, etc.).
    An optional `search` param filters by keyword, flow name or channel name, and `sort` can be `created_on` (prefix
    with `-` to reverse). Each item is serialized via Trigger.as_json().
    """

    class Pagination(PageNumberPagination):
        page_size = DEFAULT_PAGE_SIZE
        page_size_query_param = "page_size"
        max_page_size = MAX_PAGE_SIZE

    model = Trigger
    serializer_class = ModelAsJsonSerializer
    pagination_class = Pagination

    def get(self, request, *args, **kwargs):
        search = request.query_params.get("search") or ""
        if len(search) > SEARCH_MAX_LENGTH:
            return HttpResponse("Search query too long", status=413)
        return super().get(request, *args, **kwargs)

    def derive_queryset(self):
        # Build from Trigger.objects rather than the org.triggers related manager — a related manager would seed each
        # fetched row with the in-memory org instance, which Django rejects on a GET because the org was loaded from
        # the default database while this queryset reads from the readonly alias.
        org = self.request.org
        base = Trigger.objects.filter(org=org, is_active=True)

        folder_slug = (self.request.query_params.get("folder") or "active").lower()
        folder = Folder.from_slug(folder_slug)
        if folder:
            # a type folder — non-archived triggers of those types, in the legacy folder view's ordering
            qs = base.filter(is_archived=False, trigger_type__in=folder.types)
            default_order = (Trigger.type_order(), *folder.ordering, "-created_on")
        elif folder_slug == "archived":
            qs = base.filter(is_archived=True)
            default_order = ("-created_on",)
        else:
            qs = base.filter(is_archived=False)
            default_order = ("-created_on",)

        search = self.request.query_params.get("search")
        if search:
            # match the legacy list view's search fields
            qs = qs.filter(
                Q(keywords__icontains=search) | Q(flow__name__icontains=search) | Q(channel__name__icontains=search)
            )

        sort = self.request.query_params.get("sort") or ""
        desc = sort.startswith("-")
        key = sort[1:] if desc else sort

        if key == "created_on":
            order = ("-created_on" if desc else "created_on",)
        else:
            order = default_order

        return (
            qs.order_by(*order, "-id")
            .select_related("flow", "channel", "schedule")
            .prefetch_related("contacts", "groups", "exclude_groups")
        )

    def filter_queryset(self, queryset):
        # filtering (folder/search/sort) is fully resolved in derive_queryset; bypass the default backends
        return queryset
