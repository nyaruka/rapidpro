from django.conf import settings


def config(request):
    return {
        "COMPONENTS_DEV_MODE": getattr(settings, "COMPONENTS_DEV_MODE", False),
        "COMPONENTS_DEV_HOST": getattr(settings, "COMPONENTS_DEV_HOST", "localhost"),
    }


def branding(request):
    """
    Stuff our branding into the context
    """
    return dict(branding=request.branding)
