import base64
import http.client
import json
import logging
import re
import shlex
import ssl
import threading
import urllib.parse
from abc import ABC, abstractmethod
from time import sleep, time

import requests
from kubernetes.stream import stream

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
# LN networks with more than 100 nodes and 500 channels may also need to tweak ln_init.py
CHANNEL_OPEN_START_HEIGHT = 500
CHANNEL_OPENS_PER_BLOCK = 200
# Fee rate paid by every channel funding transaction. ln_init orders them in
# the block with prioritisetransaction on the miner, so it doesn't matter what
# they pay as long as every node relays them and every implementation accepts
# the rate. It is passed explicitly because there are no fee estimates on a
# new regtest chain.
CHANNEL_OPEN_FEE_RATE = 10  # s/vB
# Seconds without any node's graph growing before ln_init tries to recover gossip
GOSSIP_STALL_TIMEOUT = 60


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
    def update(self, txid_hex: str, policy: dict, capacity: int, output_index=0) -> dict:
        pass


class CLN(LNNode):
    def __init__(self, pod_name, pod_namespace, ip_address):
        super().__init__(pod_name, pod_namespace, ip_address)
        self.headers = {}
        self.impl = "cln"

    # A new connection per request, so one node can be used from many threads
    def new_connection(self):
        return http.client.HTTPSConnection(
            host=f"{self.name}.{self.namespace}", port=3010, timeout=60, context=INSECURE_CONTEXT
        )

    def setRune(self, rune):
        self.headers = {"Rune": rune}

    def get(self, uri):
        if "Rune" not in self.headers:
            self.createrune()
        conn = self.new_connection()
        conn.request(
            method="GET",
            url=uri,
            headers=self.headers,
        )
        return conn.getresponse().read().decode("utf8")

    def post(self, uri, data=None):
        if "Rune" not in self.headers:
            self.createrune()
        if not data:
            data = {}
        body = json.dumps(data)
        post_header = {
            **self.headers,
            "Content-Length": str(len(body)),
            "Content-Type": "application/json",
        }
        conn = self.new_connection()
        conn.request(
            method="POST",
            url=uri,
            body=body,
            headers=post_header,
        )
        # Stream output, otherwise we get a timeout error
        res = conn.getresponse()
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
            response = None
            try:
                response = requests.get(f"http://{self.ip_address}:8080/rune.json", timeout=5).text
            except Exception as e:
                self.log.warning(f"Error requesting /rune.json: {e}")
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
            "push_msat": push_amt * 1000,
            "id": pk,
            # A feerate without a unit suffix is interpreted as sat/kvB
            "feerate": f"{fee_rate * 1000}perkb",
        }
        response = self.post("/v1/fundchannel", data)
        res = json.loads(response)
        if "txid" not in res:
            raise Exception(res)
        return {"txid": res["txid"], "outpoint": f"{res['txid']}:{res['outnum']}"}

    def createinvoice(self, sats, label) -> str:
        # label must be unique, description is required
        response = self.post(
            "/v1/invoice", {"amount_msat": sats * 1000, "label": label, "description": label}
        )
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
        sorted_channels = sorted(
            filtered_channels,
            key=lambda x: tuple(int(n) for n in x["short_channel_id"].split("x")),
        )
        # Add capacity by dividing amount_msat by 1000
        for channel in sorted_channels:
            channel["capacity"] = channel["amount_msat"] // 1000
        return {"edges": sorted_channels}

    def update(self, txid_hex: str, policy: dict, capacity: int, output_index=0) -> dict:
        raise Exception("Channel Policy Updates not supported by CLN yet!")


