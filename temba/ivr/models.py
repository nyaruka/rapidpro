import logging
from datetime import timedelta

from django.db import models
from django.utils import timezone

from temba.channels.models import ChannelConnection, ChannelLog

logger = logging.getLogger(__name__)


class IVRManager(models.Manager):
    def create(self, *args, **kwargs):
        return super().create(*args, connection_type=IVRCall.IVR, **kwargs)

    def get_queryset(self):
        return super().get_queryset().filter(connection_type__in=[IVRCall.IVR, IVRCall.VOICE])


class IVRCall(ChannelConnection):

    objects = IVRManager()

    class Meta:
        proxy = True

    def get_duration(self):
        """
        Either gets the set duration as reported by provider, or tries to calculate
        it from the approximate time it was started
        """
        duration = self.duration
        if not duration and self.status == self.IN_PROGRESS and self.started_on:
            duration = (timezone.now() - self.started_on).seconds

        if not duration:
            duration = 0

        return timedelta(seconds=duration)

    def has_logs(self):
        """
        Returns whether this IVRCall has any channel logs
        """
        return self.channel and self.channel.is_active and ChannelLog.objects.filter(connection=self).count() > 0
