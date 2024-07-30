#!/usr/bin/env python3

import os
import re
from pathlib import Path

from click import Context
from tabulate import tabulate
from warnet.cli.main import cli

file_path = Path(os.path.dirname(os.path.abspath(__file__))) / ".." / "docs" / "warcli.md"

doc = ""


def print_cmd(cmd, super=""):
    global doc
    doc += f"### `warcli{super} {cmd['name']}`" + "\n"
    doc += cmd["help"].strip().replace("<", "\\<") + "\n"
    if len(cmd["params"]) > 1:
        doc += "\noptions:\n"
        headers = ["name", "type", "required", "default"]
        data = [
            [
                p["name"],
                p["type"]["param_type"] if p["type"]["param_type"] != "Unprocessed" else "String",
                "yes" if p["required"] else "",
                '"' + p["default"] + '"'
                if p["default"] and p["type"]["param_type"] == "String"
                else Path(p["default"]).relative_to(Path.cwd())
                if p["default"] and p["type"]["param_type"] == "Path"
                else p["default"],
            ]
            for p in cmd["params"]
            if p["name"] != "help"
        ]
        doc += tabulate(data, headers=headers, tablefmt="github")
    doc += "\n\n"


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
