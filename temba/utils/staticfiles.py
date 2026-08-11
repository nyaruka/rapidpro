import os
import subprocess

from django.conf import settings
from django.contrib.staticfiles.finders import FileSystemFinder
from django.core.files.storage import FileSystemStorage
from django.core.management.base import CommandError


class ComponentsFinder(FileSystemFinder):
    """
    Serves the components/ project's build output: its packaged bundle under components/ and its static assets
    (svg sprite, imgs) at the root. Listing it — something only collectstatic does — first builds it, so a
    single collectstatic call is all deploys need.
    """

    def __init__(self, app_names=None, *args, **kwargs):
        self.locations = []
        self.storages = {}

        for prefix, root in (
            ("", os.path.join(settings.COMPONENTS_DIR, "dist", "static")),
            ("components", os.path.join(settings.COMPONENTS_DIR, "dist")),
        ):
            self.locations.append((prefix, root))
            storage = FileSystemStorage(location=root)
            storage.prefix = prefix
            self.storages[root] = storage

    def check(self, **kwargs):
        # our locations come from code rather than the STATICFILES_DIRS setting, and dist/ legitimately
        # doesn't exist until we build it
        return []

    def list(self, ignore_patterns):
        self.build()

        yield from super().list(ignore_patterns)

    def build(self):
        # output streams through so a slow install/build (e.g. a deploy host's first full components
        # install) shows progress rather than looking hung, and the timeouts turn a genuine hang into
        # a loud failure
        #
        # puppeteer is only used for testing so skip its Chrome download
        env = {**os.environ, "PUPPETEER_SKIP_DOWNLOAD": "true"}

        for args in (["bun", "install", "--frozen-lockfile"], ["bun", "run", "build"]):
            print(f"Running {' '.join(args)} in {settings.COMPONENTS_DIR}...")

            try:
                proc = subprocess.run(args, cwd=settings.COMPONENTS_DIR, env=env, timeout=600)
            except subprocess.TimeoutExpired:
                raise CommandError(f"{' '.join(args)} timed out after 600 seconds")

            if proc.returncode != 0:
                raise CommandError(f"{' '.join(args)} failed with exit code {proc.returncode}")
