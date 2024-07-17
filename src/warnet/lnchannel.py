import logging


class LNPolicy:
    def __init__(
        self,
        min_htlc: int,
        max_htlc: int,
        base_fee_msat: int,
        fee_rate_milli_msat: int,
        time_lock_delta: int = 0,
    ) -> None:
        self.min_htlc = min_htlc
        self.max_htlc = max_htlc
        self.base_fee_msat = base_fee_msat
        self.fee_rate_milli_msat = fee_rate_milli_msat
        self.time_lock_delta = time_lock_delta

    def __str__(self) -> str:
        return (
            f"LNPolicy(min_htlc={self.min_htlc}, "
            f"max_htlc={self.max_htlc}, "
            f"base_fee={self.base_fee_msat}, "
            f"fee_rate={self.fee_rate_milli_msat}, "
            f"time_lock_delta={self.time_lock_delta})"
        )


class LNChannel:
    def __init__(
        self,
        node1_pub: str,
        node2_pub: str,
        capacity_msat: int = 0,
        short_chan_id: str = "",
        node1_policy: LNPolicy = None,
        node2_policy: LNPolicy = None,
    ) -> None:
        # Ensure that the node with the lower pubkey is node1
        if node1_pub > node2_pub:
            node1_pub, node2_pub = node2_pub, node1_pub
            node1_policy, node2_policy = node2_policy, node1_policy
        self.node1_pub = node1_pub
        self.node2_pub = node2_pub
        self.capacity_msat = capacity_msat
        self.short_chan_id = short_chan_id
        self.node1_policy = node1_policy
        self.node2_policy = node2_policy
        self.logger = logging.getLogger("lnchan")

    def __str__(self) -> str:
        return (
            f"LNChannel(short_chan_id={self.short_chan_id}, "
            f"capacity_msat={self.capacity_msat}, "
            f"node1_pub={self.node1_pub[:8]}..., "
            f"node2_pub={self.node2_pub[:8]}..., "
            f"node1_policy=({self.node1_policy.__str__()}), "
            f"node2_policy=({self.node2_policy.__str__()}))"
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
            node1_policy=self.node2_policy,
            node2_policy=self.node1_policy,
        )

    def policy_match(self, ch2: "LNChannel") -> bool:
        assert isinstance(ch2, LNChannel)

        node1_policy_match = False
        node2_policy_match = False

        if self.node1_policy is None and ch2.node1_policy is None:
            node1_policy_match = True

        if self.node2_policy is None and ch2.node2_policy is None:
            node2_policy_match = True

        def compare_attributes(attr1, attr2, min_value=0, attr_name=""):
            if attr1 == 0 or attr2 == 0:
                return True
            result = max(int(attr1), min_value) == max(int(attr2), min_value)
            if not result:
                self.logger.debug(f"Mismatch in {attr_name}: {attr1} != {attr2}")
            return result

        if self.node1_policy is not None and ch2.node1_policy is not None:
            attributes_to_compare = [
                (
                    self.node1_policy.time_lock_delta,
                    ch2.node1_policy.time_lock_delta,
                    18,
                    "node1_time_lock_delta",
                ),
                (self.node1_policy.min_htlc, ch2.node1_policy.min_htlc, 1, "node1_min_htlc"),
                (
                    self.node1_policy.base_fee_msat,
                    ch2.node1_policy.base_fee_msat,
                    0,
                    "node1_base_fee_msat",
                ),
                (
                    self.node1_policy.fee_rate_milli_msat,
                    ch2.node1_policy.fee_rate_milli_msat,
                    0,
                    "node1_fee_rate_milli_msat",
                ),
            ]
            node1_policy_match = all(compare_attributes(*attrs) for attrs in attributes_to_compare)

        if self.node2_policy is not None and ch2.node2_policy is not None:
            attributes_to_compare = [
                (
                    self.node2_policy.time_lock_delta,
                    ch2.node2_policy.time_lock_delta,
                    18,
                    "node2_time_lock_delta",
                ),
                (self.node2_policy.min_htlc, ch2.node2_policy.min_htlc, 1, "node2_min_htlc"),
                (
                    self.node2_policy.base_fee_msat,
                    ch2.node2_policy.base_fee_msat,
                    0,
                    "node2_base_fee_msat",
                ),
                (
                    self.node2_policy.fee_rate_milli_msat,
                    ch2.node2_policy.fee_rate_milli_msat,
                    0,
                    "node2_fee_rate_milli_msat",
                ),
            ]
            node2_policy_match = all(compare_attributes(*attrs) for attrs in attributes_to_compare)

        return node1_policy_match and node2_policy_match

    def channel_match(self, ch2: "LNChannel") -> bool:
        if self.capacity_msat != ch2.capacity_msat:
            self.logger.debug(f"Capacity mismatch: {self.capacity_msat} != {ch2.capacity_msat}")
            return False
        return self.policy_match(ch2)
