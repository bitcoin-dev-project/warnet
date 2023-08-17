import logging
import docker
import warnet

BITCOIN_GRAPH_FILE = './graphs/basic3.graphml'

logging.basicConfig(level=logging.INFO)


def main():
    client = docker.from_env()
    warnet.delete_containers(client)
    warnet.generate_docker_compose(BITCOIN_GRAPH_FILE)
    warnet.docker_compose()
    warnet.connect_edges(client, BITCOIN_GRAPH_FILE)


if __name__ == "__main__":
    main()