class ECLAIR(LNNode):
    # Set by eclair.api.password in the eclair chart
    API_PASSWORD = "21satoshi"

    def __init__(self, pod_name, pod_namespace, ip_address):
        super().__init__(pod_name, pod_namespace, ip_address)
        auth = base64.b64encode(f":{self.API_PASSWORD}".encode()).decode()
        self.headers = {"Authorization": f"Basic {auth}"}
        self.impl = "eclair"

    # A new connection per request, so one node can be used from many threads
    def new_connection(self):
        return http.client.HTTPConnection(
            host=f"{self.name}.{self.namespace}", port=8080, timeout=60
        )

    # https://acinq.github.io/eclair
    # All API calls are POST with form encoded parameters
    def post(self, uri, data=None):
        body = urllib.parse.urlencode(data or {})
        post_header = {
            **self.headers,
            "Content-Length": str(len(body)),
            "Content-Type": "application/x-www-form-urlencoded",
        }
        conn = self.new_connection()
        conn.request(
            method="POST",
            url=uri,
            body=body,
            headers=post_header,
        )
        response = conn.getresponse().read().decode("utf8")
        res = json.loads(response)
        if isinstance(res, dict) and "error" in res:
            raise Exception(res["error"])
        return res

    def newaddress(self):
        # Address is generated by the bitcoind wallet backing eclair
        return self.post("/getnewaddress")

    def uri(self):
        res = self.post("/getinfo")
        return f"{res['nodeId']}@{self.name}.{self.namespace}:9735"

    def walletbalance(self) -> int:
        res = self.post("/onchainbalance")
        return int(res["confirmed"])

    def channelbalance(self) -> int:
        res = self.post("/channelbalances")
        return int(sum(ch["canSend"] for ch in res) / 1000)

    def connect(self, target_uri) -> dict:
        res = self.post("/connect", {"uri": target_uri})
        if res in ("connected", "already connected"):
            return {}
        raise Exception(res)

    def channel(self, pk, capacity, push_amt, fee_rate) -> dict:
        data = {
            "nodeId": pk,
            "fundingSatoshis": capacity,
            "pushMsat": push_amt * 1000,
            "fundingFeerateSatByte": fee_rate,
            # Eclair defaults to a fee budget of 0.1% of the channel capacity,
            # allow enough for any reasonably sized funding transaction instead.
            "fundingFeeBudgetSatoshis": fee_rate * 500,
        }
        # "created channel <channel id> with fundingTxId=<txid> and fees=<fee> sat"
        res = self.post("/open", data)
        match = re.search(r"created channel ([0-9a-f]+) with fundingTxId=([0-9a-f]+)", res)
        if not match:
            raise Exception(res)
        channel_id, txid = match.groups()
        # Funding output index is not in the response. Bitcoin Core picks the
        # position of the change output so it could be either 0 or 1.
        # The channel is already open so don't raise and let the caller retry.
        while True:
            try:
                info = self.post("/channel", {"channelId": channel_id})
                outpoint = info["data"]["commitments"]["active"][0]["fundingInput"]
                return {"txid": txid, "outpoint": outpoint}
            except Exception as e:
                self.log.warning(f"Couldn't get outpoint of channel {channel_id}: {e}")
                sleep(1)

    def createinvoice(self, sats, label) -> str:
        res = self.post("/createinvoice", {"amountMsat": sats * 1000, "description": label})
        return res["serialized"]

    def payinvoice(self, payment_request) -> str:
        # Returns the payment id, payment is processed asynchronously
        return self.post("/payinvoice", {"invoice": payment_request})

    def graph(self) -> dict:
        # Channel announcements only, eclair does not know capacity
        # or policies of channels it is not a party to.
        res = self.post("/allchannels")

        def scid(ch):
            return tuple(int(n) for n in ch["shortChannelId"].split("x"))

        return {"edges": sorted(res, key=scid)}

    def update(self, txid_hex: str, policy: dict, capacity: int, output_index=0) -> dict:
        raise Exception("Channel Policy Updates not supported by ECLAIR yet!")

    def reconnect_channel_peers(self, uris_by_pubkey: dict):
        # Eclair only runs a full gossip sync with a channel peer when the
        # connection is established, so reconnecting fetches what it missed.
        try:
            peers = {ch["nodeId"] for ch in self.post("/channels")}
        except Exception as e:
            self.log.warning(f"Couldn't list channels to reconnect peers: {e}")
            return
        for pk in peers:
            if pk not in uris_by_pubkey:
                continue
            try:
                self.post("/disconnect", {"nodeId": pk})
                self.connect(uris_by_pubkey[pk])
                self.log.info(f"Reconnected to channel peer {pk}")
            except Exception as e:
                self.log.warning(f"Couldn't reconnect to channel peer {pk}: {e}")


