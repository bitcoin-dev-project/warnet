import http.client
import json
import logging
import ssl
import time
from base64 import b64encode
from typing import Any

def _self_signed_context() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


class BtcdRPCError(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        self.error = {"code": code, "message": message}
        super().__init__(f"RPC error {code}: {message}")


class BtcdRPC:
    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        timeout: int = 60,
    ):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._auth_header = "Basic " + b64encode(
            f"{user}:{password}".encode()
        ).decode()
        self._request_id = 0
        self.log = logging.getLogger(f"BtcdRPC({host}:{port})")


    def _new_connection(self) -> http.client.HTTPSConnection:
        return http.client.HTTPSConnection(
            host=self.host,
            port=self.port,
            timeout=self.timeout,
            context=_self_signed_context(),
        )

    def _build_payload(self, method: str, params: list) -> bytes:
        self._request_id += 1
        return json.dumps(
            {
                "jsonrpc": "1.0",
                "id": str(self._request_id),
                "method": method,
                "params": params,
            }
        ).encode()

    def _build_headers(self, payload: bytes) -> dict:
        return {
            "Authorization": self._auth_header,
            "Content-Type": "application/json",
            "Content-Length": str(len(payload)),
        }

    def _send_with_retry(self, method: str, payload: bytes, headers: dict, max_attempts: int = 5) -> tuple[int, str]:
        last_exc = RuntimeError("unreachable")

        for attempt in range(max_attempts):
            if attempt > 0:
                backoff = 2 ** attempt
                self.log.debug("Retry %d for %s (backoff %ds)", attempt, method, backoff)
                time.sleep(backoff)

            conn = self._new_connection()
            
            try:
                conn.request("POST", "/", body=payload, headers=headers)
                response = conn.getresponse()
                return response.status, response.read().decode("utf-8")
            except (BrokenPipeError, ConnectionResetError, OSError) as exc:
                last_exc = exc
                self.log.warning("Connection error on attempt %d for %s: %s", attempt + 1, method, exc)
            finally:
                conn.close()

        raise ConnectionError(f"btcd {method} failed after {max_attempts} attempts: {last_exc}")

    def _parse_response(self, method: str, status: int, raw: str):
        body = json.loads(raw)

        if status != 200:
            try:
                err = body.get("error") or {}
                raise BtcdRPCError(
                    code=err.get("code", status),
                    message=err.get("message", raw),
                )
            except (json.JSONDecodeError, KeyError):
                raise ConnectionError(f"btcd returned HTTP {status}: {raw[:200]}")


        if body.get("error") is not None:
            err = body["error"]
            raise BtcdRPCError(code=err["code"], message=err["message"])

        return body["result"]

    """
    Execute a JSON-RPC call and return the result field.
    """
    def _call(self, method: str, *params):
        payload = self._build_payload(method, list(params))
        headers = self._build_headers(payload)
        status, raw = self._send_with_retry(method, payload, headers)
        return self._parse_response(method, status, raw)



    # standard Bitcoin methods 

    def getblockcount(self) -> int:
        return self._call("getblockcount")

    def getbestblockhash(self) -> str:
        return self._call("getbestblockhash")

    def getblockhash(self, height: int) -> str:
        return self._call("getblockhash", height)

    def getblock(self, block_hash: str, verbosity: int = 1):
        return self._call("getblock", block_hash, verbosity)

    def getblockheader(self, block_hash: str, verbose: bool = True):
        return self._call("getblockheader", block_hash, verbose)

    def getpeerinfo(self) -> list:
        return self._call("getpeerinfo")

    def getconnectioncount(self) -> int:
        return self._call("getconnectioncount")

    def addnode(self, peer: str, command: str) -> None:
        """
        peer : str
            IP address and port of the peer, e.g. ``"10.0.0.2:18444"``.
        command : str
            ``"add"`` to add a persistent peer, ``"remove"`` to remove one,
            or ``"onetry"`` to attempt a single connection.
        """
        return self._call("addnode", peer, command)

    def getinfo(self) -> dict:
        return self._call("getinfo")

    def getmininginfo(self) -> dict:
        return self._call("getmininginfo")

    def getmempoolinfo(self) -> dict:
        return self._call("getmempoolinfo")

    def getrawmempool(self, verbose: bool = False):
        return self._call("getrawmempool", verbose)

    def getrawtransaction(self, txid: str, verbose: int = 0):
        return self._call("getrawtransaction", txid, verbose)

    def sendrawtransaction(self, signed_hex: str) -> str:
        return self._call("sendrawtransaction", signed_hex)

    def decoderawtransaction(self, hex_tx: str) -> dict:
        return self._call("decoderawtransaction", hex_tx)

    def createrawtransaction(self, inputs: list, outputs: dict) -> str:
        return self._call("createrawtransaction", inputs, outputs)

    def validateaddress(self, address: str) -> dict:
        return self._call("validateaddress", address)

    def verifychain(self, check_level: int = 3, num_blocks: int = 300) -> bool:
        return self._call("verifychain", check_level, num_blocks)

    def submitblock(self, hex_block: str):
        return self._call("submitblock", hex_block)

    def ping(self) -> None:
        return self._call("ping")

    def stop(self) -> str:
        return self._call("stop")

    
    # btcd extension methods

    def generate(self, num_blocks: int) -> list:
        return self._call("generate", num_blocks)

    def getbestblock(self) -> dict:
        return self._call("getbestblock")

    def getcurrentnet(self) -> int:
        return self._call("getcurrentnet")

    def version(self) -> dict:
        return self._call("version")

    def node(self, command: str, peer: str, connection_type: str = "") -> None:
        if connection_type:
            return self._call("node", command, peer, connection_type)
        return self._call("node", command, peer)

    def debuglevel(self, level_spec: str) -> str:
        return self._call("debuglevel", level_spec)

    def searchrawtransactions(
        self,
        address: str,
        verbose: int = 1,
        skip: int = 0,
        count: int = 100,
        vin_extra: int = 0,
        reverse: bool = False,
    ) -> list:
        return self._call(
            "searchrawtransactions", address, verbose, skip, count, vin_extra, reverse
        )


    # helpers
    
    def force_sync_from(self, source: "BtcdRPC") -> None:
        p2p_port = getattr(source, "_p2p_port", 18444)
        peer_addr = f"{source.host}:{p2p_port}"

        self.log.info("force_sync_from: disconnecting then reconnecting to %s", peer_addr)
        try:
            self.node("disconnect", peer_addr)
        except Exception as e:
            self.log.debug("disconnect %s (expected if not connected): %s", peer_addr, e)
        time.sleep(1)
        try:
            self.node("connect", peer_addr, "perm")
        except Exception as e:
            self.log.debug("connect %s: %s", peer_addr, e)


    def __repr__(self) -> str:
        return f"BtcdRPC(host={self.host!r}, port={self.port})"
