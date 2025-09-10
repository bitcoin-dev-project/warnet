#!/usr/bin/env python3

from commander import Commander


class SignetGrinder(Commander):
    def set_test_params(self):
        self.num_nodes = 0

    def run_test(self):
        self.generatetoaddress(self.tanks["miner"], 1, "tb1qjfplwf7a2dpjj04cx96rysqeastvycc0j50cch")


def main():
    SignetGrinder().main()


if __name__ == "__main__":
    main()
