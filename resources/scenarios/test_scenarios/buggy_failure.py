#!/usr/bin/env python3


# The base class exists inside the commander container
try:
    from commander import Commander
except Exception:
    from resources.scenarios.commander import Commander


class Failure(Commander):
    def set_test_params(self):
        self.num_nodes = 1

    def add_options(self, parser):
        parser.description = "This test will fail and exit with code 222"
        parser.usage = "warnet run /path/to/scenario_buggy_failure.py"

    def run_test(self):
        raise Exception("Failed execution!")


def main():
    Failure().main()


if __name__ == "__main__":
    main()
