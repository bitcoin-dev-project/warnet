import os
import re
from pathlib import Path

from cli.main import cli
from click import Context
from tabulate import tabulate

doc = ""


def print_cmd(cmd, super=""):
    global doc
    doc += f"### `warcli{super} {cmd['name']}`" + "\n"
    doc += cmd["help"].strip().replace("<", "\\<") + "\n"
    doc += "\noptions:\n"
    headers = ["name", "type", "required", "default"]
    data = [
        [
            p["name"],
            p["type"]["param_type"],
            p["required"],
            p["default"]
            if p["type"]["param_type"] != "Path"
            else Path(p["default"]).relative_to(Path.cwd()),
        ]
        for p in cmd["params"]
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

file_path = Path(os.path.dirname(os.path.abspath(__file__))) / ".." / "docs" / "warcli.md"

with open(file_path) as file:
    text = file.read()

pattern = r"(## API Commands\n)(.*\n)*?(# Next)"
updated_text = re.sub(pattern, rf"\1\n{doc}\n\3", text)

with open(file_path, "w") as file:
    file.write(updated_text)
