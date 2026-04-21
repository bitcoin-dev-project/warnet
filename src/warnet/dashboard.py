import sys

import click

from .k8s import get_host, get_ingress_ip_or_host, wait_for_ingress_endpoint


@click.command()
def dashboard():
    """Open the Warnet dashboard in default browser"""
    import webbrowser

    timeout = 300
    click.echo(f"Waiting {timeout} seconds for ingress endpoint ...")
    try:
        wait_for_ingress_endpoint(timeout=timeout)
    except Exception as e:
        click.echo(e)
        sys.exit(1)
    ip = get_ingress_ip_or_host()

    url = f"http://{ip}"

    webbrowser.open(url)
    click.echo(f"Warnet dashboard opened in default browser. URL: {url}")


@click.command()
def host():
    """Get one cluster node IP, used for accessing NodePorts"""
    click.echo(get_host())
