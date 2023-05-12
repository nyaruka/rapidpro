#!/usr/bin/env python3

import os
import re
import sys

from hamlpy.compiler import Compiler

source = sys.argv[1]
haml_parser = Compiler(options={"attr_wrapper": '"', "smart_quotes": True, "endblock_names": True})

sad_template = re.compile("\\{\n\\s+%")
sad_files = {}


def convert_template(haml_path: str, *, format: bool, delete: bool):
    html_path = os.path.splitext(haml_path)[0] + ".html"

    with open(haml_path, "r") as file:
        haml_content = file.read()

    html_content = haml_parser.process(haml_content)

    with open(html_path, "w") as file:
        file.write(html_content)


def check_for_sad(path: str):
    # check for sad templates
    formatted = open(path, "r")
    formatted_text = formatted.read()
    formatted.close()
    matches = sad_template.findall(formatted_text)
    if matches:
        sad_files[path] = len(matches)


def format_path(path: str):
    os.system(f"djlint --profile=django --reformat --quiet {path}")

    if os.path.isdir(path):
        for root, dirs, files in os.walk(path, topdown=False):
            for name in files:
                if name.endswith(".html"):
                    check_for_sad(os.path.join(root, name))
    else:
        check_for_sad(path)


def convert_directory(path: str, *, format: bool, delete: bool):
    for root, dirs, files in os.walk(path, topdown=False):
        for name in files:
            if name.endswith(".haml"):
                convert_template(os.path.join(root, name), format=format, delete=delete)
    format_path(path)


def print_sad():
    for f in sad_files.keys():
        print(f"😔 {f}: {sad_files[f]}")


if os.path.isdir(source):
    convert_directory(source, format=True, delete=True)
    print_sad()

else:
    convert_template(source, format=True, delete=True)
    format_path(source)
    print_sad()
