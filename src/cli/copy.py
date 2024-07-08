import os
import shutil
import tempfile
from cli.rpc import rpc_call
import click


@click.command()
@click.argument("source", required=True)
@click.argument("destination", required=True)
@click.option("-r", "--recursive", is_flag=True, help="Copy files recursively.")
@click.option("--network", default="warnet", show_default=True)
def cp(source: str, destination: str, recursive: bool, network: str):
    """Copy files to and from tanks."""
    print(f"source: {source}")
    print(f"destination: {destination}")
    print(f"recursive: {recursive}")

    if ":" not in source and ":" not in destination:
        raise click.UsageError(
            "Either source or destination must include a tank identifier."
        )

    if ":" in source:
        # Copy from tank to local
        if recursive and os.path.isfile(destination):
            raise click.UsageError(f"destination path not a directory: {destination}.")

        rpc_call(
            "tank_copy",
            {
                "source": source,
                "destination": None,
                "recursive": recursive,
                "network": network,
            },
        )
        # destination: for be the current system file path
        #
    elif ":" in destination:
        # Copy from local to tank
        if recursive and os.path.isfile(source):
            raise click.UsageError(f"source path not a directory: {source}.")

        if recursive and os.path.isdir(source):
            # Archive the directory
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=".tar.gz"
            ) as temp_file:
                archive_path = temp_file.name
                shutil.make_archive(
                    archive_path.replace(".tar.gz", ""), "gztar", source
                )

            # Upload the archive
            upload_file(archive_path + ".tar.gz", destination, network)
            os.remove(archive_path)  # Clean up the temporary archive
        else:
            upload_file(source, destination, network)

    elif ":" in source and ":" in destination:
        # Copy from tank to tank
        print(
            rpc_call(
                "tank_copy",
                {
                    "source": source,
                    "destination": destination,
                    "recursive": recursive,
                    "network": network,
                },
            )
        )
    else:
        raise click.UsageError("Unexpected error in determining source or destination.")


def upload_file(local_path, destination, network):
    """Uploads a single file using JSON-RPC."""
    with open(local_path, "rb") as f:
        file_data = f.read()

    print(
        rpc_call(
            "tank_copy",
            {
                "source": None,
                "destination": destination,
                "file_data": file_data.decode("latin1"),  # Encode file data as needed
                "network": network,
            },
        )
    )
