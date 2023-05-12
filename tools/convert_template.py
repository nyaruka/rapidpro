#!/usr/bin/env python3

import os
import sys

from hamlpy.compiler import Compiler

source_dir = sys.argv[1]
haml_parser = Compiler(options={"attr_wrapper": '"', "smart_quotes": True, "endblock_names": True})

if not os.path.isdir(source_dir):
    print(f"{source_dir} is not a directory")
    sys.exit(1)


def convert_template(haml_path: str, *, format: bool, delete: bool):
    html_path = os.path.splitext(haml_path)[0] + ".html"

    with open(haml_path, "r") as file:
        haml_content = file.read()

    html_content = haml_parser.process(haml_content)

    with open(html_path, "w") as file:
        file.write(html_content)

    if format:
        os.system(f"djlint --profile=django --reformat --format-css --format-js {html_path}")
    if delete:
        os.remove(haml_path)


def convert_directory(path: str, *, format: bool, delete: bool):
    for root, dirs, files in os.walk(path, topdown=False):
        for name in files:
            if name.endswith(".haml"):
                convert_template(os.path.join(root, name), format=format, delete=delete)


convert_directory(source_dir, format=True, delete=True)
