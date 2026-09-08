import json
import logging

from django.http import HttpResponse, HttpResponseForbidden
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)


def permission_denied(request, exception=None):
    """
    Handler for 403 responses which includes a toast so that the UI can tell the user what happened rather than
    treating it as a generic error.
    """

    response = HttpResponseForbidden()
    response["X-Temba-Toasts"] = json.dumps(
        [{"level": "error", "text": str(_("You don't have permission to do that."))}]
    )
    return response


class ExternalURLHandler(View):
    """
    It's useful to register Mailroom URLs in RapidPro so they can be used in templates, and if they are hit here, we
    can provide the user with a error message about
    """

    service = None

    @csrf_exempt
    def dispatch(self, request, *args, **kwargs):
        logger.error(f"URL intended for {self.service} reached RapidPro", extra={"URL": request.get_full_path()})
        return HttpResponse(f"this URL should be mapped to a {self.service} instance", status=404)


class MailroomURLHandler(ExternalURLHandler):
    service = "Mailroom"
