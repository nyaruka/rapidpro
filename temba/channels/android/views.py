from django.http import HttpResponse, JsonResponse
from django.utils.encoding import force_str
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt

from temba.utils import json

from .claim import UnsupportedAndroidChannelError, get_or_create_channel


@csrf_exempt
def register(request):
    """
    Endpoint for Android devices registering with this server
    """
    if request.method != "POST":
        return HttpResponse(status=500, content=_("POST Required"))

    client_payload = json.loads(force_str(request.body))
    cmds = client_payload["cmds"]

    try:
        # look up a channel with that id
        channel = get_or_create_channel(cmds[0], cmds[1])
        cmd = dict(
            cmd="reg", relayer_claim_code=channel.claim_code, relayer_secret=channel.secret, relayer_id=channel.id
        )
    except UnsupportedAndroidChannelError:
        cmd = dict(cmd="reg", relayer_claim_code="*********", relayer_secret="0" * 64, relayer_id=-1)

    return JsonResponse(dict(cmds=[cmd]))
