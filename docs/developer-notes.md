# Developer notes

This project primarily uses the `uv` python packaging tool: https://docs.astral.sh/uv/ along with the sister formatter/linter `ruff` https://docs.astral.sh/ruff/

With `uv` installed you can add/remove dependencies using `uv add <dep>` or `uv remove <dep>.
This will update the [`uv.lock`](https://docs.astral.sh/uv/guides/projects/#uvlock) file automatically.

`uv` can also run tools (like `ruff`) without external installation, simply run `uvx ruff check .` or `uvx ruff format .` to use a uv-managed format/lint on the project.
