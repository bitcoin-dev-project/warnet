from abc import ABC, abstractmethod
import base64
import http.client
import logging
import json
import ssl
from time import sleep
from typing import Optional
from kubernetes import client, config
from kubernetes.stream import stream

# hard-coded deterministic lnd credentials
ADMIN_MACAROON_HEX = "0201036c6e6402f801030a1062beabbf2a614b112128afa0c0b4fdd61201301a160a0761646472657373120472656164120577726974651a130a04696e666f120472656164120577726974651a170a08696e766f69636573120472656164120577726974651a210a086d616361726f6f6e120867656e6572617465120472656164120577726974651a160a076d657373616765120472656164120577726974651a170a086f6666636861696e120472656164120577726974651a160a076f6e636861696e120472656164120577726974651a140a057065657273120472656164120577726974651a180a067369676e6572120867656e657261746512047265616400000620b17be53e367290871681055d0de15587f6d1cd47d1248fe2662ae27f62cfbdc6"
# Don't worry about ln's self-signed certificates
INSECURE_CONTEXT = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
INSECURE_CONTEXT.check_hostname = False
INSECURE_CONTEXT.verify_mode = ssl.CERT_NONE

def run_command(name, command: list[str], namespace: Optional[str] = "default") -> str:
    config.load_incluster_config()
    sclient = client.CoreV1Api()
    resp = stream(
            sclient.connect_get_namespaced_pod_exec,
            name,
            namespace,
            command=command,
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False,
            _request_timeout=20,
            _preload_content=False,
        )
    result = ""
    while resp.is_open():
        resp.update(timeout=5)
        if resp.peek_stdout():
            result+=resp.read_stdout()
        if resp.peek_stderr():
            raise Exception(resp.read_stderr())
    resp.close()
    return result


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
    def __init__(self, pod_name):
        self.log = logging.getLogger(self.__class__.__name__)
        self.name = pod_name
        # Configure logger if it has no handlers
        if not self.log.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            self.log.addHandler(handler)
            self.log.setLevel(logging.INFO)

    @staticmethod
    def param_dict_to_list(params: dict) -> list[str]:
        return [f'{k}={v}' for k,v in params.items()]

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
    def graph(self):
        pass

