#!/usr/bin/env python3

import os
import sys

from hamlpy.compiler import Compiler

haml_path = sys.argv[1]
haml_parser = Compiler(options={"attr_wrapper": '"', "endblock_names": True})
html_path = os.path.splitext(haml_path)[0] + ".html"

with open(haml_path, "r") as file:
    haml_content = file.read()

html_content = haml_parser.process(haml_content)

with open(html_path, "w") as file:
    file.write(html_content)

os.system(f"djlint --reformat --format-css --format-js {html_path}")
os.remove(haml_path)
