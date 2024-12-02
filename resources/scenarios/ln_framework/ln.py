import http.client
import json
import ssl
import time

# hard-coded deterministic lnd credentials
ADMIN_MACAROON_HEX = "0201036c6e6402f801030a1062beabbf2a614b112128afa0c0b4fdd61201301a160a0761646472657373120472656164120577726974651a130a04696e666f120472656164120577726974651a170a08696e766f69636573120472656164120577726974651a210a086d616361726f6f6e120867656e6572617465120472656164120577726974651a160a076d657373616765120472656164120577726974651a170a086f6666636861696e120472656164120577726974651a160a076f6e636861696e120472656164120577726974651a140a057065657273120472656164120577726974651a180a067369676e6572120867656e657261746512047265616400000620b17be53e367290871681055d0de15587f6d1cd47d1248fe2662ae27f62cfbdc6"
# Don't worry about lnd's self-signed certificates
INSECURE_CONTEXT = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
INSECURE_CONTEXT.check_hostname = False
INSECURE_CONTEXT.verify_mode = ssl.CERT_NONE


# https://github.com/lightningcn/lightning-rfc/blob/master/07-routing-gossip.md#the-channel_update-message
# We use the field names as written in the BOLT as our canonical, internal field names.
# In LND, Policy objects returned by DescribeGraph have completely different labels
# than policy objects expected by the UpdateChannelPolicy API, and neither
# of these are the names used in the BOLT...
class Policy:
    def __init__(
        self,
        cltv_expiry_delta: int,
        htlc_minimum_msat: int,
        fee_base_msat: int,
        fee_proportional_millionths: int,
        htlc_maximum_msat: int,
    ):
        self.cltv_expiry_delta = cltv_expiry_delta
        self.htlc_minimum_msat = htlc_minimum_msat
        self.fee_base_msat = fee_base_msat
        self.fee_proportional_millionths = fee_proportional_millionths
        self.htlc_maximum_msat = htlc_maximum_msat

    @classmethod
    def from_lnd_describegraph(cls, policy: dict):
        return cls(
            cltv_expiry_delta=int(policy.get("time_lock_delta")),
            htlc_minimum_msat=int(policy.get("min_htlc")),
            fee_base_msat=int(policy.get("fee_base_msat")),
            fee_proportional_millionths=int(policy.get("fee_rate_milli_msat")),
            htlc_maximum_msat=int(policy.get("max_htlc_msat")),
        )

    @classmethod
    def from_dict(cls, policy: dict):
        return cls(
            cltv_expiry_delta=policy.get("cltv_expiry_delta"),
            htlc_minimum_msat=policy.get("htlc_minimum_msat"),
            fee_base_msat=policy.get("fee_base_msat"),
            fee_proportional_millionths=policy.get("fee_proportional_millionths"),
            htlc_maximum_msat=policy.get("htlc_maximum_msat"),
        )

    def to_dict(self):
        return {
            "cltv_expiry_delta": self.cltv_expiry_delta,
            "htlc_minimum_msat": self.htlc_minimum_msat,
            "fee_base_msat": self.fee_base_msat,
            "fee_proportional_millionths": self.fee_proportional_millionths,
            "htlc_maximum_msat": self.htlc_maximum_msat,
        }

    def to_lnd_chanpolicy(self, capacity):
        # LND requires a 1% reserve
        reserve = ((capacity * 99) // 100) * 1000
        return {
            "time_lock_delta": self.cltv_expiry_delta,
            "min_htlc_msat": self.htlc_minimum_msat,
            "base_fee_msat": self.fee_base_msat,
            "fee_rate_ppm": self.fee_proportional_millionths,
            "max_htlc_msat": min(self.htlc_maximum_msat, reserve),
            "min_htlc_msat_specified": True,
        }


class LND:
    def __init__(self, pod_name):
        self.name = pod_name
        self.conn = http.client.HTTPSConnection(
            host=pod_name, port=8080, timeout=5, context=INSECURE_CONTEXT
        )

    def get(self, uri):
        while True:
            try:
                self.conn.request(
                    method="GET",
                    url=uri,
                    headers={"Grpc-Metadata-macaroon": ADMIN_MACAROON_HEX, "Connection": "close"},
                )
                return self.conn.getresponse().read().decode("utf8")
            except Exception:
                time.sleep(1)

    def post(self, uri, data):
        body = json.dumps(data)
        attempt = 0
        while True:
            attempt += 1
            try:
                self.conn.request(
                    method="POST",
                    url=uri,
                    body=body,
                    headers={
                        "Content-Type": "application/json",
                        "Content-Length": str(len(body)),
                        "Grpc-Metadata-macaroon": ADMIN_MACAROON_HEX,
                        "Connection": "close",
                    },
                )
                # Stream output, otherwise we get a timeout error
                res = self.conn.getresponse()
                stream = ""
                while True:
                    try:
                        data = res.read(1)
                        if len(data) == 0:
                            break
                        else:
                            stream += data.decode("utf8")
                    except Exception:
                        break
                return stream
            except Exception:
                time.sleep(1)

    def newaddress(self):
        res = self.get("/v1/newaddress")
        return json.loads(res)

    def walletbalance(self):
        res = self.get("/v1/balance/blockchain")
        return int(json.loads(res)["confirmed_balance"])

    def uri(self):
        res = self.get("/v1/getinfo")
        info = json.loads(res)
        if "uris" not in info or len(info["uris"]) == 0:
            return None
        return info["uris"][0]

    def connect(self, target_uri):
        pk, host = target_uri.split("@")
        res = self.post("/v1/peers", data={"addr": {"pubkey": pk, "host": host}})
        return json.loads(res)

    def channel(self, pk, capacity, push_amt, fee_rate):
        res = self.post(
            "/v1/channels/stream",
            data={
                "local_funding_amount": capacity,
                "push_sat": push_amt,
                "node_pubkey": pk,
                "sat_per_vbyte": fee_rate,
            },
        )
        return json.loads(res)

    def update(self, txid_hex: str, policy: dict, capacity: int):
        ln_policy = Policy.from_dict(policy).to_lnd_chanpolicy(capacity)
        data = {"chan_point": {"funding_txid_str": txid_hex, "output_index": 0}, **ln_policy}
        res = self.post(
            "/v1/chanpolicy",
            # Policy objects returned by DescribeGraph have
            # completely different labels than policy objects expected
            # by the UpdateChannelPolicy API.
            data=data,
        )
        return json.loads(res)

    def graph(self):
        res = self.get("/v1/graph")
        return json.loads(res)
