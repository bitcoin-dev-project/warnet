import click

from .k8s import get_ingress_ip_or_host, wait_for_ingress_endpoint


@click.command()
def dashboard():
    """Open the Warnet dashboard in default browser"""
    import webbrowser

    timeout = 300
    click.echo(f"Waiting {timeout} seconds for ingress endpoint ...")
    try:
        wait_for_ingress_endpoint(timeout=timeout)
    except Exception as e:
        print(e)
        return
    ip = get_ingress_ip_or_host()

    url = f"http://{ip}"

    webbrowser.open(url)
    click.echo(f"Warnet dashboard opened in default browser. URL: {url}")
