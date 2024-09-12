import click


@click.command()
def dashboard():
    """Open the Warnet dashboard in default browser"""
    import webbrowser

    url = "http://localhost:2019"
    webbrowser.open(url)
    click.echo("warnet dashboard opened in default browser")
