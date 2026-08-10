import os

from django.conf import settings


def config(request):
    dev_bundle = os.path.join(settings.COMPONENTS_DIR, "dev-dist", "temba-modules.js")
    dist_bundle = os.path.join(settings.COMPONENTS_DIR, "dist", "temba-components.js")
    collected_bundle = os.path.join(settings.STATIC_ROOT, "components", "temba-components.js")

    return {
        # in development serve the components as live modules (components/dev-dist, kept fresh by
        # `bun run watch`) whenever a watcher has produced them, else the packaged bundle — but only
        # when that actually exists (built dist/ or a collected copy): its {% compress %} block
        # resolves the file at render time even with compression disabled if any precompiler is
        # configured — this repo no longer has one, but deployment settings modules that import
        # these settings may add their own — and a missing file 500s every page, e.g. before a
        # first components build has finished
        "COMPONENTS_DEV": settings.DEBUG
        and (os.path.exists(dev_bundle) or not (os.path.exists(dist_bundle) or os.path.exists(collected_bundle))),
    }


def branding(request):
    """
    Stuff our branding into the context
    """
    return dict(branding=request.branding)
