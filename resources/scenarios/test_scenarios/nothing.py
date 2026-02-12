#!/usr/bin/env python3

from time import sleep

# The base class exists inside the commander container
try:
    from commander import Commander
except Exception:
    from resources.scenarios.commander import Commander


class Nothing(Commander):
    def set_test_params(self):
        self.num_nodes = 1

    def add_options(self, parser):
        parser.description = "This test will do nothing, forever"
        parser.usage = "warnet run /path/to/nothing.py"

    def run_test(self):
        while True:
            sleep(60)


def main():
    Nothing("").main()


if __name__ == "__main__":
    main()
