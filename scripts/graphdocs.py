#!/usr/bin/env python3

import os
import re
from pathlib import Path

from tabulate import tabulate
from warnet.utils import load_schema

graph_schema = load_schema()

file_path = Path(os.path.dirname(os.path.abspath(__file__))) / ".." / "docs" / "graph.md"

doc = ""

doc += "### GraphML file format and headers\n"
doc += "```xml\n"
doc += '<?xml version="1.0" encoding="UTF-8"?><graphml xmlns="http://graphml.graphdrawing.org/xmlns">\n'

sections = ["graph", "node", "edge"]

for section in sections:
    for name, details in graph_schema[section]["properties"].items():
        if "comment" not in details:
            continue
        vname = f'"{name}"'
        vtype = f'"{details["type"]}"'
        doc += f'  <key {"id=" + vname:20} {"attr.name=" + vname:28} {"attr.type=" + vtype:20} for="{section}" />\n'
doc += '  <graph edgedefault="directed">\n    <!-- <nodes> -->\n    <!-- <edges> -->\n  </graph>\n</graphml>\n'
doc += "```\n\n"

headers = ["key", "for", "type", "default", "explanation"]
data = []
for section in sections:
    data += [
        [name, section, p["type"], p.get("default", ""), p["comment"]]
        for name, p in graph_schema[section]["properties"].items()
        if "comment" in p
    ]

doc += tabulate(data, headers=headers, tablefmt="github")


with open(file_path) as file:
    text = file.read()

pattern = r"(## GraphML file specification\n)(.*\n)*?\Z"
updated_text = re.sub(pattern, rf"\1\n{doc}\n", text)

with open(file_path, "w") as file:
    file.write(updated_text)
