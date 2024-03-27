use clap::{Parser, Subcommand};
use jsonrpsee::core::client::ClientT;
use jsonrpsee::http_client::HttpClientBuilder;
use jsonrpsee::rpc_params;
use serde_json::Value;
use std::path::PathBuf;

#[derive(Parser, Debug)]
#[command(version, about, long_about = None)]
struct Cli {
    #[arg(long, default_value = "warnet")]
    network: Option<String>,

    #[command(subcommand)]
    command: Option<Commands>,
}

#[derive(Subcommand, Debug)]
enum Commands {
    /// Network commands
    Network {
        #[command(subcommand)]
        command: Option<NetworkCommands>,
    },
    /// Debug commands
    Debug {
        #[command(subcommand)]
        command: Option<DebugCommands>,
    },
}

#[derive(Subcommand, Debug)]
enum NetworkCommands {
    /// Start a network from a <graph_file>
    Start {
        graph_file: PathBuf,
        #[arg(long, short)]
        force: bool,
    },
    /// Bring a network back up
    Up {},
    /// Take a network down
    Down {},
    /// Get network info
    Info {},
    /// Shows the status of a network
    Status {},
    /// Return if network is connected
    Connected {},
    /// Export network details for sim-ln
    Export {},
}

#[derive(Subcommand, Debug)]
enum DebugCommands {
    /// Generate the docker-compose file for a given <graph_file> and return it.
    GenerateCompose { graph_file: PathBuf },
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let cli = Cli::parse();
    let mut request = "";
    let mut params = rpc_params![];

    // Create request
    match &cli.command {
        Some(Commands::Network { command }) => match command {
            Some(NetworkCommands::Start { graph_file, force }) => {
                request = "network_from_file";
                params.insert(graph_file)?;
                params.insert(force)?;
            }
            Some(NetworkCommands::Up {}) => {
                request = "network_up";
            }
            Some(NetworkCommands::Down {}) => {
                request = "network_down";
            }
            Some(NetworkCommands::Info {}) => {
                request = "network_info";
            }
            Some(NetworkCommands::Status {}) => {
                request = "network_status";
            }
            Some(NetworkCommands::Connected {}) => {
                request = "network_connected";
            }
            Some(NetworkCommands::Export {}) => {
                request = "network_export";
            }
            _ => println!("Unknown Network command"),
        },

        Some(Commands::Debug { command }) => match command {
            Some(DebugCommands::GenerateCompose { graph_file: _ }) => {
                request = "generate_compose";
            }
            _ => println!("Unknown Debug command"),
        },
        None => {
            println!("No command provided");
        }
    }
    if request.is_empty() {
        return Err(anyhow::Error::msg("No command specified"));
    };

    let url = "http://127.0.0.1:9276/api";
    let client = HttpClientBuilder::default().build(url)?;
    let response = client.request::<Value, _>(request, params).await;

    if let Err(error) = response {
        println!("Error decoding json: {:?}", error);
        return Err(anyhow::Error::new(error));
    }
    let data = response.unwrap();
    // println!("Got data:\n{}", data);

    // Custom response handling
    match &cli.command {
        Some(Commands::Network { command }) => match command {
            Some(NetworkCommands::Start {
                graph_file: _,
                force: _,
            }) => {}
            Some(NetworkCommands::Up {}) => {}
            Some(NetworkCommands::Down {}) => {}
            Some(NetworkCommands::Info {}) => {}
            Some(NetworkCommands::Status {}) => {
                if let serde_json::Value::Array(items) = &data {
                    for item in items {
                        if let (Some(tank_index), Some(bitcoin_status)) = (
                            item.get("tank_index").and_then(|v| v.as_i64()),
                            item.get("bitcoin_status").and_then(|v| v.as_str()),
                        ) {
                            println!("Tank: {:<6} Bitcoin: {}", tank_index, bitcoin_status);
                        } else {
                            println!("Error: Response item is missing expected fields");
                        }
                    }
                } else {
                    println!("Error: Expected an array in the response");
                }
            }
            Some(NetworkCommands::Connected {}) => {}
            Some(NetworkCommands::Export {}) => {}
            _ => return Ok(()),
        },

        Some(Commands::Debug { command }) => match command {
            Some(DebugCommands::GenerateCompose { graph_file: _ }) => {}
            _ => return Ok(()),
        },
        None => return Ok(()),
    }

    Ok(())
}
