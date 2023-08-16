import docker

def get_debug_log(node):
    node = f"warnet_{node}"
    d = docker.from_env()
    c = d.containers.get(node)
    data, stat = c.get_archive("/bitcoin/regtest/debug.log")
    out = ""
    for chunk in data:
        out += chunk.decode()
    return out

def stop_network():
    d = docker.from_env()
    network = d.networks.get("warnet_network")
    containers = network.containers
    for c in containers:
        print(f"stopping container: {c.name}")
        c.stop()
        print(f"removing container: {c.name}")
        c.remove()
    print("removing network: warnet_network")
    network.remove()
    return True