class LDK(LNNode):
    # kubernetes.stream.stream() temporarily patches the shared api client,
    # so concurrent calls from ln_init threads must not overlap.
    stream_lock = threading.Lock()
    # Seconds to wait for the wallet to see a funding transaction before restarting
    # ldk-server, the wallet polls bitcoind's mempool every 2 seconds
    WALLET_SYNC_TIMEOUT = 20

    def __init__(self, pod_name, pod_namespace, ip_address, sclient):
        super().__init__(pod_name, pod_namespace, ip_address)
        self.sclient = sclient
        self.open_lock = threading.Lock()
        self.impl = "ldk"

    # ldk-server only has a gRPC API (with TLS and macaroon auth), so use
    # its JSON CLI inside the pod which is already configured to reach it.
    def exec(self, command: list, timeout=60) -> tuple[int, str, str]:
        with self.stream_lock:
            resp = stream(
                self.sclient.connect_get_namespaced_pod_exec,
                name=self.name,
                namespace=self.namespace,
                container="ldk",
                command=command,
                stderr=True,
                stdin=False,
                stdout=True,
                tty=False,
                _preload_content=False,
            )
        resp.run_forever(timeout=timeout)
        stdout = resp.read_stdout()
        stderr = resp.read_stderr()
        returncode = resp.returncode
        resp.close()
        return returncode, stdout, stderr

    def cli(self, *args) -> dict:
        returncode, stdout, stderr = self.exec(["ldk-server-cli", *map(str, args)])
        if returncode != 0:
            raise Exception(stderr.strip() or f"ldk-server-cli exited with {returncode}")
        return json.loads(stdout)

    def restart(self):
        # ldk-server shuts down cleanly on SIGTERM and the pod restarts it
        try:
            self.exec(["/bin/sh", "-c", "kill 1"])
        except Exception as e:
            self.log.warning(f"Error sending SIGTERM to ldk-server: {e}")

    def newaddress(self):
        return self.cli("onchain-receive")["address"]

    def uri(self):
        res = self.cli("get-node-info")
        return f"{res['node_id']}@{self.name}.{self.namespace}:9735"

    def walletbalance(self) -> int:
        return int(self.cli("get-balances")["spendable_onchain_balance_sats"])

    def channelbalance(self) -> int:
        channels = self.cli("list-channels")["channels"]
        return int(sum(ch["outbound_capacity_msat"] for ch in channels) / 1000)

    def connect(self, target_uri) -> dict:
        self.cli("connect-peer", target_uri, "--persist")
        return {}

    def channel(self, pk, capacity, push_amt, fee_rate) -> dict:
        # LDK's wallet only learns that its funding transactions spend its coins
        # when it next polls the mempool, so concurrent channel opens could pick
        # the same coin. Open one channel at a time and wait for the wallet to
        # see each funding transaction.
        with self.open_lock:
            balance = int(self.cli("get-balances")["total_onchain_balance_sats"])
            res = self._open_channel(pk, capacity, push_amt, fee_rate)
            waiting_since = time()
            # The channel is already open so don't raise and let the caller retry
            while True:
                try:
                    if int(self.cli("get-balances")["total_onchain_balance_sats"]) <= (
                        balance - capacity
                    ):
                        return res
                    # ldk-node skips mempool transactions that entered bitcoind's
                    # mempool in the same second as one it already processed, until
                    # they confirm. A restart makes it process the whole mempool again.
                    if time() - waiting_since > self.WALLET_SYNC_TIMEOUT:
                        self.log.warning(
                            f"Wallet hasn't seen funding tx {res['txid']} after "
                            f"{self.WALLET_SYNC_TIMEOUT} seconds, restarting ldk-server"
                        )
                        self.restart()
                        waiting_since = time()
                    else:
                        self.log.info(f"Waiting for wallet to see funding tx {res['txid']}")
                except Exception as e:
                    # Don't count time ldk-server is unreachable, e.g. restarting
                    waiting_since = time()
                    self.log.warning(f"Couldn't get balance: {e}")
                sleep(1)

    def _open_channel(self, pk, capacity, push_amt, fee_rate) -> dict:
        # ldk-server can't set the funding fee rate, it uses its own estimate.
        # ln_init orders funding transactions with prioritisetransaction, so
        # the fee paid doesn't matter.
        # ldk-server requires the address of the (already connected) peer.
        peers = [p for p in self.cli("list-peers")["peers"] if p["node_id"] == pk]
        if not peers:
            raise Exception(f"not connected to peer {pk}")
        args = ["open-channel", pk, peers[0]["address"], f"{capacity}sat", "--announce-channel"]
        if push_amt:
            args += ["--push-to-counterparty", f"{push_amt}sat"]
        res = self.cli(*args)
        user_channel_id = res["user_channel_id"]
        # The funding transaction is created asynchronously after the
        # channel open is negotiated with the peer.
        # The channel is already open so don't raise and let the caller retry.
        while True:
            try:
                for ch in self.cli("list-channels")["channels"]:
                    if ch["user_channel_id"] == user_channel_id and ch.get("funding_txo"):
                        txid = ch["funding_txo"]["txid"]
                        return {"txid": txid, "outpoint": f"{txid}:{ch['funding_txo']['vout']}"}
                self.log.info(f"Waiting for funding tx of channel {user_channel_id}")
            except Exception as e:
                self.log.warning(f"Couldn't get outpoint of channel {user_channel_id}: {e}")
            sleep(1)

    def createinvoice(self, sats, label) -> str:
        return self.cli("bolt11-receive", f"{sats}sat", "--description", label)["invoice"]

    def payinvoice(self, payment_request) -> str:
        # Returns the payment id, payment is processed asynchronously
        return self.cli("bolt11-send", payment_request)["payment_id"]

    def graph(self) -> dict:
        # Short channel IDs only, details require a call per channel
        res = self.cli("graph-list-channels")
        return {"edges": [{"short_channel_id": scid} for scid in sorted(res["short_channel_ids"])]}

    def update(self, txid_hex: str, policy: dict, capacity: int, output_index=0) -> dict:
        raise Exception("Channel Policy Updates not supported by LDK yet!")

    def reconnect_channel_peers(self, uris_by_pubkey: dict):
        # Reconnecting makes both sides resend announcement_signatures for
        # channels that aren't announced yet. Addresses come from the caller
        # because LDK only knows the remote port of incoming connections.
        try:
            peers = {ch["counterparty_node_id"] for ch in self.cli("list-channels")["channels"]}
        except Exception as e:
            self.log.warning(f"Couldn't list channels to reconnect peers: {e}")
            return
        # Every exec takes seconds, so reconnect all peers from one shell script
        script = []
        for pk in peers:
            if pk not in uris_by_pubkey:
                continue
            pk_q, uri_q = shlex.quote(pk), shlex.quote(uris_by_pubkey[pk])
            script.append(
                f"if out=$(ldk-server-cli disconnect-peer {pk_q} 2>&1 >/dev/null && "
                f"ldk-server-cli connect-peer {uri_q} --persist 2>&1 >/dev/null); "
                f"then echo ok {pk_q}; else echo fail {pk_q} $out; fi"
            )
        if not script:
            return
        try:
            # Allow a few seconds per peer
            _, stdout, _ = self.exec(["/bin/sh", "-c", "\n".join(script)], 60 + 5 * len(script))
        except Exception as e:
            self.log.warning(f"Couldn't reconnect channel peers: {e}")
            return
        for line in stdout.splitlines():
            if not line.strip():
                continue
            status, pk, *error = line.split(" ", 2)
            if status == "ok":
                self.log.info(f"Reconnected to channel peer {pk}")
            else:
                self.log.warning(f"Couldn't reconnect to channel peer {pk}: {' '.join(error)}")


