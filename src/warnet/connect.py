def connect_nodes():

    # Initialize the Docker client
    client = docker.from_env()

# Fetch all containers with a name that starts with "bitcoin-node"
    containers = client.containers.list(filters={"name": "bitcoin-node"})

# Create a list to store IP addresses
    container_ips = []
    container_ports = []

# Fetch the IP address of each Bitcoin node container
    for container in containers:
        ip_address = container.attrs['NetworkSettings']['IPAddress']
        container_ips.append(ip_address)
        cmd = f"bitcoin-cli -conf=/root/.bitcoin/bitcoin.conf -netinfo | awk '/port/ {{print $3}}'"
        port = containers[0].exec_run(cmd)
        container_ports.append(f"{ip_address}:{port}")

# Assuming the first node is the one we want to use as the 'main' node
# We will connect all other nodes to this main node
    main_node_ip = container_ips[0]


# Use bitcoin-cli to connect nodes
    for container in container_ips[1:]:
        # Execute the command
        for addr in container_ports:
            cmd = f"bitcoin-cli addnode {addr} add"
            response = container.exec_run(cmd)
            print(response.output.decode())
