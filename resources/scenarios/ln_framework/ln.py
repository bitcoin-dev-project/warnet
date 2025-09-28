import base64
import http.client
import json
import logging
import ssl
from abc import ABC, abstractmethod
from time import sleep

import requests

# Don't worry about lnd's self-signed certificates
INSECURE_CONTEXT = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
INSECURE_CONTEXT.check_hostname = False
INSECURE_CONTEXT.verify_mode = ssl.CERT_NONE

# These values may need to be tweaked depending on the network being deployed.
# Currently passes all tests and ln_init succeeds on these examples:
#  test/data/LN_10.json
#  test/data/LN_50.json
#  test/data/LN_100.json
# If any values are changed, you may need to re-build network.yaml with import-network.
# Issues I encountered while setting on these values:
# - Too many blocks generated, ln_init takes too long
# - TX that distributes miner funds to LN wallets exceeds standard weight limit
# - Too many miner distribution TXs result in too-long-mempool-chain
# - Not enough UTXO value, forcing LN nodes to combine UTXOs to open large channels
#   which results in the change output being too big which results in the tx
#   outputs being ordered unexpectedly (which change at 0 and channel open at 1)
# - LND actual fee rate ends up way off from the expected value
# LN networks with more than 100 nodes and 500 channels may also need to tweak ln_init.py
CHANNEL_OPEN_START_HEIGHT = 500
CHANNEL_OPENS_PER_BLOCK = 200
MAX_FEE_RATE = 80006  # s/vB
FEE_RATE_DECREMENT = 400
assert MAX_FEE_RATE - (FEE_RATE_DECREMENT * CHANNEL_OPENS_PER_BLOCK) > 1


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
        # "min htlc amount of 0 mSAT is below min htlc parameter of 1 mSAT"
        min_htlc = 1
        return {
            "time_lock_delta": self.cltv_expiry_delta,
            "min_htlc_msat": max(self.htlc_minimum_msat, min_htlc),
            "base_fee_msat": self.fee_base_msat,
            "fee_rate_ppm": self.fee_proportional_millionths,
            "max_htlc_msat": min(self.htlc_maximum_msat, reserve),
            "min_htlc_msat_specified": True,
        }


class LNNode(ABC):
    @abstractmethod
    def __init__(self, pod_name, pod_namespace, ip_address):
        self.name = pod_name
        self.namespace = pod_namespace
        self.ip_address = ip_address
        self.log = logging.getLogger(pod_name)
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(name)-8s - %(levelname)s: %(message)s")
        handler.setFormatter(formatter)
        self.log.addHandler(handler)
        self.log.setLevel(logging.INFO)

    @staticmethod
    def hex_to_b64(hex):
        return base64.b64encode(bytes.fromhex(hex)).decode()

    @staticmethod
    def b64_to_hex(b64, reverse=False):
        if reverse:
            return base64.b64decode(b64)[::-1].hex()
        else:
            return base64.b64decode(b64).hex()

    @abstractmethod
    def newaddress(self) -> tuple[bool, str]:
        pass

    @abstractmethod
    def uri(self) -> str:
        pass

    @abstractmethod
    def walletbalance(self) -> int:
        pass

    @abstractmethod
    def connect(self, target_uri) -> dict:
        pass

    @abstractmethod
    def channel(self, pk, capacity, push_amt, fee_rate) -> dict:
        pass

    @abstractmethod
    def graph(self) -> dict:
        pass

    @abstractmethod
    def update(self, txid_hex: str, policy: dict, capacity: int) -> dict:
        pass


