import logging


class LNChannel:
    def __init__(
        self,
        node1_pub: str,
        node2_pub: str,
        capacity_msat: int = 0,
        short_chan_id: str = "",
        node1_min_htlc: int = 0,
        node2_min_htlc: int = 0,
        node1_max_htlc: int = 0,
        node2_max_htlc: int = 0,
        node1_base_fee_msat: int = 0,
        node2_base_fee_msat: int = 0,
        node1_fee_rate_milli_msat: int = 0,
        node2_fee_rate_milli_msat: int = 0,
        node1_time_lock_delta: int = 0,
        node2_time_lock_delta: int = 0,
    ) -> None:
        # Ensure that the node with the lower pubkey is node1
        if node1_pub > node2_pub:
            node1_pub, node2_pub = node2_pub, node1_pub
            node1_min_htlc, node2_min_htlc = node2_min_htlc, node1_min_htlc
            node1_max_htlc, node2_max_htlc = node2_max_htlc, node1_max_htlc
            node1_base_fee_msat, node2_base_fee_msat = node2_base_fee_msat, node1_base_fee_msat
            node1_fee_rate_milli_msat, node2_fee_rate_milli_msat = (
                node2_fee_rate_milli_msat,
                node1_fee_rate_milli_msat,
            )
            node1_time_lock_delta, node2_time_lock_delta = (
                node2_time_lock_delta,
                node1_time_lock_delta,
            )
        self.node1_pub = node1_pub
        self.node2_pub = node2_pub
        self.capacity_msat = capacity_msat
        self.short_chan_id = short_chan_id
        self.node1_min_htlc = node1_min_htlc
        self.node2_min_htlc = node2_min_htlc
        self.node1_max_htlc = node1_max_htlc
        self.node2_max_htlc = node2_max_htlc
        self.node1_base_fee_msat = node1_base_fee_msat
        self.node2_base_fee_msat = node2_base_fee_msat
        self.node1_fee_rate_milli_msat = node1_fee_rate_milli_msat
        self.node2_fee_rate_milli_msat = node2_fee_rate_milli_msat
        self.node1_time_lock_delta = node1_time_lock_delta
        self.node2_time_lock_delta = node2_time_lock_delta
        self.logger = logging.getLogger("lnchan")

    def __str__(self) -> str:
        return (
            f"LNChannel(short_chan_id={self.short_chan_id}, "
            f"capacity_msat={self.capacity_msat}, "
            f"node1_pub={self.node1_pub[:8]}..., "
            f"node2_pub={self.node2_pub[:8]}..., "
            f"node1_policy=(min_htlc={self.node1_min_htlc}, "
            f"max_htlc={self.node1_max_htlc}, "
            f"base_fee={self.node1_base_fee_msat}, "
            f"fee_rate={self.node1_fee_rate_milli_msat}, "
            f"time_lock_delta={self.node1_time_lock_delta}), "
            f"node2_policy=(min_htlc={self.node2_min_htlc}, "
            f"max_htlc={self.node2_max_htlc}, "
            f"base_fee={self.node2_base_fee_msat}, "
            f"fee_rate={self.node2_fee_rate_milli_msat}, "
            f"time_lock_delta={self.node2_time_lock_delta}))"
        )

    # Only used to compare warnet channels imported from a mainnet source file
    # because pubkeys are unpredictable and node 1/2 might be swapped
    def flip(self) -> "LNChannel":
        return LNChannel(
            # Keep the old pubkeys so the constructor doesn't just flip it back
            node1_pub=self.node1_pub,
            node2_pub=self.node2_pub,
            capacity_msat=self.capacity_msat,
            short_chan_id=self.short_chan_id,
            # Flip the policies
            node1_min_htlc=self.node2_min_htlc,
            node2_min_htlc=self.node1_min_htlc,
            node1_max_htlc=self.node2_max_htlc,
            node2_max_htlc=self.node1_max_htlc,
            node1_base_fee_msat=self.node2_base_fee_msat,
            node2_base_fee_msat=self.node1_base_fee_msat,
            node1_fee_rate_milli_msat=self.node2_fee_rate_milli_msat,
            node2_fee_rate_milli_msat=self.node1_fee_rate_milli_msat,
            node1_time_lock_delta=self.node2_time_lock_delta,
            node2_time_lock_delta=self.node1_time_lock_delta,
        )

    def policy_match(self, ch2: "LNChannel") -> bool:
        assert isinstance(ch2, LNChannel)

        def compare_attributes(attr1, attr2, min_value=0, attr_name=""):
            if attr1 == 0 or attr2 == 0:
                return True
            result = max(int(attr1), min_value) == max(int(attr2), min_value)
            if not result:
                self.logger.debug(f"Mismatch in {attr_name}: {attr1} != {attr2}")
            return result

        attributes_to_compare = [
            (self.node1_time_lock_delta, ch2.node1_time_lock_delta, 18, "node1_time_lock_delta"),
            (self.node2_time_lock_delta, ch2.node2_time_lock_delta, 18, "node2_time_lock_delta"),
            (self.node1_min_htlc, ch2.node1_min_htlc, 1, "node1_min_htlc"),
            (self.node2_min_htlc, ch2.node2_min_htlc, 1, "node2_min_htlc"),
            (self.node1_base_fee_msat, ch2.node1_base_fee_msat, 0, "node1_base_fee_msat"),
            (self.node2_base_fee_msat, ch2.node2_base_fee_msat, 0, "node2_base_fee_msat"),
            (
                self.node1_fee_rate_milli_msat,
                ch2.node1_fee_rate_milli_msat,
                0,
                "node1_fee_rate_milli_msat",
            ),
            (
                self.node2_fee_rate_milli_msat,
                ch2.node2_fee_rate_milli_msat,
                0,
                "node2_fee_rate_milli_msat",
            ),
        ]

        return all(compare_attributes(*attrs) for attrs in attributes_to_compare)

    def channel_match(self, ch2: "LNChannel") -> bool:
        if self.capacity_msat != ch2.capacity_msat:
            self.logger.debug(f"Capacity mismatch: {self.capacity_msat} != {ch2.capacity_msat}")
            return False
        return self.policy_match(ch2)
