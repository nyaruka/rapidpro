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
        print(f"Building components bundle in {settings.COMPONENTS_DIR}...")

        for args in (["bun", "install", "--frozen-lockfile"], ["bun", "run", "build"]):
            proc = subprocess.run(args, cwd=settings.COMPONENTS_DIR, capture_output=True, text=True)
            if proc.returncode != 0:
                raise CommandError(f"{' '.join(args)} failed:\n{proc.stdout}\n{proc.stderr}")
