import os

from django.conf import settings


def config(request):
    return {
        # in development serve the components as live modules (components/dev-dist, kept fresh by
        # `bun run watch`) whenever a watcher has produced them, else the packaged bundle
        "COMPONENTS_DEV": settings.DEBUG
        and os.path.exists(os.path.join(settings.COMPONENTS_DIR, "dev-dist", "temba-modules.js")),
    }


def branding(request):
    """
    Stuff our branding into the context
    """
    return dict(branding=request.branding)
