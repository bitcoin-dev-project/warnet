use anyhow::Context;
use clap::{Parser, Subcommand};

mod debug;
mod general;
mod graph;
mod image;
mod network;
mod rpc_call;
mod scenarios;
mod util;
use crate::debug::{handle_debug_command, DebugCommand};
use crate::general::*;
use crate::graph::{handle_graph_command, GraphCommand};
use crate::image::{handle_image_command, ImageCommand};
use crate::network::{handle_network_command, NetworkCommand};
use crate::scenarios::{handle_scenario_command, ScenarioCommand};

#[derive(Parser, Debug)]
#[command(version, about, long_about = None)]
struct Cli {
    #[arg(long)]
    /// The warnet network command corresponds to
    network: Option<String>,

    #[command(subcommand)]
    command: Option<Commands>,
}

#[derive(Subcommand, Debug)]
enum Commands {
    /// Debug commands (deprecated)
    Debug {
        #[command(subcommand)]
        command: Option<DebugCommand>,
    },
    /// Fetch the Bitcoin Core debug log from <node> in [network]
    DebugLog { node: u64 },
    /// Graph commands
    Graph {
        #[command(subcommand)]
        command: Option<GraphCommand>,
    },
    /// Grep combined logs via fluentd using regex <pattern>
    GrepLogs { pattern: String },
    /// Build a warnet-ready bitcoind docker image from a github branch
    Image {
        #[command(subcommand)]
        command: Option<ImageCommand>,
    },
    /// Call lncli <method> [params] on <node> in [network]
    LnCli {
        node: u64,
        method: String,
        params: Option<Vec<String>>,
    },
    /// Fetch messages sent between <node_a> and <node_b> in [network]
    Messages { node_a: u64, node_b: u64 },
    /// Network commands
    Network {
        #[command(subcommand)]
        command: Option<NetworkCommand>,
    },
    /// Call bitcoin-cli <method> [params] on <node> in [network]
    Rpc {
        node: u64,
        #[arg(allow_hyphen_values = true)]
        method: String,
        params: Option<Vec<String>>,
    },
    /// Scenario commands
    Scenarios {
        #[command(subcommand)]
        command: Option<ScenarioCommand>,
    },
    /// Stop warnet server
    Stop {},
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let cli = Cli::parse();
    let mut rpc_params = jsonrpsee::core::params::ObjectParams::new();
    if let Some(network_value) = &cli.network {
        rpc_params
            .insert("network", network_value)
            .context("add network param")?;
    }

    match &cli.command {
        Some(Commands::Debug { command }) => {
            if let Some(command) = command {
                handle_debug_command(command, rpc_params).await?;
            }
        }
        Some(Commands::Graph { command }) => {
            if let Some(command) = command {
                handle_graph_command(command).await?;
            }
        }
        Some(Commands::Network { command }) => {
            if let Some(command) = command {
                handle_network_command(command, rpc_params).await?;
            }
        }
        Some(Commands::Scenarios { command }) => {
            if let Some(command) = command {
                handle_scenario_command(command, rpc_params).await?;
            }
        }
        Some(Commands::Rpc {
            node,
            method,
            params,
        }) => {
            handle_rpc_commands(NodeType::BitcoinCli, node, method, params, rpc_params).await?;
        }
        Some(Commands::LnCli {
            node,
            method,
            params,
        }) => {
            handle_rpc_commands(NodeType::LnCli, node, method, params, rpc_params).await?;
        }
        Some(Commands::DebugLog { node }) => {
            handle_debug_log_command(node, rpc_params).await?;
        }
        Some(Commands::Image { command }) => {
            if let Some(command) = command {
                handle_image_command(command).await?;
            }
        }
        Some(Commands::Messages { node_a, node_b }) => {
            handle_messages_command(node_a, node_b, rpc_params).await?;
        }
        Some(Commands::GrepLogs { pattern }) => {
            handle_grep_logs_command(pattern, rpc_params).await?;
        }
        Some(Commands::Stop {}) => {
            handle_stop_command(rpc_params).await?;
        }
        None => println!("No command provided"),
    }

    Ok(())
}
