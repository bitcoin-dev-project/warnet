import docker

def get_debug_log(node):
    try:
        node = f"warnet_{node}"
        d = docker.from_env()
        c = d.containers.get(node)
        data, stat = c.get_archive("/bitcoin/regtest/debug.log")
        out = ""
        for chunk in data:
            out += chunk.decode()
        return out
    except Exception as e:
        return f"Could not get debug log for {node}: {e}"

def stop_network():
    try:
        d = docker.from_env()
        network = d.networks.get("warnet_network")
        containers = network.containers
        for c in containers:
            c.stop()
            c.remove()
        network.remove()
        return "shut down warnet_network"
    except Exception as e:
        return f"Could not stop warnet_network: {e}"