class LND(LNNode):
    def __init__(self, pod_name, pod_namespace, ip_address, admin_macaroon_hex):
        super().__init__(pod_name, pod_namespace, ip_address)
        self.admin_macaroon_hex = admin_macaroon_hex
        self.headers = {
            "Grpc-Metadata-macaroon": admin_macaroon_hex,
            "Connection": "close",
        }
        self.impl = "lnd"

    # A new connection per request, so one node can be used from many threads
    def new_connection(self):
        return http.client.HTTPSConnection(
            host=f"{self.name}.{self.namespace}", port=8080, timeout=60, context=INSECURE_CONTEXT
        )

    def get(self, uri):
        conn = self.new_connection()
        conn.request(
            method="GET",
            url=uri,
            headers=self.headers,
        )
        return conn.getresponse().read().decode("utf8")

    def post(self, uri, data, wait_for_completion=True):
        body = json.dumps(data)
        post_header = {
            **self.headers,
            "Content-Length": str(len(body)),
            "Content-Type": "application/json",
        }
        conn = self.new_connection()
        conn.request(
            method="POST",
            url=uri,
            body=body,
            headers=post_header,
        )
        # Stream output, otherwise we get a timeout error
        res = conn.getresponse()
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

    def update(self, txid_hex: str, policy: dict, capacity: int, output_index=0):
        ln_policy = Policy.from_dict(policy).to_lnd_chanpolicy(capacity)
        data = {
            "chan_point": {"funding_txid_str": txid_hex, "output_index": output_index},
            **ln_policy,
        }
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


