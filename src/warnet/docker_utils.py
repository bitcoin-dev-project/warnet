import logging
import docker
from .docker_compose import generate_docker_compose


def delete_containers(client: docker.DockerClient,
                      container_name_prefix: str = "warnet"):
    """
    Delete all containers with the specified name prefix.

    :param container_name_prefix: The prefix of the container names to filter.
    """
    try:
        containers = client.containers.list(
            all=True, filters={"name": container_name_prefix})
        for container in containers:
            container.remove(force=True)
        logging.info("  Removed all containers")
    except Exception as e:
        logging.error(f"An error occurred while deleting containers: {e}")


def get_container_ip(client: docker.DockerClient, container_name: str):
    """
    Get the IP address of a container.

    :param container_name: The name of the container
    :return: The IP address of the container
    """
    try:
        container = client.containers.get(container_name)
        container.reload()
        return container.attrs["NetworkSettings"]["Networks"]["warnet"]["IPAddress"]
    except Exception as e:
        logging.error(f"An error occurred while getting container IP: {e}")


def get_containers(client: docker.DockerClient,
                   container_name_prefix: str = "warnet"):
    """
    Get the names and instances of all containers with the specified name prefix.

    :param container_name_prefix: The prefix of the container names to filter.
    :return: A list of tuples containing the names and instances of the containers
    """
    containers = client.containers.list(
        all=True, filters={"name": container_name_prefix})
    container_info = [(container.name, container) for container in containers]
    return container_info


def docker_compose():
    """
    Run docker compose
    """
    try:
        import subprocess
        # TODO: remove --build after dev
        subprocess.run(["docker-compose", "up", "-d", "--build"])
    except Exception as e:
        logging.error(f"An error occurred while running docker compose: {e}")
