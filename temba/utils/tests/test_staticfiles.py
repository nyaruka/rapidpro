import subprocess
import tempfile
from pathlib import Path
from unittest.mock import ANY, call, patch

from django.core.management.base import CommandError
from django.test import override_settings

from temba.tests import TembaTest
from temba.utils.staticfiles import ComponentsFinder


class ComponentsFinderTest(TembaTest):
    def test_finder(self):
        with tempfile.TemporaryDirectory() as components_dir:
            dist = Path(components_dir, "dist")
            (dist / "static" / "svg").mkdir(parents=True)
            (dist / "temba-components.js").write_text("//bundle")
            (dist / "static" / "svg" / "index.svg").write_text("<svg></svg>")

            with override_settings(COMPONENTS_DIR=components_dir):
                finder = ComponentsFinder()

                # our locations come from code rather than settings so nothing to check
                self.assertEqual([], finder.check())

                # finding serves the build output as-is, from both the prefixed and root locations
                self.assertEqual(str(dist / "temba-components.js"), finder.find("components/temba-components.js"))
                self.assertEqual(str(dist / "static" / "svg" / "index.svg"), finder.find("svg/index.svg"))

                # listing (i.e. collectstatic) builds first
                with patch("temba.utils.staticfiles.subprocess.run") as mock_run:
                    mock_run.return_value = subprocess.CompletedProcess([], returncode=0)

                    listed = {path for path, storage in finder.list([])}

                mock_run.assert_has_calls(
                    [
                        call(["bun", "install", "--frozen-lockfile"], cwd=components_dir, env=ANY),
                        call(["bun", "run", "build"], cwd=components_dir, env=ANY),
                    ]
                )

                # the build env should prevent puppeteer from downloading Chrome
                self.assertEqual("true", mock_run.call_args_list[0].kwargs["env"]["PUPPETEER_SKIP_DOWNLOAD"])
                self.assertIn("svg/index.svg", listed)
                self.assertIn("temba-components.js", listed)

                # a failed build aborts the listing
                with patch("temba.utils.staticfiles.subprocess.run") as mock_run:
                    mock_run.return_value = subprocess.CompletedProcess([], returncode=1, stdout="out", stderr="boom")

                    with self.assertRaises(CommandError):
                        list(finder.list([]))
