import tempfile
from pathlib import Path

from django.test import override_settings

from temba.context_processors import config
from temba.tests import TembaTest


class ConfigTest(TembaTest):
    def test_components_dev(self):
        with tempfile.TemporaryDirectory() as components_dir, tempfile.TemporaryDirectory() as static_root:
            with override_settings(DEBUG=True, COMPONENTS_DIR=components_dir, STATIC_ROOT=static_root):
                # no build output at all: stay on the dev module path rather than falling back to a
                # compress block that hard-fails on the missing packaged bundle
                self.assertTrue(config(None)["COMPONENTS_DEV"])

                # a built packaged bundle and no watcher output: fall back to it
                dist = Path(components_dir, "dist")
                dist.mkdir()
                (dist / "temba-components.js").write_text("//bundle")
                self.assertFalse(config(None)["COMPONENTS_DEV"])

                # a collected copy counts as well
                (dist / "temba-components.js").unlink()
                self.assertTrue(config(None)["COMPONENTS_DEV"])
                collected = Path(static_root, "components")
                collected.mkdir()
                (collected / "temba-components.js").write_text("//bundle")
                self.assertFalse(config(None)["COMPONENTS_DEV"])

                # watcher output always wins, even with both packaged bundles present
                (dist / "temba-components.js").write_text("//bundle")
                dev_dist = Path(components_dir, "dev-dist")
                dev_dist.mkdir()
                (dev_dist / "temba-modules.js").write_text("//modules")
                self.assertTrue(config(None)["COMPONENTS_DEV"])

            # never outside of development
            with override_settings(DEBUG=False, COMPONENTS_DIR=components_dir, STATIC_ROOT=static_root):
                self.assertFalse(config(None)["COMPONENTS_DEV"])
