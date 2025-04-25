import base64
import http.client
import json
import logging
import ssl
from abc import ABC, abstractmethod
from time import sleep

import requests

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


class LNNode(ABC):
    @abstractmethod
    def __init__(self, pod_name, ip_address):
        self.name = pod_name
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
    def newaddress(self, max_tries=10) -> tuple[bool, str]:
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
    def __init__(self, pod_name, ip_address):
        super().__init__(pod_name, ip_address)
        self.conn = None
        self.headers = {}
        self.impl = "cln"
        self.reset_connection()

    def reset_connection(self):
        self.conn = http.client.HTTPSConnection(
            host=self.name, port=3010, timeout=5, context=INSECURE_CONTEXT
        )

    def setRune(self, rune):
        self.headers = {"Rune": rune}

    def get(self, uri):
        attempt = 0
        while True:
            try:
                self.log.warning(f"headers: {self.headers}")
                self.conn.request(
                    method="GET",
                    url=uri,
                    headers=self.headers,
                )
                return self.conn.getresponse().read().decode("utf8")
            except Exception as e:
                self.reset_connection()
                attempt += 1
                if attempt > 5:
                    self.log.error(f"Error CLN GET, Abort: {e}")
                    return None
                sleep(1)

    def post(self, uri, data=None):
        if not data:
            data = {}
        body = json.dumps(data)
        post_header = self.headers
        post_header["Content-Length"] = str(len(body))
        post_header["Content-Type"] = "application/json"
        attempt = 0
        while True:
            try:
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
            except Exception as e:
                self.reset_connection()
                attempt += 1
                if attempt > 5:
                    self.log.error(f"Error CLN POST, Abort: {e}")
                    return None
                sleep(1)

    def createrune(self, max_tries=2):
        attempt = 0
        while attempt < max_tries:
            attempt += 1
            response = requests.get(f"http://{self.ip_address}:8080/rune.json", timeout=5).text
            if not response:
                sleep(2)
                continue
            self.log.debug(response)
            res = json.loads(response)
            self.setRune(res["rune"])
            return
        raise Exception(f"Unable to fetch rune from {self.name}")

    def newaddress(self, max_tries=2):
        self.createrune()
        attempt = 0
        while attempt < max_tries:
            attempt += 1
            response = self.post("/v1/newaddr")
            if not response:
                sleep(2)
                continue
            res = json.loads(response)
            if "bech32" in res:
                return True, res["bech32"]
            else:
                self.log.warning(
                    f"Couldn't get wallet address from {self.name}:\n  {res}\n  wait and retry..."
                )
            sleep(2)
        return False, ""

    def uri(self):
        res = json.loads(self.post("/v1/getinfo"))
        if len(res["address"]) < 1:
            return None
        return f"{res['id']}@{res['address'][0]['address']}:{res['address'][0]['port']}"

    def walletbalance(self, max_tries=2) -> int:
        attempt = 0
        while attempt < max_tries:
            attempt += 1
            response = self.post("/v1/listfunds")
            if not response:
                sleep(2)
                continue
            res = json.loads(response)
            return int(sum(o["amount_msat"] for o in res["outputs"]) / 1000)
        return 0

    def channelbalance(self, max_tries=2) -> int:
        attempt = 0
        while attempt < max_tries:
            attempt += 1
            response = self.post("/v1/listfunds")
            if not response:
                sleep(2)
                continue
            res = json.loads(response)
            return int(sum(o["our_amount_msat"] for o in res["channels"]) / 1000)
        return 0

    def connect(self, target_uri, max_tries=5) -> dict:
        attempt = 0
        while attempt < max_tries:
            attempt += 1
            response = self.post("/v1/connect", {"id": target_uri})
            if response:
                res = json.loads(response)
                if "id" in res:
                    return {}
                elif "code" in res and res["code"] == 402:
                    self.log.warning(f"failed connect 402: {response}, wait and retry...")
                    sleep(5)
                else:
                    return res
            else:
                self.log.debug(f"connect response: {response}, wait and retry...")
                sleep(2)
        return None

    def channel(self, pk, capacity, push_amt, fee_rate, max_tries=5) -> dict:
        data = {
            "amount": capacity,
            "push_msat": push_amt,
            "id": pk,
            "feerate": fee_rate,
        }
        attempt = 0
        while attempt < max_tries:
            attempt += 1
            response = self.post("/v1/fundchannel", data)
            if response:
                res = json.loads(response)
                if "txid" in res:
                    return {"txid": res["txid"], "outpoint": f"{res['txid']}:{res['outnum']}"}
                else:
                    self.log.warning(f"unable to open channel: {res}, wait and retry...")
                    sleep(1)
            else:
                self.log.debug(f"channel response: {response}, wait and retry...")
                sleep(2)
        return None

    def createinvoice(self, sats, label, description="new invoice") -> str:
        response = self.post(
            "invoice", {"amount_msat": sats * 1000, "label": label, "description": description}
        )
        if response:
            res = json.loads(response)
            return res["bolt11"]
        return None

    def payinvoice(self, payment_request) -> str:
        response = self.post("/v1/pay", {"bolt11": payment_request})
        if response:
            res = json.loads(response)
            if "code" in res:
                return res["message"]
            else:
                return res["payment_hash"]
        return None

    def graph(self, max_tries=2) -> dict:
        attempt = 0
        while attempt < max_tries:
            attempt += 1
            response = self.post("/v1/listchannels")
            if response:
                res = json.loads(response)
                if "channels" in res:
                    # Map to desired output
                    filtered_channels = [ch for ch in res["channels"] if ch["direction"] == 1]
                    # Sort by short_channel_id - block -> index -> output
                    sorted_channels = sorted(filtered_channels, key=lambda x: x["short_channel_id"])
                    # Add capacity by dividing amount_msat by 1000
                    for channel in sorted_channels:
                        channel["capacity"] = channel["amount_msat"] // 1000
                    return {"edges": sorted_channels}
                else:
                    self.log.warning(f"unable to open channel: {res}, wait and retry...")
                    sleep(1)
            else:
                self.log.debug(f"channel response: {response}, wait and retry...")
                sleep(2)
        return None

    def update(self, txid_hex: str, policy: dict, capacity: int, max_tries=2) -> dict:
        self.log.warning("Channel Policy Updates not supported by CLN yet!")
        return None


