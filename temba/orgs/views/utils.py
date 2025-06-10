from temba.utils import analytics

from .. import signals


def switch_to_org(request, org):
    signals.pre_org_switch.send(request, org=org)

    if not request.user.is_staff:
        analytics.identify(request.user, request.branding, org=org)

    request.session["org_id"] = org.id if org else None