class CLN(LNNode):
    def __init__(self, pod_name, pod_namespace, ip_address):
        super().__init__(pod_name, pod_namespace, ip_address)
        self.conn = None
        self.headers = {}
        self.impl = "cln"
        self.reset_connection()

    def reset_connection(self):
        self.conn = http.client.HTTPSConnection(
            host=f"{self.name}.{self.namespace}", port=3010, timeout=60, context=INSECURE_CONTEXT
        )

    def setRune(self, rune):
        self.headers = {"Rune": rune}

    def get(self, uri):
        self.reset_connection()
        self.log.info(f"CLN GET headers: {self.headers}")
        self.conn.request(
            method="GET",
            url=uri,
            headers=self.headers,
        )
        return self.conn.getresponse().read().decode("utf8")

    def post(self, uri, data=None):
        if not data:
            data = {}
        body = json.dumps(data)
        post_header = self.headers
        post_header["Content-Length"] = str(len(body))
        post_header["Content-Type"] = "application/json"
        self.reset_connection()
        self.conn.request(
            method="POST",
            url=uri,
            body=body,
            headers=post_header,
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

    def createrune(self):
        while True:
            response = requests.get(f"http://{self.ip_address}:8080/rune.json", timeout=5).text
            if not response:
                self.log.warning(f"Unable to fetch rune from {self.name}, retrying in 2 seconds...")
                sleep(2)
                continue
            self.log.debug(response)
            res = json.loads(response)
            self.setRune(res["rune"])
            return

    def newaddress(self):
        self.createrune()
        response = self.post("/v1/newaddr", data={"addresstype": "p2tr"})
        res = json.loads(response)
        if "p2tr" in res:
            return res["p2tr"]
        raise Exception(res)

    def uri(self):
        res = json.loads(self.post("/v1/getinfo"))
        return f"{res['id']}@{res['address'][0]['address']}:{res['address'][0]['port']}"

    def walletbalance(self) -> int:
        response = self.post("/v1/listfunds")
        res = json.loads(response)
        return int(sum(o["amount_msat"] for o in res["outputs"]) / 1000)

    def channelbalance(self) -> int:
        response = self.post("/v1/listfunds")
        res = json.loads(response)
        return int(sum(o["our_amount_msat"] for o in res["channels"]) / 1000)

    def connect(self, target_uri) -> dict:
        response = self.post("/v1/connect", {"id": target_uri})
        res = json.loads(response)
        if "id" in res:
            return {}
        else:
            return res

    def channel(self, pk, capacity, push_amt, fee_rate) -> dict:
        data = {
            "amount": capacity,
            "push_msat": push_amt,
            "id": pk,
            "feerate": fee_rate,
        }
        response = self.post("/v1/fundchannel", data)
        res = json.loads(response)
        return {"txid": res["txid"], "outpoint": f"{res['txid']}:{res['outnum']}"}

    def createinvoice(self, sats, label) -> str:
        response = self.post("invoice", {"amount_msat": sats * 1000, "label": label})
        res = json.loads(response)
        return res["bolt11"]

    def payinvoice(self, payment_request) -> str:
        response = self.post("/v1/pay", {"bolt11": payment_request})
        res = json.loads(response)
        return res

    def graph(self) -> dict:
        response = self.post("/v1/listchannels")
        res = json.loads(response)
        # Map to desired output
        filtered_channels = [ch for ch in res["channels"] if ch["direction"] == 1]
        # Sort by short_channel_id - block -> index -> output
        sorted_channels = sorted(filtered_channels, key=lambda x: x["short_channel_id"])
        # Add capacity by dividing amount_msat by 1000
        for channel in sorted_channels:
            channel["capacity"] = channel["amount_msat"] // 1000
        return {"edges": sorted_channels}

    def update(self, txid_hex: str, policy: dict, capacity: int) -> dict:
        raise Exception("Channel Policy Updates not supported by CLN yet!")


class LND(LNNode):
    def __init__(self, pod_name, pod_namespace, ip_address, admin_macaroon_hex):
        super().__init__(pod_name, pod_namespace, ip_address)
        self.conn = None
        self.admin_macaroon_hex = admin_macaroon_hex
        self.headers = {
            "Grpc-Metadata-macaroon": admin_macaroon_hex,
            "Connection": "close",
        }
        self.impl = "lnd"

    def reset_connection(self):
        self.conn = http.client.HTTPSConnection(
            host=f"{self.name}.{self.namespace}", port=8080, timeout=60, context=INSECURE_CONTEXT
        )

    def get(self, uri):
        self.reset_connection()
        self.conn.request(
            method="GET",
            url=uri,
            headers=self.headers,
        )
        return self.conn.getresponse().read().decode("utf8")

    def post(self, uri, data, wait_for_completion=True):
        body = json.dumps(data)
        post_header = self.headers
        post_header["Content-Length"] = str(len(body))
        post_header["Content-Type"] = "application/json"
        self.reset_connection()
        self.conn.request(
            method="POST",
            url=uri,
            body=body,
            headers=post_header,
        )
        # Stream output, otherwise we get a timeout error
        res = self.conn.getresponse()
        stream = ""
        while True:
            try:
                data = res.read(1)
                if len(data) == 0:
                    break
                if not wait_for_completion and data.decode("utf8") == "\n":
                    break
                stream += data.decode("utf8")
            except Exception:
                break
        return stream

    def newaddress(self):
        # Taproot signatures are a fixed length which improves
        # the accuracy of fee estimation, and therefore our
        # channel ID determinism.
        response = self.get("/v1/newaddress?type=TAPROOT_PUBKEY")
        res = json.loads(response)
        if "address" in res:
            return res["address"]
        raise Exception(res)

    def walletbalance(self) -> int:
        res = self.get("/v1/balance/blockchain")
        return int(json.loads(res)["confirmed_balance"])

    def channelbalance(self) -> int:
        res = self.get("/v1/balance/channels")
        return int(json.loads(res)["balance"])

    def uri(self):
        res = self.get("/v1/getinfo")
        info = json.loads(res)
        return info["uris"][0]

    def connect(self, target_uri):
        pk, host = target_uri.split("@")
        response = self.post("/v1/peers", data={"addr": {"pubkey": pk, "host": host}})
        res = json.loads(response)
        if "status" in res and "initiated" in res["status"]:
            return {}
        else:
            return res

    def channel(self, pk, capacity, push_amt, fee_rate):
        b64_pk = self.hex_to_b64(pk)
        response = self.post(
            "/v1/channels/stream",
            data={
                "local_funding_amount": capacity,
                "push_sat": push_amt,
                "node_pubkey": b64_pk,
                "sat_per_vbyte": fee_rate,
            },
        )
        res = json.loads(response)
        if "result" not in res:
            raise Exception(res)
        res["txid"] = self.b64_to_hex(res["result"]["chan_pending"]["txid"], reverse=True)
        res["outpoint"] = f"{res['txid']}:{res['result']['chan_pending']['output_index']}"
        return res

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

    def createinvoice(self, sats, label) -> str:
        response = self.post("/v1/invoices", data={"value": sats, "memo": label})
        res = json.loads(response)
        return res["payment_request"]

    def payinvoice(self, payment_request) -> str:
        response = self.post(
            "/v2/router/send",
            data={"payment_request": payment_request, "fee_limit_sat": 2100000000},
            wait_for_completion=False,
        )
        res = json.loads(response)
        return res

    def graph(self):
        res = self.get("/v1/graph")
        return json.loads(res)
