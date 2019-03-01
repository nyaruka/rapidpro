from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View


class MailroomHandler(View):
    """
    Placeholder view that returns a 500 error. Clients should never reach this view, instead all URLs prefixed with
    /mr/ should be rerouted to Mailroom.
    """

    @csrf_exempt
    def dispatch(self, *args, **kwargs):
        return HttpResponse("Misconfigured. Invalid RapidPro URL, should be redirected to Mailroom.", status=500)
