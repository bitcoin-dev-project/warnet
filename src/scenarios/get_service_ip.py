#!/usr/bin/env python3

from time import sleep

from scenarios.utils import  ensure_miner, get_service_ip
from warnet.test_framework_bridge import WarnetTestFramework


def cli_help():
    return "Test getting ip addresses from services"


class GetServiceIp(WarnetTestFramework):
    def set_test_params(self):
        # This is just a minimum
        self.num_nodes = 8

    def add_options(self, parser):
        parser.add_argument(
            "--network_name",
            dest="network_name",
            default="warnet",
            help="",
        )

    def run_test(self):
        while not self.warnet.network_connected():
            sleep(1)

        # All permutations of directed graph with zero, one, or two inputs/outputs
        #
        # | Node | In | Out | Con In | Con Out |
        # |------+----+-----+--------+---------|
        # | A  0 |  0 |   1 | -      | C       |
        # | B  1 |  0 |   2 | -      | C, D    |
        # | C  2 |  2 |   2 | A, B   | D, E    |
        # | D  3 |  2 |   1 | B, C   | F       |
        # | E  4 |  2 |   0 | C, F   | -       |
        # | F  5 |  1 |   2 | D      | E, G    |
        # | G  6 |  1 |   1 | F      | H       |
        # | H  7 |  1 |   0 | G      | -       |
        #
        #          ╭──────> E                       ╭──────> 4
        #          │        ∧                       │        ∧
        #  A ─> C ─┤        │               0 ─> 2 ─┤        │
        #       ∧  ╰─> D ─> F ─> G ─> H          ∧  ╰─> 3 ─> 5 ─> 6 ─> 7
        #       │      ∧                         │      ∧
        #  B ───┴──────╯                    1 ───┴──────╯

        zero_external, zero_internal = get_service_ip(f"{self.options.network_name}-tank-000000-service")
        one_external, one_internal = get_service_ip(f"{self.options.network_name}-tank-000001-service")
        two_external, two_internal = get_service_ip(f"{self.options.network_name}-tank-000002-service")
        three_external, three_internal = get_service_ip(f"{self.options.network_name}-tank-000003-service")
        five_external, five_internal = get_service_ip(f"{self.options.network_name}-tank-000005-service")
        six_external, six_internal = get_service_ip(f"{self.options.network_name}-tank-000006-service")

        zero_peers = self.nodes[0].getpeerinfo()
        one_peers = self.nodes[1].getpeerinfo()
        two_peers = self.nodes[2].getpeerinfo()
        three_peers = self.nodes[3].getpeerinfo()
        four_peers = self.nodes[4].getpeerinfo()
        five_peers = self.nodes[5].getpeerinfo()
        six_peers = self.nodes[6].getpeerinfo()
        seven_peers = self.nodes[7].getpeerinfo()

        assert any(d.get("addr").split(":")[0] == f"{self.options.network_name}-tank-000002-service" for d in zero_peers), f"Could not find {self.options.network_name}-tank-000002-service"
        assert any(d.get("addr").split(":")[0] == f"{self.options.network_name}-tank-000002-service" for d in one_peers), f"Could not find {self.options.network_name}-tank-000002-service"
        assert any(d.get("addr").split(":")[0] == f"{self.options.network_name}-tank-000003-service" for d in one_peers), f"Could not find {self.options.network_name}-tank-000003-service"
        assert any(d.get("addr").split(":")[0] == str(zero_internal) for d in two_peers), f"Could not find {zero_internal}"
        assert any(d.get("addr").split(":")[0] == str(one_internal) for d in two_peers), f"Could not find {one_internal}"
        assert any(d.get("addr").split(":")[0] == f"{self.options.network_name}-tank-000003-service" for d in two_peers), f"Could not find {self.options.network_name}-tank-000003-service"
        assert any(d.get("addr").split(":")[0] == f"{self.options.network_name}-tank-000004-service" for d in two_peers), f"Could not find {self.options.network_name}-tank-000004-service"
        assert any(d.get("addr").split(":")[0] == str(one_internal) for d in three_peers), f"Could not find {one_internal}"
        assert any(d.get("addr").split(":")[0] == str(two_internal) for d in three_peers), f"Could not find {two_internal}"
        assert any(d.get("addr").split(":")[0] == f"{self.options.network_name}-tank-000005-service" for d in three_peers), f"Could not find {self.options.network_name}-tank-000005-service"
        assert any(d.get("addr").split(":")[0] == str(two_internal) for d in four_peers), f"Could not find {two_internal}"
        assert any(d.get("addr").split(":")[0] == str(five_internal) for d in four_peers), f"Could not find {five_internal}"
        assert any(d.get("addr").split(":")[0] == str(three_internal) for d in five_peers), f"Could not find {three_internal}"
        assert any(d.get("addr").split(":")[0] == f"{self.options.network_name}-tank-000004-service" for d in five_peers), f"Could not find {self.options.network_name}-tank-000004-service"
        assert any(d.get("addr").split(":")[0] == f"{self.options.network_name}-tank-000006-service" for d in five_peers), f"Could not find {self.options.network_name}-tank-000006-service"
        assert any(d.get("addr").split(":")[0] == str(five_internal) for d in six_peers), f"Could not find {five_internal}"
        assert any(d.get("addr").split(":")[0] == f"{self.options.network_name}-tank-000007-service" for d in six_peers), f"Could not find {self.options.network_name}-tank-000007-service"
        assert any(d.get("addr").split(":")[0] == str(six_internal) for d in seven_peers), f"Could not find {seven_peers}"

        self.log.info("Successfully ran the get_service_ip scenario.")

if __name__ == "__main__":
    GetServiceIp().main()
