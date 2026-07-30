#!/usr/bin/env python3

import argparse
import subprocess
import tempfile

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

    status("Check for missing migrations")
    cmd("python manage.py makemigrations --check")

    status("Check locale files are up to date")
    with tempfile.TemporaryDirectory() as backup_dir:
        # take a copy of the PO files so we can compare the regenerated ones against them, and then put them
        # back. we compare against the working copy rather than using git because git isn't usable from here
        # in CI, where the checkout isn't a safe directory for the user running the checks
        cmd(f"cp -a locale/. {backup_dir}")
        cmd(
            "python manage.py makemessages -a -e haml,html,txt,py --no-location --no-wrap --ignore='env/*' "
            "--ignore='.venv/*' --ignore='.claude/*' --ignore='fabfile.py' --ignore='media/*' "
            "--ignore='sitestatic/*' --ignore='static/*' --ignore='node_modules/*' 2>&1"
        )
        cmd("for f in locale/*/LC_MESSAGES/django.po; do msgattrib --no-obsolete --no-wrap -o $f $f; done")

        # POT-Creation-Date can change without any actual message changes so ignore it. if this fails then the
        # regenerated files are left in place, ready to be committed
        cmd(f"diff -ur -I '^\"POT-Creation-Date:' {backup_dir} locale")

        # nothing to do, so restore the originals rather than leaving a dirty working tree behind
        cmd(f"cp -a {backup_dir}/. locale")

    status("Running ruff format")
    cmd("ruff format --check temba")

    status("Running ruff")
    cmd("ruff check temba")

    print("👍 " + colorama.Fore.GREEN + "Code looks good. Make that PR!")
