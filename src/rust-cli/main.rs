use clap::{Parser, Subcommand};

mod debug;
mod general;
mod network;
mod rpc_call;
mod scenarios;
mod util;
use crate::debug::{handle_debug_command, DebugCommand};
use crate::general::handle_rpc_command;
use crate::network::{handle_network_command, NetworkCommand};
use crate::scenarios::{handle_scenario_command, ScenarioCommand};

#[derive(Parser, Debug)]
#[command(version, about, long_about = None)]
struct Cli {
    #[arg(long, default_value = "warnet")]
    network: String,

    #[command(subcommand)]
    command: Option<Commands>,
}

#[derive(Subcommand, Debug)]
enum Commands {
    /// Network commands
    Network {
        #[command(subcommand)]
        command: Option<NetworkCommand>,
    },
    /// Debug commands [[deprecated]]
    Debug {
        #[command(subcommand)]
        command: Option<DebugCommand>,
    },
    /// Scenario commands
    Scenarios {
        #[command(subcommand)]
        command: Option<ScenarioCommand>,
    },
    /// Call bitcoin-cli <method> [params] on <node> in [network]
    Rpc {
        node: u64,
        method: String,
        params: Option<Vec<String>>,
    },
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let cli = Cli::parse();

    match &cli.command {
        Some(Commands::Network { command }) => {
            if let Some(command) = command {
                handle_network_command(command, &cli.network).await?;
            }
        }
        Some(Commands::Debug { command }) => {
            if let Some(command) = command {
                handle_debug_command(command, &cli.network).await?;
            }
        }
        Some(Commands::Scenarios { command }) => {
            if let Some(command) = command {
                handle_scenario_command(command, &cli.network).await?;
            }
        }
        Some(Commands::Rpc {
            node,
            method,
            params,
        }) => {
            handle_rpc_command(node, method, params, &cli.network).await?;
        }
        None => println!("No command provided"),
    }

    Ok(())
}
