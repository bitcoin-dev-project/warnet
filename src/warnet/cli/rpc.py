import requests
from jsonrpcclient.responses import Ok, parse
from jsonrpcclient.requests import request
from typing import Any, Dict, Tuple, Union, Optional
from warnet.server import WARNET_SERVER_PORT


def rpc_call(rpc_method, params: Optional[Union[Dict[str, Any], Tuple[Any, ...]]]):
    payload = request(rpc_method, params)
    response = requests.post(f"http://localhost:{WARNET_SERVER_PORT}/api", json=payload)
    parsed = parse(response.json())

    if isinstance(parsed, Ok):
        return parsed.result
    else:
        error_message = getattr(parsed, 'message', 'Unknown RPC error')
        raise Exception(error_message)

