from .. import signals


def switch_to_org(request, org):
    signals.pre_org_switch.send(switch_to_org, request=request, org=org)

    request.session["org_id"] = org.id if org else None
