from abc import ABC, abstractmethod
import ipaddress
import random

class IPV4AddressGenerator(ABC):
    def generate_ipv4_addr(self, subnet):
        """
        Generate a valid random IPv4 address within the given subnet.

        :param subnet: Subnet in CIDR notation (e.g., '100.0.0.0/8')
        :return: Random IP address within the subnet
        """
        reserved_ips = [
            "0.0.0.0/8",
            "10.0.0.0/8",
            "100.64.0.0/10",
            "127.0.0.0/8",
            "169.254.0.0/16",
            "172.16.0.0/12",
            "192.0.0.0/24",
            "192.0.2.0/24",
            "192.88.99.0/24",
            "192.168.0.0/16",
            "198.18.0.0/15",
            "198.51.100.0/24",
            "203.0.113.0/24",
            "224.0.0.0/4",
        ]

        def is_public(ip):
            for reserved in reserved_ips:
                if ipaddress.ip_address(ip) in ipaddress.ip_network(reserved, strict=False):
                    return False
            return True

        network = ipaddress.ip_network(subnet, strict=False)

        # Generate a random IP within the subnet range
        while True:
            ip_int = random.randint(
                int(network.network_address), int(network.broadcast_address)
            )
            ip_str = str(ipaddress.ip_address(ip_int))
            if is_public(ip_str):
                return ip_str
