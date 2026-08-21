#!/usr/bin/env python3

import argparse
import os
import subprocess
import tempfile
import tomllib

import colorama

parser = argparse.ArgumentParser(description="Code checks")
parser.add_argument("--debug", action="store_true")
args = parser.parse_args()

DEBUG = args.debug


def cmd(line):
    if DEBUG:
        print(colorama.Style.DIM + "% " + line + colorama.Style.RESET_ALL)
    try:
        output = subprocess.check_output(line, shell=True).decode("utf-8")
        if DEBUG:
            print(colorama.Style.DIM + output + colorama.Style.RESET_ALL)
        return output
    except subprocess.CalledProcessError as e:
        print(colorama.Fore.RED + e.stdout.decode("utf-8") + colorama.Style.RESET_ALL)
        exit(1)


def status(line):
    print(colorama.Fore.GREEN + f">>> {line}..." + colorama.Style.RESET_ALL)


if __name__ == "__main__":
    colorama.init()

    # checks run against the project in the current directory - which needn't be this checkout, as projects that
    # build on this one run this same script - and are configured by the [tool.code_check] section of its
    # pyproject.toml
    with open("pyproject.toml", "rb") as f:
        config = tomllib.load(f)["tool"]["code_check"]

    packages = " ".join(config["packages"])
    locale_dir = config["locale"]

    # makemessages only ever writes to a `locale` directory directly under its working directory, so it has to be
    # run from the parent of the configured locale directory - with the ignore globs rebased to be relative to it
    msg_dir = os.path.dirname(locale_dir) or "."
    ignores = " ".join(f"--ignore='{i.removeprefix(msg_dir + '/')}'" for i in config.get("ignore", []))

    if config.get("migrations", False):
        status("Check for missing migrations")
        cmd("python manage.py makemigrations --check")

    status("Check locale files are up to date")
    with tempfile.TemporaryDirectory() as backup_dir:
        # take a copy of the PO files so we can compare the regenerated ones against them, and then put them
        # back. we compare against the working copy rather than using git because git isn't usable from here
        # in CI, where the checkout isn't a safe directory for the user running the checks
        cmd(f"cp -a {locale_dir}/. {backup_dir}")

        # run without django settings so makemessages only sees locale directories under the current directory -
        # with settings configured, LOCALE_PATHS could pull other projects' catalogs into scope
        cmd(
            f"cd '{msg_dir}' && "
            f"DJANGO_SETTINGS_MODULE= django-admin makemessages -a -e haml,html,txt,py --no-location --no-wrap "
            f"{ignores} 2>&1"
        )
        cmd(f"for f in {locale_dir}/*/LC_MESSAGES/django.po; do msgattrib --no-obsolete --no-wrap -o $f $f; done")

        # POT-Creation-Date can change without any actual message changes so ignore it. if this fails then the
        # regenerated files are left in place, ready to be committed
        cmd(f"diff -ur -I '^\"POT-Creation-Date:' {backup_dir} {locale_dir}")

        # nothing to do, so restore the originals rather than leaving a dirty working tree behind
        cmd(f"cp -a {backup_dir}/. {locale_dir}")

    status("Running ruff format")
    cmd(f"ruff format --check {packages}")

    status("Running ruff")
    cmd(f"ruff check {packages}")

    print("👍 " + colorama.Fore.GREEN + "Code looks good. Make that PR!")