def _get_lnd_semver(pod):
    for c in pod.spec.containers:
        if c.name == "lnd":
            return c.image.removeprefix("lightninglabs/lnd:")
    raise RuntimeError("no lnd container found")


def _supports_macaroon_root_key(pod):
    semver = _get_lnd_semver(pod)
    minor = int(semver.split(".")[1])
    return minor >= 16


def _read_admin_macaroon(sclient, pod):
    chain = pod.metadata.labels["chain"]
    path = f"/root/.lnd/data/chain/bitcoin/{chain}/admin.macaroon"
    cmd = [
        "bash",
        "-c",
        f"""for i in {{1..10}}; do xxd -p '{path}' 2>/dev/null && exit 0 || sleep 1; done; exit 1""",
    ]
    out = stream(
        sclient.connect_get_namespaced_pod_exec,
        name=pod.metadata.name,
        namespace=pod.metadata.namespace,
        container="lnd",
        command=cmd,
        stderr=True,
        stdin=False,
        stdout=True,
        tty=False,
    )
    admin_macaroon_hex = "".join(out.split())
    if not re.fullmatch(r"[0-9a-fA-F]+", admin_macaroon_hex):
        raise RuntimeError(f"could not read admin.macaroon for {pod.metadata.name}")
    return admin_macaroon_hex


def get_admin_macaroon(sclient, pod):
    # we have to read admin.macaroon for lnd versions below v0.16.0-beta
    # because they cannot use adminMacaroon from the pod config
    if _supports_macaroon_root_key(pod):
        return pod.metadata.annotations["adminMacaroon"]
    else:
        return _read_admin_macaroon(sclient, pod)
