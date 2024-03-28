use base64::{engine::general_purpose, Engine as _};
use clap::Subcommand;
use jsonrpsee::core::params::ObjectParams;
use std::path::PathBuf;
use anyhow::Context;

use crate::rpc_call::make_rpc_call;

#[derive(Subcommand, Debug)]
pub enum NetworkCommands {
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

pub async fn handle_network_command(command: &NetworkCommands, network: &String) -> anyhow::Result<()> {
    let mut params = ObjectParams::new();
    params.insert("network", network).context("Add network to params")?;
    let (request, params) = match command {
        NetworkCommands::Start { graph_file, force } => {
            let file_contents = std::fs::read(graph_file).context("Failed to read graph file")?;
            let graph_file_base64 = general_purpose::STANDARD.encode(file_contents);
            params.insert("graph_file", graph_file_base64).context("Add base64 graph file to params")?;
            params.insert("force", *force).context("Add force bool to params")?;
            ("network_from_file", params)
        }
        NetworkCommands::Up {} => ("network_up", params),
        NetworkCommands::Down {} => ("network_down", params),
        NetworkCommands::Info {} => ("network_info", params),
        NetworkCommands::Status {} => ("network_status", params),
        NetworkCommands::Connected {} => ("network_connected", params),
        NetworkCommands::Export {} => ("network_export", params),
    };

    let data = make_rpc_call(request, params).await?;
    match request {
        "network_status" => {
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
        "network_start" => {
            println!("Got response: {}", data);
        }
        _ => {
            println!("{}", data)
        }
    }
    // TODO: add response handling for other network commands
    Ok(())
}