class LND(LNNode):
    def __init__(self, pod_name, ip_address):
        super().__init__(pod_name, ip_address)
        self.conn = http.client.HTTPSConnection(
            host=pod_name, port=8080, timeout=5, context=INSECURE_CONTEXT
        )
        self.headers = {
            "Grpc-Metadata-macaroon": ADMIN_MACAROON_HEX,
            "Connection": "close",
        }
        self.impl = "lnd"

    def reset_connection(self):
        self.conn = http.client.HTTPSConnection(
            host=self.name, port=8080, timeout=5, context=INSECURE_CONTEXT
        )

    def get(self, uri):
        attempt = 0
        while True:
            try:
                self.conn.request(
                    method="GET",
                    url=uri,
                    headers=self.headers,
                )
                return self.conn.getresponse().read().decode("utf8")
            except Exception as e:
                self.reset_connection()
                attempt += 1
                if attempt > 5:
                    self.log.error(f"Error LND POST, Abort: {e}")
                    return None
                sleep(1)

    def post(self, uri, data):
        body = json.dumps(data)
        post_header = self.headers
        post_header["Content-Length"] = str(len(body))
        post_header["Content-Type"] = "application/json"
        attempt = 0
        while True:
            try:
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
            except Exception as e:
                self.reset_connection()
                attempt += 1
                if attempt > 5:
                    self.log.error(f"Error LND POST, Abort: {e}")
                    return None
                sleep(1)

    def newaddress(self, max_tries=10):
        attempt = 0
        while attempt < max_tries:
            attempt += 1
            response = self.get("/v1/newaddress")
            res = json.loads(response)
            if "address" in res:
                return True, res["address"]
            else:
                self.log.warning(
                    f"Couldn't get wallet address from {self.name}:\n  {res}\n  wait and retry..."
                )
            sleep(1)
        return False, ""

    def walletbalance(self) -> int:
        res = self.get("/v1/balance/blockchain")
        return int(json.loads(res)["confirmed_balance"])

    def channelbalance(self) -> int:
        res = self.get("/v1/balance/channels")
        return int(json.loads(res)["balance"])

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

    def channel(self, pk, capacity, push_amt, fee_rate, max_tries=2):
        b64_pk = self.hex_to_b64(pk)
        attempt = 0
        while attempt < max_tries:
            attempt += 1
            response = self.post(
                "/v1/channels/stream",
                data={
                    "local_funding_amount": capacity,
                    "push_sat": push_amt,
                    "node_pubkey": b64_pk,
                    "sat_per_vbyte": fee_rate,
                },
            )
            try:
                res = json.loads(response)
                if "result" in res:
                    res["txid"] = self.b64_to_hex(
                        res["result"]["chan_pending"]["txid"], reverse=True
                    )
                    res["outpoint"] = (
                        f"{res['txid']}:{res['result']['chan_pending']['output_index']}"
                    )
                    return res
                self.log.warning(f"Open LND channel error: {res}")
            except Exception as e:
                self.log.error(f"Error opening LND channel: {e}")
            sleep(2)
        return None

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

    def createinvoice(self, sats, label, description="new invoice") -> str:
        b64_desc = base64.b64encode(description.encode("utf-8"))
        response = self.post(
            "/v1/invoices", data={"value": sats, "memo": label, "description_hash": b64_desc}
        )
        if response:
            res = json.loads(response)
            return res["payment_request"]
        return None

    def payinvoice(self, payment_request) -> str:
        response = self.post(
            "/v1/channels/transaction-stream", data={"payment_request": payment_request}
        )
        if response:
            res = json.loads(response)
            if "payment_error" in res:
                return res["payment_error"]
            else:
                return res["payment_hash"]
        return None

    def graph(self):
        res = self.get("/v1/graph")
        return json.loads(res)
