#!/usr/bin/env python3

import os
import re
from pathlib import Path

from click import Context
from tabulate import tabulate

from warnet.main import cli

file_path = Path(os.path.dirname(os.path.abspath(__file__))) / ".." / ".." / "docs" / "warnet.md"

doc = ""


def print_cmd(cmd, super=""):
    global doc
    doc += f"### `warnet{super} {cmd['name']}`" + "\n"
    doc += cmd["help"].strip().replace("<", "\\<") + "\n"
    if len(cmd["params"]) > 1:
        doc += "\noptions:\n"
        headers = ["name", "type", "required", "default"]
        data = [
            [
                p["name"],
                p["type"]["param_type"] if p["type"]["param_type"] != "Unprocessed" else "String",
                "yes" if p["required"] else "",
                format_default_value(p["default"], p["type"]["param_type"]),
            ]
            for p in cmd["params"]
            if p["name"] != "help" and p["name"] != "unknown_args"
        ]
        doc += tabulate(data, headers=headers, tablefmt="github")
    doc += "\n\n"


def format_default_value(default, param_type):
    if default is None:
        return ""
    if param_type == "String":
        return f'"{default}"'
    if param_type == "Path":
        return str(default)
    return default


with Context(cli) as ctx:
    info = ctx.to_info_dict()
    # root-level commands first
    for cmd in info["command"]["commands"].values():
        if "commands" not in cmd:
            print_cmd(cmd)
    # then groups of subcommands
    for cmd in info["command"]["commands"].values():
        if "commands" in cmd:
            doc += f"## {cmd['name'].capitalize()}\n\n"
            for subcmd in cmd["commands"].values():
                print_cmd(subcmd, " " + cmd["name"])

with open(file_path) as file:
    text = file.read()

pattern = r"(## API Commands\n)(.*\n)*?\Z"
updated_text = re.sub(pattern, rf"\1\n{doc}\n", text)

with open(file_path, "w") as file:
    file.write(updated_text)
