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

    def policy_match(self, ch2: "LNChannel") -> bool:
        assert isinstance(ch2, LNChannel)

        def compare_attributes(attr1, attr2, min_value=0):
            if attr1 == 0 or attr2 == 0:
                return True
            return max(int(attr1), min_value) == max(int(attr2), min_value)

        # Ignoring max_htlc for now since we use capacity/2
        attributes_to_compare = [
            (self.node1_time_lock_delta, ch2.node1_time_lock_delta, 18),
            (self.node2_time_lock_delta, ch2.node2_time_lock_delta, 18),
            (self.node1_min_htlc, ch2.node1_min_htlc, 1),
            (self.node2_min_htlc, ch2.node2_min_htlc, 1),
            (self.node1_base_fee_msat, ch2.node1_base_fee_msat),
            (self.node2_base_fee_msat, ch2.node2_base_fee_msat),
            (self.node1_fee_rate_milli_msat, ch2.node1_fee_rate_milli_msat),
            (ch2.node2_fee_rate_milli_msat, ch2.node2_fee_rate_milli_msat),
        ]

        return all(compare_attributes(*attrs) for attrs in attributes_to_compare)

    def channel_match(self, ch2: "LNChannel") -> bool:
        if self.capacity_msat != ch2.capacity_msat:
            return False
        return self.policy_match(ch2)
