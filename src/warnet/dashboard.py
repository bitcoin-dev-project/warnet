import click

from .k8s import get_ingress_ip_or_host, wait_for_ingress_controller


@click.command()
def dashboard():
    """Open the Warnet dashboard in default browser"""
    import webbrowser

    wait_for_ingress_controller()
    ip = get_ingress_ip_or_host()

    if not ip:
        click.echo("Error: Could not get the IP address of the dashboard")
        click.echo(
            "If you are running Minikube please run 'minikube tunnel' in a separate terminal"
        )
        click.echo(
            "If you are running in the cloud, you may need to wait a short while while the load balancer is provisioned"
        )
        return

    url = f"http://{ip}"

    webbrowser.open(url)
    click.echo("Warnet dashboard opened in default browser")
