import requests
import sys
from jsonrpcclient.responses import Error, Ok, parse
from jsonrpcclient.requests import request
from typing import Any, Dict, Tuple, Union, Optional
from warnet.server import WARNET_SERVER_PORT


class JSONRPCException(Exception):
    def __init__(self, code, message):
        try:
            errmsg = f"{code} {message}"
        except (KeyError, TypeError):
            errmsg = ""
        super().__init__(errmsg)


def rpc_call(rpc_method, params: Optional[Union[Dict[str, Any], Tuple[Any, ...]]]):
    payload = request(rpc_method, params)
    response = requests.post(f"http://localhost:{WARNET_SERVER_PORT}/api", json=payload)
    match parse(response.json()):
        case Ok(result, _):
            return result
        case Error(code, message, _, _):
            print(f"{code}: {message}")
            sys.exit(1)
            # raise JSONRPCException(code, message)