class CLN(LNNode):
    def __init__(self, pod_name):
        super().__init__(pod_name)
        self.headers = {}
        self.impl = "cln"
   
    def rpc(self, method: str, params: list[str] = [], namespace: Optional[str] = "default", max_tries=5):
        cmd = ["lightning-cli", method]
        cmd.extend(params)
        attempt=0
        while attempt < max_tries:
            attempt+=1
            try:
                response = run_command(self.name, cmd, namespace)
                if not response:
                    continue
                return response
            except Exception as e:
                self.log.info(f"CLN rpc error: {e}")
                sleep(2)
        return None

    def newaddress(self, max_tries=2):
        attempt=0
        while attempt < max_tries:
            attempt+=1
            response = self.rpc("newaddr")
            if not response:
                sleep(2)
                continue
            res = json.loads(response)
            if "bech32" in res:
                return True, res["bech32"]
            else:
                self.log.info(
                    f"Couldn't get wallet address from {self.name}:\n  {res}\n  wait and retry..."
                )
            sleep(2)
        return False, ""

    def uri(self):
        res = json.loads(self.rpc("getinfo"))
        if len(res["address"]) < 1:
            return None
        return f'{res["id"]}@{res["address"][0]["address"]}:{res["address"][0]["port"]}'

    def walletbalance(self, max_tries=2):
        attempt=0
        while attempt < max_tries:
            attempt+=1
            response = self.rpc("listfunds")
            if not response:
                sleep(2)
                continue
            res = json.loads(response)
            return int(sum(o["amount_msat"] for o in res["outputs"]) / 1000)
        return 0
            
    def connect(self, target_uri, max_tries=5):
        attempt=0
        self.log.info(f"CLN connect {self.name} to {target_uri}")
        while attempt < max_tries:
            attempt+=1
            response = self.rpc("connect", [target_uri])
            if response:
                res = json.loads(response)
                if "id" in res:
                    self.log.debug(f"finished connect response: {response}")
                    return {}
                elif "code" in res and res["code"] == 402:
                    self.log.info(f"failed connect response: {response}")
                    sleep(5)
                else:
                    return res
            else:
                self.log.debug(f"connect response: {response}")
                sleep(5)
        return ""
    
    def channel(self, pk, capacity, push_amt, fee_rate, max_tries=5):
        data={
            "amount": capacity,
            "push_msat": push_amt,
            "id": pk,
            "feerate": fee_rate,
        }
        attempt=0
        while attempt < max_tries:
            attempt+=1
            response = self.rpc("fundchannel", self.param_dict_to_list(data))
            if response:
                res = json.loads(response)
                if "txid" in res:
                    self.log.debug(f"open channel succeeded: {res}")
                    return {"txid": res["txid"], "outpoint": f'{res["txid"]}:{res["outnum"]}'}
                else:
                    self.log.info(f"unable to open channel: {res}")
            else:
                self.log.debug(f"channel response: {response}")
                sleep(5)
        return ""

    def graph(self, max_tries=2):
        attempt=0
        while attempt < max_tries:
            attempt+=1
            response = self.rpc("listchannels")
            if response:
                res = json.loads(response)
                if "channels" in res:
                    return {"edges": res["channels"]}
                else:
                    self.log.info(f"unable to open channel: {res}")
            else:
                self.log.debug(f"channel response: {response}")
                sleep(5)
        return ""
    
    def update(self, txid_hex: str, policy: dict, capacity: int, max_tries=2):
        self.log.info("Channel Policy Updates not supported by CLN yet!")
        return
        # ln_policy = Policy.from_dict(policy).to_lnd_chanpolicy(capacity)
        # data = {"chan_point": {"funding_txid_str": txid_hex, "output_index": 0}, **ln_policy}
        # attempt=0
        # while attempt < max_tries:
        #     attempt+=1
        #     response = self.rpc("setchannel")
        #     if response:
        #         res = json.loads(response)
        #         if "channels" in res:
        #             print(f"graph succeeded: {res}")
        #             return {"edges": res["channels"]}
        #         else:
        #             print(f"unable to open channel: {res}")
        #     else:
        #         print(f"channel response: {response}")
        #         sleep(5)
        # return ""

class LND(LNNode):
    def __init__(self, pod_name):
        super().__init__(pod_name)
        self.conn = http.client.HTTPSConnection(
            host=pod_name, port=8080, timeout=5, context=INSECURE_CONTEXT
        )
        self.headers = {
                        "Grpc-Metadata-macaroon": ADMIN_MACAROON_HEX,
                        "Connection": "close",
                        }
        self.impl = "lnd"

    def get(self, uri):
        while True:
            try:
                self.conn.request(
                    method="GET",
                    url=uri,
                    headers=self.headers,
                )
                return self.conn.getresponse().read().decode("utf8")
            except Exception:
                sleep(1)

    def post(self, uri, data):
        body = json.dumps(data)
        post_header=self.headers
        post_header["Content-Length"]=str(len(body))
        post_header["Content-Type"] = "application/json"
        attempt = 0
        while True:
            attempt += 1
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
            except Exception:
                sleep(1)

    def newaddress(self, max_tries=10):
        attempt=0
        while attempt < max_tries:
            attempt+=1
            response = self.get("/v1/newaddress")
            res = json.loads(response)
            if "address" in res:
                return True, res["address"]
            else:
                self.log.info(
                    f"Couldn't get wallet address from {self.name}:\n  {res}\n  wait and retry..."
                )
            sleep(1)
        return False, ""

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
        try:
            res = json.loads(response)
            if "result" in res:
                res["txid"] = self.b64_to_hex(res["result"]["chan_pending"]["txid"], reverse=True)
                res["outpoint"] = f'{res["txid"]}:{res["result"]["chan_pending"]["output_index"]}'
                self.log.info(f"LND channel RESPONSE: {res}")
        except Exception as e:
            self.log.info(f"Error opening LND channel: {e}")
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

    def graph(self):
        res = self.get("/v1/graph")
        return json.loads(res)
