from .models import Notification


class NotificationTargetMixin:
    """
    Mixin for views which can be targets of notifications to help them clear unseen notifications. This is defined in a
    separate module to views.py to avoid creating a circular dependency with orgs/views.py
    """

    notification_type = None
    notification_scope = ""

    def get_notification_scope(self) -> tuple[str, str]:  # pragma: no cover
        return self.notification_type, [self.notification_scope] if self.notification_scope is not None else []

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)

        notification_type, scopes = self.get_notification_scope()
        if request.org and notification_type and request.user.is_authenticated:
            Notification.mark_seen(request.org, request.user, notification_type, scopes=scopes)

        return response
