use clap::{Parser, Subcommand};

use crate::debug::{handle_debug_command, DebugCommands};
use crate::network::{handle_network_command, NetworkCommands};
use crate::scenarios::{handle_scenario_command, ScenarioCommands};
mod debug;
mod network;
mod rpc_call;
mod scenarios;

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
        command: Option<NetworkCommands>,
    },
    /// Debug commands [[deprecated]]
    Debug {
        #[command(subcommand)]
        command: Option<DebugCommands>,
    },
    /// Scenario commands
    Scenarios {
        #[command(subcommand)]
        command: Option<ScenarioCommands>,
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
        None => println!("No command provided"),
    }

    Ok(())
}
