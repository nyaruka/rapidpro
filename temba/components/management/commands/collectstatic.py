import subprocess

from django.conf import settings
from django.contrib.staticfiles.management.commands.collectstatic import Command as CollectStaticCommand
from django.core.management.base import CommandError


class Command(CollectStaticCommand):
    """
    Overrides collectstatic to first build the components bundle (components/) so that its dist/ output exists to be
    collected. Requires this app to be listed before django.contrib.staticfiles in INSTALLED_APPS.
    """

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument("--no-build", action="store_true", help="Skip building the components bundle.")

    def handle(self, **options):
        if not options["no_build"]:
            self.build_components(options["verbosity"])

        return super().handle(**options)

    def build_components(self, verbosity: int):
        components_dir = settings.COMPONENTS_DIR

        for args in (["bun", "install", "--frozen-lockfile"], ["bun", "run", "build"]):
            if verbosity >= 1:
                self.stdout.write(f"Running {' '.join(args)} in {components_dir}...")

            proc = subprocess.run(args, cwd=components_dir, capture_output=True, text=True)
            if proc.returncode != 0:
                raise CommandError(f"{' '.join(args)} failed:\n{proc.stdout}\n{proc.stderr}")
