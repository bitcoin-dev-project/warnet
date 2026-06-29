import http.client
import json
import logging
import ssl
import time
from base64 import b64encode


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
        self._auth_header = "Basic " + b64encode(f"{user}:{password}".encode()).decode()
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

    def _send_with_retry(
        self, method: str, payload: bytes, headers: dict, max_attempts: int = 5
    ) -> tuple[int, str]:
        last_exc = RuntimeError("unreachable")

        for attempt in range(max_attempts):
            if attempt > 0:
                backoff = 2**attempt
                self.log.debug("Retry %d for %s (backoff %ds)", attempt, method, backoff)
                time.sleep(backoff)

            conn = self._new_connection()

            try:
                conn.request("POST", "/", body=payload, headers=headers)
                response = conn.getresponse()
                return response.status, response.read().decode("utf-8")
            except (BrokenPipeError, ConnectionResetError, OSError) as exc:
                last_exc = exc
                self.log.warning(
                    "Connection error on attempt %d for %s: %s", attempt + 1, method, exc
                )
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
                raise ConnectionError(f"btcd returned HTTP {status}: {raw[:200]}") from None

        if body.get("error") is not None:
            err = body["error"]
            raise BtcdRPCError(code=err["code"], message=err["message"])

        return body["result"]

    def _call(self, method: str, *params):
        """Execute a JSON-RPC call and return the result field."""
        payload = self._build_payload(method, list(params))
        headers = self._build_headers(payload)
        status, raw = self._send_with_retry(method, payload, headers)
        return self._parse_response(method, status, raw)

    def __getattr__(self, name: str):
        """Dispatch any unknown attribute as a JSON-RPC call."""
        if name.startswith("_"):
            raise AttributeError(name)

        def method(*args):
            return self._call(name, *args)

        method.__name__ = name
        return method

    def node(self, command: str, peer: str, connection_type: str = "") -> None:
        if connection_type:
            return self._call("node", command, peer, connection_type)
        return self._call("node", command, peer)

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
