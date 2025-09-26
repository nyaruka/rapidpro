from django import template
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from temba.ivr.models import Call
from temba.msgs.models import Msg

register = template.Library()


@register.inclusion_tag("channels/tags/channel_log_link.html", takes_context=True)
def channel_log_link(context, obj):
    assert isinstance(obj, (Msg, Call)), "tag only supports Msg or Call instances"

    user = context["user"]
    org = context["user_org"]
    logs_url = None

    if user.has_org_perm(org, "channels.channel_logs") or user.is_staff:
        has_channel = obj.channel and obj.channel.is_active

        obj_age = timezone.now() - obj.created_on

        if has_channel and obj_age < settings.RETENTION_PERIODS["channellog"]:
            if isinstance(obj, Call):
                logs_url = reverse("channels.channel_logs_read", args=[obj.channel.uuid, "call", obj.uuid])
            if isinstance(obj, Msg):
                logs_url = reverse("channels.channel_logs_read", args=[obj.channel.uuid, "msg", obj.uuid])

    return {"logs_url": logs_url}
